import unittest
from unittest.mock import patch

from bot.combat import apply_weapon_control
from bot.controller import Controller
from test_bot import HELLO, observation, enemy


class SoundScanTests(unittest.TestCase):
    def setUp(self):
        self.state = Controller(HELLO)
        self.obs = observation()
        self.obs['t'] = 10
        self.action = {'move': [1, 0], 'fire': [False, False]}

    def apply(self, target=None):
        apply_weapon_control(self.state, self.obs, self.action, target, target, True)
        return self.action['aim'][0]

    def test_near_sound_guides_aim_then_expires(self):
        self.obs['sounds'] = [{'kind': 'step', 'bearing': 1.2, 'dist': 'near', 'age': .1}]
        self.assertEqual(self.apply(), 1.2)
        self.assertEqual(self.action['fire'], [False, False])
        self.obs['sounds'] = [{'kind': 'gun', 'bearing': -2, 'dist': 'mid', 'age': 0}]
        self.obs['t'] = 10.3
        self.assertEqual(self.apply(), 1.2)
        self.obs['sounds'] = []
        self.obs['t'] = 11
        self.assertNotEqual(self.apply(), 1.2)

    def test_stale_irrelevant_and_far_sounds_are_ignored(self):
        self.obs['sounds'] = [
            {'kind': 'step', 'bearing': 1.2, 'dist': 'near', 'age': 1.1},
            {'kind': 'explosion', 'bearing': 1.4, 'dist': 'near', 'age': 0},
            {'kind': 'gun', 'bearing': 1.6, 'dist': 'far', 'age': 0},
        ]
        self.assertNotIn(self.apply(), (1.2, 1.4, 1.6))

    def test_combat_and_recent_damage_take_priority(self):
        self.obs['sounds'] = [{'kind': 'step', 'bearing': 1.2, 'dist': 'near', 'age': 0}]
        self.state.last_hurt = 9
        self.state.hurt_bearing = -.7
        self.assertEqual(self.apply(), -.7)
        with patch('bot.combat.aim_and_fire', return_value={'aim': [.4, 0]}):
            self.assertEqual(self.apply(enemy()), .4)

    def test_sound_inside_vision_does_not_interrupt_scan(self):
        self.obs['sounds'] = [{'kind': 'step', 'bearing': .2, 'dist': 'near', 'age': 0}]
        self.assertNotEqual(self.apply(), .2)

    def test_high_value_cue_wins_at_equal_distance(self):
        self.obs['sounds'] = [
            {'kind': 'gun', 'bearing': -1.5, 'dist': 'near', 'age': 0},
            {'kind': 'step', 'bearing': 1.5, 'dist': 'near', 'age': 0},
        ]
        self.assertEqual(self.apply(), 1.5)

    def test_outside_vision_is_preferred_near_its_edge(self):
        self.obs['sounds'] = [
            {'kind': 'boost', 'bearing': .9, 'dist': 'near', 'age': 0},
            {'kind': 'boost', 'bearing': -1.5, 'dist': 'near', 'age': 0},
        ]
        self.assertEqual(self.apply(), -1.5)

    def test_nearer_sound_is_preferred(self):
        self.obs['sounds'] = [
            {'kind': 'gun', 'bearing': -1.5, 'dist': 'mid', 'age': 0},
            {'kind': 'boost', 'bearing': 1.1, 'dist': 'near', 'age': .2},
        ]
        self.assertEqual(self.apply(), 1.1)


if __name__ == '__main__':
    unittest.main()
