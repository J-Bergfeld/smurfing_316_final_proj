"""Checks for the dev aiming model shared by the queued experiments."""
import unittest
from array import array
from unittest.mock import Mock, patch

from bot.combat import aim_and_fire, aim_at, intercept, lead
from bot.geometry import Arena
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

    def test_partial_cover_uses_clear_upper_body_and_preserves_clear_center(self):
        # A finite-height wall blocks the ray to the chest but leaves an
        # opening to the upper body. Exercise the real arena ray geometry.
        world = Arena.__new__(Arena)
        world.terrain = {'minX': -10, 'minY': -20, 'nx': 130, 'ny': 41,
                         'step': 1, 'scale': .01}
        world.heights = array('h', [0]) * (130 * 41)
        world._block_max = {}
        wall = {'box': (90, -4, 92, 4), 'base': 0, 'top': 6,
                'ring': [90, -4, 92, -4, 92, 4, 90, 4], 'holes': []}
        world.prisms = [wall]
        world.grid = {(5, -1): [0], (5, 0): [0]}
        self.foe['vel'] = [0, 0, 0]
        height = HELLO['config']['mech']['height']
        center = [100, 0, height * .5]
        upper = [100, 0, height * .8]
        self.assertFalse(world.shot_clear(self.muzzle, center))
        self.assertTrue(world.shot_clear(self.muzzle, upper))
        self.me['aim'] = aim_at(self.muzzle, upper)
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action = aim_and_fire(self.me, self.foe, HELLO['config'], world=world)
        self.assertAlmostEqual(action['aim'][1], self.me['aim'][1])
        self.assertTrue(action['fire'][0])

        # When the center is open, no alternate point changes baseline aim.
        world.prisms = []; world.grid = {}
        self.me['aim'] = aim_at(self.muzzle, center)
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            actual = aim_and_fire(self.me, self.foe, HELLO['config'], world=world)
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'0'}):
            baseline = aim_and_fire(self.me, self.foe, HELLO['config'], world=world)
        self.assertEqual(actual, baseline)

    def test_partial_cover_rejects_blocked_upper_and_narrows_pitch(self):
        world=Mock(); height=HELLO['config']['mech']['height']
        self.foe['vel']=[0,0,0]
        upper=[100,0,height*.8]
        world.shot_clear.side_effect=lambda origin,point: point[2] > height*.7
        # Aim too high: the original center tolerance could accept this, but
        # the upper-body fallback must not fire above the target cylinder.
        self.me['aim']=aim_at(self.muzzle,upper)
        self.me['aim'][1]+=.30
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertFalse(action['fire'][0])
        world.shot_clear.return_value=False; world.shot_clear.side_effect=None
        self.me['aim']=aim_at(self.muzzle,upper)
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertFalse(action['fire'][0])

    def test_partial_cover_respects_shared_laser_aim_and_reload(self):
        world=Mock(); height=HELLO['config']['mech']['height']
        self.foe['vel']=[0,0,0]
        world.shot_clear.side_effect=lambda origin,point: point[2] > height*.7
        self.me['weapons'][1]={'kind':'laser','charge':.75,'cooldown':0,
                               'stats':HELLO['config']['weapons']['laser']}
        self.me['aim']=aim_at(self.muzzle,[100,0,height*.5])
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_AIM_CHECK':'actual', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertFalse(action['fire'][0])
        self.me['weapons'][0]['reload']=1
        world.shot_clear.reset_mock()
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertFalse(action['fire'][0])
        world.shot_clear.assert_not_called()

    def test_partial_cover_can_aim_while_gun_is_cooling(self):
        self.foe['vel']=[0,0,0]
        height=HELLO['config']['mech']['height']
        world=Mock()
        world.shot_clear.side_effect=lambda origin,point: point[2] > height*.7
        self.me['weapons'][0]['cooldown']=.5
        self.me['aim']=aim_at(self.muzzle,[100,0,height*.8])
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertAlmostEqual(action['aim'][1],self.me['aim'][1])

    def test_partial_cover_uses_conservative_pitch_bounds_at_steep_elevation(self):
        self.foe['pos']=[20,0,30]; self.foe['vel']=[0,0,0]
        height=HELLO['config']['mech']['height']
        upper=[20,0,30+height*.8]
        upper_aim=aim_at(self.muzzle,upper)
        world=Mock()
        world.shot_clear.side_effect=lambda origin,point: point[2] > 30+height*.7
        # After one pitch step, this ray remains .035 radians above the upper
        # point. At this elevation it passes above the target's top; the
        # flat-angle approximation used to allow it.
        self.me['aim']=[upper_aim[0],upper_aim[1]+.035+self.me['stats']['pitch_rate']*.05]
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertFalse(action['fire'][0])
        self.me['aim']=upper_aim
        with patch.dict('os.environ', {'BOT_AIM_MODEL':'dev', 'BOT_GUN_PARTIAL_COVER':'1'}):
            action=aim_and_fire(self.me,self.foe,HELLO['config'],world=world)
        self.assertTrue(action['fire'][0])

if __name__ == '__main__': unittest.main()
