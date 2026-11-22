import math
import random
import time
import unittest
from unittest.mock import patch

from bot.movement import Movement, escape_direction, predictive_dodge, surface_path
from bot.geometry import Arena


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

    def test_escape_increases_clearance_and_rejects_fully_blocked_path(self):
        class Wall(OpenWorld):
            def standable(self,x,y,z,radius,height): return x >= radius
        world=Wall(); me=mech(); me['pos'][0]=1
        direction=escape_direction(world,me,[20,0],time.perf_counter()+1)
        self.assertGreater(direction[0],.9)
        world.standable=lambda *args: False
        self.assertIsNone(escape_direction(world,me,[20,0],time.perf_counter()+1))

    def test_surface_path_and_energy_budget(self):
        class Ledge(OpenWorld):
            def walk_at(self,x,y): return 10 if x>=8 else 0
            def line_walkable(self,a,b): return not (a[0]<8<=b[0])
        world=Ledge(); me=mech()
        path=surface_path(world,me,[16,0],time.perf_counter()+1)
        self.assertIsNotNone(path)
        self.assertEqual(path[-1][2],10)
        me['energy']=20
        self.assertIsNone(surface_path(world,me,[16,0],time.perf_counter()+1))

    def test_overhead_obstruction_prevents_climb(self):
        class CoveredLedge(OpenWorld):
            def walk_at(self,x,y): return 10 if x>=8 else 0
            def line_walkable(self,a,b): return not (a[0]<8<=b[0])
            def standable(self,x,y,z,radius,height): return not (x<8 and z>2)
        self.assertIsNone(surface_path(CoveredLedge(),mech(),[16,0],time.perf_counter()+1))

    def test_surface_climb_commands_jump_then_jet(self):
        movement=Movement(OpenWorld(),{},random.Random(1)); me=mech()
        movement.surface_route=[(8,0,10)]; movement.surface_goal=[16,0]; movement.surface_at=0
        movement.action_deadline=time.perf_counter()+1
        self.assertGreater(movement.follow_surface(me,[16,0],.1)[0],0)
        self.assertTrue(movement.surface_action['jump'])
        me['grounded']=False; me['pos'][2]=3
        movement.follow_surface(me,[16,0],.2)
        self.assertTrue(movement.surface_action['boost'])

    def test_recorded_invalid_start_recovers_only_after_wait(self):
        world=Arena('arena'); me=mech()
        me['pos']=[82.15561428329133,-31.073427601942203,4.010000228881836]
        me['stats'].update(radius=3.25,height=11.7)
        world.set_body_size(3.25,11.7)
        movement=Movement(world,{},random.Random(1)); movement.vertical_allowed=True
        goal=[82.233783954831,-110.24609920299201]
        movement.action_deadline=time.perf_counter()+.05
        self.assertEqual(movement.failed_route(me,goal,0),[0.,0.])
        movement.action_deadline=1.
        with patch('bot.movement.time.perf_counter', return_value=0.):
            direction=movement.failed_route(me,goal,1.1)
        self.assertLess(direction[1],-.5)


if __name__ == '__main__':
    unittest.main()
