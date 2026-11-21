import hashlib
import json
import random
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.controller import Controller
from bot.geometry import Arena
from test_bot import HELLO
from tools.build_world import build
from tools.compare_worlds import compare, read_grid


class WorldBuilderTests(unittest.TestCase):
    def test_builds_terrain_obstacles_slabs_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); world=root/'v2'; world.mkdir()
            data={'bounds':{'minX':-1,'maxX':21,'minY':-1,'maxY':21},
                  'terrain':{'minX':0,'minY':0,'step':1,'nx':21,'ny':21,'scale':.01},
                  'prisms':[{'kind':'building','base':0,'top':6,'ring':[8,8,12,8,12,12,8,12],'holes':[]},
                            {'kind':'bridge','base':3,'top':4,'ring':[3,3,5,3,5,5,3,5],'holes':[]}]}
            (world/'world.json').write_text(json.dumps(data)); (world/'terrain.i16').write_bytes(struct.pack('<441h',*([0]*441)))
            cache=root/'terrain_grid.bin.gz'
            result=build(root,cache); grid=read_grid(cache,441)
            self.assertGreater(result['blocked'],0)
            self.assertEqual(grid['top'][10*21+10],6)
            self.assertEqual(grid['slabs'][4*21+4],[(3,4)])
            self.assertEqual(grid['top'][4*21+4],0)
            manifest=json.loads((root/'terrain_grid.bin.gz.meta.json').read_text())
            self.assertEqual(manifest['world_sha256'],hashlib.sha256((world/'world.json').read_bytes()).hexdigest())
            self.assertTrue(compare(grid,grid)['header_equal'])
            self.assertEqual(compare(grid,grid)['blocked']['different'],0)
            with patch('bot.geometry.__file__',str(root/'geometry.py')):
                self.assertIsNotNone(Arena(root).baked)
                (world/'world.json').write_text(json.dumps(data,indent=2))
                self.assertIsNone(Arena(root).baked)

    def test_controller_uses_python_seeded_random(self):
        hello=dict(HELLO,seed=42)
        bot=Controller(hello)
        expected=random.Random(42)
        self.assertIsInstance(bot.rng,random.Random)
        self.assertEqual([bot.rng.random() for _ in range(3)],[expected.random() for _ in range(3)])

    def test_step_limit_uses_float32_rounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); world=root/'v2'; world.mkdir()
            data={'bounds':{'minX':-5,'maxX':25,'minY':-5,'maxY':25},
                  'terrain':{'minX':0,'minY':0,'step':1,'nx':21,'ny':21,'scale':.01},'prisms':[]}
            (world/'world.json').write_text(json.dumps(data))
            heights=[0 if x<=10 else 220 for y in range(21) for x in range(21)]
            (world/'terrain.i16').write_bytes(struct.pack('<441h',*heights))
            build(root,root/'grid.gz'); grid=read_grid(root/'grid.gz',441)
            self.assertEqual(grid['component'][5*11+5],grid['component'][5*11+6])


if __name__=='__main__': unittest.main()
