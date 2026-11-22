import unittest

from bot.lead_tracker import LeadTracker
from test_bot import enemy, observation


class LeadTrackerTests(unittest.TestCase):
    def test_learns_per_opponent_motion_without_unbounded_history(self):
        tracker = LeadTracker()
        me = observation()['self']
        walker = enemy(100)
        jitter = enemy(100)
        jitter['id'] = 8
        self.assertEqual(tracker.factor(walker), .45)
        for tick in range(100):
            now = tick * .1
            walker['pos'][1] = now * 10
            walker['vel'] = [0, 10, 0]
            jitter['vel'] = [0, 10 if tick % 2 else -10, 0]
            tracker.observe(walker, me, now)
            tracker.observe(jitter, me, now)
        self.assertEqual(tracker.factor(walker), 1.)
        self.assertEqual(tracker.factor(jitter), 0.)
        self.assertLessEqual(len(tracker.tracks[7]['samples']), 64)

    def test_missing_gun_and_npc_do_not_create_mech_history(self):
        tracker = LeadTracker()
        me = observation()['self']
        me['weapons'] = [None, None]
        tracker.observe(enemy(), me, 1.)
        self.assertEqual(tracker.tracks, {})
        self.assertEqual(tracker.factor({'kind': 'npc'}), 1.)
