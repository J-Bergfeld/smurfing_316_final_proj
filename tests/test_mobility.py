import time
import unittest

from bot.movement import predictive_dodge


class OpenWorld:
    def inside(self, x, y): return abs(x) < 100 and abs(y) < 100
    def line_walkable(self, a, b): return True
    def standable(self, x, y, z, radius, height): return True
    def walk_at(self, x, y): return 0


def mech():
    return {'pos':[0.,0.,0.], 'vel':[0.,0.,0.], 'grounded':True, 'energy':100,
            'stats':{'radius':2.5, 'height':9, 'walk_speed':11.7,
                     'ground_accel':58.5, 'jet_drain':15}}


class MobilityTests(unittest.TestCase):
    def test_predicts_crossing_projectile_and_keeps_heading_without_threat(self):
        world=OpenWorld(); me=mech(); deadline=time.perf_counter()+1
        self.assertIsNone(predictive_dodge(world,me,[],[1,0],False,deadline))
        shot={'kind':'gun','pos':[-40,0,4], 'vel':[100,0,0]}
        move=predictive_dodge(world,me,[shot],[1,0],False,deadline)
        self.assertIsNotNone(move)
        self.assertGreater(abs(move[1]),.5)


if __name__ == '__main__':
    unittest.main()
