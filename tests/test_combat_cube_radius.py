import unittest
from unittest.mock import Mock, patch

from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class CombatCubeRadiusTests(unittest.TestCase):
    def setUp(self):
        self.bot = Controller(HELLO)
        self.obs = observation()
        self.obs.update(t=10, tick=200)
        self.foe = enemy(100)
        self.bot.update_world = Mock()
        self.bot.assess_combat = Mock(return_value=([self.foe], self.foe, self.foe, True, False))
        self.bot.field = None
        self.bot.corner_duel = False
        self.bot.movement.avoid_shells = Mock(return_value=None)
        self.bot.movement.combat_move = Mock(return_value=[0, 1])
        self.bot.movement.navigate = Mock(return_value=[1, 0])
        self.bot.movement.apply_evasion_and_recovery = Mock()
        self.bot.hold = (*self.obs['zone']['center'], self.obs['zone']['radius'])

    def mode_for(self, distance, hp=1400):
        self.obs['self']['hp'] = hp
        self.bot.items = {5000: ('cubes', {'id': 5000, 'pos': [distance, 0, 0]}, 10)}
        with patch('bot.controller.apply_weapon_control'):
            self.bot.act(self.obs)
        return self.bot.mode

    def test_healthy_detour_boundary(self):
        self.assertEqual(self.mode_for(59.9), 'fight:cube')
        self.assertEqual(self.mode_for(60), 'fight')
        self.assertEqual(self.mode_for(65), 'fight')

    def test_low_health_threshold_is_unchanged(self):
        self.assertEqual(self.mode_for(39.8, 700), 'fight:cube')
        self.assertEqual(self.mode_for(40, 700), 'fight')


if __name__ == '__main__':
    unittest.main()
