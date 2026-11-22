import unittest
from unittest.mock import patch

from main import Bot
from test_bot import HELLO, observation


class PracticeRoutingTests(unittest.TestCase):
    def setUp(self):
        self.obs = observation()
        self.obs['offer'] = {'choices': [{'id': 'gun_mag'}, {'id': 'gun_damage'}]}
        with patch.dict('os.environ', {'BOT_PROFILE': 'adaptive'}):
            self.bot = Bot(HELLO)

    def test_first_tick_and_credited_kill_use_practice_upgrade_order(self):
        self.assertEqual(self.bot.act(self.obs)['pick'], 1)
        self.obs.update(t=.1, tick=2, alive=15, events=[{'type':'kill', 'target':8}])
        self.assertEqual(self.bot.act(self.obs)['pick'], 1)

    def test_unexplained_death_keeps_practice_policy(self):
        self.bot.act(self.obs)
        for i in range(1, 6):
            self.obs.update(t=i*.1, tick=2*i, alive=15)
            self.assertEqual(self.bot.act(self.obs)['pick'], 1)
        self.assertFalse(self.bot.strategy.ffa)
        self.obs.update(t=.6, tick=12, events=[{'type':'kill', 'target':8}])
        self.assertEqual(self.bot.act(self.obs)['pick'], 1)

    def test_integrated_policy_remains_practice_for_final_profile(self):
        with patch.dict('os.environ', {'BOT_PROFILE': 'final'}):
            bot = Bot(HELLO)
        for t in (0, 25):
            self.obs.update(t=t,tick=t*10)
            self.assertEqual(bot.act(self.obs)['pick'], 1)
            self.assertFalse(bot.strategy.ffa)
