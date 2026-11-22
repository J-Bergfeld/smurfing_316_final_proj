import copy
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot.tactical_planner import TacticalPlanner
from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class Arena:
    def line_walkable(self, a, b):
        return b[1] >= -1

    def walk_at(self, x, y):
        return 0

    def shot_clear(self, a, b):
        # The western attacker's line is blocked north of the origin; our
        # shot at the eastern target remains clear.
        return a[0] >= -50 or b[1] < 3


class TacticalPlannerTests(unittest.TestCase):
    def setUp(self):
        self.obs = observation()
        self.obs['t'] = 20
        self.target = enemy(70)
        other = dict(enemy(-70), id=8, aim=[0, 0])
        self.state = SimpleNamespace(cfg=copy.deepcopy(HELLO['config']),
            tracks={a['id']: {'actor': a, 'seen': 20} for a in (self.target, other)},
            attacker_memory={}, items={5000: ('cubes', {'pos': [0, -10, 0]}, 20)},
            hold=(0, 0, 500), body_size=(2.5, 9), action_deadline=time.perf_counter()+1)
        self.planner = TacticalPlanner(Arena())

    def test_crossfire_cover_wins_over_unreachable_cube(self):
        move = self.planner.choose(self.state, self.obs, self.target)
        self.assertIsNotNone(move)
        self.assertGreater(move[1], 0)

    def test_budget_exhaustion_uses_controller_fallback(self):
        self.state.action_deadline = time.perf_counter() - 1
        self.assertIsNone(self.planner.choose(self.state, self.obs, self.target))

    def test_incomplete_search_is_never_used(self):
        with patch('bot.tactical_planner.time.perf_counter', side_effect=[0, 0, 0, .005]):
            self.assertIsNone(self.planner.choose(self.state, self.obs, self.target))

    def test_no_recent_threat_uses_controller_fallback(self):
        self.obs['t'] = 22
        self.assertIsNone(self.planner.choose(self.state, self.obs, self.target))

    def test_controller_uses_planner_but_zone_emergency_preempts_it(self):
        with patch.dict('os.environ', {'BOT_TACTICAL_PLANNER': '1', 'BOT_POSITIONAL_FIELD': '0'}):
            bot = Controller(HELLO)
        bot.movement.stuck_since = -1
        self.obs['mechs'] = [self.target]
        combat = patch.object(bot, 'assess_combat', return_value=([self.target], self.target, self.target, True, False))
        combat.start()
        self.addCleanup(combat.stop)
        with patch.object(bot.tactical, 'choose', return_value=[0, 1]) as choose:
            bot.act(self.obs)
            self.assertEqual(bot.mode, 'tactical')
            choose.assert_called_once()
        self.obs['self']['in_zone'] = False
        self.obs['zone']['next_center'] = [150, 0]
        self.obs['zone']['next_radius'] = 30
        with patch.object(bot.tactical, 'choose', side_effect=AssertionError('zone must take priority')):
            with patch.object(bot.movement, 'navigate', return_value=[1, 0]):
                bot.act(self.obs)
                self.assertEqual(bot.mode, 'zone')
