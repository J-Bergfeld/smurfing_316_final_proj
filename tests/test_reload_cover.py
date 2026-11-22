import math
import unittest
from unittest.mock import patch

from bot.controller import Controller
from test_bot import HELLO, enemy, observation
from test_positional_field import FieldArena


@unittest.skip('Reload-cover experiment is not present in this branch')
class ReloadCoverTests(unittest.TestCase):
    def setUp(self):
        with patch.dict('os.environ', {'BOT_RELOAD_COVER': '1', 'BOT_POSITIONAL_FIELD': '1',
                                      'BOT_CORNER_DUEL': '1', 'BOT_NAV_METHOD': 'legacy'}):
            self.bot = Controller(HELLO)
        self.bot.world = self.bot.movement.world = self.bot.field.world = FieldArena()
        self.bot.movement.stuck_since = -1
        self.obs = observation()
        self.obs.update(t=30, tick=300)
        self.obs['mechs'] = [dict(enemy(-70), aim=[0, 0])]
        self.gun = self.obs['self']['weapons'][0]
        self.gun.update(ammo=0, reload=2)

    def test_take_hold_and_leave_cover(self):
        action = self.bot.act(self.obs)
        self.assertEqual(self.bot.mode, 'reload-cover')
        self.assertGreater(action['move'][1], 0)
        _, _, shelter = self.bot.reload_peek
        self.obs['self']['pos'] = [*shelter, 0]
        self.obs['mechs'] = []
        self.obs['t'] += .4
        action = self.bot.act(self.obs)
        self.assertEqual(action['move'], [0, 0])
        self.assertGreater(abs(action['aim'][0]), math.pi / 2)
        self.gun.update(ammo=12, reload=0)
        self.obs['t'] += .1
        self.assertLess(self.bot.act(self.obs)['move'][1], 0)

    def test_short_reload_skips_cover(self):
        self.gun['reload'] = .1
        self.bot.act(self.obs)
        self.assertNotEqual(self.bot.mode, 'reload-cover')

    def test_no_cover_falls_back(self):
        self.bot.world.shot_clear = lambda a, b: True
        self.bot.act(self.obs)
        self.assertNotEqual(self.bot.mode, 'reload-cover')
