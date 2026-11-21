"""Mech Royale entrypoint. Set BOT_PROFILE=final for free-for-all policy."""
import math
import os
import mechfight
from bot.geometry import Map, distance
from bot.world import World
from bot.combat import Combat
from bot.strategy import Strategy
from bot.controller import Controller
from bot.navigation import NavigationGraph
from bot.tactics import dodge, blend_dodge


class Bot:
    name = 'botted-out'

    def __init__(self, hello):
        self.integrated_policy = os.environ.get('BOT_POLICY', 'integrated') != 'legacy'
        if self.integrated_policy:
            self.strategy = Controller(hello)
            return
        config = hello['config']; self.arena = Map(hello['map']['dir'])
        self.navigation = NavigationGraph(self.arena, config)
        self.world = World(config,self.arena); self.combat = Combat(config)
        self.strategy = Strategy(self.arena,self.combat,config,os.environ.get('BOT_PROFILE','adaptive'),self.navigation)

    def act(self, obs):
        if getattr(self, 'integrated_policy', False):
            return self.strategy.act(obs)
        self.world.update(obs); mode, enemy, urgent = self.strategy.choose(self.world)
        goal = self.strategy.goal_for(self.world,mode,enemy,urgent)
        action = self.strategy.movement(self.world,goal,urgent,mode,enemy)
        evasive = dodge(self.world)
        if evasive is not None:
            action['move'] = blend_dodge(self.world, action['move'], evasive, urgent)
        if hasattr(self.strategy, 'motion'):
            self.strategy.motion.record(action['move'])
        action.update(self.strategy.inventory(self.world))
        target = enemy if enemy and (mode=='attack' or (mode=='flee' and distance(obs['self']['pos'],enemy['actor']['pos'])<110)) else None
        capturing = any(drop.get('lands_in',0)<=0 and distance(obs['self']['pos'],drop['pos']) < drop.get('radius',8) for drop in obs.get('drops', []))
        farm_health = .5 if getattr(self.strategy,'practice_economy',False) and self.world.field == 'squad' else .7
        if mode=='loot' and target is None and not capturing and obs['self']['hp'] >= farm_health*obs['self']['max_hp']:
            p=obs['self']['pos']; origin=[p[0],p[1],p[2]+obs['self'].get('stats',{}).get('muzzle_height',7)]
            farm = [dict(crate,kind='crate',vel=[0,0,0]) for crate in obs.get('crates', [])]
            farm += [actor for actor in obs.get('mechs', []) if actor.get('kind')=='npc']
            farm = [actor for actor in farm if distance(p,actor['pos']) < (75 if actor['kind']=='npc' else 60)
                    and self.world.arena.clear(origin,[actor['pos'][0],actor['pos'][1],actor['pos'][2]+(1.75 if actor['kind']=='npc' else 1.2)])]
            if farm:
                target={'actor':min(farm,key=lambda actor:distance(p,actor['pos'])),'visible':True}
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
