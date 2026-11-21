"""Small closed-loop scenarios, deliberately not a copy of the game engine."""
import math
import unittest
from test_bot import HELLO, OpenMap, observation
from bot.world import World
from bot.combat import Combat
from bot.strategy import Strategy
from main import Bot


class Scenario:
    def __init__(self):
        arena=OpenMap(); self.obs=observation()
        self.bot=Bot.__new__(Bot); self.bot.world=World(HELLO['config'],arena)
        self.bot.combat=Combat(HELLO['config'])
        self.bot.strategy=Strategy(arena,self.bot.combat,HELLO['config'])

    def step(self):
        o=self.obs; action=self.bot.act(o); me=o['self']; dt=.1
        speed=me['stats'].get('walk_speed',11.7)
        me['pos'][0] += action.get('move',[0,0])[0]*speed*dt
        me['pos'][1] += action.get('move',[0,0])[1]*speed*dt
        if 'aim' in action: me['aim']=action['aim'][:]
        o['t'] += dt; o['tick'] += 2
        o['events']=[]
        return action


class ClosedLoopTests(unittest.TestCase):
    def test_bot_moves_to_visible_cube(self):
        s=Scenario(); s.obs['cubes']=[{'id':5000,'pos':[35,0,0]}]
        for _ in range(60):
            s.step()
            if math.dist(s.obs['self']['pos'][:2],[35,0]) < 3.5: break
        self.assertLess(math.dist(s.obs['self']['pos'][:2],[35,0]),3.5)

    def test_zone_escape_makes_progress(self):
        s=Scenario(); s.obs['self']['pos']=[480,0,0]; s.obs['self']['in_zone']=False
        for _ in range(40): s.step()
        self.assertLess(s.obs['self']['pos'][0],440)

    def test_damage_interrupts_loot(self):
        s=Scenario(); s.obs['cubes']=[{'id':5000,'pos':[50,0,0]}]
        s.step(); self.assertEqual(s.bot.strategy.mode,'loot')
        s.obs['events']=[{'type':'damaged','amount':50,'weapon':'gun','bearing':0,'by':7}]
        s.step(); self.assertEqual(s.bot.strategy.mode,'flee')


if __name__=='__main__': unittest.main()
