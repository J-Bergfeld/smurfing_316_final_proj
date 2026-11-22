import unittest
from unittest.mock import patch

from bot.combat import favorable_fight
from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class FavorableFightTests(unittest.TestCase):
    def setUp(self):
        self.bot = Controller(HELLO)
        self.obs = observation()
        self.obs['t'] = 10
        self.foe = enemy(100)
        self.foe['aim'] = [0, 0]  # facing away; not already engaged by baseline rules
        self.track = {'actor': self.foe, 'seen': 10, 'los': True}
        self.bot.tracks = {self.foe['id']: self.track}

    def test_favorable_fight_adds_target_in_practice(self):
        _, target, _, danger, _ = self.bot.assess_combat(self.obs, True, False, 1.)
        self.assertIs(target, self.foe)
        self.assertTrue(danger)
        _, target, _, _, _ = self.bot.assess_combat(self.obs, False, False, 1.)
        self.assertIsNone(target)

    def test_rejects_low_health_no_los_range_or_retreat(self):
        self.assertFalse(favorable_fight(self.bot, self.obs, self.track, .6))
        self.track['los'] = False
        self.assertFalse(favorable_fight(self.bot, self.obs, self.track, 1.))
        self.track['los'] = True
        self.foe['pos'][0] = 130
        self.assertFalse(favorable_fight(self.bot, self.obs, self.track, 1.))
        self.foe['pos'][0] = 100
        self.bot.retreat = True
        self.assertFalse(favorable_fight(self.bot, self.obs, self.track, 1.))

    def test_rejects_unready_gun_and_unfavorable_exchange(self):
        self.obs['self']['weapons'][0]['ammo'] = 0
        self.assertFalse(favorable_fight(self.bot, self.obs, self.track, 1.))
        self.obs['self']['weapons'][0]['ammo'] = 12
        with patch('bot.combat.Combat.estimate', return_value=1.29):
            self.assertFalse(favorable_fight(self.bot, self.obs, self.track, 1.))

    def test_recent_second_enemy_blocks_initiation(self):
        other = enemy(120)
        other.update(id=8, aim=[0, 0])
        self.bot.tracks[8] = {'actor': other, 'seen': 9, 'los': False}
        self.assertFalse(favorable_fight(self.bot, self.obs, self.track, 1.))
        self.bot.tracks[8]['seen'] = 7
        self.assertTrue(favorable_fight(self.bot, self.obs, self.track, 1.))

    def test_pressure_profile_accepts_marginal_exchange_but_respects_health(self):
        self.bot.pressure_policy = True
        with patch('bot.combat.Combat.estimate', return_value=.8):
            self.assertTrue(favorable_fight(self.bot, self.obs, self.track, 1.))
            self.assertFalse(favorable_fight(self.bot, self.obs, self.track, .6))
        self.bot.pressure_policy = False
        with patch('bot.combat.Combat.estimate', return_value=.8):
            self.assertFalse(favorable_fight(self.bot, self.obs, self.track, 1.))


if __name__ == '__main__':
    unittest.main()
