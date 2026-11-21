"""Core controller behavior independent of local comparison materials."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot.controller import Controller
from bot.combat import aim_and_fire
from bot.loadout import choose_loadout
from test_bot import HELLO, enemy, observation


class ControllerTests(unittest.TestCase):
    def test_gun_respects_final_laser_aim(self):
        obs = observation()
        me = obs['self']
        foe = enemy(100)
        foe['vel'] = [0, 25, 0]
        me['weapons'][0].update(kind='gun', ammo=12, reload=0, cooldown=0,
                                stats=HELLO['config']['weapons']['gun'])
        me['weapons'][1] = {'kind': 'laser', 'charge': .7, 'cooldown': 0,
                            'stats': HELLO['config']['weapons']['laser']}
        me['aim'] = [0, 0]
        with patch.dict('os.environ', {'BOT_GUN_AIM_CHECK': 'legacy'}):
            self.assertTrue(aim_and_fire(me, foe, HELLO['config'])['fire'][0])
        with patch.dict('os.environ', {'BOT_GUN_AIM_CHECK': 'actual'}):
            self.assertFalse(aim_and_fire(me, foe, HELLO['config'])['fire'][0])

    def test_movement_shares_controller_world_and_random_generator(self):
        bot = Controller(HELLO)
        self.assertIs(bot.movement.world, bot.world)
        self.assertIs(bot.movement.rng, bot.rng)

    def test_assess_combat_selects_nearby_visible_threat(self):
        bot = Controller(HELLO)
        obs = observation()
        foe = enemy(30)
        bot.tracks[foe['id']] = {'actor': foe, 'seen': obs['t'], 'los': True}
        seen, target, pursuit, danger, finishing = bot.assess_combat(obs, False, False, 1.0)
        self.assertEqual(seen, [foe])
        self.assertIs(target, foe)
        self.assertIs(pursuit, foe)
        self.assertTrue(danger)
        self.assertFalse(finishing)

    def test_choose_objective_ranks_reachable_cube(self):
        bot = Controller(HELLO)
        obs = observation()
        bot.world = SimpleNamespace(ground=Mock(return_value=0), cell=Mock(return_value=(0, 0)),
                                    nearest_free=Mock(return_value=(0, 0)), baked=None)
        bot.hold = (*obs['zone']['center'], obs['zone']['radius'])
        item = {'id': 5000, 'pos': [30, 0, 0]}
        bot.items[item['id']] = ('cubes', item, obs['t'])
        self.assertEqual(bot.choose_objective(obs, 1.0, False, True)[0], item['id'])

    def test_pickup_and_unseen_attacker_memory(self):
        bot = Controller(HELLO)
        obs = observation()
        obs['mechs'] = []
        obs['events'] = [{'type': 'damaged', 'by': 987, 'weapon': 'gun', 'bearing': 0}]
        bot.update_world(obs)
        self.assertEqual(bot.attacker_memory[987], obs['t'])
        self.assertNotIn(987, bot.hits)
        pickup_obs = copy.deepcopy(obs)
        pickup_obs['pickups'] = [{'id': 12345, 'kind': 'laser', 'pos': obs['self']['pos'][:]}]
        pickup_obs['self']['weapons'][1] = None
        self.assertEqual(choose_loadout(pickup_obs, HELLO['config'])['take'], 12345)

    def test_farming_uses_movement_component(self):
        bot = Controller(HELLO)
        obs = observation()
        obs.update(t=21, tick=2)
        npc = enemy(40)
        npc.update(id=100, kind='npc')
        obs['mechs'] = [npc]
        bot.world = SimpleNamespace(shot_clear=Mock(return_value=True), ground=Mock(return_value=0),
                                    cell=Mock(return_value=(0, 0)), nearest_free=Mock(return_value=(0, 0)),
                                    baked=None)
        bot.movement = Mock()
        bot.movement.unstuck_until = 0
        bot.movement.avoid_shells.return_value = None
        bot.movement.combat_move.return_value = [0, 0]
        action = bot.act(obs)
        bot.movement.combat_move.assert_called_once()
        self.assertEqual(action['tick'], obs['tick'])


if __name__ == '__main__':
    unittest.main()
