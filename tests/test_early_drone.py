"""Opening farm preference is opt-in and yields to actual danger."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot.loadout import choose_objective
from test_bot import HELLO, observation, enemy


class EarlyDroneTests(unittest.TestCase):
    def setUp(self):
        self.obs=observation(); self.obs.update(t=30, alive=16)
        drone={'id':101,'kind':'npc','pos':[45,0,0],'hp':350,'vel':[0,0,0]}
        cube={'id':5000,'pos':[25,0,0]}
        world=SimpleNamespace(ground=Mock(return_value=0),cell=Mock(return_value=(0,0)),
            nearest_free=Mock(return_value=(0,0)),baked=None,line_walkable=Mock(return_value=True))
        self.state=SimpleNamespace(items={5000:('cubes',cube,30)},
            tracks={101:{'actor':drone,'seen':30}},cfg=HELLO['config'],world=world,
            bad={},loot_id=None,hold=(0,0,500),supply_drops=False,slot=0,
            laser_rush=False,ffa=False,farming_policy='legacy')

    def choice(self, enabled, danger=False):
        with patch.dict('os.environ', {'BOT_EARLY_DRONE':enabled}):
            return choose_objective(self.state,self.obs,1.,danger,True)

    def test_opt_in_prefers_near_reachable_drone(self):
        self.assertEqual(self.choice('0')[1], 'cubes')
        self.assertEqual(self.choice('1')[1], 'npc')

    def test_blocked_route_keeps_baseline_priority(self):
        self.state.world.line_walkable.return_value=False
        self.assertEqual(self.choice('1')[1], 'cubes')

    def test_visible_enemy_cancels_opening_preference(self):
        self.state.tracks[7]={'actor':enemy(90),'seen':30}
        self.assertEqual(self.choice('1')[1], 'cubes')

    def test_stale_drone_and_later_game_keep_baseline_priority(self):
        self.state.tracks[101]['seen']=28
        self.assertEqual(self.choice('1')[1], 'cubes')
        self.state.tracks[101]['seen']=61; self.obs['t']=61
        self.assertEqual(self.choice('1')[1], 'cubes')

    def test_active_danger_prevents_npc_objective(self):
        self.assertEqual(self.choice('1',danger=True)[1], 'cubes')

    def test_distant_drone_is_not_prioritized(self):
        self.state.tracks[101]['actor']['pos'] = [85,0,0]
        self.assertEqual(self.choice('1')[1], 'cubes')

    def test_low_health_preserves_baseline_preference(self):
        with patch.dict('os.environ', {'BOT_EARLY_DRONE':'1'}):
            selected = choose_objective(self.state,self.obs,.7,False,True)
        self.assertEqual(selected[1], 'cubes')

if __name__ == '__main__': unittest.main()
