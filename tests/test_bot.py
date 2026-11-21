import copy
import gzip
import json
import math
import os
import unittest

from bot.combat import Combat, intercept, mortar_pitch
from bot.geometry import Map, angle_diff, distance
from bot.strategy import Strategy
from bot.world import World
from main import Bot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with gzip.open(os.path.join(ROOT, 'check/stream.jsonl.gz'), 'rt') as f:
    HELLO = json.loads(next(f))
    OBS = json.loads(next(f))
HELLO['map']['dir'] = os.path.join(ROOT, 'arena')


class OpenMap:
    def height(self,x,y): return 0
    def clear(self,a,b): return True
    def walkable(self,*args): return True
    def route(self,a,b,*args): return b


def observation():
    o=copy.deepcopy(OBS); o.update(t=0,alive=16,mechs=[],sounds=[],events=[],projectiles=[],cubes=[],pickups=[],crates=[],drops=[],offer=None)
    o['self'].update(pos=[0,0,0],vel=[0,0,0],aim=[0,0],hp=1400,max_hp=1400,energy=100,grounded=True,in_zone=True)
    o['zone'].update(center=[0,0],radius=500,next_center=[0,0],next_radius=400,shrink_start=60,shrink_end=110)
    return o


def enemy(x=100):
    return {'id':7,'kind':'mech','pos':[x,0,0],'vel':[0,0,0],'aim':[math.pi,0],'hp':1400,'max_hp':1400,'weapons':['gun']}


