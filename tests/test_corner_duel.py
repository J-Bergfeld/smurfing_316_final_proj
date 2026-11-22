import math
import unittest
from unittest.mock import patch

from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class CornerArena:
    """Level ground with a wall along x=-35 north of y=2."""
    baked = None

    def __init__(self, wall=True):
        self.wall = wall

    def shot_clear(self, a, b):
        if not self.wall or (a[0] + 35) * (b[0] + 35) >= 0:
            return True
        fraction = (-35 - a[0]) / (b[0] - a[0])
        return a[1] + fraction * (b[1] - a[1]) < 2

    def cell(self, x, y): return (x, y)
    def free_cell(self, cell): return True
    def line_walkable(self, a, b): return self.shot_clear(a, b)
    def walk_at(self, x, y): return 0


class CornerDuelTests(unittest.TestCase):
    def setUp(self):
        self.obs = observation()
        self.obs.update(t=30, tick=300)
        second = dict(enemy(-70), id=8, aim=[0, 0])
        self.obs['mechs'] = [dict(enemy(70), hp=300), second]
        self.obs['cubes'] = [dict(id=5000, pos=[0, -10, 0])]
        self.map = CornerArena()

    def controller(self, enabled):
        with patch.dict('os.environ', {'BOT_CORNER_DUEL': str(int(enabled)),
                        'BOT_NAV_METHOD': 'legacy', 'BOT_SUPPLY_DROPS': '0',
                        'BOT_POSITIONAL_FIELD': '0', 'BOT_FINISH_APPROACH': '0'}):
            bot = Controller(HELLO)
        bot.world = bot.movement.world = self.map
        return bot

    def assert_champion_action(self):
        expected = self.controller(False).act(self.obs)
        bot = self.controller(True)
        self.assertEqual(bot.act(self.obs), expected)
        self.assertEqual(bot.mode, 'fight:cube')

    def test_one_hunter_and_open_ground_fall_back(self):
        self.map.wall = False
        self.assert_champion_action()
        self.map.wall = True
        self.obs['mechs'][1]['aim'] = [math.pi, 0]
        self.assert_champion_action()
        self.obs['mechs'].pop()
        self.assert_champion_action()

    def test_corner_blocks_second_hunter_and_preserves_shot(self):
        bot = self.controller(True)
        action = bot.act(self.obs)
        self.assertEqual(bot.mode, 'corner-duel')
        dx, dy = action['move']
        self.assertGreater(dy, 0)
        self.assertTrue(any(not self.map.shot_clear((-70, 0), (dx*r, dy*r)) and
                            self.map.shot_clear((dx*r, dy*r), (70, 0)) for r in (6, 12)))
        self.assertAlmostEqual(action['aim'][0], 0, places=2)

    def test_urgent_zone_preempts_corner(self):
        self.obs['zone'].update(next_center=[130, 0], next_radius=30)
        self.obs['self']['in_zone'] = False
        bot = self.controller(True)
        with patch.object(bot.movement, 'navigate', return_value=[1, 0]), \
             patch.object(bot.movement, 'isolate_hunter', side_effect=AssertionError):
            action = bot.act(self.obs)
        self.assertEqual(bot.mode, 'zone')
        self.assertEqual(action['move'], [1, 0])
