"""Reduce C's whole-loop failures by deleting source vertices, outside kit.py test.

uv run --no-project --with numpy,shapely,numba python -B tests/fixtures/hidden-lines/adversarial/minimise.py doubles-min-loop-spike-C

The two source loops must remain closed, simple and disjoint. The expectation is
recomputed from construction geometry after every deletion. --paired deletes
corresponding vertices together (nested rims). Every drawing has a 60 s timeout.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

import shapely

from doubles import GAP, witness
from run import execute
from scenes import all_scenes, page

HERE = Path(__file__).resolve().parent


def oracle(s):
    curves = [p for p in s['parts'] if 'curve' in p]
    a, b = [shapely.LineString(page(s, p['curve'])) for p in curves]
    if not a.is_simple or not b.is_simple or not a.is_closed or not b.is_closed or a.intersects(b):
        return None
    # inscribed buffers bracket the exact Euclidean gap by under 0.00001 pt
    threshold = GAP + 0.125
    if b.covered_by(a.buffer(threshold - 0.00001, quad_segs=256)):
        absent = True
    elif b.difference(a.buffer(threshold + 0.00001, quad_segs=256)).length > 0.00001:
        absent = False
    else:
        return None
    s.update(checks=[], observations=[])
    witness(s, curves[1]['curve'], absent=absent, cover=0.99, tol=0.075)
    s['reason'] = 'Two simple disjoint closed source polylines; exact polygon buffer bounds place the entire lesser loop ' + ('inside' if absent else 'not entirely inside') + f' the {threshold:.9f} pt centre gap, so C must ' + ('remove' if absent else 'keep') + ' it whole. Coordinates are retained in this generator record.'
    return absent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('seed')
    ap.add_argument('--paired', action='store_true')
    ap.add_argument('--jobs', type=int, default=4)
    args = ap.parse_args()
    os.environ.setdefault('NUMBA_CACHE_DIR', str(Path.home() / '.cache/hidden-lines/adversarial-numba'))
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    current = copy.deepcopy(next(s for s in all_scenes() if s['name'] == args.seed))
    base = Path(tempfile.mkdtemp(prefix='hl-minimise-'))
    log = []
    serial = 0

    def draw(s):
        r = execute(s, base / s['name'])
        log.append(dict(scene=s['name'], status=r['status'], failures=r['failures'],
                        vertices=[len(p['curve']) - 1 for p in s['parts'] if 'curve' in p],
                        parts=len(s['parts']), reason=s['reason'],
                        checks=[dict(kind=c['check'].get('kind', c['check'].get('field')), passed=c['passed'], measure=c['measure']) for c in r['checks']]))
        return r['returncode'] == 0 and any(c['passed'] is False for c in r['checks'] if c['check'].get('kind') in ('line', 'clear'))

    try:
        if oracle(current) is None or not draw(current):
            raise SystemExit('seed is not a whole-loop failure under the construction oracle')
        while True:
            candidates = []
            curves = [i for i, p in enumerate(current['parts']) if 'curve' in p]
            operations = [[(j, i)] for j in curves for i in range(len(current['parts'][j]['curve']) - 1)
                          if len(current['parts'][j]['curve']) > 4]
            if args.paired:
                operations = [[(j, i) for j in curves] for i in range(len(current['parts'][curves[0]]['curve']) - 1)] if len(current['parts'][curves[0]]['curve']) > 4 else []
                n = len(operations)
                for chunks in (2, 4, 8):
                    for start in range(0, n, max(1, n // chunks)):
                        ids = list(range(start, min(n, start + max(1, n // chunks))))
                        if n - len(ids) >= 3:
                            operations.insert(0, [(j, i) for j in curves for i in ids])
            operations += [[('part', j)] for j, p in enumerate(current['parts']) if 'curve' not in p]
            for operation in operations:
                v = copy.deepcopy(current)
                if operation[0][0] == 'part':
                    del v['parts'][operation[0][1]]
                else:
                    for j in curves:
                        points = v['parts'][j]['curve'][:-1]
                        for i in sorted([i for jj, i in operation if jj == j], reverse=True):
                            del points[i]
                        v['parts'][j]['curve'] = points + [points[0]]
                serial += 1
                v['name'] = f'doubles-reduction-{serial}-C'
                if oracle(v) is not None:
                    candidates.append(v)
            if not candidates:
                break
            candidates.sort(key=lambda s: (len(s['parts']), sum(len(p['curve']) for p in s['parts'] if 'curve' in p)))
            next_scene = None
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                for start in range(0, len(candidates), args.jobs):
                    batch = candidates[start:start + args.jobs]
                    verdicts = list(pool.map(draw, batch))
                    next_scene = next((s for s, failed in zip(batch, verdicts) if failed), None)
                    if next_scene is not None:
                        break
            print(f'{len(log)} drawings; {len(candidates)} valid single-step/chunk deletions; retained ' + (next_scene['name'] if next_scene else 'none'), flush=True)
            if next_scene is None:
                break
            current = next_scene
        stem = 'rim' if args.paired or 'rim' in args.seed else 'loop'
        current['name'] = 'doubles-reduced-' + stem
        current.pop('rule', None)
        current.pop('request', None)
        current['minimal_kind'] = stem
        (HERE / f'reduced-{stem}.json').write_text(json.dumps(current, indent=2) + '\n')
        (HERE / f'reduction-{stem}.json').write_text(json.dumps(dict(seed=args.seed, paired=args.paired, trials=log), indent=2) + '\n')
    finally:
        shutil.rmtree(base)


if __name__ == '__main__':
    main()