class BotTests(unittest.TestCase):
    def setUp(self):
        self.map=OpenMap(); self.world=World(HELLO['config'],self.map); self.combat=Combat(HELLO['config']); self.strategy=Strategy(self.map,self.combat,HELLO['config'])

    def test_intercept_and_angles(self):
        point=intercept([0,0,0],[100,0,0],[0,10,0],100)
        self.assertAlmostEqual(math.dist([0,0,0],point)/100,point[1]/10)
        self.assertAlmostEqual(angle_diff(-math.pi+.1,math.pi-.1),.2)
        self.assertIsNone(mortar_pitch([0,0,0],[1000,0,0],72,22))

    def test_enemy_memory_decays_and_expires(self):
        o=observation(); o['mechs']=[enemy()]; self.world.update(o)
        self.assertTrue(self.world.tracks[7]['visible'])
        o['mechs']=[]; o['t']=2; self.world.update(o)
        self.assertFalse(self.world.tracks[7]['visible']); self.assertLess(self.world.tracks[7]['confidence'],1)
        o['t']=10; self.world.update(o); self.assertNotIn(7,self.world.tracks)

    def test_loot_memory_survives_leaving_view_and_expires(self):
        o=observation(); o['pickups']=[{'id':8001,'kind':'laser','pos':[40,0,0]}]
        self.world.update(o)
        o['t']=3; o['pickups']=[]; self.world.update(o)
        self.assertIn(8001,self.world.loot)
        self.assertEqual(self.strategy.choose(self.world)[0],'loot')
        o['t']=94; self.world.update(o)
        self.assertNotIn(8001,self.world.loot)

    def test_loot_absence_nearby_clears_memory(self):
        o=observation(); o['cubes']=[{'id':5000,'pos':[2,0,0]}]; self.world.update(o)
        o['t']=.1; o['cubes']=[]; self.world.update(o)
        self.assertNotIn(5000,self.world.loot)

    def test_approaching_zone_edge_starts_rotation(self):
        o=observation(); o['t']=55; o['self']['pos']=[170,0,0]
        o['zone'].update(radius=200,next_radius=100,shrink_start=60,shrink_end=110)
        self.world.update(o)
        self.assertTrue(self.strategy.choose(self.world)[2])

    def test_stationary_combat_strafes_if_walkable(self):
        o=observation(); o['mechs']=[enemy(100)]; self.world.update(o)
        action=self.strategy.movement(self.world,[0,0,0],False,'attack',self.world.tracks[7])
        self.assertAlmostEqual(action['move'][0],0)
        self.assertGreater(abs(action['move'][1]),0)

    def test_commitment_and_emergency(self):
        o=observation(); self.world.update(o); self.strategy.choose(self.world)
        o['t']=.1; o['cubes']=[{'id':1,'pos':[10,0,0]}]; self.world.update(o)
        self.assertEqual(self.strategy.choose(self.world)[0],'hold')
        o['t']=.2; o['events']=[{'type':'damaged','amount':5,'weapon':'gun','bearing':0,'by':7}]; self.world.update(o)
        self.assertEqual(self.strategy.choose(self.world)[0],'flee')

    def test_first_observation_can_choose_loot(self):
        o=observation(); o['cubes']=[{'id':1,'pos':[10,0,0]}]
        self.world.update(o)
        self.assertEqual(self.strategy.choose(self.world)[0],'loot')

    def test_idle_scans_over_time(self):
        class StationaryStrategy:
            def choose(self,world): return 'hold',None,False
            def goal_for(self,*args): return [0,0,0]
            def movement(self,*args): return {'move':[0,0]}
            def inventory(self,*args): return {}
        bot=Bot.__new__(Bot); bot.world=self.world
        bot.strategy=StationaryStrategy(); bot.combat=self.combat
        o=observation(); first=bot.act(o)
        o['t']=2; second=bot.act(o)
        self.assertNotEqual(first['aim'][0],second['aim'][0])

    def test_zone_interrupt_and_progress(self):
        o=observation(); o['self']['pos']=[480,0,0]; o['self']['in_zone']=False; self.world.update(o)
        mode,e,urgent=self.strategy.choose(self.world); self.assertTrue(urgent)
        initial=distance(o['self']['pos'],o['zone']['next_center'])
        for i in range(30):
            o['t']=i*.1; self.world.update(o); goal=self.strategy.goal_for(self.world,mode,e,urgent); action=self.strategy.movement(self.world,goal,urgent)
            o['self']['pos'][0]+=action['move'][0]*1.17; o['self']['pos'][1]+=action['move'][1]*1.17
        self.assertLess(distance(o['self']['pos'],o['zone']['next_center']),initial-20)

    def test_gun_and_laser_release(self):
        o=observation(); e=enemy(60); o['mechs']=[e]; self.world.update(o)
        w=o['self']['weapons'][0]; w.update(kind='gun',ammo=12,reload=0,cooldown=0,stats=HELLO['config']['weapons']['gun'])
        a=self.combat.action(self.world,self.world.tracks[7],'attack'); self.assertTrue(a['fire'][0])
        laser={'kind':'laser','charge':.3,'cooldown':0,'stats':HELLO['config']['weapons']['laser']}; o['self']['weapons']=[laser,None]
        a=self.combat.action(self.world,self.world.tracks[7],'attack'); self.assertTrue(a['fire'][0])
        laser['charge']=.75; a=self.combat.action(self.world,self.world.tracks[7],'attack'); self.assertFalse(a['fire'][0])
        self.world.tracks[7]['visible']=False; self.assertFalse(self.combat.action(self.world,self.world.tracks[7],'attack')['fire'][0])

    def test_final_avoids_observed_fight(self):
        o=observation(); a=enemy(70); b=enemy(100); b['id']=8
        a['aim']=[0,0]; b['aim']=[math.pi,0]; o['mechs']=[a,b]
        self.world.update(o)
        final=Strategy(self.map,self.combat,HELLO['config'],profile='final')
        self.assertEqual(final.choose(self.world)[0],'flee')

    def test_reload_when_safe(self):
        o=observation(); w=o['self']['weapons'][0]
        w.update(kind='gun',ammo=2,reload=0,stats=HELLO['config']['weapons']['gun'])
        self.world.update(o)
        self.assertTrue(self.combat.action(self.world,None,'hold')['reload'])

    def test_pickup_and_upgrade(self):
        o=observation(); o['self']['weapons']=[o['self']['weapons'][0],None]; o['pickups']=[{'id':8001,'kind':'laser','pos':[2,0,0]}]
        o['offer']={'choices':[{'id':'gun_velocity'},{'id':'armor'}]}; self.world.update(o)
        a=self.strategy.inventory(self.world); self.assertEqual(a['take'],8001); self.assertEqual(a['pick'],1)

    def test_real_map_queries(self):
        m=Map(HELLO['map']['dir']); self.assertTrue(math.isfinite(m.height(0,0)))
        self.assertTrue(m.blocked(10000,10000,0,9))
        p=m.prisms[0]; self.assertGreaterEqual(p['top'],p['base'])

    def test_projectile_closest_approach(self):
        o=observation(); o['projectiles']=[{'id':1,'kind':'gun','pos':[60,0,4.5],'vel':[-100,0,0]}]
        self.world.update(o)
        self.assertGreater(self.world.projectile_risk([0,0,0]),0)
        self.assertEqual(self.world.projectile_risk([0,40,0]),0)
        o['projectiles'][0]['vel']=[100,0,0]; self.world.update(o)
        self.assertEqual(self.world.projectile_risk([0,0,0]),0)

    def test_reloading_prefers_cover(self):
        class CoverMap(OpenMap):
            def clear(self,a,b): return a[1] <= 10
        arena=CoverMap(); world=World(HELLO['config'],arena)
        strategy=Strategy(arena,self.combat,HELLO['config'])
        o=observation(); o['self']['weapons'][0]['reload']=2
        o['mechs']=[enemy(100)]; world.update(o)
        goal=strategy.goal_for(world,'attack',world.tracks[7],False)
        self.assertGreater(goal[1],10)
        o['t']=.1; o['self']['weapons'][0]['reload']=0; o['self']['weapons'][0]['ammo']=12
        world.update(o); strategy.goal_for(world,'attack',world.tracks[7],False)
        self.assertEqual(strategy.positioner.reloading,False)

    def test_goal_change_invalidates_cached_route(self):
        o=observation(); self.world.update(o)
        self.assertGreater(self.strategy.movement(self.world,[100,0,0],False)['move'][0],0)
        o['t']=.1; self.world.update(o)
        self.assertLess(self.strategy.movement(self.world,[-100,0,0],False)['move'][0],0)

    def test_roof_climb_uses_jump_and_jet(self):
        o=observation(); self.world.update(o)
        self.assertTrue(self.strategy.movement(self.world,[20,0,15],False)['jump'])
        o['t']=.1; o['self']['grounded']=False; o['self']['pos'][2]=2; self.world.update(o)
        self.assertTrue(self.strategy.movement(self.world,[20,0,15],False)['boost'])

    def test_mortar_solution_reaches_target_height(self):
        origin=[0,0,9.5]; target=[100,0,4.5]; speed=72; gravity=22
        pitch=mortar_pitch(origin,target,speed,gravity)
        t=100/(speed*math.cos(pitch))
        self.assertAlmostEqual(origin[2]+speed*math.sin(pitch)*t-gravity*t*t/2,target[2])


if __name__=='__main__': unittest.main()
