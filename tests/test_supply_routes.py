"""Drop detours affect preference and the estimated zone deadline."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot.loadout import choose_objective
from test_bot import HELLO, observation


class SupplyRouteTests(unittest.TestCase):
    def setUp(self):
        self.obs = observation()
        self.obs['t'] = 100
        self.drop = dict(id=20000, pos=[30, 0, 0], radius=8, lands_in=0,
                         capture_s=4, progress=0, holder=None)
        self.obs['drops'] = [self.drop]
        cube = dict(id=5000, pos=[10, 0, 0])
        world = SimpleNamespace(ground=Mock(return_value=0), cell=Mock(return_value=(0, 0)),
                                nearest_free=Mock(return_value=(0, 0)), baked=None,
                                line_walkable=Mock(return_value=True))
        self.state = SimpleNamespace(items={5000: ('cubes', cube, 100)}, tracks={},
            cfg=HELLO['config'], world=world, bad={}, loot_id=None, hold=(0, 0, 500),
            supply_drops=True, slot=0, laser_rush=False, ffa=False, farming_policy='legacy')

    def choose(self):
        return choose_objective(self.state, self.obs, 1., False, True)

    def test_blocked_drop_loses_to_nearby_cube(self):
        self.assertEqual(self.choose()[1], 'drops')
        self.state.world.line_walkable.return_value = False
        self.assertEqual(self.choose()[1], 'cubes')

    def test_blocked_detour_can_miss_zone_deadline(self):
        self.state.items.clear()
        with patch('bot.loadout.zone_deadline', return_value=109):
            self.assertEqual(self.choose()[1], 'drops')
            self.state.world.line_walkable.return_value = False
            self.assertIsNone(self.choose())

    def test_already_inside_does_not_penalize_capture(self):
        self.state.items.clear()
        self.obs['self']['pos'] = [27, 0, 0]
        self.state.world.line_walkable.return_value = False
        self.assertEqual(self.choose()[1], 'drops')
        self.state.world.line_walkable.assert_not_called()


if __name__ == '__main__':
    unittest.main()
