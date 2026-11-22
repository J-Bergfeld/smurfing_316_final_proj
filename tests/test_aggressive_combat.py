import unittest
import time
from unittest.mock import Mock, patch

from bot.controller import Controller
from test_bot import HELLO, enemy, observation


class AggressiveCombatTests(unittest.TestCase):
    def setUp(self):
        self.bot = Controller(HELLO)
        self.obs = observation()
        self.obs['t'] = 10

    def track(self, actor, los=True):
        self.bot.tracks[actor['id']] = {'actor': actor, 'seen': self.obs['t'], 'los': los}

    def test_switches_from_healthy_target_to_vulnerable_enemy(self):
        healthy = enemy(70)
        weak = enemy(150); weak.update(id=8, hp=300, aim=[0, 0])
        self.track(healthy); self.track(weak)
        self.bot.target_id = healthy['id']; self.bot.target_at = 9.9
        self.assertIs(self.bot.assess_combat(self.obs, True, False, 1)[1], weak)

    def test_does_not_target_obscured_weak_enemy(self):
        healthy = enemy(70)
        weak = enemy(150); weak.update(id=8, hp=300)
        self.track(healthy); self.track(weak, los=False)
        self.assertIs(self.bot.assess_combat(self.obs, True, False, 1)[1], healthy)

    def test_retreat_starts_earlier_and_persists_after_threat_leaves(self):
        first = enemy(80); second = enemy(100); second['id'] = 8
        self.track(first); self.track(second)
        self.bot.assess_combat(self.obs, True, False, .6)
        self.assertTrue(self.bot.retreat)
        self.bot.tracks.clear(); self.obs['t'] = 12
        self.bot.assess_combat(self.obs, True, False, .6)
        self.assertTrue(self.bot.retreat)
        self.obs['t'] = 13.1
        self.bot.assess_combat(self.obs, True, False, .6)
        self.assertFalse(self.bot.retreat)

    def test_finishable_enemy_can_cancel_losing_condition(self):
        foe = enemy(80); foe['hp'] = 200
        other = enemy(100); other['id'] = 8
        self.track(foe); self.track(other)
        self.bot.assess_combat(self.obs, True, False, .4)
        self.assertFalse(self.bot.retreat)

    def test_retreat_takes_priority_over_offensive_planners(self):
        obs = self.obs; obs['tick'] = 200
        foe = enemy(80)
        self.bot.update_world = Mock()
        self.bot.assess_combat = Mock(return_value=([foe], foe, foe, True, False))
        self.bot.retreat = True
        self.bot.field = Mock(); self.bot.corner_duel = True
        self.bot.movement.avoid_shells = Mock(return_value=None)
        self.bot.movement.seek_cover = Mock(return_value=[-1, 0])
        self.bot.movement.isolate_hunter = Mock()
        self.bot.hold = (*obs['zone']['center'], obs['zone']['radius'])
        with patch('bot.controller.apply_weapon_control'):
            self.bot.act(obs)
        self.assertEqual(self.bot.mode, 'cover')
        self.bot.field.choose.assert_not_called()
        self.bot.movement.isolate_hunter.assert_not_called()

    def test_gun_range_tuning_closes_slightly_only_while_seeking_shot(self):
        movement = self.bot.movement
        movement.world = Mock(baked=None)
        movement.world.line_walkable.return_value = True
        movement.world.free_cell.return_value = True
        movement.world.walk_at.return_value = 0
        movement.world.shot_clear.return_value = True
        movement.strafe_until = 100
        movement.action_deadline = time.perf_counter() + 10
        foe = enemy(83)
        baseline = movement.combat_move(self.obs, foe, [foe], True, 1)
        tuned = movement.combat_move(self.obs, foe, [foe], True, 1, aggressive=True)
        self.assertGreater(tuned[0], baseline[0])
        hidden = movement.combat_move(self.obs, foe, [foe], True, -1)
        tuned_hidden = movement.combat_move(self.obs, foe, [foe], True, -1, aggressive=True)
        self.assertEqual(hidden, tuned_hidden)


if __name__ == '__main__':
    unittest.main()
