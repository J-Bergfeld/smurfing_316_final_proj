import math
import unittest
from unittest.mock import patch

from bot.controller import Controller
from bot.positional_field import PositionalField
from test_bot import HELLO, enemy, observation
from test_corner_duel import CornerArena


class FieldArena(CornerArena):
    def __init__(self):
        super().__init__()
        self.block_north = False

    def line_walkable(self, a, b):
        return not (self.block_north and b[1] > 1)

    def shot_clear(self, a, b):
        # East hunter can shoot throughout. West hunter loses its line
        # immediately north, but only beyond ten metres to the south.
        return a[0] >= -50 or -10 < b[1] < 2

    def set_body_size(self, radius, height):
        self.block_north = radius > 3

    def path(self, start, goal, budget_s):
        return [], False


class FieldTests(unittest.TestCase):
    def setUp(self):
        with patch.dict('os.environ', {'BOT_POSITIONAL_FIELD':'1','BOT_CORNER_DUEL':'1'}):
            self.bot = Controller(HELLO)
        self.map = FieldArena()
        self.bot.world = self.bot.movement.world = self.map
        self.field = self.bot.field = PositionalField(self.map)
        self.obs = observation()
        self.obs.update(t=30, tick=300)
        self.bot.movement.stuck_since = -1
        self.obs['mechs'] = [dict(enemy(70),hp=300), dict(enemy(-70),id=8,aim=[0,0])]
        self.obs['cubes'] = [dict(id=5000,pos=[0,-12,0])]
        # Both endpoints allow the same shot. The southern one is closer and has loot.
        self.candidates = patch.object(self.field,'candidates',return_value=[(0,0),(0,-12),(0,18)])
        self.candidates.start()
        self.addCleanup(self.candidates.stop)

    def test_longer_sheltered_approach_beats_short_exposed_loot_route(self):
        action = self.bot.act(self.obs)
        self.assertEqual(self.bot.mode,'positional-field')
        self.assertEqual(action['move'],[0.,1.])
        self.assertEqual(self.field.breakdown['goal'],(0,18))
        self.assertEqual(self.field.breakdown['dual_exposure_s'],0)
        self.assertAlmostEqual(action['aim'][0],0.)

    def test_sound_alone_cannot_supply_second_hunter(self):
        second = self.obs['mechs'].pop()
        self.obs['sounds'] = [dict(kind='gun',bearing=math.pi,dist='mid',age=0.)]
        self.bot.act(self.obs)
        self.assertNotEqual(self.bot.mode,'positional-field')
        self.assertTrue(self.field.sounds)
        self.obs['mechs'].append(second)
        self.bot.act(self.obs)
        self.assertEqual(self.bot.mode,'positional-field')

    def test_visible_closing_second_hunter_activates_existing_field(self):
        self.obs['mechs'][0]['hp'] = 1000
        second=self.obs['mechs'][1]
        second['aim']=[math.pi,0]; second['vel']=[6,0,0]
        self.field.closing_hunter_field = False
        self.bot.act(self.obs)
        self.assertNotEqual(self.bot.mode,'positional-field')
        self.field.closing_hunter_field = True
        self.obs['t'] += .1
        action=self.bot.act(self.obs)
        self.assertEqual(self.bot.mode,'positional-field')
        self.assertEqual(self.field.breakdown['goal'],(0,18))
        self.assertAlmostEqual(action['aim'][0],0.)

    def test_closing_hunter_requires_visibility_range_and_relative_motion(self):
        self.field.closing_hunter_field=True
        first=dict(enemy(70),hp=1000)
        second=dict(enemy(-70),id=8,aim=[math.pi,0],vel=[6,0,0])
        self.bot.tracks={7:dict(actor=first,seen=30,los=True),8:dict(actor=second,seen=30,los=True)}
        _,active=self.field.hunters(self.bot,30,(0,0),7,(0,0),True)
        self.assertEqual(set(active),{7,8})
        self.bot.tracks[8]['seen']=29.9
        _,active=self.field.hunters(self.bot,30,(0,0),7,(0,0),True)
        self.assertEqual(active,[7])
        self.bot.tracks[8]['seen']=30; self.bot.tracks[8]['los']=False
        _,active=self.field.hunters(self.bot,30,(0,0),7,(0,0),True)
        self.assertEqual(active,[7])
        self.bot.tracks[8]['los']=True
        _,active=self.field.hunters(self.bot,30,(0,0),7,(5,0),True)
        self.assertEqual(active,[7])
        second['pos']=[-231,0,0]
        _,active=self.field.hunters(self.bot,30,(0,0),7,(0,0),True)
        self.assertEqual(active,[7])

    def test_closing_warning_cannot_displace_near_lethal_finish(self):
        self.field.closing_hunter_field=True
        self.obs['mechs'][1].update(aim=[math.pi,0],vel=[6,0,0])
        self.bot.act(self.obs)
        self.assertNotEqual(self.bot.mode,'positional-field')
        # The original two-hunter defense still applies at the same health.
        self.obs['mechs'][1]['aim']=[0,0]; self.obs['t'] += .1
        self.bot.act(self.obs)
        self.assertEqual(self.bot.mode,'positional-field')

    def test_cached_step_rechecked_and_growth_changes_route(self):
        self.bot.act(self.obs)
        self.obs['t'] += .1
        self.obs['self']['stats']['radius'] += 1
        self.bot.act(self.obs)
        self.assertEqual(self.field.breakdown['goal'],(0,-12))
        self.map.line_walkable = lambda a,b: False
        self.obs['t'] += .1
        self.bot.act(self.obs)
        self.assertNotEqual(self.bot.mode,'positional-field')

    def test_zone_preempts_cached_route(self):
        self.bot.act(self.obs)
        self.obs['self']['in_zone'] = False
        self.obs['zone'].update(next_center=[130,0],next_radius=30)
        with patch.object(self.field,'choose',side_effect=AssertionError), patch.object(self.bot.movement,'navigate',return_value=[1,0]):
            self.bot.act(self.obs)
        self.assertEqual(self.bot.mode,'zone')
        self.assertIsNone(self.field.key)
