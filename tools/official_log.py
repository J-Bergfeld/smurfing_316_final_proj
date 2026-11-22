"""Local manual queue, rolling-window accounting, and matched reference-panel calibration."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import statistics

if __package__:
    from .match_telemetry import fingerprint
else:
    from match_telemetry import fingerprint


def schema(db):
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY, revision TEXT, bot_hash TEXT, config_hash TEXT, archive TEXT);
        CREATE TABLE IF NOT EXISTS reference_runs (
            build TEXT REFERENCES candidates, panel TEXT, mean REAL, path TEXT,
            PRIMARY KEY(build,panel));
        CREATE TABLE IF NOT EXISTS queue (
            build TEXT PRIMARY KEY REFERENCES candidates, reason TEXT, queued REAL);
        CREATE TABLE IF NOT EXISTS submissions (
            run_id TEXT PRIMARY KEY, build TEXT REFERENCES candidates, submitted REAL,
            version TEXT, score REAL CHECK(score BETWEEN 0 AND 15));
    ''')


def import_panel(db, path):
    m = json.loads((path/'manifest.json').read_text())
    build = fingerprint([m['bot']['commit'],m['snapshot']['bot'],m['config_sha256']])
    panel = fingerprint([m['snapshot']['sim'],m['snapshot']['kit'],m['snapshot']['tools'],
                         m['field'],m['seed_start'],m['seeds']])
    values = []
    for seed in range(m['seed_start'],m['seed_start']+m['seeds']):
        r = json.loads((path/f'{seed}.json').read_text())
        if r['seed'] != seed or not 1 <= r['place'] <= 16 or r['points'] != 16-r['place']:
            raise ValueError('invalid reference score')
        values.append(r['points'])
    db.execute('INSERT OR IGNORE INTO candidates VALUES (?,?,?,?,?)',
               (build,m['bot']['commit'],m['snapshot']['bot'],m['config_sha256'],str(path.resolve()/'inputs.zip')))
    db.execute('INSERT INTO reference_runs VALUES (?,?,?,?)',(build,panel,statistics.mean(values),str(path.resolve())))
    return dict(build=build,panel=panel,local_mean=statistics.mean(values))


def parse_time(value):
    dt = datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:
        raise ValueError('include timezone in submission timestamp')
    return dt.timestamp()


def utc(ts):
    return datetime.fromtimestamp(ts,timezone.utc).isoformat()


def slots(times, now, limit):
    if limit < 1:
        raise ValueError('positive rolling limit required')
    active = sorted(t for t in times if now-3600 < t <= now)
    return dict(available=max(0,limit-len(active)), reopens_utc=[utc(t+3600) for t in active],
                next_available_utc=utc(now if len(active)<limit else active[len(active)-limit]+3600))


def ranks(values):
    ordered = sorted(values)
    return [ordered.index(v)+(ordered.count(v)+1)/2 for v in values]


def correlation(x,y):
    a,b = statistics.mean(x),statistics.mean(y)
    denom = (sum((v-a)**2 for v in x)*sum((v-b)**2 for v in y))**.5
    return sum((v-a)*(w-b) for v,w in zip(x,y))/denom if denom else None


def calibration(db,panel,version):
    rows = [dict(build=b,local=l,official=o,repeats=n,official_minus_local=o-l) for b,l,o,n in db.execute('''
        SELECT r.build,r.mean,AVG(s.score),COUNT(s.score) FROM reference_runs r JOIN submissions s
        ON s.build=r.build WHERE r.panel=? AND s.version=? AND s.score IS NOT NULL
        GROUP BY r.build ORDER BY r.build''',(panel,version))]
    result = dict(n=len(rows),builds=rows)
    if rows:
        errors = [r['official_minus_local'] for r in rows]
        result.update(bias=statistics.mean(errors),mae=statistics.mean(map(abs,errors)))
        x,y=[r['local'] for r in rows],[r['official'] for r in rows]
        result['inversions'] = [[rows[i]['build'],rows[j]['build']] for i in range(len(rows))
                                for j in range(i) if (x[i]-x[j])*(y[i]-y[j])<0]
        # Descriptive guard against reporting a line through one or two builds.
        if len(rows)>=5:
            result.update(pearson=correlation(x,y),spearman=correlation(ranks(x),ranks(y)))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    sub = p.add_subparsers(dest='command',required=True)
    sub.add_parser('import-panel').add_argument('path',type=Path)
    q=sub.add_parser('queue')
    q.add_argument('build')
    q.add_argument('reason')
    sub.add_parser('list')
    q=sub.add_parser('submitted')
    for name in ('build','run_id','timestamp','version'):
        q.add_argument(name)
    q=sub.add_parser('result')
    q.add_argument('run_id')
    q.add_argument('score',type=float)
    sub.add_parser('slots').add_argument('--limit',type=int,required=True)
    q=sub.add_parser('calibration')
    q.add_argument('panel')
    q.add_argument('version')
    q.add_argument('--chart',type=Path,help='Write a Vega-Lite scatterplot specification')
    args=p.parse_args()
    now=datetime.now(timezone.utc).timestamp()
    with sqlite3.connect(args.db) as db:
        schema(db)
        if args.command=='import-panel':
            result=import_panel(db,args.path)
        elif args.command=='queue':
            db.execute('INSERT INTO queue VALUES (?,?,?)',(args.build,args.reason,now))
            result=dict(queued=args.build)
        elif args.command=='list':
            result=dict(queue=db.execute('SELECT build,reason FROM queue ORDER BY queued').fetchall(),
                        submissions=db.execute('SELECT run_id,build,version,score FROM submissions ORDER BY submitted').fetchall(),
                        champions_by_version=db.execute('''SELECT version,build,score,run_id FROM
                            (SELECT *,ROW_NUMBER() OVER(PARTITION BY version ORDER BY score DESC,submitted,run_id) pos
                             FROM submissions WHERE score IS NOT NULL) WHERE pos=1''').fetchall())
        elif args.command=='submitted':
            stamp=parse_time(args.timestamp)
            if stamp>now:
                p.error('actual submission timestamp required')
            db.execute('INSERT INTO submissions VALUES (?,?,?,?,NULL)',(args.run_id,args.build,stamp,args.version))
            db.execute('DELETE FROM queue WHERE build=?',(args.build,))
            result=dict(recorded=args.run_id)
        elif args.command=='result':
            if not 0 <= args.score <= 15 or not db.execute(
                    'UPDATE submissions SET score=? WHERE run_id=? AND score IS NULL',(args.score,args.run_id)).rowcount:
                p.error('require an unscored submission and score from 0 to 15')
            result=dict(run_id=args.run_id,score=args.score)
        elif args.command=='slots':
            result=slots([r[0] for r in db.execute('SELECT submitted FROM submissions')],now,args.limit)
        else:
            result=calibration(db,args.panel,args.version)
            if args.chart:
                chart={'$schema':'https://vega.github.io/schema/vega-lite/v5.json','mark':'point',
                       'data':{'values':result['builds']},'encoding':{
                           'x':{'field':'local','type':'quantitative'},'y':{'field':'official','type':'quantitative'},
                           'tooltip':[{'field':'build'},{'field':'local'},{'field':'official'}]}}
                with args.chart.open('x') as f:
                    json.dump(chart,f,indent=2)
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
