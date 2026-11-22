import io
import json
import unittest
from types import SimpleNamespace

from tools.diagnose import diagnose
from tools.match_telemetry import Observer, fingerprint, layout_hash


class EvaluationTests(unittest.TestCase):
    def test_layout_identity_is_stable_and_sensitive_to_spawns(self):
        match = SimpleNamespace(subject=0, order=[], zone_phases=[], crates={}, pickups={}, npcs={},
                                npc_cd={}, drop_plan=[], players=[SimpleNamespace(role='subject',s={'pos':[0,0,0]})])
        saved = layout_hash(match)
        self.assertEqual(saved, layout_hash(match))
        match.players[0].s['pos'][0] = 1
        self.assertNotEqual(saved, layout_hash(match))
        self.assertEqual(fingerprint({'a':1,'b':2}), fingerprint({'b':2,'a':1}))

    def test_terminal_damage_is_counted_once_and_attributed(self):
        match = SimpleNamespace(subject=0, order=[], zone_phases=[], crates={}, pickups={}, npcs={},
                                npc_cd={}, drop_plan=[], players=[], tick=21, t=1.05, phase=0)
        stream = io.StringIO()
        observer = Observer(stream,match)
        player = SimpleNamespace(life=False, fatal_source=None, fatal_weapon='zone',
                                 s=dict(pos=[0,0,0],hp=0,cubes=0,upgrades=[],weapons=[]),
                                 events=[dict(type='damaged',weapon='zone',amount=10,by=None)])
        summary = observer.finish(match,player)
        self.assertEqual(summary['incoming_damage'],{'zone':10})
        rows = list(map(json.loads,stream.getvalue().splitlines()))
        self.assertEqual([r['origin'] for r in rows], ['simulator']*2)
        self.assertEqual(set(diagnose(rows,summary['terminal'],.35,2)), {'zone_elimination'})

    def test_alive_timeout_and_unknown_death(self):
        self.assertEqual(diagnose([],{'alive':True},.35,2),{})
        self.assertEqual(diagnose([],{'alive':False,'fatal_weapon':None},.35,2),{'unknown':{}})


class PipelineTests(unittest.TestCase):
    def test_pairing_requires_unique_seeds_and_equal_layout(self):
        from tools.experiment import compare
        row = dict(seed=42,points=3,initial_layout_sha256='world')
        with self.assertRaises(ValueError):
            compare([row,row],[row])
        with self.assertRaises(ValueError):
            compare([row],[dict(row,initial_layout_sha256='other')])
        result = compare([row,dict(row,seed=43)],[dict(row,points=1),dict(row,seed=43,points=5)])
        self.assertEqual(result['median'],0)
        self.assertEqual(result['per_seed'],{42:-2,43:2})
        self.assertEqual(result['worst_regressions'],[(42,-2)])

    def test_reference_panel_rejects_inconsistent_points(self):
        from pathlib import Path
        import sqlite3
        from tempfile import TemporaryDirectory
        from tools.official_log import import_panel, schema
        with TemporaryDirectory() as tmp, sqlite3.connect(':memory:') as db:
            path = Path(tmp)
            manifest = dict(snapshot=dict(bot='b',sim='s',kit='k',tools='t'),bot=dict(commit='sha'),
                            config_sha256='c',field='squad',seed_start=42,seeds=1)
            (path/'manifest.json').write_text(json.dumps(manifest))
            (path/'42.json').write_text(json.dumps(dict(seed=42,points=15,place=16)))
            schema(db)
            with self.assertRaises(ValueError):
                import_panel(db,path)

    def test_slots_and_matched_calibration(self):
        import sqlite3
        from tools.official_log import calibration, schema, slots
        self.assertEqual(slots([100,101],3700,2)['available'],1)
        with sqlite3.connect(':memory:') as db:
            schema(db)
            for i in range(5):
                name=str(i)
                db.execute('INSERT INTO candidates VALUES (?,?,?,?,?)',(name,name,name,name,name))
                db.execute('INSERT INTO reference_runs VALUES (?,?,?,?)',(name,'p',i,'path'))
                db.execute('INSERT INTO submissions VALUES (?,?,?,?,?)',(name,name,100,'v',4-i))
            result=calibration(db,'p','v')
            self.assertEqual(result['spearman'],-1)
            self.assertEqual(len(result['inversions']),10)
            self.assertEqual(calibration(db,'other','v')['n'],0)

    def test_source_snapshot_changes_with_dirty_runtime_file(self):
        import zipfile
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from tools.baseline import freeze
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for d in ['a','b','bot','sim/local_sim']:
                (root/d).mkdir(parents=True)
            entry = root/'bot/main.py'
            entry.write_text('print(1)')
            first = freeze(root/'a',root/'sim',root/'bot')
            entry.write_text('print(2)')
            second = freeze(root/'b',root/'sim',root/'bot')
            self.assertNotEqual(first['bot'],second['bot'])
            with zipfile.ZipFile(root/'a/inputs.zip') as archive:
                self.assertEqual(archive.read('bot/main.py'),b'print(1)')

    def test_undated_official_scores_are_separate_from_confirmed_runs(self):
        import sqlite3
        from tools.official_log import schema, calibration
        with sqlite3.connect(':memory:') as db:
            schema(db)
            db.execute('INSERT INTO candidates VALUES (?,?,?,?,?)',('b','rev','h','cfg','archive'))
            db.execute('INSERT INTO reference_runs VALUES (?,?,?,?)',('b','p',3,'path'))
            db.execute('INSERT INTO historical_scores VALUES (?,?,?,?)',('b','unknown-version',5,'scoreboard'))
            self.assertEqual(calibration(db,'p','unknown-version')['n'],0)
            historical=calibration(db,'p','unknown-version',historical=True)
            self.assertEqual((historical['n'],historical['bias']),(1,2))
            self.assertEqual(db.execute('SELECT count(*) FROM submissions').fetchone()[0],0)
