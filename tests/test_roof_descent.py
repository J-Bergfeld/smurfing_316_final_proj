import random
import time
import unittest

from bot.movement import Movement


class RoofWorld:
    def __init__(self, landing=True):
        self.landing = landing

    def ground(self, x, y): return 0
    def inside(self, x, y): return abs(x) < 100 and abs(y) < 100
    def cell(self, x, y): return (round(x / 2), round(y / 2))
    def standable(self, x, y, z, radius, height): return True
    def free_cell(self, cell): return self.landing and cell[0] >= 2
    def walk_at(self, x, y): return 0 if x >= 4 else 20
    def line_walkable(self, a, b): return False


class RoofDescentTests(unittest.TestCase):
    def setUp(self):
        self.world = RoofWorld()
        self.movement = Movement(self.world, {}, random.Random(1))
        self.me = {'pos': [-3, 0, 20], 'vel': [0, 0, 0], 'grounded': True,
                   'stats': {'radius': 2.5, 'height': 9}}

    def navigate(self, t):
        self.movement.action_deadline = time.perf_counter() + .05
        return self.movement.navigate(self.me, [50, 0, 0], t)

    def test_descends_toward_ground_and_keeps_direction_in_air(self):
        self.assertGreater(self.navigate(0)[0], .9)
        self.me['grounded'] = False
        self.me['pos'] = [1, 0, 18]
        self.assertGreater(self.navigate(.2)[0], .9)

    def test_no_valid_landing_stops(self):
        self.world.landing = False
        self.assertEqual(self.navigate(0), [0., 0.])

    def test_landing_obstructed_during_fall_is_rejected(self):
        self.world.standable = lambda x, y, z, radius, height: z > 10
        self.assertEqual(self.navigate(0), [0., 0.])

    def test_stalled_exit_is_temporarily_banned(self):
        self.navigate(0)
        first = self.world.cell(*self.movement.roof_exit)
        self.navigate(1.6)
        self.assertGreater(self.movement.roof_exit_bans[first], 1.6)
        self.assertNotEqual(self.world.cell(*self.movement.roof_exit), first)

    def test_ground_navigation_is_unchanged(self):
        self.me['pos'][2] = 0
        self.world.line_walkable = lambda a, b: True
        self.movement.action_deadline = time.perf_counter() + .05
        self.assertEqual(self.movement.navigate(self.me, [30, 0, 0], 0), [1., 0.])
        self.assertFalse(self.movement.descending)


if __name__ == '__main__':
    unittest.main()
