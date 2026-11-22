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
