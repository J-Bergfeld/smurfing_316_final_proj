import unittest
from unittest.mock import Mock, patch

from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class ApproachBoostTests(unittest.TestCase):
    def setUp(self):
        self.bot = Controller(HELLO)
        self.obs = observation()
        self.obs.update(t=10, tick=200)
        self.foe = enemy(115)
        self.bot.update_world = Mock()
        self.bot.assess_combat = Mock(return_value=([self.foe], self.foe, self.foe, True, False))
        self.bot.field = None
        self.bot.corner_duel = False
        self.bot.movement.avoid_shells = Mock(return_value=None)
        self.bot.movement.combat_move = Mock(return_value=[1, 0])
        self.bot.movement.navigate = Mock(return_value=[-1, 0])
        self.bot.movement.apply_evasion_and_recovery = Mock()
        self.bot.hold = (*self.obs['zone']['center'], self.obs['zone']['radius'])

    def act(self):
        with patch('bot.controller.apply_weapon_control'):
            return self.bot.act(self.obs)

    def test_boosts_toward_target_even_with_another_mech(self):
        other = enemy(120); other['id'] = 8
        self.bot.assess_combat.return_value = ([self.foe, other], self.foe, self.foe, True, False)
        self.assertTrue(self.act()['boost'])

    def test_respects_readiness_energy_health_retreat_and_direction(self):
        gun = self.obs['self']['weapons'][0]
        for field, value in [('reload', .1), ('ammo', 0)]:
            old = gun[field]; gun[field] = value
            self.assertFalse(self.act()['boost'])
            gun[field] = old
        for field, value in [('energy', 60), ('hp', 980), ('grounded', False)]:
            old = self.obs['self'][field]; self.obs['self'][field] = value
            self.assertFalse(self.act()['boost'])
            self.obs['self'][field] = old
        self.bot.retreat = True
        self.bot.movement.seek_cover = Mock(return_value=[-1, 0])
        self.assertTrue(self.act()['boost'])  # existing retreat boost
        self.assertEqual(self.bot.mode, 'cover')
        self.bot.retreat = False
        self.bot.movement.combat_move.return_value = [0, 1]
        self.assertFalse(self.act()['boost'])
        self.bot.movement.combat_move.return_value = [1, 0]
        for distance in (95, 100, 130):
            self.foe['pos'][0] = distance
            self.assertFalse(self.act()['boost'])

    def test_urgent_zone_retains_existing_boost(self):
        self.obs['self'].update(pos=[600, 0, 0], in_zone=False)
        action = self.act()
        self.assertEqual(self.bot.mode, 'zone')
        self.assertEqual(action['move'], [-1, 0])
        self.assertTrue(action['boost'])

    def test_dodge_direction_does_not_trigger_approach_boost(self):
        self.bot.movement.avoid_shells.return_value = [0, 1]
        action = self.act()
        self.assertEqual(self.bot.mode, 'dodge')
        self.assertTrue(action['boost'])  # existing emergency dodge boost
        self.assertEqual(action['move'], [0, 1])

    def test_evasion_or_stuck_recovery_can_override_approach(self):
        self.bot.movement.apply_evasion_and_recovery.side_effect = lambda obs, action, mode: action.update(move=[0, 1])
        self.assertFalse(self.act()['boost'])
        self.bot.movement.apply_evasion_and_recovery.side_effect = lambda obs, action, mode: action.update(jump=True)
        self.assertFalse(self.act()['boost'])


if __name__ == '__main__':
    unittest.main()
