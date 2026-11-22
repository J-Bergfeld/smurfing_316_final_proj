import unittest
from unittest.mock import patch

from bot.controller import Controller
from test_bot import HELLO, enemy, observation
from test_positional_field import FieldArena


@unittest.skip('Finish-approach experiment is not present in this branch')
class FinishApproachTests(unittest.TestCase):
    def act(self, obs, enabled=True):
        with patch.dict('os.environ', {'BOT_FINISH_APPROACH': str(int(enabled)), 'BOT_NAV_METHOD': 'legacy',
                                      'BOT_POSITIONAL_FIELD': '1', 'BOT_CORNER_DUEL': '1'}):
            bot = Controller(HELLO)
        # Give both sides of the policy comparison the same random draws.
        bot.practice_rng = bot.rng
        bot.world = bot.movement.world = bot.field.world = FieldArena()
        bot.movement.stuck_since = -1
        action = bot.act(obs)
        return bot.mode, action

    def setUp(self):
        self.obs = observation()
        self.obs.update(t=30, tick=300)
        self.obs['mechs'] = [dict(enemy(70), hp=350)]

    def test_closes_on_isolated_wounded_mech(self):
        _, baseline = self.act(self.obs, enabled=False)
        mode, action = self.act(self.obs)
        self.assertEqual(mode, 'finish')
        self.assertGreater(baseline['move'][0], 0)
        self.assertGreater(action['move'][0], 0)
        self.assertEqual(action['aim'], baseline['aim'])

    def test_finish_ignores_combat_cube(self):
        self.obs['cubes'] = [dict(id=5000,pos=[-10,0,0])]
        self.assertEqual(self.act(self.obs, enabled=False)[0], 'fight:cube')
        mode, action = self.act(self.obs)
        self.assertEqual(mode, 'finish')
        self.assertGreater(action['move'][0], 0)

    def test_falls_back_under_pressure_or_without_gun(self):
        for condition in ('second_mech', 'low_health', 'reload', 'lightning', 'mortar', 'healthy_target'):
            with self.subTest(condition=condition):
                obs = observation()
                obs.update(t=30,tick=300)
                target = dict(enemy(70),hp=350)
                obs['mechs'] = [target]
                if condition == 'second_mech':
                    obs['mechs'].append(dict(enemy(150),id=8))
                elif condition == 'low_health':
                    obs['self']['hp'] = 750
                elif condition == 'reload':
                    obs['self']['weapons'][0].update(ammo=0,reload=1.5)
                elif condition == 'healthy_target':
                    target['hp'] = 800
                else:
                    target['weapons'].append(condition)
                self.assertEqual(self.act(obs), self.act(obs, enabled=False))
