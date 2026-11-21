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

    def test_commitment_and_emergency(self):
        o=observation(); self.world.update(o); self.strategy.choose(self.world)
        o['t']=.1; o['cubes']=[{'id':1,'pos':[10,0,0]}]; self.world.update(o)
        self.assertEqual(self.strategy.choose(self.world)[0],'hold')
        o['t']=.2; o['events']=[{'type':'damaged','amount':5,'weapon':'gun','bearing':0,'by':7}]; self.world.update(o)
        self.assertEqual(self.strategy.choose(self.world)[0],'flee')

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

    def test_retreat_returns_fire_at_range(self):
        o=observation(); e=enemy(150); o['mechs']=[e]
        o['self']['aim']=[0,math.atan2(-2.5,150)]
        w=o['self']['weapons'][0]
        w.update(kind='gun',ammo=12,reload=0,cooldown=0,stats=HELLO['config']['weapons']['gun'])
        self.world.update(o)
        action=self.combat.action(self.world,self.world.tracks[7],'flee')
        self.assertTrue(action['fire'][0])

    def test_retreat_boosts_only_under_pressure(self):
        o=observation(); o['mechs']=[enemy(150)]; self.world.update(o)
        track=self.world.tracks[7]
        action=self.strategy.movement(self.world,[-100,0,0],False,'flee',track)
        self.assertTrue(action['boost'])
        o['self']['energy']=30
        action=self.strategy.movement(self.world,[-100,0,0],False,'flee',track)
        self.assertFalse(action['boost'])
        o['self']['energy']=100
        action=self.strategy.movement(self.world,[-100,0,0],False,'hold',track)
        self.assertFalse(action['boost'])

    def test_route_replans_when_goal_changes_direction(self):
        o=observation(); self.world.update(o)
        first=self.strategy.movement(self.world,[100,0,0],False)
        self.assertGreater(first['move'][0],0)
        o['t']=.1; self.world.update(o)
        changed=self.strategy.movement(self.world,[-100,0,0],False,'flee')
        self.assertLess(changed['move'][0],0)

    def test_route_cache_survives_small_goal_changes(self):
        class CountingMap(OpenMap):
            calls=0
            def route(self,a,b,*args):
                self.calls += 1
                return b
        arena=CountingMap(); self.strategy=Strategy(arena,self.combat,HELLO['config'])
        o=observation(); self.world.update(o)
        self.strategy.movement(self.world,[100,0,0],False)
        o['t']=.1; self.world.update(o)
        self.strategy.movement(self.world,[105,0,0],False)
        self.assertEqual(arena.calls,1)

    def test_pickup_and_upgrade(self):
        o=observation(); o['self']['weapons']=[o['self']['weapons'][0],None]; o['pickups']=[{'id':8001,'kind':'laser','pos':[2,0,0]}]
        o['offer']={'choices':[{'id':'gun_velocity'},{'id':'armor'}]}; self.world.update(o)
        a=self.strategy.inventory(self.world); self.assertEqual(a['take'],8001); self.assertEqual(a['pick'],1)

    def test_real_map_queries(self):
        m=Map(HELLO['map']['dir']); self.assertTrue(math.isfinite(m.height(0,0)))
        self.assertTrue(m.blocked(10000,10000,0,9))
        p=m.prisms[0]; self.assertGreaterEqual(p['top'],p['base'])


if __name__=='__main__': unittest.main()
