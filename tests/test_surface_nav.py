import time
import unittest

from bot.surface_nav import SurfaceNavigator
from test_bot import observation


class SurfaceWorld:
    def inside(self,x,y): return -20<=x<=24 and -8<=y<=8
    def ground(self,x,y): return 0
    def solids(self,x,y): return [{'top':10}] if x>=8 else []
    def standable(self,x,y,z,radius,height): return True


class SurfaceNavigationTests(unittest.TestCase):
    def test_jet_climb_requires_energy_and_continues_in_air(self):
        nav=SurfaceNavigator(SurfaceWorld())
        obs=observation(); obs['self']['pos']=[4,0,0]
        goal=[16,0,10]
        obs['self']['energy']=10
        waiting=nav.step(obs,goal,time.perf_counter()+.1)
        self.assertEqual(waiting['move'],[0.,0.])
        self.assertFalse(waiting['jump'])
        obs['t']=2
        self.assertEqual(nav.step(obs,goal,time.perf_counter()+.1)['move'],[0.,0.])
        self.assertEqual(nav.banned,{})
        obs['self']['energy']=100
        self.assertTrue(nav.step(obs,goal,time.perf_counter()+.1)['jump'])
        obs['self']['grounded']=False
        self.assertTrue(nav.step(obs,goal,time.perf_counter()+.1)['boost'])

    def test_unclimbable_wall_and_deadline_return_no_path(self):
        nav=SurfaceNavigator(SurfaceWorld())
        self.assertEqual(nav.plan([4,0,0],[16,0],5,0,time.perf_counter()+.1),[])
        self.assertEqual(nav.plan([0,0,0],[16,0],40,0,0),[])
