"""Checks for the dev aiming model shared by the queued experiments."""
import unittest
from unittest.mock import Mock, patch

from bot.combat import aim_and_fire, aim_at, intercept, lead
from test_bot import HELLO, enemy, observation


class TeammateAimTests(unittest.TestCase):
    def setUp(self):
        self.me = observation()['self']
        self.foe = enemy(100)
        self.foe['vel'] = [0,10,0]
        self.me['weapons'][0].update(kind='gun',ammo=12,reload=0,cooldown=0,
                                      stats=HELLO['config']['weapons']['gun'])
        self.muzzle = (0,0,self.me['stats']['muzzle_height'])
        self.point = intercept(self.muzzle,[100,0,HELLO['config']['mech']['height']/2],
                               self.foe['vel'],self.me['weapons'][0]['stats']['speed'])
        self.me['aim'] = aim_at(self.muzzle,self.point)

    def test_intercept_and_predicted_path_blocking(self):
        world=Mock(); world.shot_clear.return_value=False
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertAlmostEqual(action['aim'][0],self.me['aim'][0])
        self.assertFalse(action['fire'][0])
        world.shot_clear.assert_called_once_with(self.muzzle,self.point)
        world.shot_clear.return_value=True
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev'}):
            self.assertTrue(aim_and_fire(self.me,self.foe,HELLO['config'],world=world)['fire'][0])

    def test_dev_model_uses_observed_muzzle_not_predicted_shooter_position(self):
        self.me['vel']=[0,25,0]
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'])
        self.assertAlmostEqual(action['aim'][0],self.me['aim'][0])
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'sam'}):
            previous=aim_and_fire(self.me,self.foe,HELLO['config'])
        self.assertNotAlmostEqual(previous['aim'][0],action['aim'][0])

    def test_no_gun_does_not_require_intercept(self):
        self.me['weapons'][0]=None
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'])
        self.assertFalse(action['fire'][0])

if __name__ == '__main__': unittest.main()
