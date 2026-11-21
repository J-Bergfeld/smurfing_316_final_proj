"""Layered navigation tests with a small synthetic solid building."""
import unittest
from bot.navigation import NavigationGraph
from test_bot import HELLO


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


if __name__ == '__main__': unittest.main()
