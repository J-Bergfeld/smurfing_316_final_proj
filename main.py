"""Mech Royale entrypoint. Set BOT_PROFILE=final for free-for-all policy."""
import math
import os
import mechfight
from bot.geometry import Map, distance
from bot.world import World
from bot.combat import Combat
from bot.strategy import Strategy


class Bot:
    name = 'botted-out'

    def __init__(self, hello):
        config = hello['config']; self.arena = Map(hello['map']['dir'])
        self.world = World(config,self.arena); self.combat = Combat(config)
        self.strategy = Strategy(self.arena,self.combat,config,os.environ.get('BOT_PROFILE','practice'))

    def act(self, obs):
        self.world.update(obs); mode, enemy, urgent = self.strategy.choose(self.world)
        goal = self.strategy.goal_for(self.world,mode,enemy,urgent)
        action = self.strategy.movement(self.world,goal,urgent,mode,enemy)
        action.update(self.strategy.inventory(self.world))
        target = enemy if enemy and mode in ('attack','flee') else None
        if mode=='loot' and target is None and obs.get('crates'):
            crate = min(obs['crates'],key=lambda x:distance(obs['self']['pos'],x['pos']))
            if distance(obs['self']['pos'],crate['pos']) < 100:
                target = {'actor':dict(crate,kind='crate',vel=[0,0,0]),'visible':True}
        combat = self.combat.action(self.world,target,mode); action.update(combat)
        if 'aim' not in action:
            # Scan toward the most likely threat, otherwise look in the direction of travel.
            if enemy:
                p=obs['self']['pos']; e=enemy['actor']['pos']; action['aim']=[math.atan2(e[1]-p[1],e[0]-p[0]),0]
            elif action['move'] != [0,0]: action['aim']=[math.atan2(action['move'][1],action['move'][0]),0]
        return action


if __name__ == '__main__':
    mechfight.run(Bot)
