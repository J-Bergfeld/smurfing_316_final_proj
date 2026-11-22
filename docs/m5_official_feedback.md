# Official feedback and historical calibration

The historical practice scoreboard records a best of 5.17 for 4991fa6 at default settings, tied later by c5aeebb. The machine-readable reference lists the full Git revisions, Dockerfile digests, settings, scores, evidence and champion tie rule. A Git checkout of the recorded revision recovers the public source candidate. Official image digests, run IDs, timestamps, individual game outcomes and benchmark versions are unavailable for these five entries. [Historical reference](../experiments/historical_practice.json) · [Score provenance](experiments.md#official-practice)

## Reproduction

We selected five recorded default builds with identifiable commits and ran them on the same five fresh squad-proxy seeds (424000–424004, arena/v2). Each checkout was clean. The study used build-by-build serial execution, so wall-clock load is a possible order effect. These commands use fresh destinations and the repository's existing simulator checkout.

```sh
SIM="competitors/updated/$(python3 -c 'import json; print(json.load(open("competitors/lineup.json"))["simulator"])')"
mkdir -p mech-testing/m5-history
for ref in 4991fa6 c5aeebb fb85097 37d1a1d ded4a9c; do
  git clone --quiet --shared --no-checkout . "mech-testing/m5-history/$ref" &&
  git -C "mech-testing/m5-history/$ref" checkout --quiet --detach "$ref" &&
  python3 tools/baseline.py --sim "$SIM" --bot-root "mech-testing/m5-history/$ref" \
    --seed-start 424000 --seeds 5 --out "mech-testing/m5-reference-$ref" || break
done
```

Import each reference panel into the same database. The historical-score command requires a registered build and exact matching full revision. Record unknown-version aggregates in their own cohort. Live submission records remain available for separate version-specific calibration. The script below reconstructs the historical report from the five directories.

```sh
python3 - <<'PY'
import json, subprocess
from pathlib import Path
source = json.loads(Path('experiments/historical_practice.json').read_text())
cmd = ['python3','tools/official_log.py','--db','mech-testing/eval-registry.sqlite']
for row in source['builds']:
    rev = row['revision']
    path = 'mech-testing/m5-reference-' + rev[:7]
    imported = json.loads(subprocess.check_output(cmd + ['import-panel',path]))
    subprocess.run(cmd + ['historical-score',imported['build'],rev,source['cohort'],
                          source['source'],str(row['official_score'])],check=True)
result = subprocess.check_output(cmd + ['calibration',imported['panel'],source['cohort'],
                                      '--historical','--chart','/tmp/m5-scatter.vl.json'])
Path('/tmp/m5-calibration.json').write_bytes(result)
PY
```

## Operator workflow

Queue entries identify a build and a reason. A human submits through the platform and records the run ID, actual timestamp with timezone, and benchmark version with the existing submitted/result commands. The slot command reports an upper bound from recorded timestamps until the operator supplies a verified limit and reconciles the preceding hour with the official platform. This session had no verified live capacity or new official result. Before a repeat, check whether the platform accepts a previously submitted revision.

```sh
DB=mech-testing/eval-registry.sqlite
python3 tools/official_log.py --db "$DB" list
python3 tools/official_log.py --db "$DB" slots --limit "$VERIFIED_LIMIT"
python3 tools/official_log.py --db "$DB" slots --limit "$VERIFIED_LIMIT" --history-complete
```

## Measurements and decision

| Default revision | Local mean, 5 seeds | Reported official mean |
|---|---:|---:|
| 4991fa6 | 3.20 | 5.17 |
| c5aeebb | 5.60 | 5.17 |
| fb85097 | 3.20 | 5.10 |
| 37d1a1d | 4.80 | 5.06 |
| ded4a9c | 3.60 | 4.81 |

The two tied official leaders were 2.40 points apart locally. Spearman rank correlation was −0.03, Pearson correlation 0.24, and four build pairs reversed order. Mean official minus local was +0.982. Raw mean absolute error was 1.154. Holding out one build at a time, adding the other builds' average offset gave 1.067 mean absolute error. Predicting the other builds' mean official score gave 0.127. Five related builds, five local seeds and unknown official benchmark versions limit generalization. Use local comparisons for screening and recorded official scores for the champion decision. This sample provides no reliable ranking model for unsubmitted candidates.

![Local and official points by build](m5_calibration.svg)

[Calibration data and leave-one-build-out residuals](m5_calibration.json) · [Portable chart specification](m5_calibration.vl.json)

The local SQLite queue contains the earlier 5.17 champion as a reproducibility repeat and the later tied build as backup, conditional on repeat eligibility. No submission was sent. The platform limit and prior-hour history were unverified. Pending timestamps do not consume a slot. To reproduce the two queue entries in a fresh database after importing the five panels, or regenerate the static plot (ReportLab required), run:

```sh
python3 tools/official_log.py --db "$DB" queue 453532dd0720ac796c52c06399a566f0e0b2f65b4f23e250c45707ef83527666 "Diagnostic repeat of earlier 5.17 champion if eligible"
python3 tools/official_log.py --db "$DB" queue 88f826b5287111faa8c03fc1e8e6489af74d2b012cea61330bc3086252ad5353 "Backup repeat of later tied 5.17 build if eligible"
python3 tools/plot_calibration.py docs/m5_calibration.json docs/m5_calibration.svg
```
