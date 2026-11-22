"""Focused tests for the optional targeting and combat-safety candidates."""
import unittest
from unittest.mock import Mock, patch

from bot.combat import assess_combat, apply_weapon_control, opportunity_target, aim_and_fire, intercept
from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class TacticalCandidateTests(unittest.TestCase):
    def setUp(self):
        self.obs=observation(); self.obs.update(t=30,tick=300)
        self.bot=Controller(HELLO)

    def test_finish_selects_weak_attacker_but_does_not_cancel_retreat(self):
        first=dict(enemy(50),id=7,hp=300)
        weak=dict(enemy(100),id=8,hp=60)
        self.bot.target_id=7; self.bot.target_at=30
        self.bot.tracks={a['id']:{'actor':a,'seen':30,'los':True} for a in (first,weak)}
        self.bot.hits[8]=30
        with patch.dict('os.environ',{'BOT_TARGET_POLICY':'baseline'}):
            self.assertEqual(assess_combat(self.bot,self.obs,True,False,1)[1]['id'],7)
        with patch.dict('os.environ',{'BOT_TARGET_POLICY':'finish'}):
            self.assertEqual(assess_combat(self.bot,self.obs,True,False,1)[1]['id'],8)
            self.obs['self']['hp']=.4*self.obs['self']['max_hp']
            _,_,_,_,finishing=assess_combat(self.bot,self.obs,True,False,.4)
            self.assertTrue(self.bot.retreat)
            self.assertFalse(finishing)

    def test_opportunity_respects_danger_and_weapon_readiness(self):
        foe=dict(enemy(80),hp=100)
        self.bot.tracks={7:{'actor':foe,'seen':30,'los':True}}
        self.assertIs(opportunity_target(self.bot,self.obs,[foe],False,False,'loot'),foe)
        self.assertIsNone(opportunity_target(self.bot,self.obs,[foe],True,False,'loot'))
        self.assertIsNone(opportunity_target(self.bot,self.obs,[foe],False,True,'loot'))
        self.assertIsNone(opportunity_target(self.bot,self.obs,[foe,dict(enemy(90),id=8)],False,False,'loot'))
        self.obs['self']['weapons'][0]['reload']=1
        self.assertIsNone(opportunity_target(self.bot,self.obs,[foe],False,False,'loot'))

    def test_finish_and_retreat_switches_are_independent(self):
        first=dict(enemy(50),id=7,hp=300)
        weak=dict(enemy(100),id=8,hp=60)
        self.bot.tracks={a['id']:{'actor':a,'seen':30,'los':True} for a in (first,weak)}
        self.bot.hits[8]=30
        for finish,retreat,expected in [('off','off',7),('on','off',8),('off','on',7),('on','on',8)]:
            with self.subTest(finish=finish,retreat=retreat):
                self.bot.target_id=7; self.bot.target_at=30; self.bot.lose_at=-100
                self.bot.retreat=False
                with patch.dict('os.environ',{'BOT_TARGET_POLICY':'baseline','BOT_FINISH_PRIORITY':finish,'BOT_SAFE_RETREAT':retreat}):
                    target=assess_combat(self.bot,self.obs,True,False,.4)[1]
                    self.assertEqual(target['id'],expected)
                    self.assertEqual(self.bot.retreat,retreat=='on')

    def test_next_tick_aim_offsets_both_positions(self):
        me=self.obs['self']; me['vel']=[4,6,0]
        target=enemy(100); target['vel']=[-2,8,0]
        for timing,offset in [('current',0),('next_tick',.05)]:
            with self.subTest(timing=timing), patch.dict('os.environ',{'BOT_AIM_MODEL':'dev','BOT_GUN_TIMING':timing,'BOT_COVER_AIM':'off'}), patch('bot.combat.intercept',wraps=intercept) as spy:
                aim_and_fire(me,target,HELLO['config'])
                muzzle,center,_,_=spy.call_args.args
                self.assertAlmostEqual(muzzle[0],me['pos'][0]+4*offset)
                self.assertAlmostEqual(muzzle[1],me['pos'][1]+6*offset)
                self.assertAlmostEqual(center[0],target['pos'][0]-2*offset)
                self.assertAlmostEqual(center[1],target['pos'][1]+8*offset)

    def test_cover_reload_requires_time_and_cover(self):
        gun=self.obs['self']['weapons'][0]; gun.update(ammo=4,reload=0,stats=HELLO['config']['weapons']['gun'])
        foe=enemy(120); self.bot.tracks={7:{'actor':foe,'seen':30,'los':False}}
        self.bot.last_hurt=30; self.bot.world=Mock(); self.bot.world.shot_clear.return_value=False
        with patch.dict('os.environ',{'BOT_RELOAD_MODEL':'cover'}):
            action={'move':[0,0],'fire':[False,False]}
            apply_weapon_control(self.bot,self.obs,action,None,None,True)
            self.assertTrue(action.get('reload',False))
            foe['pos'][0]=60
            action={'move':[0,0],'fire':[False,False]}
            apply_weapon_control(self.bot,self.obs,action,None,None,True)
            self.assertFalse(action.get('reload',False))
            foe['pos'][0]=120; self.bot.world.shot_clear.return_value=True
            action={'move':[0,0],'fire':[False,False]}
            apply_weapon_control(self.bot,self.obs,action,None,None,True)
            self.assertFalse(action.get('reload',False))
