import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.controller import Controller
from bot.geometry import Arena
from test_bot import HELLO, observation
from tools.build_world import build


class SizeRoutingTests(unittest.TestCase):
    def test_growth_invalidates_route_before_decision(self):
        bot = Controller(HELLO)
        pinch = bot.world.cell(25, -326)
        self.assertTrue(bot.world.free_cell(pinch))
        obs = observation()
        # Use the reported dimensions even if cube count has not changed.
        obs['self']['stats'].update(radius=3.25, height=11.7)
        bot.movement.path = [pinch]
        with patch.object(bot, 'update_world', side_effect=StopIteration):
            with self.assertRaises(StopIteration):
                bot.act(obs)
        self.assertFalse(bot.world.free_cell(pinch))
        self.assertEqual(bot.movement.path, [])

    def test_bridge_detour_and_open_ground(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root/'v2'
            data.mkdir()
            terrain = dict(minX=0, minY=0, step=1, nx=61, ny=61, scale=.01)
            bridge = dict(kind='bridge', base=10, top=12,
                          ring=[24,24,36,24,36,36,24,36], holes=[])
            world = dict(bounds=dict(minX=0,maxX=60,minY=0,maxY=60),terrain=terrain,prisms=[bridge])
            (data/'world.json').write_text(json.dumps(world))
            (data/'terrain.i16').write_bytes(struct.pack('<h', 0)*61*61)
            build(root, root/'terrain_grid.bin.gz')
            for cached in (True, False):
                with self.subTest(cached=cached), patch('bot.geometry.__file__', str(root/'geometry.py')):
                    arena = Arena(root, use_cache=cached)
                    start, goal = (12,30), (48,30)
                    self.assertTrue(arena.line_walkable(start, goal))
                    arena.set_body_size(3.25, 11.7)
                    self.assertFalse(arena.free_cell(arena.cell(30,30)))
                    self.assertFalse(arena.line_walkable(start, goal))
                    path, reached = arena.path(start, goal, budget_s=1)
                    self.assertTrue(reached)
                    points = list(map(arena.cell_pos, path))
                    self.assertTrue(all(arena.line_walkable(a,b) for a,b in zip(points,points[1:])))
                    self.assertTrue(arena.line_walkable((12,12),(48,12)))
                    arena.set_body_size(6, 22)
                    self.assertTrue(arena.free_cell(arena.cell(12,12)))
                    arena.set_body_size(2.5, 9)
                    self.assertTrue(arena.free_cell(arena.cell(30,30)))

    def test_shortcut_cannot_cut_a_blocked_diagonal(self):
        arena = Arena(HELLO['map']['dir'])
        with patch.object(arena, 'walk_at', return_value=0), patch.object(arena, 'standable', return_value=True):
            a = arena.cell(0,0)
            b = (a[0]+1, a[1]+1)
            def free(cell):
                arena._surface[cell] = 0
                return cell != (a[0]+1, a[1])
            with patch.object(arena, 'free_cell', side_effect=free):
                self.assertFalse(arena.line_walkable(arena.cell_pos(a), arena.cell_pos(b)))
