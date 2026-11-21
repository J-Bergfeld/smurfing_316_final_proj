import math
import unittest

from sim.physics import accelerate, future_circle, projectile, regen, turn


class PhysicsTests(unittest.TestCase):
    def test_acceleration_and_clamped_input(self):
        self.assertAlmostEqual(accelerate((0, 0), (2, 0), 11.7, 58.5, .1)[0], 5.85)
        self.assertAlmostEqual(accelerate((11.7, 0), (2, 0), 11.7, 58.5, .1)[0], 11.7)

    def test_yaw_uses_shortest_rotation(self):
        yaw, _ = turn([math.pi-.1, 0], [-math.pi+.1, 0], 4, 3, .1)
        self.assertAlmostEqual(yaw, -math.pi+.1)

    def test_current_circle_is_not_interpolated_twice(self):
        zone = {'center':[5, 0], 'radius':75, 'next_center':[10, 0], 'next_radius':50,
                'shrink_start':0, 'shrink_end':100}
        self.assertEqual(future_circle(zone, 50, 0), ((5., 0.), 75.))
        self.assertEqual(future_circle(zone, 50, 25), ((7.5, 0.), 62.5))

    def test_projectile_and_healing(self):
        self.assertEqual(projectile([0,0,0], [10,0,11], 22, 1), [10,0,0])
        self.assertAlmostEqual(regen(100, 200, 5.05, 5, 45, .1), 102.25)
        self.assertEqual(regen(100, 200, 6, 5, 45, .1, False), 100)
