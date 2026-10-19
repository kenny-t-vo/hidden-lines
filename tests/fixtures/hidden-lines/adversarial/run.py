#!/usr/bin/env python3
"""Run outside kit.py test:

uv run --no-project --with numpy,shapely,numba python -B tests/fixtures/hidden-lines/adversarial/run.py

Each export, request and checks file is built in a temporary directory. --keep retains
that directory. --results records measurements; failures intentionally exit 1.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from scenes import all_scenes, checks_for, page, write
from hiddenlines.hidden import check_notes


def command(argv, timeout):
    start = time.monotonic()
    p = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, time.monotonic() - start
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        return None, out, err, time.monotonic() - start


def execute(s, folder, timeout=60, profile=False):
    write(folder, s)
    argv = ['python3', str(ROOT / 'kit.py'), 'hidden-lines', str(folder / 'request.json'), '--check', str(folder / 'checks.json')]
    if profile:
        argv = [sys.executable, '-m', 'cProfile', '-o', str(folder / 'profile.pstats'), str(ROOT / 'kit.py'), 'hidden-lines', str(folder / 'request.json'), '--check', str(folder / 'checks.json')]
    measured = [sys.executable, str(HERE / 'run.py'), '--measure'] + argv
    rc, out, err, seconds = command(['/usr/bin/time', '-l'] + measured, timeout)
    result = dict(scene=s['name'], family=s['family'], reason=s['reason'], seconds=round(seconds, 3),
                  rule=s.get('rule', 'A'), status='PASS', failures=[], checks=[], returncode=rc)
    metric = re.search(r'ADVERSARIAL_RESOURCE (.+)', err)
    measured = json.loads(metric[1]) if metric else {}
    rss = re.search(r'(\d+)\s+maximum resident set size', err)
    result['peak_bytes'] = int(rss[1]) if rss else measured.get('peak_bytes')
    if metric:
        rc = measured['returncode']
        result['returncode'] = rc
        result['seconds'] = measured['seconds']
    if 'sysctl kern.clockrate' in err:
        result['time_error'] = 'time: sysctl kern.clockrate: Operation not permitted'
    err = re.sub(r'^ADVERSARIAL_RESOURCE .*\n?|^time: sysctl kern.clockrate:.*\n?', '', err, flags=re.M)
    result['command'] = 'python3 kit.py hidden-lines REQUEST --check CHECKS'
    if rc is None:
        result.update(status='SKIP', failures=[f'timeout after {timeout:g} s; process group killed'])
        return result
    traceback = 'Traceback (most recent call last)' in err
    if rc:
        diagnostic = re.sub(r'^\s*\d.*(?:real|user|sys|size|faults|reclaims|swaps|messages|signals|switches|instructions|cycles|memory).*$', '', err, flags=re.M).strip()
        result['diagnostic'] = diagnostic
        if traceback or not s.get('error_ok') or not diagnostic:
            result.update(status='FAIL', failures=[diagnostic.splitlines()[-1] if diagnostic else f'exit {rc}'])
        else:
            result['accepted_error'] = diagnostic.splitlines()[0]
        return result
    svg = folder / (s['name'] + '.svg')
    if not svg.is_file():
        result.update(status='FAIL', failures=['no SVG despite successful exit'])
        return result
    for c, passed, measure, detail in check_notes(svg, checks_for(s)):
        result['checks'].append(dict(check=c, passed=passed, measure=measure, detail=detail))
        if passed is False:
            result['failures'].append(f'note {c["note"]} {c["kind"]}: {detail} (measure {measure})')
    report = json.loads((folder / (s['name'] + '-report.json')).read_text())
    result['cuts'] = report['cuts']
    result['engine_seconds'] = report['seconds']
    result['faces'] = report.get('faces')
    result['doubles'] = report.get('doubles')
    result['counts'] = report.get('counts')
    if s.get('checkpoint') == 7:
        result['model'] = report.get('model')
        result['paths_to_node'] = report.get('paths_to_node')
        result['fixes'] = report.get('fixes')
        for c in s.get('report_checks', []):
            value = report
            for key in c['field'].split('.'):
                value = value.get(key, 0) if isinstance(value, dict) else 0
            passed = c.get('min', -float('inf')) <= value <= c.get('max', float('inf'))
            result['checks'].append(dict(check=c, passed=passed, measure=value, detail=c['field']))
            if not passed:
                result['failures'].append(f'{c["field"]}: {value}, expected {c}')
        if 'allowed_reasons' in s:
            wrong = sorted(set(report['model']['dropped']) - set(s['allowed_reasons']))
            if wrong:
                result['failures'].append('unexpected dropped reasons: ' + ', '.join(wrong))
        if s['name'].startswith('doubles-occluder-'):
            import shapely
            from archkit.lint import read_svg
            ps = read_svg(svg)['paths']
            front = page(s, s['parts'][1]['tris'][0])
            front = shapely.LineString(front + [front[0]])
            ink = shapely.union_all([shapely.LineString([a, b]) for p in ps
                                    if p.layer == 'BEYOND' and p.width for a, b in p.segs])
            result['occlusion_geometry'] = dict(front_missing_pt=float(front.difference(ink.buffer(0.075)).length))
        obs = dict(s, checks=s.get('observations', []))
        result['observations'] = [dict(check=c, passed=passed, measure=measure, detail=detail)
                                  for c, passed, measure, detail in check_notes(svg, checks_for(obs))]
        if s.get('exact_model_tol') is not None:
            import shapely
            from archkit.lint import read_svg
            source = shapely.union_all([shapely.LineString(page(s, p['curve'])) for p in s['parts'] if 'curve' in p])
            paths = [p for p in read_svg(svg)['paths'] if p.stroke not in (None, 'none') and p.width]
            drawn = shapely.union_all([shapely.LineString([a, b]) for p in paths for a, b in p.segs])
            off = drawn.difference(source.buffer(s['exact_model_tol'] + 1e-8, quad_segs=32)).length
            vertices = [q for p in paths for a, b in p.segs for q in (a, b)]
            worst = max(shapely.distance(shapely.points(vertices), source), default=0) if vertices else 0
            result['exact_source'] = dict(off_pt=float(off), max_vertex_pt=float(worst), tol_pt=s['exact_model_tol'])
            if off > 1e-6:
                result['failures'].append(f'continuous source distance: {off:.6f} pt beyond {s["exact_model_tol"]:g} pt; worst vertex {worst:.6f} pt')
    if s.get('mismatch'):
        # a mismatched cap must be named, rather than silently trusted
        diag = json.dumps([report.get('issues'), report['cuts'].get('unresolved')]).lower()
        if not any(word in diag for word in ('mismatch', 'disagree', 'cap', 'ring')):
            result['failures'].append('report: no ring/mesh mismatch diagnostic')
    if s.get('unresolved'):
        result['unresolved_cells'] = len(report['cuts']['unresolved'])
    if result['failures']:
        result['status'] = 'FAIL'
    if profile and (folder / 'profile.pstats').exists():
        import pstats
        import io
        buf = io.StringIO()
        pstats.Stats(str(folder / 'profile.pstats'), stream=buf).strip_dirs().sort_stats('cumulative').print_stats(r'(hidden|idbuf)\.py', 18)
        result['profile'] = buf.getvalue()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', help='regular expression matching scene names')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--results', type=Path)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--profile', action='store_true', help='profile selected scenes; use the uv Python with kit dependencies')
    parser.add_argument('--jobs', type=int, default=1, help='independent drawing processes (default 1)')
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error('--timeout must be in (0,60] seconds')
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    os.environ.setdefault('NUMBA_CACHE_DIR', str(Path.home() / '.cache' / 'hidden-lines' / 'adversarial-numba'))
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    base = Path(tempfile.mkdtemp(prefix='hidden-lines-adversarial-'))
    results = []
    print(f'{"scene":47} {"family":12} rule {"result":6} {"seconds":>8} failing check', flush=True)
    try:
        from concurrent.futures import ThreadPoolExecutor
        selected = [s for s in all_scenes() if not args.only or re.search(args.only, s['name'])]
        def draw(s):
            return execute(s, base / s['name'], args.timeout, args.profile)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for s, result in zip(selected, pool.map(draw, selected)):
                results.append(result)
                print(f'{s["name"]:47} {s["family"]:12} {result["rule"]:4} {result["status"]:6} {result["seconds"]:8.3f} {"; ".join(result["failures"])}', flush=True)
                if args.results:
                    args.results.write_text(json.dumps(results, indent=2) + '\n')
        totals = {status: sum(r['status'] == status for r in results) for status in ('PASS', 'FAIL', 'SKIP')}
        print(' / '.join(f'{n} {status}' for status, n in totals.items()), flush=True)
    finally:
        if args.keep:
            print(f'Exports, requests and checks retained: {base}', flush=True)
        else:
            import shutil
            shutil.rmtree(base)
    return int(any(r['status'] != 'PASS' for r in results))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--measure']:
        import resource
        start = time.monotonic()
        child = subprocess.run(sys.argv[2:])
        rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        print('ADVERSARIAL_RESOURCE ' + json.dumps(dict(returncode=child.returncode,
              seconds=round(time.monotonic() - start, 3), peak_bytes=int(rss * (1 if sys.platform == 'darwin' else 1024)))), file=sys.stderr)
        sys.exit(child.returncode)
    sys.exit(main())
