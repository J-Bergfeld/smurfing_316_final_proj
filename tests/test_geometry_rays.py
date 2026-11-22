"""Long-ray acceleration must preserve the exact collision decision."""
import math
import random
import unittest
from unittest.mock import patch

from bot.geometry import Arena, _ray_cells
from test_bot import HELLO


def rectangle_cells(a, b):
    for x in range(math.floor(min(a[0],b[0])/16), math.floor(max(a[0],b[0])/16)+1):
        for y in range(math.floor(min(a[1],b[1])/16), math.floor(max(a[1],b[1])/16)+1):
            yield x,y


class GeometryRayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = Arena(HELLO['map']['dir'])

    def test_grid_edge_and_corner_rays_complete(self):
        for a,b in [((0,0),(160,160)),((0,0),(-160,-160)),
                    ((0,0),(0,-160)),((16,32),(-16,48)),
                    ((0,0),(160,-160)),((16,16),(16,16))]:
            cells=list(_ray_cells(a,b))
            self.assertEqual(cells[0],(math.floor(a[0]/16),math.floor(a[1]/16)))
            self.assertEqual(cells[-1],(math.floor(b[0]/16),math.floor(b[1]/16)))
            self.assertLess(len(cells),100)

    def test_proximity_vision_accounts_for_trunks_but_shots_do_not(self):
        world = Arena.__new__(Arena)
        world.trunks = [(5., 0., 0., 10., 1.)]
        world.trunk_grid = {(0, 0): [0]}
        world.shot_clear = lambda a, b: True
        self.assertFalse(world.proximity_visible((0, 0, 5), (10, 0, 5)))
        self.assertTrue(world.proximity_visible((0, 0, 12), (10, 0, 12)))
        self.assertTrue(world.proximity_visible((0, 2, 5), (10, 2, 5)))
        world.shot_clear = lambda a, b: False
        self.assertFalse(world.proximity_visible((0, 2, 5), (10, 2, 5)))

    def test_canopy_blocks_distant_vision_but_not_proximity_sensors(self):
        world = Arena.__new__(Arena)
        world.proximity_visible = lambda a, b: True
        world.crowns = [(5., 0., 5., 3., 3.)]
        world.crown_grid = {(0, 0): [0]}
        world.canopy_limit = 4.
        self.assertFalse(world.vision_clear((0, 0, 5), (10, 0, 5)))
        self.assertTrue(world.vision_clear((0, 0, 5), (10, 0, 5), proximity=True))
        self.assertTrue(world.vision_clear((0, 4, 5), (10, 4, 5)))

    def test_exposure_hold_goal_is_walkable_and_inside_next_circle(self):
        zone={'next_center':[72.,-222.], 'next_radius':380.}
        pos=[182.,-168.,5.]
        goal=self.world.exposure_hold_goal(pos,zone)
        self.assertIsNotNone(goal)
        self.assertLess(math.dist(goal,zone['next_center']),zone['next_radius']-14)
        self.assertTrue(self.world.free_cell(self.world.cell(*goal)))

    def test_exposure_hold_falls_back_without_matching_navigation_cache(self):
        uncached=Arena(HELLO['map']['dir'],use_cache=False)
        self.assertIsNone(uncached.exposure_hold_goal([0,0,0],{'next_center':[0,0],'next_radius':100}))

    def test_exposure_hold_does_not_reuse_goal_outside_next_circle(self):
        zone={'next_center':[0.,0.], 'next_radius':100.}
        goal=self.world.exposure_hold_goal([0,0,0],zone,previous=(300.,300.),deadline=0)
        self.assertIsNone(goal)

    def test_real_map_matches_rectangle_broad_phase(self):
        rng=random.Random(8621)
        for i in range(600):
            x,y,x2,y2=(rng.uniform(-500,500) for _ in range(4))
            if i%5==0: x=16*round(x/16)
            if i%7==0: y2=16*round(y2/16)
            if i%11==0: x2=x
            if i%13==0: y2=y
            a=(x,y,rng.uniform(3,45)); b=(x2,y2,rng.uniform(3,45))
            result=self.world.shot_clear(a,b)
            with patch('bot.geometry._ray_cells',rectangle_cells):
                expected=self.world.shot_clear(a,b)
            self.assertEqual(result,expected,(a,b))

if __name__ == '__main__': unittest.main()
