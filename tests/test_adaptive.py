import math
import unittest

from test_bot import HELLO, OpenMap, enemy, observation
from bot.combat import Combat
from bot.strategy import Strategy
from bot.world import World


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.world = World(HELLO['config'], OpenMap())

    def test_field_inference_requires_distinct_observations(self):
        obs = observation()
        self.world.update(obs)
        obs['alive'] = 15
        for tick in range(1, 5):
            obs['tick'] = tick
            self.world.update(obs)
            self.world.update(obs)
        self.assertNotEqual(self.world.field, 'ffa')
        obs['tick'] = 5
        self.world.update(obs)
        self.assertEqual(self.world.field, 'ffa')

    def test_own_kill_does_not_imply_free_for_all(self):
        obs = observation()
        self.world.update(obs)
        obs.update(t=21, alive=15, events=[{'type': 'kill', 'target': 7}])
        for tick in range(1, 8):
            obs['tick'] = tick
            self.world.update(obs)
        self.assertEqual(self.world.field, 'squad')

    def test_heavy_damage_forces_retreat(self):
        obs = observation()
        obs['mechs'] = [enemy(70)]
        obs['events'] = [{'type': 'damaged', 'amount': 300, 'weapon': 'gun', 'by': 7, 'bearing': 0}]
        self.world.update(obs)
        strategy = Strategy(self.world.arena, Combat(HELLO['config']), HELLO['config'], 'adaptive')
        self.assertEqual(strategy.choose(self.world)[0], 'flee')

    def test_lost_laser_aims_high_before_release(self):
        obs = observation()
        obs['self']['weapons'] = [{'kind': 'laser', 'charge': .5, 'cooldown': 0,
                                    'stats': HELLO['config']['weapons']['laser']}, None]
        self.world.update(obs)
        action = Combat(HELLO['config']).action(self.world, None, 'flee')
        self.assertTrue(action['fire'][0])
        self.assertGreater(action['aim'][1], 1)
        obs['self']['aim'][1] = action['aim'][1]
        action = Combat(HELLO['config']).action(self.world, None, 'flee')
        self.assertFalse(action['fire'][0])

    def test_gun_does_not_fire_along_laser_aim_at_moving_target(self):
        obs = observation()
        foe = enemy(100)
        foe['vel'] = [0, 25, 0]
        obs['mechs'] = [foe]
        gun = obs['self']['weapons'][0]
        gun.update(kind='gun', ammo=12, reload=0, cooldown=0, stats=HELLO['config']['weapons']['gun'])
        obs['self']['weapons'] = [gun, {'kind': 'laser', 'charge': .7, 'cooldown': 0,
                                        'stats': HELLO['config']['weapons']['laser']}]
        obs['self']['aim'] = [0, math.atan2(-2.5, 100)]
        self.world.update(obs)
        action = Combat(HELLO['config']).action(self.world, self.world.tracks[7], 'attack')
        self.assertFalse(action['fire'][0])
