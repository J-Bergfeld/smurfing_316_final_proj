"""Mech Royale entrypoint. Set BOT_PROFILE=final for free-for-all policy."""
import math
import os
import mechfight
from bot.geometry import Map, distance
from bot.world import World
from bot.combat import Combat
from bot.strategy import Strategy
from bot.navigation import NavigationGraph
from bot.tactics import dodge


class Bot:
    name = 'botted-out'

    def __init__(self, hello):
        config = hello['config']; self.arena = Map(hello['map']['dir'])
        self.navigation = NavigationGraph(self.arena, config)
        self.world = World(config,self.arena); self.combat = Combat(config)
        self.strategy = Strategy(self.arena,self.combat,config,os.environ.get('BOT_PROFILE','practice'),self.navigation)

    def act(self, obs):
        self.world.update(obs); mode, enemy, urgent = self.strategy.choose(self.world)
        goal = self.strategy.goal_for(self.world,mode,enemy,urgent)
        action = self.strategy.movement(self.world,goal,urgent,mode,enemy)
        evasive = dodge(self.world)
        if evasive is not None:
            action['move'] = evasive
        action.update(self.strategy.inventory(self.world))
        target = enemy if enemy and (mode=='attack' or (mode=='flee' and distance(obs['self']['pos'],enemy['actor']['pos'])<110)) else None
        capturing = any(drop.get('lands_in',0)<=0 and distance(obs['self']['pos'],drop['pos']) < drop.get('radius',8) for drop in obs.get('drops', []))
        if mode=='loot' and target is None and not capturing and obs.get('crates') and obs['self']['hp'] >= .9*obs['self']['max_hp']:
            crate = min(obs['crates'],key=lambda x:distance(obs['self']['pos'],x['pos']))
            if distance(obs['self']['pos'],crate['pos']) < 100:
                target = {'actor':dict(crate,kind='crate',vel=[0,0,0]),'visible':True}
        combat = self.combat.action(self.world,target,mode); action.update(combat)
        if 'aim' not in action:
            # Scan toward the most likely threat, otherwise look in the direction of travel.
            if enemy:
                p=obs['self']['pos']; e=enemy['actor']['pos']; action['aim']=[math.atan2(e[1]-p[1],e[0]-p[0]),0]
            elif mode in ('flee','recover') and obs['t']-self.world.last_damage < 3 and self.world.last_damage_bearing is not None:
                action['aim']=[self.world.last_damage_bearing,0]
            elif action['move'] != [0,0]: action['aim']=[math.atan2(action['move'][1],action['move'][0]),0]
            else:
                # Sweep a full circle when holding still; vision follows torso yaw.
                action['aim']=[(obs['t'] * 0.6 + math.pi) % (2 * math.pi) - math.pi, 0]
        return action


if __name__ == '__main__':
    mechfight.run(Bot)
