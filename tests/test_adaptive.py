import math
import unittest
from unittest.mock import patch

from test_bot import HELLO, OpenMap, enemy, observation
from bot.combat import Combat
from bot.strategy import Strategy
from bot.world import World
from bot.movement import MovementSupport
from bot.loadout import pickup_slot


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

    def test_unseen_attacker_is_remembered_when_seen_later(self):
        obs = observation()
        obs['events'] = [{'type': 'damaged', 'amount': 20, 'weapon': 'gun', 'by': 7, 'bearing': 0}]
        self.world.update(obs)
        obs.update(t=1, tick=2, events=[], mechs=[enemy(100)])
        self.world.update(obs)
        self.assertEqual(self.world.attackers[7], 0)
        self.assertIn(7, self.world.tracks)

    def test_squad_economy_can_farm_at_moderate_health(self):
        obs=observation(); obs.update(t=21, tick=2, cubes=[{'id':5000,'pos':[35,0,0]}])
        obs['self']['hp']=.65*obs['self']['max_hp']
        self.world.update(obs)
        with patch.dict('os.environ', {'BOT_ECONOMY':'adaptive'}):
            strategy=Strategy(self.world.arena, Combat(HELLO['config']), HELLO['config'], 'adaptive')
        self.assertEqual(strategy.choose(self.world)[0], 'loot')

    def test_active_threats_distinguish_passive_and_closing_enemies(self):
        obs=observation(); obs.update(t=21,tick=2)
        foe=enemy(100); foe['aim']=[0,0]; obs['mechs']=[foe]
        self.world.update(obs)
        with patch.dict('os.environ', {'BOT_THREAT_MODEL':'active'}):
            strategy=Strategy(self.world.arena,Combat(HELLO['config']),HELLO['config'],'adaptive')
        self.assertEqual(strategy.choose(self.world)[0], 'hold')
        foe['vel']=[-8,0,0]; obs.update(t=21.1,tick=4); self.world.update(obs)
        self.assertIn(strategy.choose(self.world)[0], ('attack','flee'))

    def test_predictive_gun_waits_only_for_remaining_slew(self):
        obs=observation(); foe=enemy(100); obs['mechs']=[foe]
        gun=obs['self']['weapons'][0]
        gun.update(kind='gun', ammo=12, reload=0, cooldown=0, stats=HELLO['config']['weapons']['gun'])
        obs['self']['stats']['turn_rate']=2
        obs['self']['aim']=[-.06, math.atan2(-2.5,100)]
        self.world.update(obs)
        with patch.dict('os.environ', {'BOT_FIRE_CONTROL':'legacy'}): legacy=Combat(HELLO['config'])
        with patch.dict('os.environ', {'BOT_FIRE_CONTROL':'predictive'}): predictive=Combat(HELLO['config'])
        self.assertFalse(legacy.action(self.world,self.world.tracks[7],'attack')['fire'][0])
        self.assertTrue(predictive.action(self.world,self.world.tracks[7],'attack')['fire'][0])

    def test_preserve_gun_loadout_upgrades_secondary(self):
        obs=observation()
        obs['self']['weapons']=[{'kind':'gun'}, {'kind':'lightning'}]
        self.world.update(obs)
        with patch.dict('os.environ', {'BOT_LOADOUT':'preserve_gun'}):
            self.assertEqual(pickup_slot({'kind':'laser'},self.world),(True,1))
            self.assertEqual(pickup_slot({'kind':'mortar'},self.world),(False,None))
            obs['self']['weapons'][1]={'kind':'laser','charge':.3}
            self.assertEqual(pickup_slot({'kind':'lightning'},self.world),(False,None))

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
        with patch.dict('os.environ', {'BOT_FIRE_CONTROL':'predictive'}):
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
