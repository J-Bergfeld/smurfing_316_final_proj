"""Core controller behavior independent of local comparison materials."""
import copy
import random
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot.controller import Controller
from bot.combat import aim_and_fire
from bot.loadout import choose_loadout
from bot.movement import Movement
from test_bot import HELLO, enemy, observation


class ControllerTests(unittest.TestCase):
    def test_small_circle_uses_selective_combat_until_final_three(self):
        with patch.dict('os.environ', {'BOT_LATE_HIDE': '1'}):
            bot = Controller(HELLO)
        obs = observation()
        obs.update(t=180, tick=1800)
        obs['zone']['next_radius'] = 140
        bot.assess_combat = Mock(return_value=([], None, None, False, False))
        bot.act(obs)
        self.assertEqual(bot.assess_combat.call_args.args[1:3], (False, False))
        self.assertFalse(bot.ffa)
        obs['alive'] = 3
        bot.act(obs)
        self.assertEqual(bot.assess_combat.call_args.args[1:3], (True, True))

    def test_opening_laser_run_reserves_energy_and_yields_in_ffa(self):
        with patch.dict('os.environ', {'BOT_LASER_RUSH': '1'}):
            bot = Controller(HELLO)
        obs = observation()
        obs['pickups'] = [{'id': 8000, 'kind': 'laser', 'pos': [115, 0, 0]}]
        bot.world = Mock(baked=None)
        bot.world.ground.return_value = 0
        bot.movement = Mock(unstuck_until=0)
        bot.movement.avoid_shells.return_value = None
        bot.movement.navigate.return_value = [1, 0]
        obs['self']['weapons'][1] = None
        action = bot.act(obs)
        self.assertEqual(bot.loot_id, 8000)
        self.assertTrue(action['boost'])
        self.assertGreater(action['aim'][0], 1)
        obs['self']['energy'] = 55
        self.assertFalse(bot.act(obs)['boost'])
        bot.ffa = True
        self.assertIsNone(bot.choose_objective(obs, 1., False, False))

    def test_supply_drop_approach_hold_and_yield(self):
        bot = Controller(HELLO)
        obs = observation()
        obs.update(t=100, tick=1000)
        drop = dict(id=20000, pos=[30, 0, 0], radius=8, lands_in=0,
                    capture_s=4, progress=0, holder=None)
        obs['drops'] = [drop]
        bot.world = Mock(baked=None)
        bot.world.ground.return_value = 0
        bot.movement = Mock(unstuck_until=0)
        bot.movement.avoid_shells.return_value = None
        bot.movement.navigate.return_value = [1, 0]
        self.assertEqual(bot.act(obs)['move'], [1, 0])
        self.assertEqual(bot.mode, 'capture')
        obs['self']['pos'] = [27, 0, 0]
        drop.update(holder=bot.slot, progress=2)
        self.assertEqual(bot.act(obs)['move'], [0, 0])
        self.assertEqual(bot.mode, 'capture')
        self.assertIsNone(bot.choose_objective(obs, .5, True, True))
        drop['holder'] = (bot.slot + 1) % 16
        self.assertIsNone(bot.choose_objective(obs, .5, False, True))
        drop.update(holder=None, progress=0, lands_in=25)
        self.assertIsNone(bot.choose_objective(obs, .5, False, True))

    def test_cornered_projectile_boost_respects_energy_and_ground_contact(self):
        obs = observation()
        obs['projectiles'] = [{'kind':'gun', 'pos':[-20, 0, 5], 'vel':[200, 0, 0]}]
        for flag, mode, grounded, energy, expected in [
            ('1','cornered',True,26,True), ('0','cornered',True,26,False),
            ('1','fight',True,26,False), ('1','cornered',False,26,False),
            ('1','cornered',True,25,False),
        ]:
            with self.subTest(flag=flag,mode=mode,grounded=grounded,energy=energy):
                with patch.dict('os.environ', {'BOT_CORNERED_BOOST':flag}):
                    move = Movement(Mock(), HELLO['config'], random.Random(1))
                obs['self'].update(grounded=grounded,energy=energy)
                action = dict(move=[0,0],boost=False)
                move.apply_evasion_and_recovery(obs,action,mode)
                self.assertEqual(action['boost'],expected)
                self.assertNotEqual(action['move'],[0,0])

    def test_spacing_moves_away_from_nearby_second_enemy(self):
        obs=observation(); foe=enemy(80); other=enemy(-30); other['id']=8
        world=Mock(); world.line_walkable.return_value=True; world.free_cell.return_value=True
        world.walk_at.return_value=0; world.shot_clear.return_value=True; world.baked=None
        moves={}
        for method in ('legacy','spacing'):
            movement=Movement(world,HELLO['config'],random.Random(1))
            movement.nav_method=method; movement.action_deadline=time.perf_counter()+1
            moves[method]=movement.combat_move(obs,foe,[foe,other],True)
        self.assertLess(moves['legacy'][0],0)
        self.assertGreater(moves['spacing'][0],0)

    def test_squad_position_seeks_cover_from_aimed_laser(self):
        with patch.dict('os.environ', {'BOT_SQUAD_POSITION':'cover', 'BOT_SQUAD_RECOVERY':'legacy'}):
            bot=Controller(HELLO)
        obs=observation(); obs.update(t=21,tick=2)
        foe=enemy(100); foe['charging']=True; foe['aim']=[3.141592653589793,0]
        bot.update_world=Mock()
        bot.assess_combat=Mock(return_value=([foe],foe,foe,True,False))
        bot.movement=Mock(); bot.movement.unstuck_until=0
        bot.movement.avoid_shells.return_value=None
        bot.movement.combat_move.return_value=[0,0]
        bot.act(obs)
        self.assertEqual(bot.movement.combat_move.call_args.args[4],-1.6)

    def test_squad_recovery_is_disabled_by_default(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertFalse(Controller(HELLO).recovery_enabled)
        with patch.dict('os.environ', {'BOT_SQUAD_RECOVERY': 'cover'}):
            self.assertTrue(Controller(HELLO).recovery_enabled)

    def test_squad_recovery_holds_fire_and_persists_then_stops(self):
        with patch.dict('os.environ', {'BOT_SQUAD_RECOVERY': 'cover'}):
            bot = Controller(HELLO)
        obs = observation()
        obs.update(t=21, tick=2)
        obs['self']['hp'] = obs['self']['max_hp'] * .45
        foe = enemy(100)
        bot.update_world = Mock()
        bot.assess_combat = Mock(return_value=([foe], foe, foe, True, False))
        bot.retreat = True
        bot.movement = Mock()
        bot.movement.unstuck_until = 0
        bot.movement.avoid_shells.return_value = None
        bot.movement.seek_cover.return_value = [0, 0]
        bot.movement.combat_move.return_value = [1, 0]
        action = bot.act(obs)
        self.assertEqual(bot.mode, 'recover')
        self.assertEqual(action['fire'], [False, False])
        bot.retreat = False
        obs['t'] += 6
        self.assertEqual(bot.act(obs)['fire'], [False, False])
        self.assertEqual(bot.mode, 'recover')
        obs['self']['hp'] = obs['self']['max_hp'] * .8
        bot.act(obs)
        self.assertNotEqual(bot.mode, 'recover')

    def test_squad_recovery_yields_to_close_threat_and_zone(self):
        with patch.dict('os.environ', {'BOT_SQUAD_RECOVERY': 'cover'}):
            bot = Controller(HELLO)
        obs = observation()
        obs.update(t=21, tick=2)
        obs['self']['hp'] = obs['self']['max_hp'] * .45
        foe = enemy(20)
        bot.update_world = Mock()
        bot.assess_combat = Mock(return_value=([foe], foe, foe, True, False))
        bot.retreat = True
        bot.movement = Mock()
        bot.movement.unstuck_until = 0
        bot.movement.avoid_shells.return_value = None
        bot.movement.seek_cover.return_value = [0, 0]
        bot.movement.combat_move.return_value = [1, 0]
        bot.act(obs)
        self.assertNotEqual(bot.mode, 'recover')
        obs['self']['in_zone'] = False
        obs['self']['pos'] = [480, 0, 0]
        bot.hold = (*obs['zone']['center'], obs['zone']['radius'])
        bot.movement.navigate.return_value = [-1, 0]
        bot.act(obs)
        self.assertEqual(bot.mode, 'zone')

    def test_gun_respects_final_laser_aim(self):
        obs = observation()
        me = obs['self']
        foe = enemy(100)
        foe['vel'] = [0, 25, 0]
        me['weapons'][0].update(kind='gun', ammo=12, reload=0, cooldown=0,
                                stats=HELLO['config']['weapons']['gun'])
        me['weapons'][1] = {'kind': 'laser', 'charge': .7, 'cooldown': 0,
                            'stats': HELLO['config']['weapons']['laser']}
        me['aim'] = [0, 0]
        with patch.dict('os.environ', {'BOT_GUN_AIM_CHECK': 'legacy'}):
            self.assertTrue(aim_and_fire(me, foe, HELLO['config'])['fire'][0])
        with patch.dict('os.environ', {'BOT_GUN_AIM_CHECK': 'actual'}):
            self.assertFalse(aim_and_fire(me, foe, HELLO['config'])['fire'][0])
        with patch.dict('os.environ', {}, clear=True):
            self.assertFalse(aim_and_fire(me, foe, HELLO['config'])['fire'][0])

    def test_movement_shares_controller_world_and_random_generator(self):
        bot = Controller(HELLO)
        self.assertIs(bot.movement.world, bot.world)
        self.assertIs(bot.movement.rng, bot.rng)

    def test_assess_combat_selects_nearby_visible_threat(self):
        bot = Controller(HELLO)
        obs = observation()
        foe = enemy(30)
        bot.tracks[foe['id']] = {'actor': foe, 'seen': obs['t'], 'los': True}
        seen, target, pursuit, danger, finishing = bot.assess_combat(obs, False, False, 1.0)
        self.assertEqual(seen, [foe])
        self.assertIs(target, foe)
        self.assertIs(pursuit, foe)
        self.assertTrue(danger)
        self.assertFalse(finishing)

    def test_choose_objective_ranks_reachable_cube(self):
        bot = Controller(HELLO)
        obs = observation()
        bot.world = SimpleNamespace(ground=Mock(return_value=0), cell=Mock(return_value=(0, 0)),
                                    nearest_free=Mock(return_value=(0, 0)), baked=None)
        bot.hold = (*obs['zone']['center'], obs['zone']['radius'])
        item = {'id': 5000, 'pos': [30, 0, 0]}
        bot.items[item['id']] = ('cubes', item, obs['t'])
        self.assertEqual(bot.choose_objective(obs, 1.0, False, True)[0], item['id'])

    def test_selective_farming_prefers_unblocked_cube(self):
        bot = Controller(HELLO)
        obs = observation()
        bot.world = SimpleNamespace(ground=Mock(return_value=0), cell=Mock(return_value=(0, 0)),
                                    nearest_free=Mock(return_value=(0, 0)), baked=None,
                                    line_walkable=Mock(side_effect=lambda start, end: end[0] > 30))
        bot.hold = (*obs['zone']['center'], obs['zone']['radius'])
        bot.items = {5000: ('cubes', {'id': 5000, 'pos': [20, 0, 0]}, obs['t']),
                     5001: ('cubes', {'id': 5001, 'pos': [35, 0, 0]}, obs['t'])}
        bot.farming_policy = 'legacy'
        self.assertEqual(bot.choose_objective(obs, 1.0, False, True)[0], 5000)
        bot.farming_policy = 'route'
        self.assertEqual(bot.choose_objective(obs, 1.0, False, True)[0], 5001)

    def test_pickup_and_unseen_attacker_memory(self):
        bot = Controller(HELLO)
        obs = observation()
        obs['mechs'] = []
        obs['events'] = [{'type': 'damaged', 'by': 987, 'weapon': 'gun', 'bearing': 0}]
        bot.update_world(obs)
        self.assertEqual(bot.attacker_memory[987], obs['t'])
        self.assertNotIn(987, bot.hits)
        pickup_obs = copy.deepcopy(obs)
        pickup_obs['pickups'] = [{'id': 12345, 'kind': 'laser', 'pos': obs['self']['pos'][:]}]
        pickup_obs['self']['weapons'][1] = None
        self.assertEqual(choose_loadout(pickup_obs, HELLO['config'])['take'], 12345)

    def test_farming_uses_movement_component(self):
        bot = Controller(HELLO)
        obs = observation()
        obs.update(t=21, tick=2)
        npc = enemy(40)
        npc.update(id=100, kind='npc')
        obs['mechs'] = [npc]
        bot.world = SimpleNamespace(shot_clear=Mock(return_value=True), ground=Mock(return_value=0),
                                    cell=Mock(return_value=(0, 0)), nearest_free=Mock(return_value=(0, 0)),
                                    baked=None)
        bot.movement = Mock()
        bot.movement.unstuck_until = 0
        bot.movement.avoid_shells.return_value = None
        bot.movement.combat_move.return_value = [0, 0]
        action = bot.act(obs)
        bot.movement.combat_move.assert_called_once()
        self.assertEqual(action['tick'], obs['tick'])


if __name__ == '__main__':
    unittest.main()
