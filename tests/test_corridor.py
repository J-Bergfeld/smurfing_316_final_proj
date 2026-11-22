import math
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot.corridor import FightCorridor, incoming_risk, potential_cover
from bot.controller import Controller
from bot.geometry import Arena as RealArena
from bot.positional_field import PositionalField
from test_bot import HELLO, enemy, observation


class Arena:
    def __init__(self):
        self.block = False
        self.cover = True
    def walk_at(self, x, y): return 0
    def line_walkable(self, a, b): return not self.block
    def shot_clear(self, a, b):
        # Synthetic hard cover north of the starting position; target shots
        # point east, while anonymous radial probes point inward.
        if self.cover and b[1] > 4 and a[0] < -50:
            return False
        return True


class CorridorTests(unittest.TestCase):
    def setUp(self):
        self.obs = observation(); self.obs.update(t=30, alive=12)
        self.target = enemy(80)
        self.arena = Arena()
        field = SimpleNamespace(hunters=Mock(return_value=([], [])),
                                candidates=Mock(return_value=[(0,0),(0,12)]))
        self.corridor = FightCorridor(field)
        attacker = dict(enemy(-70), id=8, aim=[0,0])
        self.state = SimpleNamespace(world=self.arena, movement=SimpleNamespace(path=[]),
            action_deadline=time.perf_counter()+1, body_size=(2.5,9),
            cfg=HELLO['config'], hold=(*self.obs['zone']['center'],self.obs['zone']['radius']),
            tracks={8:{'actor':attacker,'seen':30}}, attacker_memory={8:30})

    def test_prepares_route_with_cover_and_exit(self):
        self.assertEqual(self.corridor.choose(self.state,self.obs,self.target,[1,0]), [0.,1.])
        self.assertEqual(self.corridor.breakdown['goal'], (0,12))

    def test_open_ground_and_blocked_route_fall_back(self):
        self.arena.cover = False
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        self.arena.cover = True; self.arena.block = True
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_cached_route_invalidated_when_blocked(self):
        self.assertIsNotNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        self.obs['t'] += .1; self.arena.block = True
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        self.assertFalse(self.corridor.route)

    def test_early_single_hunter_falls_back(self):
        self.obs['alive'] = 15
        self.state.tracks = {}; self.state.attacker_memory = {}
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_baseline_already_in_cover_is_not_overridden(self):
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[0,1]))

    def test_approaching_unaimed_enemy_is_considered(self):
        actor = self.state.tracks[8]['actor']
        actor['aim'] = [math.pi,0]; actor['vel'] = [8,0,0]
        self.state.attacker_memory = {}; self.obs['alive'] = 15
        self.assertIsNotNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_low_health_target_keeps_baseline_finish(self):
        self.target['hp'] = 100
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_two_segment_route_around_corner(self):
        self.arena.line_walkable = lambda a,b: not (a[:2] == (0,0) and b == (0,12))
        self.arena.path = lambda a,b,budget_s: ([(0,0),(0,6),(0,12)],True)
        self.arena.cell_pos = lambda c: c
        self.assertIsNotNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        self.assertEqual(len(self.corridor.route), 2)

    def test_threat_movement_invalidates_cached_route(self):
        self.assertIsNotNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        previous_key = self.corridor.key
        self.obs['t'] += .1
        self.state.tracks[8]['actor']['pos'][0] += 10
        self.corridor.choose(self.state,self.obs,self.target,[1,0])
        self.assertNotEqual(previous_key,self.corridor.key)

    def test_failed_search_is_temporarily_throttled(self):
        self.arena.cover = False
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        self.assertEqual(self.corridor.metrics['no_route'],1)
        self.obs['t'] += .1
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        self.assertEqual(self.corridor.metrics['no_route'],1)

    def test_real_map_route_is_walkable_if_selected(self):
        world = RealArena(HELLO['map']['dir'])
        self.state.world = world
        self.corridor = FightCorridor(PositionalField(world))
        self.obs['self']['pos'] = [25,-326,world.walk_at(25,-326)]
        self.obs['zone'].update(center=[25,-326],next_center=[25,-326])
        self.state.hold = (25,-326,500)
        self.target['pos'] = [90,-326,world.walk_at(90,-326)]
        self.state.tracks[8]['actor']['pos'] = [-30,-326,world.walk_at(-30,-326)]
        move = self.corridor.choose(self.state,self.obs,self.target,[1,0])
        if move is not None:
            self.assertTrue(world.line_walkable(self.obs['self']['pos'], self.corridor.route[0]))

    def test_two_threats_can_activate_early(self):
        self.obs['alive'] = 15
        self.assertIsNotNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_dead_end_is_rejected(self):
        self.arena.line_walkable = lambda a,b: not (a[1] == 12 and b != (0,12))
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_losing_target_line_rejects_route(self):
        original = self.arena.shot_clear
        self.arena.shot_clear = lambda a,b: False if b[0] == 80 and a[1] > 4 else original(a,b)
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_timeout_falls_back(self):
        self.state.action_deadline = time.perf_counter()-1
        self.assertIsNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))

    def test_missing_target_clears_cached_route(self):
        self.assertIsNotNone(self.corridor.choose(self.state,self.obs,self.target,[1,0]))
        self.assertIsNone(self.corridor.choose(self.state,self.obs,None,[1,0]))
        self.assertFalse(self.corridor.route)

    def test_zone_escape_preempts_corridor(self):
        with patch.dict('os.environ', {'BOT_FIGHT_CORRIDOR':'1','BOT_POSITIONAL_FIELD':'1'}):
            bot = Controller(HELLO)
        obs = observation(); obs.update(t=30, tick=300, alive=12)
        obs['self']['in_zone'] = False
        obs['zone'].update(next_center=[130,0], next_radius=30)
        bot.corridor.choose = Mock(side_effect=AssertionError('zone must take priority'))
        bot.movement.navigate = Mock(return_value=[1,0])
        bot.act(obs)
        self.assertEqual(bot.mode, 'zone')

    def test_selected_target_and_rear_attackers_contribute_risk(self):
        self.arena.cover = False
        threats = [(7,(80,0,7),230,1.), (8,(-70,0,7),230,1.)]
        self.assertEqual(incoming_risk(self.arena,(0,0),(0,0,5),[80,0,0],threats), 2.5)
        self.assertEqual(incoming_risk(self.arena,(0,0),(0,0,5),[80,0,0],threats[:1]), 1.)

    def test_cover_score_is_bounded_and_safe_at_map_edges(self):
        self.arena.baked = {'nx':2,'ny':1,'clearance':[0,6]}
        self.arena.cell = lambda x,y: (int(x),int(y))
        self.assertEqual(potential_cover(self.arena,(0,0)),1.)
        self.assertEqual(potential_cover(self.arena,(1,0)),0.)
        self.assertEqual(potential_cover(self.arena,(-1,0)),0.)

    def test_near_wall_preparation_with_only_target(self):
        self.state.tracks = {}; self.state.attacker_memory = {}
        self.arena.cover = False
        self.arena.baked = {'nx':2,'ny':1,'clearance':[0,6]}
        self.arena.cell = lambda x,y: (0 if y > 4 else 1,0)
        self.assertEqual(self.corridor.choose(self.state,self.obs,self.target,[1,0]),[0.,1.])

    def test_practice_mode_survives_uncredited_death(self):
        bot = Controller(HELLO)
        obs = observation(); obs.update(t=0, tick=0, alive=16)
        bot.update_world(obs)
        obs.update(t=30, tick=300, alive=15)
        for i in range(6):
            obs['tick'] += 2
            bot.update_world(obs)
        self.assertFalse(bot.ffa)
        with patch.object(bot,'assess_combat',return_value=([],None,None,False,False)) as assess:
            bot.act(obs)
        self.assertTrue(assess.call_args.args[1])

    def test_practice_mode_starts_on_first_tick(self):
        bot = Controller(HELLO); obs = observation()
        with patch.object(bot,'assess_combat',return_value=([],None,None,False,False)) as assess:
            bot.act(obs)
        self.assertTrue(assess.call_args.args[1])

if __name__ == '__main__': unittest.main()
