"""Sequential performance sweeps, outside tests/run.py.

uv run --no-project --with numpy,shapely,numba,scipy,ezdxf python -B \
  tests/fixtures/hidden-lines/adversarial/run.py --family perf --only '^triangles$' --sizes triangles=10000,30000

--sizes may repeat; omitted kinds use their defaults. --only selects kinds by regex.
Every measured size is drawn twice in fresh processes. Larger sizes are skipped after
a timeout, or when the preceding two paired sizes predict more than the time limit.
--first-run draws each --real export cold/warm twice, with separate empty numba caches.
Results resume by size; use a fresh --out after changing the engine.
Sizes are counts except frame/frame_min (page width in pt), camera (distance 1/n m),
and curve (points). curve_objects adds one backdrop object to its curves. weld stacks
triangles 1 nm apart; frame_min has one curve and no triangles.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import numpy as np
from scenes import sy, VIEW, GROUPS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DEFAULTS = dict(triangles=[10000, 30000, 100000, 300000, 1000000, 3000000],
                objects=[100, 300, 1000, 3000, 10000, 30000, 100000],
                segments=[1000, 3000, 10000, 30000, 100000, 300000, 1000000],
                slivers=[100, 300, 1000, 3000], coincident=[10, 30, 100, 300, 1000, 3000, 10000],
                parallel=[10, 30, 100, 300, 1000, 3000], tiny=[100, 300, 1000, 3000, 10000],
                camera=[1, 3, 10, 30, 100, 300], frame=[200, 600, 1800, 5400],
                curve=[1000, 3000, 10000, 30000, 100000], stacks=[10, 30, 100, 300, 1000, 3000],
                diagonal=[100, 300, 1000, 3000], fan=[10, 30, 100, 300, 1000, 3000],
                curve_objects=[100, 300, 1000, 3000, 10000, 30000, 100000],
                frame_min=[200, 600, 1800, 5400], weld=[100, 300, 1000, 3000, 6000])


def obj(i, kind='mesh'):
    return dict(i=i, ids=[f'perf-{i}'], group='b', layer='adv::b', kind=kind,
                solid=False, user={}, issues=[], parts=1)


def segment(i, points):
    return dict(o=i, src='curve', sil='MiscellaneousFeature', **{'pass': 'main'},
                pts=points, sides='', scene=False)


def write(folder, kind, n):
    folder.mkdir(parents=True, exist_ok=True)
    sy.write(folder, [], VIEW, GROUPS, scale=100, frame=(200, 120))
    data = json.loads((folder / 'scene.json').read_text())
    req = json.loads((folder / 'request.json').read_text())
    req.update(id=f'perf-{kind}-{n}', title=f'performance {kind} {n}')
    k = data['view']['pt_per_unit']
    V = np.array([[-4, -3, -5], [4, -3, -5], [4, 3, -5], [-4, 3, -5]], float)
    F = np.array([[0, 1, 2], [0, 2, 3]])
    objects = [obj(0)]
    segments = []
    items = None
    if kind == 'triangles':
        cells = (n + 1) // 2
        nx = int(math.sqrt(cells))
        ny = math.ceil(cells / nx)
        x, y = np.meshgrid(np.linspace(-2, 2, nx + 1), np.linspace(-1.4, 1.4, ny + 1))
        V = np.c_[x.ravel(), y.ravel(), np.zeros(x.size)]
        a = (np.arange(ny)[:, None] * (nx + 1) + np.arange(nx)).ravel()[:cells]
        F = np.stack([np.c_[a, a + 1, a + nx + 2], np.c_[a, a + nx + 2, a + nx + 1]], 1).reshape(-1, 3)[:n]
        segments = [segment(0, [[-1, -0.7, -1000], [1, -0.7, -1000]])]
    elif kind in ('objects', 'tiny'):
        nx = math.ceil(math.sqrt(n))
        xy = np.c_[np.arange(n) % nx, np.arange(n) // nx] / nx * [4, 2.8] - [2, 1.4]
        width = (0.9 if kind == 'tiny' else 1) / nx
        corners = np.array([[0, 0], [4 * width, 0], [4 * width, 2.8 * width], [0, 2.8 * width]])
        V = np.c_[(xy[:, None, :] + corners).reshape(-1, 2), np.zeros(n * 4)]
        F = np.tile([[0, 1, 2], [0, 2, 3]], (n, 1))
        objects = [obj(i) for i in range(n)]
        items = [dict(o=i, v0=4*i, nv=4, f0=2*i, nf=2) for i in range(n)]
    elif kind in ('segments', 'curve_objects'):
        nx = math.ceil(math.sqrt(n))
        req['frame'] = dict(w_pt=nx * 3 + 10, h_pt=math.ceil(n / nx) * 3 + 10)
        for i in range(n):
            x, y = ((i % nx) * 3 - nx * 1.5) / k, ((i // nx) * 3 - math.ceil(n / nx) * 1.5) / k
            segments.append(segment(i + 1 if kind == 'curve_objects' else 0,
                                    [[x, y, -1000], [x + 1 / k, y, -1000]]))
        V[:, :2] *= max(nx * 3 / 100, 0.2)
        if kind == 'curve_objects':
            objects += [obj(i + 1, 'curve') for i in range(n)]
    elif kind in ('coincident', 'parallel'):
        segments = [segment(0, [[-1, i * 0.5 / max(n, 1) / k if kind == 'parallel' else 0, -1000],
                                [1, i * 0.5 / max(n, 1) / k if kind == 'parallel' else 0, -1000]]) for i in range(n)]
    elif kind == 'fan':
        for i in range(n):
            slope = (i / max(n - 1, 1) - 0.5) * 0.02
            crossing = math.sin(i * 2.399963229728653) * 1.5
            segments.append(segment(0, [[-2, slope * (-2 - crossing), -1000],
                                        [2, slope * (2 - crossing), -1000]]))
    elif kind == 'curve':
        x = np.linspace(-2, 2, n)
        segments = [segment(0, np.c_[x, 0.6 * np.sin(x * 10), np.full(n, -1000)].tolist())]
    elif kind in ('slivers', 'stacks', 'diagonal', 'weld'):
        x = np.arange(n) / max(n, 1) * 4 - 2
        if kind == 'weld':
            V = np.tile([[-1, -0.7, 0], [1, -0.7, 0], [0, 0.7, 0]], (n, 1)).astype(float)
            V[:, 2] = np.repeat(np.arange(n) * 1e-9, 3)
            F = np.arange(3*n).reshape(-1, 3)
        elif kind == 'diagonal':
            y = np.arange(n) / max(n, 1) * 2 - 1
            V = np.stack([np.c_[np.full(n, -2), y - 1.4, np.zeros(n)],
                          np.c_[np.full(n, 2), y + 1.4, np.zeros(n)],
                          np.c_[np.full(n, 2), y + 1.401, np.zeros(n)]], 1).reshape(-1, 3)
            F = np.arange(3*n).reshape(-1, 3)
        elif kind == 'slivers':
            V = np.stack([np.c_[x, np.full(n, -1.4), np.zeros(n)],
                          np.c_[x + 1e-5, np.full(n, 1.4), np.zeros(n)],
                          np.c_[x + 0.01, np.full(n, 1.4), np.zeros(n)]], 1).reshape(-1, 3)
            F = np.arange(3*n).reshape(-1, 3)
        else:
            V = np.tile([[-2, -1.4, 0], [2, -1.4, 0], [2, 1.4, 0], [-2, 1.4, 0]], (n, 1)).astype(float)
            V[:, 2] -= np.repeat(np.arange(n) * 0.02, 4)
            F = (np.tile([[0, 1, 2], [0, 2, 3]], (n, 1)) + np.repeat(np.arange(n) * 4, 2)[:, None])
        segments = [segment(0, [[-1.5, 0, -1000], [1.5, 0, -1000]])]
    elif kind == 'camera':
        distance = 1 / n
        V = np.array([[-1, -0.7, 0], [1, -0.7, 0], [1, 0.7, 0], [-1, 0.7, 0]], float)
        V[:, :2] *= 8 / distance
        V[:, 2] = 8 - distance
        data['meshes']['origin'][2] = -8
        data['view'].update(projection='perspective', focal=8, near=0.001, shift=0)
        data['view']['xform'][2][3] = -8
        segments = [segment(0, [[-0.5 * 8 / distance, 0, -distance], [0.5 * 8 / distance, 0, -distance]])]
    elif kind in ('frame', 'frame_min'):
        req['frame'] = dict(w_pt=n, h_pt=n * 0.6)
        req['scale'] = 10000
        data['view']['pt_per_unit'] /= 100
        if kind == 'frame_min':
            V, F = np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
            segments = [segment(0, [[-1, 0, -1000], [1, 0, -1000]])]
        else:
            segments = [segment(0, [[-1, 0, -1000], [1, 0, -1000]])]
    if kind == 'weld' or kind in ('slivers', 'diagonal') and n <= 2:
        segments = []
    if segments:
        objects[0]['kind'] = 'brep' if len(F) else 'curve'
    data.update(objects=objects, segments=segments)
    data['meshes'].update(vertices=len(V), triangles=len(F), items=items or [dict(o=0, v0=0, nv=len(V), f0=0, nf=len(F))])
    (folder / 'meshes.bin').write_bytes(V.astype('<f4').tobytes() + F.astype('<i4').tobytes())
    (folder / 'scene.json').write_text(json.dumps(data, separators=(',', ':')))
    (folder / 'request.json').write_text(json.dumps(req))
    return dict(triangles=len(F), objects=len(objects), segments=sum(len(s['pts']) - 1 for s in segments),
                frame=req['frame'])


class Usage(ctypes.Structure):
    _fields_ = [('uuid', ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in (
        'user', 'system', 'pkg_idle', 'interrupt', 'pageins', 'wired', 'resident', 'phys_footprint', 'start', 'exit',
        'c_user', 'c_system', 'c_pkg_idle', 'c_interrupt', 'c_pageins', 'c_elapsed', 'io_read', 'io_written',
        'q_default', 'q_maintenance', 'q_background', 'q_utility', 'q_legacy', 'q_user_initiated', 'q_user_interactive',
        'billed_system', 'serviced_system', 'logical_writes', 'lifetime_max_phys_footprint', 'instructions', 'cycles',
        'billed_energy', 'serviced_energy', 'interval_max_phys_footprint', 'runnable')]


def worker(req, profile=False, deadline=585):
    match = re.fullmatch(r'perf-(.+)-(\d+)', json.loads(req.read_text())['id'])
    results = req.parent.parent / 'results.json'
    if match and results.exists():
        kind, size = match[1], int(match[2])
        prior = {}
        for row in json.loads(results.read_text()):
            if row.get('kind') == kind and row.get('n', size) < size and row['status'] == 'PASS':
                prior.setdefault(row['n'], []).append(row['wall'])
        paired = sorted((n, sum(values) / len(values)) for n, values in prior.items() if len(values) >= 2)
        if len(paired) >= 2 and paired[-1][1] >= 30:
            (n0, t0), (n1, t1) = paired[-2:]
            exponent = max(1, math.log(t1 / t0) / math.log(n1 / n0))
            predicted = t1 * (size / n1) ** exponent
            if predicted > deadline + 5:
                print('PERF_RESULT ' + json.dumps(dict(status='SKIP', returncode=124,
                      reason=f'paired-size extrapolation {predicted:.1f}s exceeds {deadline + 5:g}s budget')),
                      flush=True)
                sys.exit(124)
    sys.path.insert(0, str(ROOT))
    import ezdxf
    from numba.core import event
    from hiddenlines import hidden
    ezdxf.options.write_fixed_meta_data_for_testing = True
    floor = {}
    read_scene = hidden.read_scene
    def read(folder):
        scene, V, F, owners = read_scene(folder)
        floor['parsed_arrays_bytes'] = V.nbytes + F.nbytes + owners.nbytes
        floor['scene_json_bytes'] = (folder / 'scene.json').stat().st_size
        return scene, V, F, owners
    hidden.read_scene = read
    tris_init = hidden.Tris.__init__
    def init(tris, *args, **kwargs):
        tris_init(tris, *args, **kwargs)
        floor['tris_arrays_bytes'] = sum(v.nbytes for v in vars(tris).values() if isinstance(v, np.ndarray))
    hidden.Tris.__init__ = init
    phases = {}
    progress = (req.parent / 'progress.jsonl').open('w')
    phase_lines = {i + 1: m[1] for i, line in enumerate(Path(hidden.__file__).read_text().splitlines())
                   if (m := re.search(r"report\['seconds'\]\['(\w+)'\] =", line))}
    import types
    def phase_time():
        now = time.time()
        frame = sys._getframe(1)
        if frame.f_code is hidden.build.__code__ and frame.f_lineno in phase_lines:
            phase = phase_lines[frame.f_lineno]
            record = dict(elapsed=time.monotonic() - start)
            if phase == 'total':
                record['engine_seconds'] = dict(frame.f_locals['report']['seconds'],
                                                total=round(now - frame.f_locals['T0'], 2))
            if sys.platform == 'darwin':
                usage = Usage()
                status = ctypes.CDLL('/usr/lib/libproc.dylib').proc_pid_rusage(os.getpid(), 4, ctypes.byref(usage))
                if status == 0:
                    record.update(footprint_bytes=int(usage.phys_footprint), peak_bytes=int(usage.lifetime_max_phys_footprint))
            phases[phase] = record
            line = 'PERF_PHASE ' + json.dumps(dict(phase=phase, **record))
            print(line, flush=True)
            progress.write(line + '\n')
            progress.flush()
        return now
    hidden.time = types.SimpleNamespace(time=phase_time)
    compiles = []
    class Compile(event.Listener):
        depth = 0
        def on_start(self, evt):
            evt.data['_perf_start'] = time.monotonic()
            evt.data['_perf_depth'] = self.depth
            self.depth += 1
        def on_end(self, evt):
            self.depth -= 1
            compiles.append(dict(function=evt.data['dispatcher'].py_func.__qualname__,
                                 seconds=time.monotonic() - evt.data['_perf_start'], depth=evt.data['_perf_depth']))
    start = time.monotonic()
    import faulthandler
    faulthandler.dump_traceback_later(deadline)
    queries = {}
    collections = []
    if profile:
        import gc
        import shapely
        gc_start = {}
        def collection(phase, info):
            if phase == 'start':
                caller = sys._getframe(1)
                gc_start.update(time=time.monotonic(), at=f'{Path(caller.f_code.co_filename).name}:{caller.f_lineno}')
            elif gc_start:
                collections.append(dict(seconds=time.monotonic() - gc_start['time'], at=gc_start['at'],
                                        generation=info['generation']))
        gc.callbacks.append(collection)
        query = shapely.STRtree.query
        def counted(tree, *args, **kwargs):
            pairs = query(tree, *args, **kwargs)
            caller = sys._getframe(1)
            key = f'{Path(caller.f_code.co_filename).name}:{caller.f_lineno}:{caller.f_code.co_name}'
            count = pairs.shape[-1]
            row = queries.setdefault(key, dict(calls=0, pairs=0, max_pairs=0))
            row.update(calls=row['calls'] + 1, pairs=row['pairs'] + count, max_pairs=max(row['max_pairs'], count))
            return pairs
        shapely.STRtree.query = counted
    with event.install_listener('numba:compile', Compile()):
        if profile:
            import cProfile
            profiler = cProfile.Profile()
            profiler.enable()
        rc = hidden.main([str(req)])
        if profile:
            profiler.disable()
            profiler.dump_stats(str(req.parent / 'profile.pstats'))
            gc.callbacks.remove(collection)
    faulthandler.cancel_dump_traceback_later()
    progress.close()
    result = dict(returncode=rc, wall=time.monotonic() - start, compiles=compiles, floor=floor, phases=phases)
    if profile:
        result['queries'] = queries
        result['collections'] = collections
    if sys.platform == 'darwin':
        usage = Usage()
        status = ctypes.CDLL('/usr/lib/libproc.dylib').proc_pid_rusage(os.getpid(), 4, ctypes.byref(usage))
        result.update(footprint_bytes=int(usage.lifetime_max_phys_footprint) if status == 0 else None,
                      footprint_status=status)
    result['rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result['cpu_seconds'] = usage.ru_utime + usage.ru_stime
    print('PERF_RESULT ' + json.dumps(result), flush=True)


def system_cpu():
    if sys.platform != 'darwin':
        return None
    lib = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
    ticks = (ctypes.c_uint32 * 4)()
    count = ctypes.c_uint32(4)
    if lib.host_statistics(lib.mach_host_self(), 3, ctypes.byref(ticks), ctypes.byref(count)) == 0:
        return list(ticks)


def draw(folder, cache, timeout, profile=False):
    env = dict(os.environ, NUMBA_CACHE_DIR=str(cache), NUMBA_NUM_THREADS='14', PYTHONDONTWRITEBYTECODE='1')
    argv = [sys.executable, '-B', str(HERE / 'perf.py'), '--worker', str(folder / 'request.json')]
    argv += ['--deadline', str(max(0.1, timeout - 5))]
    if profile:
        argv.append('--profile')
    start = time.monotonic()
    load = os.getloadavg()
    cpu_start = system_cpu()
    p = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        (folder / 'last-run.log').write_text(out + err)
        return dict(status='SKIP', reason=f'timeout {timeout}s', elapsed=time.monotonic()-start,
                    load_start=load, load_end=os.getloadavg(), stderr=err,
                    phases=[json.loads(line[11:]) for line in out.splitlines() if line.startswith('PERF_PHASE ')])
    result = dict(status='PASS' if p.returncode == 0 else 'FAIL', returncode=p.returncode,
                  elapsed=time.monotonic()-start, load_start=load, load_end=os.getloadavg(), stderr=err)
    for line in out.splitlines():
        if line.startswith('PERF_RESULT '):
            result.update(json.loads(line[12:]))
    cpu_end = system_cpu()
    if cpu_start is not None and cpu_end is not None:
        delta = [(b - a) % 2**32 for a, b in zip(cpu_start, cpu_end)]
        if sum(delta):
            busy = 1 - delta[2] / sum(delta)
            result['system_busy_percent'] = 100 * busy
            if 'cpu_seconds' in result:
                result['other_busy_percent_estimate'] = 100 * (busy - result['cpu_seconds'] / (result['elapsed'] * os.cpu_count()))
    req = json.loads((folder / 'request.json').read_text())
    report = folder / (req['id'] + '-report.json')
    if p.returncode == 0:
        data = json.loads(report.read_text())
        result.update(engine_seconds=data['seconds'], counts=data['counts'])
        result['sha256'] = {ext: hashlib.sha256((folder / (req['id'] + ext)).read_bytes()).hexdigest()
                            for ext in ('.svg', '.dxf', '.ai')}
    (folder / 'last-run.log').write_text(out + err)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', choices=['perf'], required=True)
    parser.add_argument('--sizes', action='append', default=[], metavar='KIND=N,N')
    parser.add_argument('--only', default='.*')
    parser.add_argument('--out', type=Path, default=Path(tempfile.gettempdir()) / 'hl-perf')
    parser.add_argument('--timeout', type=float, default=590)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--real', type=Path, action='append', default=[])
    parser.add_argument('--first-run', action='store_true')
    args = parser.parse_args()
    if not 0 < args.timeout < 600 or args.repeats < 2:
        parser.error('timeout must be in (0,600); repeats must be at least two')
    sizes = dict(DEFAULTS)
    for value in args.sizes:
        try:
            kind, values = value.split('=')
            sizes[kind] = sorted(set(int(v) for v in values.split(',')))
            if kind not in DEFAULTS or min(sizes[kind]) <= 0:
                raise ValueError
        except ValueError:
            parser.error(f'invalid --sizes {value!r}')
    args.out.mkdir(parents=True, exist_ok=True)
    rows_path = args.out / 'results.json'
    rows = json.loads(rows_path.read_text()) if rows_path.exists() else []
    def record(row):
        rows.append(row)
        rows_path.write_text(json.dumps(rows, indent=1))
        print(json.dumps({k: v for k, v in row.items() if k not in ('sha256', 'compiles', 'stderr', 'phases', 'queries', 'collections')}), flush=True)
    for kind, ns in sizes.items():
        if not re.search(args.only, kind):
            continue
        blocked = False
        for n in ns:
            folder = args.out / f'{kind}-{n}'
            existing = [r for r in rows if r.get('kind') == kind and r.get('n') == n]
            if len(existing) >= args.repeats:
                blocked |= any(r['status'] != 'PASS' for r in existing)
                continue
            if blocked:
                record(dict(kind=kind, n=n, status='SKIP', reason='smaller size exceeded the run budget or failed'))
                continue
            inputs = write(folder, kind, n)
            for repeat in range(len(existing), args.repeats):
                result = draw(folder, args.out / 'numba', args.timeout, args.profile)
                record(dict(kind=kind, n=n, repeat=repeat, inputs=inputs, **result))
                blocked |= result['status'] != 'PASS'
    for source in args.real:
        folder = args.out / ('real-' + source.parent.name + '-' + source.name)
        folder.mkdir(exist_ok=True)
        req = json.loads((source / 'request.json').read_text())
        req['out'] = '.'
        (folder / 'request.json').write_text(json.dumps(req))
        for name in ('scene.json', 'meshes.bin'):
            if not (folder / name).exists():
                shutil.copyfile(source / name, folder / name)
        for repeat in range(args.repeats):
            cache = args.out / f'cold-{source.parent.name}-{source.name}-{repeat}' if args.first_run else args.out / 'numba'
            modes = ('cold', 'warm') if args.first_run else ('warm',)
            for mode in modes:
                if any(r.get('source') == str(source) and r.get('repeat') == repeat and r.get('mode') == mode for r in rows):
                    continue
                if mode == 'cold' and cache.exists():
                    shutil.rmtree(cache)
                record(dict(kind='real', source=str(source), repeat=repeat, mode=mode,
                            **draw(folder, cache, args.timeout, args.profile)))
    return int(any(r['status'] == 'FAIL' for r in rows))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        worker(Path(sys.argv[2]), '--profile' in sys.argv,
               float(sys.argv[sys.argv.index('--deadline') + 1]) if '--deadline' in sys.argv else 585)
    else:
        sys.exit(main())
