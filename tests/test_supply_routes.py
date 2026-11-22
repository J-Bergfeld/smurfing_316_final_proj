"""Supply selection uses its current straight-line travel estimate."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot.loadout import choose_objective, choose_loadout
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

    def test_legacy_drop_selection_does_not_check_walkability(self):
        self.assertEqual(self.choose()[1], 'drops')
        self.state.world.line_walkable.return_value = False
        self.assertEqual(self.choose()[1], 'drops')
        self.state.world.line_walkable.assert_not_called()

    def test_drop_rejected_when_straight_line_estimate_misses_deadline(self):
        self.state.items.clear()
        with patch('bot.loadout.zone_deadline', return_value=109):
            self.assertEqual(self.choose()[1], 'drops')
        with patch('bot.loadout.zone_deadline', return_value=106):
            self.assertIsNone(self.choose())

    def test_already_inside_does_not_penalize_capture(self):
        self.state.items.clear()
        self.obs['self']['pos'] = [27, 0, 0]
        self.state.world.line_walkable.return_value = False
        self.assertEqual(self.choose()[1], 'drops')
        self.state.world.line_walkable.assert_not_called()

    def test_pressure_prefers_a_hidden_cube_to_a_similar_exposed_one(self):
        self.state.decision_policy = 'pressure'
        self.state.ffa = True
        self.state.supply_drops = False
        self.obs['self']['cubes'] = 0
        self.state.items = {
            5000: ('cubes', {'id': 5000, 'pos': [30, 0, 0]}, 100),
            5001: ('cubes', {'id': 5001, 'pos': [40, 0, 0]}, 100),
        }
        self.state.tracks = {7: {'actor': {'kind': 'mech', 'pos': [100, 0, 0]}, 'seen': 100}}
        self.state.world.shot_clear = Mock(side_effect=lambda eye, target: target[0] == 30)
        self.assertEqual(self.choose()[0], 5001)

    def test_pressure_rooftop_loot_requires_a_reachable_roof(self):
        self.state.decision_policy = 'pressure'
        self.state.supply_drops = False
        self.state.items = {5000: ('cubes', {'id': 5000, 'pos': [30, 0, 10]}, 100)}
        roof = {'cells': {(0, 0)}, 'top': 10,
                'access': [((0, 0), (24, 0), (32, 0), 10)]}
        self.state.movement = SimpleNamespace(roof_graph=[roof])
        self.assertEqual(self.choose()[0], 5000)
        roof['access'] = []
        self.assertIsNone(self.choose())

    def test_pressure_take_request_has_a_short_cooldown(self):
        state = SimpleNamespace()
        self.obs['self']['weapons'][1] = None
        self.obs['pickups'] = [{'id': 8001, 'kind': 'laser', 'pos': [0, 0, 0]}]
        first = choose_loadout(self.obs, HELLO['config'], pressure=True, state=state)
        self.assertEqual(first['take'], 8001)
        self.obs['t'] += .1
        self.assertNotIn('take', choose_loadout(self.obs, HELLO['config'], pressure=True, state=state))
        self.obs['t'] += .2
        self.assertEqual(choose_loadout(self.obs, HELLO['config'], pressure=True, state=state)['take'], 8001)

    def test_pressure_can_take_recently_seen_pickup(self):
        self.obs['self']['weapons'][1] = None
        item = {'id': 8001, 'kind': 'laser', 'pos': [0, 0, 0]}
        state = SimpleNamespace(items={8001: ('pickups', item, self.obs['t']-.4)})
        self.assertEqual(choose_loadout(self.obs, HELLO['config'], pressure=True, state=state)['take'], 8001)
        self.obs['t'] += .2
        self.assertNotIn('take', choose_loadout(self.obs, HELLO['config'], pressure=True, state=state))


if __name__ == '__main__':
    unittest.main()
