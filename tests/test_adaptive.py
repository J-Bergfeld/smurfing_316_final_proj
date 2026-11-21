import math
import unittest

from test_bot import HELLO, OpenMap, enemy, observation
from bot.combat import Combat
from bot.strategy import Strategy
from bot.world import World
from bot.movement import MovementSupport
from bot.ranges import desired_distance, engagement_range, incoming_dps, unsafe_to_close, weapon_range


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.world = World(HELLO['config'], OpenMap())

    def test_field_inference_requires_distinct_observations(self):
        obs = observation()
        self.world.update(obs)
        obs['alive'] = 15
        for tick in range(1, 5):
            obs['tick'] = tick
            self.world.update(obs)
            self.world.update(obs)
        self.assertNotEqual(self.world.field, 'ffa')
        obs['tick'] = 5
        self.world.update(obs)
        self.assertEqual(self.world.field, 'ffa')

    def test_own_kill_does_not_imply_free_for_all(self):
        obs = observation()
        self.world.update(obs)
        obs.update(t=21, alive=15, events=[{'type': 'kill', 'target': 7}])
        for tick in range(1, 8):
            obs['tick'] = tick
            self.world.update(obs)
        self.assertEqual(self.world.field, 'squad')

    def test_heavy_damage_forces_retreat(self):
        obs = observation()
        obs['mechs'] = [enemy(70)]
        obs['events'] = [{'type': 'damaged', 'amount': 300, 'weapon': 'gun', 'by': 7, 'bearing': 0}]
        self.world.update(obs)
        strategy = Strategy(self.world.arena, Combat(HELLO['config']), HELLO['config'], 'adaptive')
        self.assertEqual(strategy.choose(self.world)[0], 'flee')

    def test_lost_laser_aims_high_before_release(self):
        obs = observation()
        obs['self']['weapons'] = [{'kind': 'laser', 'charge': .5, 'cooldown': 0,
                                    'stats': HELLO['config']['weapons']['laser']}, None]
        self.world.update(obs)
        action = Combat(HELLO['config']).action(self.world, None, 'flee')
        self.assertTrue(action['fire'][0])
        self.assertGreater(action['aim'][1], 1)
        obs['self']['aim'][1] = action['aim'][1]
        action = Combat(HELLO['config']).action(self.world, None, 'flee')
        self.assertFalse(action['fire'][0])

    def test_gun_does_not_fire_along_laser_aim_at_moving_target(self):
        obs = observation()
        foe = enemy(100)
        foe['vel'] = [0, 25, 0]
        obs['mechs'] = [foe]
        gun = obs['self']['weapons'][0]
        gun.update(kind='gun', ammo=12, reload=0, cooldown=0, stats=HELLO['config']['weapons']['gun'])
        obs['self']['weapons'] = [gun, {'kind': 'laser', 'charge': .7, 'cooldown': 0,
                                        'stats': HELLO['config']['weapons']['laser']}]
        obs['self']['aim'] = [0, math.atan2(-2.5, 100)]
        self.world.update(obs)
        action = Combat(HELLO['config']).action(self.world, self.world.tracks[7], 'attack')
        self.assertFalse(action['fire'][0])

    def test_roof_edge_can_be_crossed_for_descent(self):
        class Roof(OpenMap):
            def supported(self, x, y, z, radius, height):
                return x < 2
            def blocked(self, x, y, z, height=0):
                return False
        obs = observation()
        obs['self']['pos'][2] = 20
        motion = MovementSupport()
        move = motion.steer(Roof(), obs['self'], [1, 0], obs['zone'], allow_drop=True)
        self.assertGreater(move[0], .9)

    def test_cover_reload_requires_distance_and_blocked_line(self):
        class Cover(OpenMap):
            def clear(self, a, b): return False
        world=World(HELLO['config'],Cover()); combat=Combat(HELLO['config']); combat.reload_policy='cover'
        obs=observation(); obs['mechs']=[enemy(100)]; world.update(obs)
        self.assertTrue(combat.reload_safe(world))
        obs['mechs'][0]['pos'][0]=30; world.update(obs)
        self.assertFalse(combat.reload_safe(world))

    def test_combat_boost_reserves_energy_and_avoids_laser_charge(self):
        obs=observation(); obs['mechs']=[enemy(100)]; obs['t']=.1; self.world.update(obs)
        strategy=Strategy(self.world.arena,Combat(HELLO['config']),HELLO['config']); strategy.combat_boost=True
        target=self.world.tracks[7]
        self.assertTrue(strategy.movement(self.world,[0,0,0],False,'attack',target)['boost'])
        obs['self']['energy']=50
        self.assertFalse(strategy.movement(self.world,[0,0,0],False,'attack',target)['boost'])
        obs['self']['energy']=100
        obs['self']['weapons'][1]={'kind':'laser','charge':.3,'cooldown':0,'stats':HELLO['config']['weapons']['laser']}
        self.assertFalse(strategy.movement(self.world,[0,0,0],False,'attack',target)['boost'])

    def test_laser_peek_finds_nearby_firing_lane(self):
        class Cover(OpenMap):
            def clear(self, a, b): return a[1] > 4
        arena=Cover(); world=World(HELLO['config'],arena)
        obs=observation(); obs['t']=2; obs['mechs']=[enemy(100)]
        obs['self']['weapons'][1]={'kind':'laser','charge':0,'cooldown':0,'stats':HELLO['config']['weapons']['laser']}
        world.update(obs); world.laser_shot_at=1; world.laser_shot_pos=[0,0,0]
        strategy=Strategy(arena,Combat(HELLO['config']),HELLO['config']); strategy.positioner.laser_peek=True
        goal=strategy.goal_for(world,'attack',world.tracks[7],False)
        self.assertGreater(goal[1],4)
        self.assertLessEqual(math.hypot(*goal[:2]),6.01)

    def test_weapon_ranges_and_upgrades_affect_positioning(self):
        obs=observation(); me=obs['self']; config=HELLO['config']
        gun=me['weapons'][0]
        laser={'kind':'laser','stats':config['weapons']['laser']}
        lightning={'kind':'lightning','stats':dict(config['weapons']['lightning'],range=60)}
        self.assertEqual(weapon_range(gun,config),230)
        self.assertAlmostEqual(weapon_range({'kind':'mortar'},config),72**2/22)
        me['weapons']=[laser,None]
        self.assertGreater(desired_distance(me,enemy(),config),160)
        me['weapons']=[lightning,None]
        self.assertEqual(desired_distance(me,enemy(),config),45)
        me['weapons']=[gun,None]
        self.assertGreater(desired_distance(me,dict(enemy(),weapons=['lightning']),config),45)

    def test_long_range_engagement_remains_within_vision(self):
        obs=observation(); me=obs['self']; config=HELLO['config']
        me['weapons']=[{'kind':'laser','stats':config['weapons']['laser']},None]
        self.assertEqual(engagement_range(me,config),200)
        me['weapons']=[{'kind':'lightning','stats':config['weapons']['lightning']},None]
        self.assertEqual(engagement_range(me,config),160)

    def test_matchup_counts_only_weapons_that_can_reach(self):
        config=HELLO['config']; foe=dict(enemy(),weapons=['gun','lightning'])
        far=incoming_dps(foe,100,config)
        close=incoming_dps(foe,30,config)
        self.assertGreater(far,0)
        self.assertGreater(close,far)
        self.assertEqual(incoming_dps(dict(foe,weapons=['lightning']),100,config),0)

    def test_exposed_close_against_long_range_weapon_is_unsafe(self):
        obs=observation(); me=obs['self']; me['hp']=300
        me['weapons']=[{'kind':'lightning','stats':HELLO['config']['weapons']['lightning']},None]
        foe=enemy(140)
        self.assertTrue(unsafe_to_close(me,foe,HELLO['config'],True))
        self.assertFalse(unsafe_to_close(me,foe,HELLO['config'],False))
        foe['pos'][0]=35
        self.assertFalse(unsafe_to_close(me,foe,HELLO['config'],True))

    def test_strategy_does_not_attack_during_unsafe_approach(self):
        class OptimisticCombat(Combat):
            def estimate(self, *args, **kwargs): return 10
        obs=observation(); obs['self']['hp']=300
        obs['self']['weapons']=[{'kind':'lightning','stats':HELLO['config']['weapons']['lightning']},None]
        obs['mechs']=[enemy(140)]; self.world.update(obs)
        strategy=Strategy(self.world.arena,OptimisticCombat(HELLO['config']),HELLO['config'])
        strategy.range_matchup=True
        self.assertEqual(strategy.choose(self.world)[0],'flee')
