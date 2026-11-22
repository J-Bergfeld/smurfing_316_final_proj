"""Layered navigation tests with a small synthetic solid building."""
import unittest
import random
import time
from unittest.mock import Mock
from bot.movement import Movement
from bot.geometry import Arena
from bot.navigation import NavigationGraph
from test_bot import HELLO, observation


class BuildingMap:
    bounds={'minX':-72,'maxX':96,'minY':-72,'maxY':72}
    @staticmethod
    def height(x,y): return 0
    @staticmethod
    def _inside(x,y): return 0 <= x <= 48 and -24 <= y <= 24
    def solids(self,x,y):
        return iter([{'top':20}] if self._inside(x,y) else [])
    def blocked(self,x,y,z,height=0): return self._inside(x,y) and z < 20 and z+height > 0
    def walkable(self,x,y,radius=2.5,height=9): return not self._inside(x,y)
    @staticmethod
    def clear(a,b): return True


class NavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.graph=NavigationGraph(BuildingMap(),HELLO['config'])

    def test_ground_route_goes_around_wall(self):
        path=self.graph.route([-48,0,0],[72,0,0],energy=0)
        self.assertIsNotNone(path)
        self.assertTrue(any(abs(point[1])>24 for point in path[:-1]))
        self.assertTrue(all(not BuildingMap._inside(*point[:2]) for point in path if point[2]<1))

    def test_roof_ascent_requires_energy(self):
        self.assertIsNone(self.graph.route([-24,0,0],[24,0,20],energy=10))
        path=self.graph.route([-24,0,0],[24,0,20],energy=100)
        self.assertIsNotNone(path)
        self.assertTrue(any(point[2]==20 for point in path))

    def test_roof_can_route_back_to_ground(self):
        path=self.graph.route([24,0,20],[-48,0,0],energy=0)
        self.assertIsNotNone(path)
        self.assertEqual(path[-1],[-48,0,0])

    def test_stuck_recovery_applies_to_routes_not_combat_strafing(self):
        world = Mock()
        world.line_walkable.return_value = True
        movement = Movement(world, HELLO['config'], random.Random(1))
        movement.avoid_projectiles = Mock(return_value=([0, 0], False))
        obs = {'t': 10., 'self': {'pos': [0, 0, 0], 'vel': [0, 0, 0],
                                  'grounded': True, 'energy': 100}}
        def act(mode, now):
            obs['t'] = now
            action = {'move': [1, 0], 'jump': False, 'boost': False}
            movement.apply_evasion_and_recovery(obs, action, mode)
            return action
        self.assertFalse(act('fight', 10)['jump'])
        self.assertFalse(act('fight', 12)['jump'])
        self.assertFalse(act('loot', 13)['jump'])
        self.assertTrue(act('loot', 14)['jump'])

    def test_elevated_navigation_does_not_use_ground_graph(self):
        world = Mock()
        world.walk_at.return_value = 0
        movement = Movement(world, HELLO['config'], random.Random(1))
        me = {'pos': [0, 0, 20], 'grounded': True}
        self.assertEqual(movement.navigate(me, [0, 20], 1), [0., 1.])
        world.path.assert_not_called()

    def test_pressure_strafe_moves_toward_a_distant_target(self):
        world = Mock()
        world.line_walkable.return_value = True
        world.walk_at.return_value = 0
        world.cell.side_effect = lambda x, y: (int(x), int(y))
        world.free_cell.return_value = True
        movement = Movement(world, HELLO['config'], random.Random(1))
        obs = observation(); obs['t'] = 1.
        vx, vy = movement.pressure_strafe(obs, {'pos': [100, 0, 0]})
        self.assertGreater(vx, 0.9)
        self.assertAlmostEqual(vx*vx + vy*vy, 1.)

    def test_pressure_steering_respects_an_obstructed_direction(self):
        world = Mock()
        world.walk_at.return_value = 0
        world.cell.side_effect = lambda x, y: (int(round(x)), int(round(y)))
        world.free_cell.side_effect = lambda cell: cell[0] < 1
        movement = Movement(world, HELLO['config'], random.Random(1))
        obs = observation()
        vx, vy = movement.pressure_steer(obs, (1., 0.))
        self.assertFalse(vx > .5 and abs(vy) < .1)

    def test_roof_plan_waits_for_clearance_then_jumps(self):
        movement = Movement(Arena(HELLO['map']['dir']), HELLO['config'], random.Random(1))
        obs = observation(); obs['t'] = 136.5
        obs['self']['pos'] = [196.99, 92.03, 5.08]
        movement.action_deadline = time.perf_counter() + .027
        waiting = movement.pressure_roof_step(obs, allow_climb=False)
        self.assertEqual(waiting['mode'], 'roof-wait')
        self.assertFalse(waiting['jump'])
        climbing = movement.pressure_roof_step(obs, allow_climb=True)
        self.assertEqual(climbing['mode'], 'roof-climb')
        self.assertTrue(climbing['jump'])
        self.assertGreater(climbing['move'][1], .9)


if __name__ == '__main__': unittest.main()
