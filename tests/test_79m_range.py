import time
import unittest
from unittest.mock import Mock

from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class GunRangeTests(unittest.TestCase):
    def test_squad_gun_closes_at_80m_only_while_seeking_a_shot(self):
        movement = Controller(HELLO).movement
        movement.world = Mock(baked=None)
        movement.world.line_walkable.return_value = True
        movement.world.free_cell.return_value = True
        movement.world.walk_at.return_value = 0
        movement.world.shot_clear.return_value = True
        movement.strafe_until = 100
        movement.action_deadline = time.perf_counter() + 10
        obs = observation()
        foe = enemy(80)
        tuned = movement.combat_move(obs, foe, [foe], True, 1, aggressive=True)
        baseline = movement.combat_move(obs, foe, [foe], True, 1)
        self.assertGreater(tuned[0], baseline[0])
        cover = movement.combat_move(obs, foe, [foe], True, -1)
        tuned_cover = movement.combat_move(obs, foe, [foe], True, -1, aggressive=True)
        self.assertEqual(cover, tuned_cover)


if __name__ == '__main__':
    unittest.main()
