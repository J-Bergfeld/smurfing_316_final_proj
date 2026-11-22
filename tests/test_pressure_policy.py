import unittest
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot.combat import aim_and_fire, apply_weapon_control, assess_pressure, mortar_solution, shot_to_surface_clear, pressure_advantage, pressure_dps, pressure_laser_peek
from bot.controller import Controller
from bot.loadout import pressure_pickup, choose_loadout
from test_bot import HELLO, enemy, observation


class PressurePolicyTests(unittest.TestCase):
    def test_laser_peek_charges_in_cover_then_moves_to_firing_position(self):
        obs=observation(); me=obs['self']; me['pos']=[-3,0,0]
        laser={'kind':'laser','charge':0,'cooldown':0,'stats':HELLO['config']['weapons']['laser']}
        me['weapons'][1]=laser
        foe=enemy(90)
        def clear(a,b):
            return b[0]>=0 if a[0]>50 else a[0]>=0
        world=SimpleNamespace(walk_at=lambda x,y:0,inside=lambda x,y:True,
                              cell=lambda x,y:(x,y),free_cell=lambda cell:True,
                              line_walkable=lambda a,b:True,shot_clear=clear)
        state=SimpleNamespace(world=world,cfg=HELLO['config'],action_deadline=time.perf_counter()+1)
        step=pressure_laser_peek(state,obs,foe,[foe])
        self.assertEqual(step['goal'],(-3,0))
        self.assertTrue(step['charge'])
        laser['charge']=.2
        step=pressure_laser_peek(state,obs,foe,[foe])
        self.assertGreaterEqual(step['goal'][0],0)
        self.assertFalse(step['charge'])

    def test_pressure_exchange_accounts_for_weapon_range_and_armor(self):
        self_state = observation()['self']
        opponent = enemy(100)
        initial = pressure_advantage(HELLO['config'], self_state, opponent, False)
        self_state['stats']['armor'] = .3
        self.assertGreater(pressure_advantage(HELLO['config'], self_state, opponent, False), initial)
        self.assertGreater(pressure_dps(HELLO['config'], {'lightning'}, 0, 30, True, False), 0)
        self.assertEqual(pressure_dps(HELLO['config'], {'lightning'}, 0, 100, True, False), 0)

    def test_lightning_spacing_considers_secondary_carrier(self):
        primary = enemy(100)
        carrier = enemy(45)
        carrier['id'] = 8
        carrier['weapons'] = ['lightning']
        self.obs['mechs'] = [primary, carrier]
        with patch.object(self.bot.world, 'line_walkable', return_value=True):
            move = self.bot.movement.pressure_avoid_lightning(self.obs, (1., 0.))
            self.assertLessEqual(move[0], 0)
            self.obs['self']['weapons'][1] = {'kind': 'lightning'}
            self.assertEqual(self.bot.movement.pressure_avoid_lightning(self.obs, (1., 0.)), (1., 0.))

    def test_shot_clearance_stops_at_target_surface(self):
        class WallAtTarget:
            def shot_clear(self, start, end): return end[0] < 99
        self.assertTrue(shot_to_surface_clear(WallAtTarget(), (0, 0, 0), (100, 0, 0), 2.5))

    def test_pressure_gun_lead_uses_target_motion_and_live_speed(self):
        me = self.obs['self']
        target = enemy(120)
        target['vel'] = [0, 12, 0]
        slow = aim_and_fire(me, target, HELLO['config'], pressure=True)['aim'][0]
        gun = next(w for w in me['weapons'] if w and w['kind'] == 'gun')
        gun['stats']['speed'] *= 2
        fast = aim_and_fire(me, target, HELLO['config'], pressure=True)['aim'][0]
        self.assertGreater(slow, fast)
        self.assertGreater(fast, 0)
        target['vel'] = [0, 0, 0]
        self.assertAlmostEqual(aim_and_fire(me, target, HELLO['config'], pressure=True)['aim'][0], 0)

    def test_pressure_aims_at_exposed_head_over_low_cover(self):
        me = self.obs['self']
        target = enemy(80)
        class LowWall:
            def shot_clear(self, start, end):
                return end[2] > 7
        open_aim = aim_and_fire(me, target, HELLO['config'], pressure=True)['aim']
        covered_aim = aim_and_fire(me, target, HELLO['config'], world=LowWall(), pressure=True)['aim']
        self.assertGreater(covered_aim[1], open_aim[1])

    def test_pressure_loadout_accepts_mortar_without_dropping_gun(self):
        gun = {'kind': 'gun'}
        self.assertEqual(pressure_pickup('mortar', [gun, None]), (True, None))
        self.assertEqual(pressure_pickup('mortar', [gun, {'kind': 'lightning'}]), (True, 1))
        self.assertEqual(pressure_pickup('laser', [gun, {'kind': 'mortar'}]), (False, None))
        self.assertEqual(pressure_pickup('mortar', [gun, {'kind': 'mortar'}]), (False, None))

    def test_pressure_upgrades_follow_reference_priority(self):
        self.obs['offer'] = {'choices': [{'id': 'plating'}, {'id': 'sensors'}, {'id': 'armor'}]}
        self.assertEqual(choose_loadout(self.obs, HELLO['config'], pressure=True)['pick'], 1)

    def test_roaming_requires_health_and_missing_cubes(self):
        self.obs['t'] = 10
        self.obs['self']['cubes'] = 0
        self.assertIsNone(self.bot.pressure_roam(self.obs, .5))
        self.obs['self']['cubes'] = 26
        self.assertIsNone(self.bot.pressure_roam(self.obs, 1.0))

    def test_exploration_resumes_after_its_time_budget(self):
        self.obs['tick'] = 0
        self.bot.action_deadline = 100.
        clock = iter(i * .001 for i in range(100))
        with patch('bot.controller.time.perf_counter', side_effect=lambda: next(clock)):
            self.bot.mark_exploration(self.obs)
            first = self.bot.exploration_cursor
            self.assertIsNotNone(first)
            self.bot.mark_exploration(self.obs)
            second = self.bot.exploration_cursor
        self.assertIsNotNone(second)
        self.assertGreater((second[1], second[0]), (first[1], first[0]))

    def test_pressure_idle_tracks_recent_sound_then_resumes_scan(self):
        self.bot.decision_policy = 'pressure'
        self.bot.tracks = {}
        self.obs['sounds'] = [{'kind': 'gun', 'dist': 'near', 'bearing': 1.2, 'age': 0}]
        action = {'move': [1., 0.], 'fire': [False, False]}
        apply_weapon_control(self.bot, self.obs, action, None, None, True)
        self.assertEqual(action['aim'][0], 1.2)
        self.obs['t'] += 2
        self.obs['sounds'] = []
        apply_weapon_control(self.bot, self.obs, action, None, None, True)
        self.assertAlmostEqual(self.bot.scan_phase, .1)

    def setUp(self):
        self.bot = Controller(HELLO)
        self.obs = observation()
        self.obs['t'] = 10
        self.foe = enemy(80)
        self.bot.tracks = {self.foe['id']: {'actor': self.foe, 'seen': 10, 'los': True}}

    def test_aimed_opponent_is_a_current_threat(self):
        known, engaged, target = assess_pressure(self.bot, self.obs)
        self.assertEqual(len(known), 1)
        self.assertEqual(len(engaged), 1)
        self.assertIs(target['actor'], self.foe)
        self.foe['aim'] = [0, 0]
        _, engaged, _ = assess_pressure(self.bot, self.obs)
        self.assertEqual(len(engaged), 1)
        self.obs['t'] += 1
        self.bot.tracks[self.foe['id']]['seen'] = self.obs['t']
        _, engaged, _ = assess_pressure(self.bot, self.obs)
        self.assertEqual(engaged, [])

    def test_force_squad_blocks_automatic_ffa_inference(self):
        self.bot.tracks = {}
        with patch.object(self.bot, 'mark_exploration'), \
             patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'), \
             patch.object(self.bot, 'choose_objective', return_value=None), \
             patch.object(self.bot, 'pressure_roam', return_value=None), \
             patch.object(self.bot, 'pressure_exposure_hold', return_value=None), \
             patch('bot.controller.apply_weapon_control'):
            self.bot.pressure_force_squad = True
            self.bot.act_pressure(self.obs)
            self.obs['alive'] -= 1
            self.bot.act_pressure(self.obs)
            self.assertEqual(self.bot.lobby_unknown_deaths, 1)
            self.assertFalse(self.bot.ffa)
            self.bot.pressure_force_squad = False
            self.bot.act_pressure(self.obs)
            self.assertTrue(self.bot.ffa)

    def test_optional_pressure_field_preserves_target_and_safety_priorities(self):
        self.bot.pressure_field = True
        self.bot.field = Mock(key='previous', route=[(1, 1)], breakdown={'old': True})
        self.bot.field.choose.return_value = [.25, .75]
        self.bot.action_deadline = time.perf_counter() + 10
        second = enemy(90)
        second['id'] = 8
        selected = {'actor': self.foe, 'track': {'los': True}, 'distance': 80,
                    'current': True, 'active': True}
        other = {'actor': second, 'track': {'los': True}, 'distance': 90,
                 'current': True, 'active': True}
        with patch('bot.controller.assess_pressure', return_value=([selected, other], [selected, other], selected)), \
             patch.object(self.bot, 'mark_exploration'), \
             patch.object(self.bot, 'pressure_zone', return_value=((50, 0), False)) as zone, \
             patch.object(self.bot, 'pressure_fight_weapon', return_value=None), \
             patch.object(self.bot, 'pressure_fight_cube', return_value=None), \
             patch.object(self.bot.movement, 'avoid_shells', return_value=None) as shells, \
             patch.object(self.bot.movement, 'navigate', return_value=[1., 0.]), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'), \
             patch('bot.controller.apply_weapon_control') as weapon_control:
            action = self.bot.act_pressure(self.obs)
            self.assertEqual(action['move'], [.25, .75])
            self.assertEqual(self.bot.mode, 'positional-field')
            self.assertIs(weapon_control.call_args.args[3], self.foe)
            self.bot.field.choose.assert_called_once()

            self.bot.field.choose.reset_mock()
            shells.return_value = [-1., 0.]
            action = self.bot.act_pressure(self.obs)
            self.assertEqual(action['move'], [-1., 0.])
            self.bot.field.choose.assert_not_called()
            self.assertIsNone(self.bot.field.key)
            self.assertEqual(self.bot.field.route, [])

            shells.return_value = None
            zone.return_value = ((50, 0), True)
            self.bot.act_pressure(self.obs)
            self.assertEqual(self.bot.mode, 'zone')
            self.bot.field.choose.assert_not_called()

    def test_pressure_field_skipped_when_budget_nearly_spent(self):
        self.bot.pressure_field = True
        self.bot.field = Mock(route=[], breakdown={})
        self.bot.action_deadline = time.perf_counter() + .001
        selected = {'actor': self.foe, 'track': {'los': True}, 'distance': 80,
                    'current': True, 'active': True}
        with patch('bot.controller.assess_pressure', return_value=([selected, selected], [selected, selected], selected)), \
             patch.object(self.bot, 'mark_exploration'), \
             patch.object(self.bot, 'pressure_zone', return_value=((0, 0), False)), \
             patch.object(self.bot, 'pressure_fight_weapon', return_value=None), \
             patch.object(self.bot, 'pressure_fight_cube', return_value=None), \
             patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'pressure_kite', return_value=[1., 0.]), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'), \
             patch('bot.controller.apply_weapon_control'):
            self.bot.act_pressure(self.obs)
        self.bot.field.choose.assert_not_called()

    def test_missing_opponent_is_not_treated_as_current(self):
        self.bot.tracks[self.foe['id']]['seen'] = self.obs['t'] - .1
        _, engaged, target = assess_pressure(self.bot, self.obs)
        self.assertEqual(engaged, [])
        self.assertIsNone(target)

    def test_pressure_target_scoring_favors_finishable_rear_target(self):
        other = enemy(80)
        other.update(id=8, hp=200, aim=[0, 0])
        self.bot.tracks[8] = {'actor': other, 'seen': self.obs['t'], 'los': True}
        self.assertIs(assess_pressure(self.bot, self.obs)[2]['actor'], other)
        self.bot.tracks[8]['seen'] -= 1
        self.assertIs(assess_pressure(self.bot, self.obs)[2]['actor'], self.foe)

    def test_missing_nearby_drone_is_removed_when_position_is_visible(self):
        npc = {'id': 101, 'kind': 'npc', 'pos': [5, 0, 0], 'vel': [0, 0, 0]}
        self.bot.tracks = {101: {'actor': npc, 'seen': self.obs['t'] - .1, 'los': True}}
        self.bot.decision_policy = 'pressure'
        with patch.object(self.bot.world, 'shot_clear', return_value=True):
            self.bot.update_world(self.obs)
        self.assertNotIn(101, self.bot.tracks)

    def test_missing_entities_outside_proximity_are_retained(self):
        npc = {'id': 101, 'kind': 'npc', 'pos': [-30, 0, 0], 'vel': [0, 0, 0]}
        self.bot.tracks = {101: {'actor': npc, 'seen': self.obs['t'] - .1, 'los': True}}
        self.bot.items = {102: ('cubes', {'id': 102, 'pos': [-30, 0, 0]}, self.obs['t'] - 1)}
        self.bot.decision_policy = 'pressure'
        with patch.dict(self.bot.cfg['vision'], {'near_range': 20}), \
             patch.object(self.bot.world, 'shot_clear', return_value=True):
            self.bot.update_world(self.obs)
        self.assertIn(101, self.bot.tracks)
        self.assertIn(102, self.bot.items)

    def test_lead_history_uses_visible_observations_only(self):
        self.bot.decision_policy = 'pressure'
        self.obs['mechs'] = [self.foe]
        with patch.object(self.bot.world, 'shot_clear', return_value=True), \
             patch.object(self.bot.world, 'vision_clear', return_value=False):
            self.bot.update_world(self.obs)
        self.assertFalse(self.bot.tracks[self.foe['id']]['visible'])
        self.assertNotIn(self.foe['id'], self.bot.lead_tracker.tracks)
        self.obs['t'] += .1
        with patch.object(self.bot.world, 'shot_clear', return_value=True), \
             patch.object(self.bot.world, 'vision_clear', return_value=True):
            self.bot.update_world(self.obs)
        self.assertTrue(self.bot.tracks[self.foe['id']]['visible'])
        self.assertIn(self.foe['id'], self.bot.lead_tracker.tracks)

    def test_unseen_attacker_direction_takes_priority_over_idle_aim(self):
        self.bot.tracks = {}
        self.obs['events'] = [{'type': 'damaged', 'weapon': 'gun', 'by': 3,
                               'bearing': .7, 'amount': 40}]
        with patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'), \
             patch.object(self.bot, 'choose_objective', return_value=None), \
             patch.object(self.bot, 'pressure_roam', return_value=None), \
             patch('bot.controller.apply_weapon_control'):
            action = self.bot.act_pressure(self.obs)
        self.assertEqual(action['aim'], [.7, 0.])
        self.assertFalse(any(action['fire']))

    def test_unseen_attacker_counts_as_engaged_but_is_not_selected(self):
        self.bot.tracks = {}
        self.bot.unseen_hit_at = self.obs['t']
        self.bot.unseen_hit_bearing = .7
        self.bot.unseen_hit_distance = 115.
        known, engaged, target = assess_pressure(self.bot, self.obs)
        self.assertEqual(len(known), 1)
        self.assertTrue(engaged[0]['phantom'])
        self.assertIsNone(target)
        self.obs['t'] += 4.1
        self.assertEqual(assess_pressure(self.bot, self.obs)[1], [])

    def test_close_listed_attacker_can_be_engaged_despite_map_occlusion(self):
        self.foe['pos'] = [30, 0, 0]
        self.bot.tracks[self.foe['id']]['los'] = False
        self.bot.hits[self.foe['id']] = self.obs['t']
        self.bot.ffa = True
        with patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'combat_move', return_value=[0, 0]), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'), \
             patch('bot.controller.apply_weapon_control') as weapon_control:
            self.bot.act_pressure(self.obs)
        self.assertIs(weapon_control.call_args.args[3], self.foe)

    def test_optional_weapon_range_leaves_lightning_close(self):
        with patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'combat_move', return_value=[0, 0]) as move, \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'), \
             patch.object(self.bot, 'pressure_fight_weapon', return_value=None), \
             patch.object(self.bot, 'pressure_fight_cube', return_value=None), \
             patch('bot.controller.apply_weapon_control'):
            self.bot.pressure_weapon_range = False
            self.bot.act_pressure(self.obs)
            self.assertEqual(move.call_args.kwargs['desired_override'], 30)
            self.bot.pressure_weapon_range = True
            self.bot.act_pressure(self.obs)
            self.assertIsNone(move.call_args.kwargs['desired_override'])
            self.obs['self']['weapons'][1] = {
                'kind': 'laser', 'stats': HELLO['config']['weapons']['laser']}
            self.bot.act_pressure(self.obs)
            self.assertIsNone(move.call_args.kwargs['desired_override'])
            self.obs['self']['weapons'][1] = {
                'kind': 'lightning', 'stats': HELLO['config']['weapons']['lightning']}
            self.bot.act_pressure(self.obs)
            self.assertEqual(move.call_args.kwargs['desired_override'], 30)

    def test_peek_can_start_laser_charge_while_moving_to_cover(self):
        self.bot.laser_peek = True
        self.bot.ffa = True
        self.obs['self']['weapons'][1] = {'kind': 'laser', 'charge': 0, 'cooldown': 0,
                                         'stats': HELLO['config']['weapons']['laser']}
        plan = {'goal': (5, 0), 'charge': True, 'slot': 1}
        with patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'navigate', return_value=[1, 0]), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'), \
             patch('bot.controller.pressure_laser_peek', return_value=plan), \
             patch('bot.controller.apply_weapon_control'):
            action = self.bot.act_pressure(self.obs)
        self.assertEqual(self.bot.mode, 'peek')
        self.assertTrue(action['fire'][1])

    def test_reload_only_when_idle_or_empty_while_engaging(self):
        self.bot.decision_policy = 'pressure'
        gun = self.obs['self']['weapons'][0]
        gun['ammo'] = 4
        action = {'fire': [False, False], 'move': [0, 0]}
        apply_weapon_control(self.bot, self.obs, action, None, self.foe, True)
        self.assertNotIn('reload', action)
        self.bot.tracks = {}
        action = {'fire': [False, False], 'move': [0, 0]}
        apply_weapon_control(self.bot, self.obs, action, None, None, True)
        self.assertTrue(action['reload'])
        gun['ammo'] = 0
        action = {'fire': [False, False], 'move': [0, 0]}
        apply_weapon_control(self.bot, self.obs, action, self.foe, self.foe, True)
        self.assertTrue(action['reload'])

    def test_retreat_persists_until_healed_when_no_threat_is_known(self):
        self.bot.tracks = {}
        self.bot.retreat = True
        self.obs['self']['hp'] = 500
        with patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'seek_cover', return_value=None), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'):
            self.bot.act_pressure(self.obs)
            self.assertTrue(self.bot.retreat)
            self.assertEqual(self.bot.mode, 'heal')
            self.obs['self']['hp'] = 800
            self.bot.act_pressure(self.obs)
            self.assertFalse(self.bot.retreat)

    def test_pressure_weapon_can_charge_against_crates(self):
        me = self.obs['self']
        me['weapons'][1] = {'kind': 'laser', 'charge': 0, 'cooldown': 0,
                            'stats': HELLO['config']['weapons']['laser']}
        crate = {'kind': 'crate', 'pos': [40, 0, 0], 'vel': [0, 0, 0], 'hp': 200}
        self.assertFalse(aim_and_fire(me, crate, HELLO['config'])['fire'][1])
        self.assertTrue(aim_and_fire(me, crate, HELLO['config'], pressure=True)['fire'][1])
        me['weapons'][1]['cooldown'] = 1
        self.assertFalse(aim_and_fire(me, crate, HELLO['config'], pressure=True)['fire'][1])

    def test_pressure_mortar_aims_at_stationary_target_with_gun_ready(self):
        me = self.obs['self']
        me['weapons'][1] = {'kind': 'mortar', 'cooldown': 0,
                            'stats': HELLO['config']['weapons']['mortar']}
        me['aim'] = [0, .2]
        crate = {'kind': 'crate', 'pos': [40, 0, 0], 'vel': [0, 0, 0], 'hp': 200}
        with patch('bot.combat.mortar_solution', return_value=(0, .2)):
            action = aim_and_fire(me, crate, HELLO['config'], world=self.bot.world, pressure=True)
        self.assertEqual(action['aim'], [0, .2])
        self.assertTrue(action['fire'][1])

    def test_uncredited_early_death_changes_lobby_belief(self):
        self.bot.tracks = {}
        with patch.object(self.bot.movement, 'avoid_shells', return_value=None), \
             patch.object(self.bot.movement, 'apply_evasion_and_recovery'):
            self.bot.act_pressure(self.obs)
            self.obs['alive'] -= 1
            self.obs['t'] += .1
            self.bot.act_pressure(self.obs)
        self.assertTrue(self.bot.ffa)

    def test_pressure_laser_holds_until_full_or_lethal(self):
        me = self.obs['self']
        me['weapons'] = [None, {'kind': 'laser', 'charge': .72, 'cooldown': 0,
                                'stats': HELLO['config']['weapons']['laser']}]
        target = {'kind': 'crate', 'pos': [40, 0, 0], 'vel': [0, 0, 0], 'hp': 1000}
        action = aim_and_fire(me, target, HELLO['config'], pressure=True)
        me['aim'] = action['aim']
        self.assertTrue(aim_and_fire(me, target, HELLO['config'], pressure=True)['fire'][1])
        target['hp'] = 100
        self.assertFalse(aim_and_fire(me, target, HELLO['config'], pressure=True)['fire'][1])

    def test_aim_only_does_not_start_a_weapon_but_keeps_active_charge(self):
        me = self.obs['self']
        me['weapons'][1] = {'kind': 'laser', 'charge': 0, 'cooldown': 0,
                            'stats': HELLO['config']['weapons']['laser']}
        target = enemy(40)
        self.assertFalse(any(aim_and_fire(me, target, HELLO['config'], pressure=True, allow_fire=False)['fire']))
        me['weapons'][1]['charge'] = .2
        self.assertTrue(aim_and_fire(me, target, HELLO['config'], pressure=True, allow_fire=False)['fire'][1])

    def test_pressure_laser_uses_rear_and_cookoff_for_lethal_release(self):
        me = self.obs['self']
        me['weapons'] = [None, {'kind': 'laser', 'charge': .3, 'cooldown': 0,
                                'stats': HELLO['config']['weapons']['laser']}]
        target = enemy(40)
        target['hp'] = 260
        me['aim'] = aim_and_fire(me, target, HELLO['config'], pressure=True)['aim']
        self.assertTrue(aim_and_fire(me, target, HELLO['config'], pressure=True)['fire'][1])
        target['aim'] = [0, 0]
        self.assertFalse(aim_and_fire(me, target, HELLO['config'], pressure=True)['fire'][1])
        target['aim'] = [3.141592653589793, 0]
        target['weapons'].append('mortar')
        self.assertFalse(aim_and_fire(me, target, HELLO['config'], pressure=True)['fire'][1])

    def test_pressure_mortar_tries_high_arc_over_obstacle(self):
        class Obstacle:
            def solid(self, x, y, z):
                return 60 < x < 90 and z < 25
        solution = mortar_solution(Obstacle(), (0, 0, 9), (150, 0, 0), (0, 0, 0),
                                   72, 22, {'min_pitch': -.7, 'max_pitch': 1.3}, True)
        self.assertIsNotNone(solution)
        self.assertGreater(solution[1], 1.0)

    def test_ready_laser_takes_aim_priority_over_mortar(self):
        me = self.obs['self']
        me['weapons'] = [
            {'kind': 'laser', 'charge': .7, 'cooldown': 0, 'stats': HELLO['config']['weapons']['laser']},
            {'kind': 'mortar', 'cooldown': 0, 'stats': HELLO['config']['weapons']['mortar']},
        ]
        target = {'kind': 'crate', 'pos': [80, 0, 0], 'vel': [0, 0, 0], 'hp': 1000}
        with patch('bot.combat.mortar_solution', return_value=(1, .4)) as solve:
            action = aim_and_fire(me, target, HELLO['config'], world=object(), pressure=True)
        solve.assert_not_called()
        self.assertAlmostEqual(action['aim'][0], 0)


if __name__ == '__main__':
    unittest.main()
