"""HL tests. Run with python3 kit.py test; exits 1 if any check fails."""
import collections, contextlib, hashlib, io, json, math, os, re, shutil, subprocess, sys, tempfile, types
from pathlib import Path
import xml.etree.ElementTree as ET_

KIT = Path(__file__).resolve().parent.parent
FX = KIT / 'tests' / 'fixtures'
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / 'rhino'))
from archkit import lint
from archkit.project import load, merge
from archkit.draw import Drawing as HDrawing_

fails = []
if 'ok' not in globals():
    def ok(cond, msg):
        print(('ok    ' if cond else 'FAIL  ') + msg)
        if not cond:
            fails.append(msg)

def load_hidden_lines(script=None):
    """rhino/hidden_lines.py, or script, run with stand-ins for Rhino's modules, for its parts that need no Rhino: its
    namespace as a module"""
    import sys, types
    from pathlib import Path
    script = Path(script or KIT / 'rhino' / 'hidden_lines.py')
    names = ('Rhino', 'Rhino.Geometry', 'Rhino.Geometry.Intersect', 'scriptcontext')
    modules = {name: types.ModuleType(name) for name in names}
    modules['Rhino'].Geometry = modules['Rhino.Geometry']
    modules['Rhino.Geometry'].Intersect = modules['Rhino.Geometry.Intersect']
    modules['Rhino.Geometry.Intersect'].Intersection = types.SimpleNamespace()
    previous = {name: sys.modules.get(name) for name in names}
    export = types.ModuleType('hidden_lines')
    export.__file__ = str(script)
    try:
        sys.modules.update(modules)
        exec(compile(script.read_text(encoding='utf-8'), str(script), 'exec'), export.__dict__)
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return export


def power_throttling_tests():
    import ctypes
    import runpy
    from unittest.mock import Mock, patch

    entry = runpy.run_path(str(KIT / 'kit.py'))
    main = entry['main']
    events = []
    handle = 0x123456789

    def set_information(process, kind, pointer, size):
        state = pointer._obj
        events.append((process, kind, size, state.Version, state.ControlMask, state.StateMask))
        return 1

    kernel = types.SimpleNamespace(GetCurrentProcess=Mock(return_value=handle),
                                   SetProcessInformation=Mock(side_effect=set_information))
    drawing = types.ModuleType('hiddenlines.hidden')
    drawing.main = lambda args: events.append(('draw', args)) or 0
    with patch.dict(main.__globals__, ensure=lambda *args: None), \
            patch.dict(sys.modules, {'hiddenlines.hidden': drawing}), \
            patch.object(ctypes, 'WinDLL', return_value=kernel, create=True) as dll:
        with patch.object(sys, 'platform', 'win32'):
            result = main(['hidden-lines', 'request.json'])
        ok(result == 0 and events == [(handle, 4, 12, 1, 1, 0), ('draw', ['request.json'])],
           'power-throttling: Windows opts out of execution-speed throttling before drawing with a 64-bit handle')
        ok(dll.call_args.args == ('kernel32',) and kernel.GetCurrentProcess.restype is ctypes.c_void_p
           and kernel.SetProcessInformation.argtypes == [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32],
           'power-throttling: the Windows API has explicit pointer-sized handle and argument types')
        for platform in ('darwin', 'linux'):
            events.clear()
            dll.reset_mock()
            with patch.object(sys, 'platform', platform):
                main(['hidden-lines', 'request.json'])
            ok(not dll.called and events == [('draw', ['request.json'])],
               f'power-throttling: {platform} draws without loading the Windows API')
        with patch.object(sys, 'platform', 'win32'):
            kernel.SetProcessInformation.side_effect = None
            kernel.SetProcessInformation.return_value = 0
            ok(main(['hidden-lines', 'request.json']) == 0,
               'power-throttling: a refused opt-out does not fail the drawing')
            for error in (OSError('access denied'), AttributeError('SetProcessInformation')):
                kernel.SetProcessInformation.side_effect = error
                ok(main(['hidden-lines', 'request.json']) == 0,
                   f'power-throttling: {type(error).__name__} does not fail the drawing')


power_throttling_tests()


def kit_dir_tests():
    import os
    from unittest.mock import patch
    export = load_hidden_lines()
    ok(os.path.realpath(export.kit_dir()) == os.path.realpath(str(KIT)),
       'hl: the export runs the kit.py of the folder above it when nothing names another')
    export.KIT_ROOT = '/somewhere/a-kit'
    ok(export.kit_dir() == '/somewhere/a-kit', 'hl: a KIT_ROOT the running script names is the kit it draws with')
    with patch.object(export.sys, 'platform', 'darwin'):
        mac = export.mac_malloc({})
        kept = export.mac_malloc({'MallocLargeCache': '1'})
    with patch.object(export.sys, 'platform', 'win32'):
        win = export.mac_malloc({})
    ok(mac == {'MallocLargeCache': '0'} and kept == {'MallocLargeCache': '1'} and win == {},
       "hl: on a Mac the drawing starts with malloc's large cache off unless the user set it, and elsewhere as it was")


kit_dir_tests()


def export_mesh_tests():
    import array
    import itertools
    import numpy as np

    scalar, batched = load_hidden_lines(), load_hidden_lines()
    scalar.np = None

    class Vertices(list):
        def ToPoint3dArray(self):
            return self

    class Faces(list):
        def ConvertQuadsToTriangles(self):
            pass

    class Mesh:
        def __init__(self, vertices, faces):
            self.Vertices = Vertices(types.SimpleNamespace(X=float(x), Y=float(y), Z=float(z)) for x, y, z in vertices)
            self.Faces = Faces(types.SimpleNamespace(A=int(a), B=int(b), C=int(c)) for a, b, c in faces)

        def DuplicateMesh(self):
            return self

    class Transform:
        def __init__(self, rows):
            self.rows = rows

        def __getitem__(self, ij):
            return float(self.rows[ij])

    point = lambda p: types.SimpleNamespace(X=float(p[0]), Y=float(p[1]), Z=float(p[2]))
    theta = 0.31
    camera = np.array([[np.cos(theta), -np.sin(theta), 0., 2.],
                       [np.sin(theta), np.cos(theta), 0., -3.], [0., 0., 1., -5.]])
    planes = [((0., 0., 0.), (1., 0., 0.)), ((0., -1., 0.), (0.3, 0.4, 0.5))]

    def state(mesh, planes, perspective, xf):
        return dict(objs=[dict(kind='mesh', geom=mesh)], planes=[(point(p), point(n)) for p, n in planes],
                    persp=dict(L=17., shift=1.2, near=0.25) if perspective else None, xf=Transform(xf),
                    origin=(0.125, -0.25, -78740.), mesh_v=array.array('f'), mesh_f=array.array('i'), mesh_items=[])

    def compare(mesh, planes, perspective, xf=camera):
        a, b = state(mesh, planes, perspective, xf), state(mesh, planes, perspective, xf)
        V = np.array([(p.X, p.Y, p.Z) for p in mesh.Vertices], dtype=np.float64).reshape(-1, 3)
        F = np.array([(f.A, f.B, f.C) for f in mesh.Faces], dtype=np.int32).reshape(-1, 3)
        for repeat in range(2):
            scalar.mesh_one(a, 0, None)
            batched.mesh_tail(b, 0, V, F)
            if (a['mesh_v'].tobytes() != b['mesh_v'].tobytes()
                    or a['mesh_f'].tobytes() != b['mesh_f'].tobytes()
                    or a['mesh_items'] != b['mesh_items']):
                return False
        return (b['mesh_v'].typecode == 'f' and b['mesh_f'].typecode == 'i'
                and V.dtype == np.float64 and F.dtype == np.int32
                and V.shape == (len(mesh.Vertices), 3) and F.shape == (len(mesh.Faces), 3))

    rng = np.random.default_rng(805)
    for scale in (1e-9, 1., 1e9):
        tris = rng.normal(size=(3000, 3, 3)) * scale
        boundary = np.array([[(s, i, 0.) for i, s in enumerate(signs)]
                             for signs in itertools.product((-1., -0., 0., 1.), repeat=3)]) * scale
        tris = np.concatenate([tris, boundary, np.zeros((1, 3, 3))])
        expected = np.array([t for tri in tris.tolist() for t in scalar.clip_tri(tri, lambda p: p[0])],
                            dtype=np.float64).reshape(-1, 3, 3)
        got = batched.clip_batch(tris, tris[..., 0])
        ok(expected.tobytes() == got.tobytes(),
           f'export-mesh: float64 clipping and fan order at scale {scale:g}, including signed zeros and degeneracy')
    for count in (0, 1, 257, 33001):
        for scale in (1e-9, 1., 1e9):
            tris = (rng.normal(size=(count, 1, 3)) + rng.normal(0., 0.1, size=(count, 3, 3))) * scale
            mesh = Mesh(tris.reshape(-1, 3), np.arange(count * 3).reshape(-1, 3))
            results = [compare(mesh, planes[:n], perspective) for n in (0, 1, 2) for perspective in (False, True)]
            ok(all(results), f'export-mesh: {count} triangles at scale {scale:g}, 0/1/2 planes, parallel/perspective, '
               f'frame shift and appended offsets: {results}')

    boundary = np.array([[(x, i, z) for i, (x, z) in enumerate(zip(signs, depths))]
                         for signs in itertools.product((-1., -0., 0., 1.), repeat=3)
                         for depths in itertools.product((-0.25, np.nextafter(-0.25, -np.inf),
                                                          np.nextafter(-0.25, np.inf)), repeat=3)])
    boundary = np.concatenate([boundary, np.zeros((1, 3, 3)), np.full((1, 3, 3), 2.)])
    mesh = Mesh(boundary.reshape(-1, 3), np.arange(len(boundary) * 3).reshape(-1, 3))
    results = [compare(mesh, planes[:n], perspective, np.eye(4)) for n in (0, 1, 2) for perspective in (False, True)]
    ok(all(results), f'export-mesh: vertices on the model and near planes, one ulp either side, signed zeros, '
       f'degenerate and fully discarded triangles: {results}')
    mesh = Mesh([(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (2, 3, -4)],
                [(0, 1, 2), (0, 2, 3), (0, 0, 1)])
    results = [compare(mesh, planes[:n], perspective) for n in (0, 1, 2) for perspective in (False, True)]
    ok(all(results), f'export-mesh: shared and unused vertices and degenerate faces: {results}')

    st = state(mesh, [], False, camera)
    arrays = (np.array([(p.X, p.Y, p.Z) for p in mesh.Vertices], dtype=np.float64).reshape(-1, 3),
              np.array([(f.A, f.B, f.C) for f in mesh.Faces], dtype=np.int32).reshape(-1, 3))
    calls = []

    def mesh_arrays(m):
        calls.append(m)
        return arrays

    batched.mesh_arrays = mesh_arrays
    batched.mesh_one(st, 0, None)
    expected = state(mesh, [], False, camera)
    scalar.mesh_one(expected, 0, None)
    ok(calls == [mesh] and st['mesh_v'].tobytes() == expected['mesh_v'].tobytes()
       and st['mesh_f'].tobytes() == expected['mesh_f'].tobytes() and st['mesh_items'] == expected['mesh_items'],
       'export-mesh: mesh_one dispatches through the replaceable mesh_arrays when numpy imports')

# ---------------------------------------------------------------- export cache

export_script = KIT / 'rhino' / 'hidden_lines.py'
export_cache = load_hidden_lines(export_script)
cache_key, cache_get, cache_put, cache_trim = [getattr(export_cache, name) for name in
                                             ('cache_key', 'cache_get', 'cache_put', 'cache_trim')]
with tempfile.TemporaryDirectory() as td:
    import inspect, time
    root = Path(td) / 'cache'
    key = cache_key('payload')
    payload = b'contact curves\x00\xff'
    cache_put(root, key, payload)
    entry = root / key[:2] / key
    ok(cache_get(root, key) == payload and entry.read_bytes() == b'HLC1' + hashlib.sha256(payload).digest() + payload,
       'export-cache: a put and get round-trip with the header and payload digest')
    ok(cache_get(root, cache_key('missing')) is None, 'export-cache: a missing key is a miss')
    for label, data in (('empty', b''), ('5 MB', b'x' * (5 * 1024 ** 2))):
        k = cache_key(label)
        cache_put(root, k, data)
        ok(cache_get(root, k) == data, f'export-cache: {label} payload round-trips')

    parts = ['contacts', 1, 0.5, ['id', 2, 1.25]]
    changed = [['checks', 1, 0.5, ['id', 2, 1.25]], ['contacts', 2, 0.5, ['id', 2, 1.25]],
               ['contacts', 1, math.nextafter(0.5, math.inf), ['id', 2, 1.25]],
               ['contacts', 1, 0.5, ['id', 2, math.nextafter(1.25, math.inf)]]]
    expected = hashlib.sha256(json.dumps(parts, separators=(',', ':')).encode('utf-8')).hexdigest()
    ok(cache_key(*parts) == cache_key(*json.loads(json.dumps(parts))) == expected
       and all(cache_key(*p) != expected for p in changed),
       'export-cache: keys are stable SHA-256 of compact JSON and distinguish parts and floats one ulp apart')

    for label in ('payload byte', 'digest byte', 'truncated file', 'header'):
        cache_put(root, key, payload)
        damaged = bytearray(entry.read_bytes())
        if label in ('payload byte', 'digest byte'):
            damaged[36 if label == 'payload byte' else 4] ^= 1
        elif label == 'truncated file':
            del damaged[12:]
        else:
            damaged[:4] = b'OTHER'[:4]
        entry.write_bytes(damaged)
        ok(cache_get(root, key) is None and not entry.exists(),
           f'export-cache: {label} corruption is a miss and removed')

    lru_root = Path(td) / 'lru'
    keys = [cache_key('lru', i) for i in range(4)]
    paths = [lru_root / k[:2] / k for k in keys]
    now = time.time()
    for i, (k, p) in enumerate(zip(keys, paths)):
        cache_put(lru_root, k, b'x' * 64)
        os.utime(p, (now - 400 + i * 100, now - 400 + i * 100))
    ok(cache_trim(lru_root, limit=300, now=now) == (2, 200)
       and [p.exists() for p in paths] == [False, False, True, True],
       'export-cache: trim removes the least recently used down to three quarters of the byte limit')

    refresh_root = Path(td) / 'refresh'
    for i, k in enumerate(keys[:2]):
        cache_put(refresh_root, k, b'x' * 64)
        os.utime(refresh_root / k[:2] / k, (now - 200 + i * 100, now - 200 + i * 100))
    hit = cache_get(refresh_root, keys[0])
    refreshed = (refresh_root / keys[0][:2] / keys[0]).stat().st_mtime
    ok(hit == b'x' * 64 and refreshed >= now and cache_trim(refresh_root, limit=150) == (1, 100)
       and (refresh_root / keys[0][:2] / keys[0]).exists()
       and not (refresh_root / keys[1][:2] / keys[1]).exists(),
       'export-cache: a get refreshes modification time and keeps the just-read entry when trimming to one')

    tie_root = Path(td) / 'ties'
    for k in keys[:2]:
        cache_put(tie_root, k, b'x' * 64)
        os.utime(tie_root / k[:2] / k, (now, now))
    ok(cache_trim(tie_root, limit=150, now=now) == (1, 100)
       and not (tie_root / min(keys[:2])[:2] / min(keys[:2])).exists(),
       'export-cache: equal modification times are evicted by name')

    age_root = Path(td) / 'age'
    for i, k in enumerate(keys[:2]):
        cache_put(age_root, k, b'x' * 64)
        age = (90 * 24 * 3600 + 1) if i == 0 else (90 * 24 * 3600 - 1)
        os.utime(age_root / k[:2] / k, (now - age, now - age))
    stale = age_root / keys[0][:2] / '.123-dead.tmp'
    fresh = stale.with_name('.123-live.tmp')
    stale.write_bytes(b'partial')
    fresh.write_bytes(b'partial')
    os.utime(stale, (now - 3601, now - 3601))
    os.utime(fresh, (now - 3599, now - 3599))
    ok(cache_trim(age_root, now=now) == (2, 100) and not stale.exists() and fresh.exists()
       and not (age_root / keys[0][:2] / keys[0]).exists() and (age_root / keys[1][:2] / keys[1]).exists(),
       'export-cache: trim removes entries over 90 days and hour-old temporary files, keeping fresh ones')
    with open(age_root / '.lock', 'a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        ok(cache_trim(age_root, limit=0) == (0, None) and (age_root / keys[1][:2] / keys[1]).exists(),
           'export-cache: trim does nothing while another open file holds the lock')

    blocked_root = Path(td) / 'blocked'
    blocked_root.mkdir()
    blocker = blocked_root / key[:2]
    blocker.write_bytes(b'not a folder')
    cache_put(blocked_root, key, payload)
    ok(list(blocked_root.iterdir()) == [blocker] and blocker.read_bytes() == b'not a folder',
       'export-cache: an unwritable subfolder raises nothing and leaves no temporary file')

    worker = Path(td) / 'writers.py'
    worker.write_text(inspect.getsource(load_hidden_lines) + '''
import multiprocessing, sys

def write_entries(script, root, barrier, i):
    cache = load_hidden_lines(script)
    barrier.wait(timeout=10)
    for _ in range(8):
        cache.cache_put(root, cache.cache_key('shared'), b'shared' * 1024)
        cache.cache_put(root, cache.cache_key('worker', i), str(i).encode() * 32768)

if __name__ == '__main__':
    ctx = multiprocessing.get_context('spawn')
    barrier = ctx.Barrier(4)
    processes = [ctx.Process(target=write_entries, args=(sys.argv[1], sys.argv[2], barrier, i)) for i in range(4)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        if process.is_alive():
            process.terminate()
            process.join()
    sys.exit(0 if all(process.exitcode == 0 for process in processes) else 1)
''', encoding='utf-8')
    concurrent_root = Path(td) / 'concurrent'
    writers = subprocess.run([sys.executable, '-B', str(worker), str(export_script), str(concurrent_root)],
                             capture_output=True, text=True, timeout=20)
    ok(writers.returncode == 0 and cache_get(concurrent_root, cache_key('shared')) == b'shared' * 1024
       and all(cache_get(concurrent_root, cache_key('worker', i)) == str(i).encode() * 32768 for i in range(4))
       and not list(concurrent_root.rglob('*.tmp')),
       'export-cache: four spawned processes write shared and own keys atomically without temporary files'
       + (': ' + writers.stderr if writers.returncode else ''))
export_mesh_tests()

# ---------------------------------------------------------------- hidden lines
# the exports in fixtures/hidden-lines are rhino/hidden_lines.py's, recorded in Rhino 8 from the scenes
# fixtures/hidden-lines/make_scenes.py builds; each scene is drawn in a copy of its folder
from hiddenlines import hidden as hl_
from shapely.geometry import LineString as HLine_, Point as HPoint_, Polygon as HPoly_, MultiLineString as HMulti_

def hl_draw_(scene, edit=None, req=None):
    """a scene drawn in a temporary copy, edit(scene_json) changing its export first and req (a dict) added to its
    request: (drawing, report, svg, dxf, folder)"""
    td_ = Path(tempfile.mkdtemp(prefix='hl-'))
    for f_ in ('request.json', 'scene.json', 'meshes.bin'):
        shutil.copy(FX / 'hidden-lines' / scene / f_, td_ / f_)
    if req:
        (td_ / 'request.json').write_text(json.dumps(dict(json.loads((td_ / 'request.json').read_text()), **req)))
    if edit:
        s_ = json.loads((td_ / 'scene.json').read_text())
        edit(s_)
        (td_ / 'scene.json').write_text(json.dumps(s_))
    d_, rep_ = hl_.build(td_ / 'request.json')
    req_ = json.loads((td_ / 'request.json').read_text())
    W_, H_ = req_['frame']['w_pt'], req_['frame']['h_pt']
    d_.to_svg(td_ / 'out.svg', canvas=(W_, H_), origin=(0.0, H_))
    d_.to_dxf(td_ / 'out.dxf')
    return d_, rep_, td_ / 'out.svg', td_ / 'out.dxf', td_

def hl_page_(td, p):
    """a model point on the page, in points from the top-left, y down"""
    s_ = json.loads((td / 'scene.json').read_text())
    v_ = s_['view']
    M_ = v_['xform']
    kf_ = v_['pt_per_unit'] * v_['true_factor']
    req_ = json.loads((td / 'request.json').read_text())
    x_, y_, z_ = (sum(M_[i][j] * v for j, v in enumerate(list(p) + [1])) for i in range(3))
    if v_.get('projection') == 'perspective':
        x_, y_ = v_['focal'] * x_ / -z_, v_['focal'] * y_ / -z_ - v_['shift']
    return (req_['frame']['w_pt'] / 2 + x_ * kf_, req_['frame']['h_pt'] / 2 - y_ * kf_)

def hl_lines_(svg, layers=None):
    """the drawn lines of an SVG as one shapely geometry"""
    data_ = lint.read_svg(svg)
    return HMulti_([[a, b] for p in data_['paths'] for a, b in p.segs
                    if p.stroke != 'none' and (layers is None or p.layer in layers) and p.layer not in ('GROUND',)])

def hl_drawn_(lines, td, a, b, tol=0.15):
    """the share of the model segment ab that a drawn line runs along, within tol pt"""
    pa, pb = hl_page_(td, a), hl_page_(td, b)
    n_ = 40
    pts_ = [HPoint_(pa[0] + (pb[0] - pa[0]) * (i + 0.5) / n_, pa[1] + (pb[1] - pa[1]) * (i + 0.5) / n_) for i in range(n_)]
    return sum(1 for q in pts_ if lines.distance(q) <= tol) / n_

hl_scenes_ = ['touching', 'coplanar', 'tjunction', 'open', 'roof', 'cut-box', 'cut-lwall', 'cut-rooms', 'persp', 'persp-aim',
              'persp-cut', 'bad', 'twisted']
hl_out_ = {}
for sc_ in hl_scenes_:
    d_, rep_, svg_, dxf_, td_ = hl_draw_(sc_)
    hl_out_[sc_] = (d_, rep_, svg_, dxf_, td_)
    tk_ = load(svg_)
    fs_ = lint.check(lint.read_svg(svg_), tk_)
    fd_ = lint.check(lint.read_dxf(dxf_, None), tk_)
    errs_ = [m for lv, _, m, _ in fs_ + fd_ if lv == 'error']
    warns_ = [k for lv, k, m, _ in fs_ + fd_ if lv == 'warning' and k not in ('double', 'beside')]
    ok(not errs_ and not warns_, f'hidden-lines: the {sc_} scene\'s SVG and DXF lint with no errors and no warnings but doubles'
       + ('' if not errs_ + warns_ else ': ' + '; '.join(errs_[:2] + warns_[:2])))

# every line end not on the frame is a vertex of another path, written with the same coordinates
d_, rep_, svg_, dxf_, td_ = hl_out_['tjunction']
data_ = lint.read_svg(svg_)
hl_req_ = json.loads((td_ / 'request.json').read_text())
verts_ = collections.Counter()
for p in data_['paths']:
    for v in set([p.segs[0][0]] + [b for a, b in p.segs]):
        verts_[v] += 1
ends_ = [e for p in data_['paths'] for e in p.ends() if 0.01 < e[0] < hl_req_['frame']['w_pt'] - 0.01 and 0.01 < e[1] < hl_req_['frame']['h_pt'] - 0.01]
ok(ends_ and all(verts_[e] >= 2 for e in ends_),
   f'hidden-lines: at T-junctions every one of {len(ends_)} line ends is a vertex of the line it meets, not within a tolerance of it')

# the box hides the wall's edges behind it and its outline is the heavy weight; creases are light
lines_ = hl_lines_(svg_)
subs_ = {(s['layer'], s['sublayer']): s['weight'] for s in rep_['sublayers']}
ok(subs_.get(('OUTLINE', 'front profiles')) == 'heavy' and subs_.get(('DETAIL', 'front creases')) == 'light'
   and all(w == 'fine' for (l_, n_), w in subs_.items() if l_ == 'CONTEXT'),
   'hidden-lines: the subject\'s profile is on OUTLINE at heavy and its creases light; context stays fine')
hl_box_ = [hl_page_(td_, (x, y, z)) for x in (5, 8) for y in (2, 5) for z in (0, 3)]
hl_hull_ = HMulti_([[a, b] for a in hl_box_ for b in hl_box_ if a != b]).convex_hull.buffer(-0.5)
ok(hl_lines_(svg_, ('CONTEXT',)).intersection(hl_hull_).length == 0
   and hl_drawn_(lines_, td_, (0.2, 6, 0), (2, 6, 0)) > 0.95 and hl_drawn_(lines_, td_, (14, 6, 0), (15.8, 6, 0)) > 0.95,
   'hidden-lines: the wall\'s lines stop at the box in front of them and run on past it')

# robustness: ends jittered by up to 0.4 of the grid, and one end pulled 0.3 pt back from the line it meets
import random as hl_random_
def hl_jitter_(s):
    r_ = hl_random_.Random(7)
    g_ = 0.4 * 0.05 / (s['view']['pt_per_unit'] * s['view']['true_factor'])
    for seg in s['segments']:
        for q in seg['pts']:
            q[0] += r_.uniform(-g_, g_)
            q[1] += r_.uniform(-g_, g_)
_, rep_j_, svg_j_, dxf_j_, _ = hl_draw_('tjunction', hl_jitter_)
ok(not [x for x in lint.check(lint.read_svg(svg_j_), load(svg_j_)) if x[0] == 'error'],
   'hidden-lines: ends jittered by up to 0.4 of the noding grid still meet their lines exactly')
def hl_pull_(s):
    kf = s['view']['pt_per_unit'] * s['view']['true_factor']
    for seg in s['segments']:
        P = seg['pts']
        L = math.dist(P[0][:2], P[-1][:2])
        if len(P) == 2 and seg['src'] == 'geom' and L * kf > 20 and not seg['scene']:
            u = ((P[0][0] - P[-1][0]) / L, (P[0][1] - P[-1][1]) / L)
            P[0][0] -= u[0] * 0.3 / kf
            P[0][1] -= u[1] * 0.3 / kf
            return
_, rep_p_, svg_p_, _, _ = hl_draw_('tjunction', hl_pull_)
ok(not [x for x in lint.check(lint.read_svg(svg_p_), load(svg_p_)) if x[0] == 'error']
   and any(f['kind'] == 'end cut back clear' and len(f['model']) == 3 for f in rep_p_['fixes']) and rep_p_['model']['off_pt'] == 0,
   'hidden-lines: a line end 0.3 pt short of the line it met, the model having nothing between, is cut back clear of it, '
   'nothing drawn off the model, and listed with its place in the model')
# six ends 0.3 pt short of one line: the first met splits it, and its halves stand for it for the ends after it in the
# round (the model's joists along a beam were met one a round, and those left over were near misses)
def hl_six_(s):
    kf = s['view']['pt_per_unit'] * s['view']['true_factor']
    wall = next(o['i'] for o in s['objects'] if o['layer'].endswith('::wall'))
    seg = max((g for g in s['segments'] if g['o'] == wall and len(g['pts']) == 2 and not g.get('vis')),
              key=lambda g: math.dist(g['pts'][0][:2], g['pts'][1][:2]))
    (ax, ay, az), (bx, by, bz) = seg['pts']
    L = math.hypot(bx - ax, by - ay)
    nx, ny = (by - ay) / L, -(bx - ax) / L
    for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        px, py, pz = ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz - az) * t
        s['segments'].append(dict(seg, pts=[[px + nx * 0.3 / kf, py + ny * 0.3 / kf, pz], [px + nx * 8 / kf, py + ny * 8 / kf, pz]]))
_, rep_6_, svg_6_, _, _ = hl_draw_('tjunction', hl_six_)
ok(not [x for x in lint.check(lint.read_svg(svg_6_), load(svg_6_)) if x[0] == 'error']
   and sum(1 for f in rep_6_['fixes'] if f['kind'] == 'end cut back clear' and 0.25 < f['length_pt'] < 0.4) == 6 and rep_6_['model']['off_pt'] == 0,
   'hidden-lines: six line ends 0.3 pt short of one line are all cut back clear of it, nothing drawn off the model')

# touching homes: one line on each shared wall, the base on the ground, no line lying on another
d_, rep_, svg_, dxf_, td_ = hl_out_['touching']
lines_ = hl_lines_(svg_)
dup_ = [x for x in lint.check(lint.read_svg(svg_), load(svg_)) if x[1] == 'duplicate']
ok(not dup_ and hl_drawn_(lines_, td_, (4, 0, 0), (4, 0, 3)) > 0.95 and hl_drawn_(lines_, td_, (8, 0, 3), (8, 6, 3)) > 0.95
   and hl_drawn_(lines_, td_, (4, 0, 3), (4, 6, 3)) > 0.95,
   'hidden-lines: touching homes\' shared walls are drawn on their faces and their roofs, each once')
ok(rep_['classes_pt'].get('seam', 0) > 0 and rep_['classes_pt'].get('base', 0) > 0 and rep_['classes_pt'].get('overlap', 0) > 0,
   'hidden-lines: the homes\' shared walls are seams, their foot on the ground a base, the taller home\'s edge against the roof behind an overlap')

# coplanar: a terrace on the roof and a gallery on the wall are seen and filled; each tint fills its own ground
d_, rep_, svg_, dxf_, td_ = hl_out_['coplanar']
data_ = lint.read_svg(svg_)
def hl_area_(td, pts):
    return HPoly_([hl_page_(td, p) for p in pts]).area
fills_ = collections.defaultdict(float)
for p in data_['paths']:
    if p.layer == 'GROUND' and p.fill:
        ring_ = [p.segs[0][0]] + [b for a, b in p.segs]
        fills_[p.fill.lower()] += HPoly_(ring_).area
acc_ = hl_area_(td_, [(1, 1.5, 6), (5, 1.5, 6), (5, 4.5, 6), (1, 4.5, 6)]) + hl_area_(td_, [(2, 0, 2), (8, 0, 2), (8, 0, 3.5), (2, 0, 3.5)])
ok(abs(fills_[load(svg_).hex('Accent').lower()] - acc_) < 0.01 * acc_,
   f'hidden-lines: the terrace on the roof and the gallery on the wall fill their exact projected area '
   f'({fills_[load(svg_).hex("Accent").lower()]:.1f} of {acc_:.1f} pt²)')
ok(fills_[load(svg_).hex('K20').lower()] > 0 and fills_[load(svg_).hex('K6').lower()] > 0,
   'hidden-lines: the paving and the lawn each take their own tint by source layer')
ok(all(p.stroke == 'none' for p in data_['paths'] if p.layer == 'GROUND'), 'hidden-lines: fills draw no outline of their own')

# open: an open porch roof hides the wall behind it; an open polysurface is reported
d_, rep_, svg_, dxf_, td_ = hl_out_['open']
lines_ = hl_lines_(svg_)
porch_ = HPoly_([hl_page_(td_, p) for p in [(0, 0.5, 2.2), (6, 0.5, 2.2), (6, 2, 2.6), (0, 2, 2.6)]]).buffer(-0.5)
ok(lines_.intersection(porch_).length == 0 and hl_drawn_(lines_, td_, (0, 0.5, 2.2), (6, 0.5, 2.2)) > 0.95,
   'hidden-lines: an open surface (a porch roof) hides what is behind it, and its edge is drawn')
ok(any('open polysurface: 4 naked edges' in i['issue'] for i in rep_['issues']),
   'hidden-lines: a box missing its top is reported as an open polysurface with its four naked edges')

# roof: a chimney through a roof is drawn where they meet, for the house joined by its key and the one left in parts;
# the sunk box's line on the ground and the trunk's foot are drawn
d_, rep_, svg_, dxf_, td_ = hl_out_['roof']
lines_ = hl_lines_(svg_)
zc_ = 5 - (3 - 2.5) * (2 / 2.9)
ok(all(hl_drawn_(lines_, td_, (x0 + 4.2, 3, zc_), (x0 + 4.8, 3, zc_), tol=0.2) > 0.9 for x0 in (0, 9)),
   'hidden-lines: a chimney meets its roof in a line, in a house joined into one solid by its id and in one left in parts')
sc_roof_ = json.loads((td_ / 'scene.json').read_text())
ok(sum(1 for o in sc_roof_['objects'] if o['parts'] == 3) == 1 and sum(1 for o in sc_roof_['objects'] if o['group'] == 'houses') == 4,
   'hidden-lines: the parts sharing an id are one solid; parts without one stay apart')
ok(hl_drawn_(lines_, td_, (16.1, 9, 0), (18.9, 9, 0)) > 0.95 and hl_drawn_(lines_, td_, (19, 9.1, 0), (19, 11.9, 0)) > 0.95,
   'hidden-lines: a box sunk into the ground is drawn where it meets the ground')
foot_ = hl_page_(td_, (4 + 0.2 * math.sin(math.radians(135)), 10 + 0.2 * math.cos(math.radians(135)), 0))
ok(lines_.distance(HPoint_(foot_)) < 0.1, 'hidden-lines: a trunk standing in the ground is drawn at its foot')

# cuts: the request's clip planes cut the solids; each body's cut is closed paths on CUT, merged where its parts touch
def hl_cuts_(svg):
    """the CUT paths of an SVG as (closed, polygon on the page)"""
    out_ = []
    for p in lint.read_svg(svg)['paths']:
        if p.layer == 'CUT':
            out_.append((p.closed, HPoly_([p.segs[0][0]] + [b for a, b in p.segs])))
    return out_

def hl_inside_(svg, poly, layers=None):
    """the length of drawn lines (not CUT) strictly inside a page polygon"""
    return hl_lines_(svg, layers).intersection(poly.buffer(-0.3)).length

d_, rep_, svg_, dxf_, td_ = hl_out_['cut-box']
cuts_ = hl_cuts_(svg_)
ring_ = HPoly_([hl_page_(td_, q) for q in [(5, 0, 0), (5, 6, 0), (5, 6, 4), (5, 0, 4)]])
subs_ = {(s['layer'], s['sublayer']): s['weight'] for s in rep_['sublayers']}
ok(len(cuts_) == 1 and cuts_[0][0] and abs(cuts_[0][1].area - ring_.area) < 0.01 * ring_.area
   and cuts_[0][1].symmetric_difference(ring_).area < 0.01 * ring_.area and not rep_['cuts']['open'],
   f'hidden-lines: a box cut by a plane is one closed path on CUT, its exact projected section '
   f'({cuts_[0][1].area if cuts_ else 0:.1f} of {ring_.area:.1f} pt²)')
ok(subs_.get(('BEYOND', 'box profiles')) == 'medium' and subs_.get(('BEYOND', 'box creases')) == 'fine'
   and not any(l_ == 'DETAIL' or l_ == 'OUTLINE' and not sub_.endswith(' open cuts') for l_, sub_ in subs_)
   and subs_.get(('CUT', 'box cuts')) == 'heavy',
   'hidden-lines: a group on CUT draws its lines seen past the plane on BEYOND, its profile medium and its creases fine')
lines_ = hl_lines_(svg_)
ok(hl_inside_(svg_, ring_) == 0 and hl_drawn_(hl_lines_(svg_, ('OUTLINE',)), td_, (5, -10, 0), (5, -1, 0)) > 0.95
   and hl_drawn_(lines_, td_, (0.2, 0, 4), (4.8, 0, 4)) > 0.95,
   'hidden-lines: nothing is drawn across the cut face; the ground cut along the plane is drawn at the cut\'s weight on '
   'OUTLINE; the box\'s edges run up to the cut')

d_, rep_, svg_, dxf_, td_ = hl_out_['cut-lwall']
cuts_ = hl_cuts_(svg_)
wall_ = lambda x0, y0, x1, y1: HPoly_([hl_page_(td_, (x, y, 1.2)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])
lw_ = wall_(0, 0, 8, 0.3).union(wall_(0, 0, 0.3, 6)).union(wall_(3.8, 0.3, 4.2, 0.7))
post_ = wall_(5.8, 3.8, 6.2, 4.2)
big_ = max(cuts_, key=lambda c: c[1].area) if cuts_ else (False, HPoly_())
ok(len(cuts_) == 2 and all(c for c, _ in cuts_) and big_[1].symmetric_difference(lw_).area < 0.01 * lw_.area
   and min(c[1].area for c in cuts_) > 0.95 * post_.area,
   f'hidden-lines: walls overlapping in an L and the post against one are one closed region on CUT, the free post '
   f'another ({len(cuts_)} paths; L {big_[1].area:.1f} of {lw_.area:.1f} pt²)')
ok(hl_inside_(svg_, lw_) == 0 and not rep_['cuts']['open'] and rep_['cuts']['objects'] == 4,
   'hidden-lines: no line of the walls\' overlap or the post\'s joint is drawn inside the merged cut')

d_, rep_, svg_, dxf_, td_ = hl_out_['cut-rooms']
cuts_ = hl_cuts_(svg_)
rooms_ = HPoly_([hl_page_(td_, q) for q in [(0, 3, 0), (8, 3, 0), (8, 3, 6), (0, 3, 6)]])
ok(len(cuts_) == 1 and cuts_[0][0] and cuts_[0][1].symmetric_difference(rooms_).area < 0.01 * rooms_.area
   and hl_inside_(svg_, rooms_) == 0,
   'hidden-lines: three touching rooms cut square to the view are one closed region, no line between them')
annex_ = [p for p in lint.read_svg(svg_)['paths'] if p.layer == 'OUTLINE']
cut_verts_ = set(q for p in lint.read_svg(svg_)['paths'] if p.layer == 'CUT' for a, b in p.segs for q in (a, b))
ok(annex_ and any(e in cut_verts_ for p in annex_ for e in p.ends())
   and hl_drawn_(hl_lines_(svg_, ('OUTLINE',)), td_, (8.2, 8, 2.5), (13.8, 8, 2.5)) > 0.95
   and hl_lines_(svg_, ('OUTLINE',)).intersection(rooms_.buffer(-0.3)).length == 0,
   'hidden-lines: an annex behind the cut is hidden by the cut face and its top edge ends on a vertex of the cut')
ok(hl_drawn_(hl_lines_(svg_, ('OUTLINE',)), td_, (-8, 3, 0), (-1, 3, 0)) > 0.95
   and any(s['sublayer'] == 'ground open cuts' and s['layer'] == 'OUTLINE' and s['weight'] == 'heavy' for s in rep_['sublayers']),
   'hidden-lines: the ground cut by the plane, an open surface, is a line as heavy as the building\'s cut, on OUTLINE '
   'since CUT holds closed paths (the review, the model note 3)')

# perspective: the camera's frame, verticals, the vanishing point of the street, what is behind the camera
d_, rep_, svg_, dxf_, td_ = hl_out_['persp']
sp_ = json.loads((td_ / 'scene.json').read_text())
rq_ = json.loads((td_ / 'request.json').read_text())
F_ = rq_['frame']['w_pt'] / 2 * 35 / 18                        # 36 mm of film across the frame, in pt
ok(abs(sp_['view']['focal'] * sp_['view']['pt_per_unit'] - F_) < 1e-6 * F_
   and math.dist(sp_['view']['camera'], [-15, 0, 1.6]) < 1e-6 and any('2 outside the frame' in l_ for l_ in sp_['log']),
   'hidden-lines: a perspective keeps the camera named, a 35 mm lens across the frame, and leaves out what is behind '
   'the camera or outside the view')
lines_ = hl_lines_(svg_)
c0_, c1_ = hl_page_(td_, (22, 8, 0.2)), hl_page_(td_, (22, 8, 11.8))
ok(abs(c0_[0] - c1_[0]) < 1e-6 and hl_drawn_(lines_, td_, (22, 8, 0.2), (22, 8, 11.8)) > 0.95
   and hl_drawn_(lines_, td_, (2, 8, 0), (9.8, 8, 0)) > 0.95,
   'hidden-lines: in a two-point perspective a building\'s corner is drawn vertical, and its foot on the ground')
curbs_ = [p for p in lint.read_svg(svg_)['paths'] if p.layer == 'FLOOR']
def hl_meet_(a, b):
    (x1, y1), (x2, y2) = a.segs[0][0], a.segs[-1][1]
    (x3, y3), (x4, y4) = b.segs[0][0], b.segs[-1][1]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
vp_ = hl_meet_(curbs_[0], curbs_[1]) if len(curbs_) == 2 else (0, 0)
eye_ = (rq_['frame']['w_pt'] / 2, rq_['frame']['h_pt'] / 2 + sp_['view']['shift'] * sp_['view']['pt_per_unit'])
ok(len(curbs_) == 2 and math.dist(vp_, eye_) < 0.5,
   f'hidden-lines: the curbs, lines lying on the ground, are drawn and meet at the eye\'s vanishing point '
   f'({vp_[0]:.2f}, {vp_[1]:.2f} against {eye_[0]:.2f}, {eye_[1]:.2f})')
ok(rep_['classes_pt'].get('overlap', 0) > 0 and hl_drawn_(hl_lines_(svg_, ('DETAIL',)), td_, (12.2, 8, 6), (19.8, 8, 6)) > 0.95,
   'hidden-lines: in a perspective a lower building\'s roof edge against a taller one behind is an overlap, depth read as 1/z')
d_, rep_, svg_, dxf_, td_ = hl_out_['persp-aim']
sa_ = json.loads((td_ / 'scene.json').read_text())
ok(abs(math.dist(sa_['view']['camera'], [14, 0, 3]) - sa_['view']['focal']) < 1e-6
   and abs(sa_['view']['focal'] * sa_['view']['pt_per_unit'] - 280 * 28 / 18) < 1e-6,
   'hidden-lines: a perspective with no camera named stands it where the target is drawn at the request\'s scale')
d_, rep_, svg_, dxf_, td_ = hl_out_['persp-cut']
ring2_ = lambda x0, y0, x1, y1: [hl_page_(td_, (x, y, 1.5)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
block_ = HPoly_(ring2_(0, 0, 24, 18), [ring2_(6, 5, 18, 13)])
data_ = lint.read_svg(svg_)
cut_paths_ = [p for p in data_['paths'] if p.layer == 'CUT']
ok(len(cut_paths_) == 3 and all(p.closed for p in cut_paths_) and not rep_['cuts']['open'] and rep_['cuts']['regions'] == 2
   and any(abs(HPoly_([p.segs[0][0]] + [b for a, b in p.segs]).area - HPoly_(ring2_(6, 5, 18, 13)).area) < 0.01 * block_.area
           for p in cut_paths_),
   'hidden-lines: a perspective plan cut of a block round a court is an outline and a hole, closed; a wall running out of the '
   'view closes past the frame on the view\'s own edge, and nothing of that edge is drawn or reported')
def hl_filled_(d, td, p):
    """is the model point p under a fill on GROUND (the drawing's own polygons, holes and all)"""
    x_, y_ = hl_page_(td, p)
    H_ = json.loads((td / 'request.json').read_text())['frame']['h_pt']
    q_ = HPoint_(x_ / d.k, (H_ - y_) / d.k)
    return any(HPoly_(e['rings'][0], e['rings'][1:]).contains(q_) for e in d.ents['GROUND'] if e.get('fill'))
ok(hl_filled_(d_, td_, (12, 9, 0)) and hl_filled_(d_, td_, (40, 30, 0)) and not hl_filled_(d_, td_, (3, 9, 1.5)),
   'hidden-lines: the ground is filled in the court and round the block, the cut is not')
ok(any('depth unit' in l_ and 'computed again' in l_ for l_ in json.loads((td_ / 'scene.json').read_text())['log']),
   'hidden-lines: where the engine\'s perspective depth unit differs from the estimate, the drawing is computed again with it')

# the check of the engine against the meshes: no scene has a drawn edge another object stands well in front of; a wall
# edge moved across the box in front of it, its depth kept, is caught
ok(all(not hl_out_[sc_][1].get('verify', {}).get('occluded') for sc_ in hl_scenes_),
   'hidden-lines: no drawn edge in any scene has another object more than gap_m in front of it')
def hl_plant_(s):
    """a wall edge seen across the box: moved on paper onto the box's middle, 3 m behind it"""
    kf = s['view']['pt_per_unit'] * s['view']['true_factor']
    wall = next(o['i'] for o in s['objects'] if o['layer'].endswith('::wall'))
    M_ = s['view']['xform']
    cx, cy, cz = (sum(M_[i][j] * v for j, v in enumerate([6.5, 2, 1.5, 1])) for i in range(3))
    seg = next(g for g in s['segments'] if g['o'] == wall and len(g['pts']) == 2)
    s['segments'].append(dict(seg, pts=[[cx - 10 / kf, cy, cz - 3], [cx + 10 / kf, cy, cz - 3]]))
_, rep_v_, svg_v_, _, td_v_ = hl_draw_('tjunction', hl_plant_)
ok(rep_v_['hidden_by_meshes']['count'] >= 1 and any(x['layer'].endswith('::wall') for x in rep_v_['hidden_by_meshes']['examples'])
   and hl_drawn_(hl_lines_(svg_v_), td_v_, (6.0, 2, 1.5), (7.0, 2, 1.5)) == 0 and not rep_v_['verify']['occluded'],
   'hidden-lines: a wall edge across the box in front of it, which the engine would have hidden, is taken out by the meshes '
   'and listed')

# a version 3 export's meshes keep their tolerance on twisted faces too, so the check measures square to the surface in
# front and needs it only 0.27 pt in front, not gap_m (contact curves 4 to 11 cm behind the model's outer roof skin): wall
# edges planted 5 cm and 1 mm under the box's top
def hl_under_top_(version):
    def edit(s):
        wall = next(o['i'] for o in s['objects'] if o['layer'].endswith('::wall'))
        M_ = s['view']['xform']
        cam_ = lambda p: [sum(M_[i][j] * v for j, v in enumerate(list(p) + [1])) for i in range(3)]
        seg = next(g for g in s['segments'] if g['o'] == wall and len(g['pts']) == 2)
        for dz_ in (0.05, 0.001):
            s['segments'].append(dict(seg, pts=[cam_((5.5, 2.5 + 20 * dz_, 3 - dz_)), cam_((7.5, 2.5 + 20 * dz_, 3 - dz_))]))
        s['version'] = version
    return edit
hl_top_ = {}
for v_ in (2, 3):
    _, rep_t_, svg_t_, _, td_t_ = hl_draw_('tjunction', hl_under_top_(v_))
    lines_t_ = hl_lines_(svg_t_)
    hl_top_[v_] = [round(hl_drawn_(lines_t_, td_t_, (5.6, 2.5 + 20 * dz_, 3 - dz_), (7.4, 2.5 + 20 * dz_, 3 - dz_)), 2)
                   for dz_ in (0.05, 0.001)]
ok(hl_top_[2] == [1.0, 1.0] and hl_top_[3] == [0.0, 1.0],
   'hidden-lines: in a version 3 export a wall edge 5 cm under the box\'s top is taken out and one 1 mm under it, on the '
   'face within the meshes\' tolerance, is kept; a version 2 export keeps both, the box less than gap_m in front: '
   + str(hl_top_))

# the model the model's tall roof (fixtures twisted): four twisted faces joined as one surface, which the engine drew the frame's
# contact curves through, 2 to 7 cm behind the front face; with that face alone it hid them. The export's meshes keep
# the twisted faces within tolerance, so the tile lines on the face stay whole while the contact curves go
_, rep_tw_, svg_tw_, dxf_tw_, td_tw_ = hl_out_['twisted']
rep_tw2_ = hl_draw_('twisted', lambda s: s.update(version=2))[1]
s_tw_ = json.loads((td_tw_ / 'scene.json').read_text())
tiles_tw_ = sum(math.dist(a[:2], b[:2]) for g in s_tw_['segments'] if s_tw_['objects'][g['o']]['layer'].endswith('::tiles')
                for a, b in zip(g['pts'], g['pts'][1:])) * s_tw_['view']['pt_per_unit'] * s_tw_['view']['true_factor']
subs_tw_ = {(x['layer'], x['sublayer']): x['length_pt'] for x in rep_tw_['sublayers']}
subs_tw2_ = {(x['layer'], x['sublayer']): x['length_pt'] for x in rep_tw2_['sublayers']}
ok(any(g['src'] == 'contact' and not g.get('vis') for g in s_tw_['segments'])
   and not [x for x in subs_tw_ if x[1].startswith('frame')] and [x for x in subs_tw2_ if x[1].startswith('frame')]
   and abs(subs_tw_.get(('TEXTURE', 'tiles lines'), 0) / tiles_tw_ - 1) < 0.01,
   'hidden-lines: through a roof of twisted faces joined as one surface the engine drew the frame\'s contact curves; they '
   'are taken out and every tile line on the front face is drawn whole, where drawn as a version 2 export the frame '
   'shows through: ' + str(sorted(subs_tw_.items())) + f', tiles in the export {tiles_tw_:.1f} pt')

# the model check: each fault named on the object that has it, nothing on the clean ones; a creased face is split on the
# copy drawn, so its creases are drawn
d_, rep_, svg_, dxf_, td_ = hl_out_['bad']
sb_ = json.loads((td_ / 'scene.json').read_text())
said_ = collections.defaultdict(list)
for o_ in sb_['objects']:
    said_[o_['layer'].split('::')[-1]] += o_['issues']
want_ = {'crossing': 'cross their own boundary', 'warped': 'nearly planar', 'creased': 'creased inside', 'duplicates': 'duplicate of',
         'notched': 'edges under', 'sheet': 'lies on', 'slab': 'lies on', 'clash': 'runs into', 'roof': 'shares an edge',
         'nonmanifold': 'non-manifold mesh'}
miss_ = [k for k, w in want_.items() if not any(w in i for i in said_[k])]
ok(not miss_ and not said_['row'] and not said_['ground']
   and any('touch face to face with no union key' in l_ for l_ in sb_['log']),
   'hidden-lines: the model check names a profile crossing itself, a warped face, a creased face, a duplicate, an edge under '
   'ten tolerances, faces lying on each other, solids running into each other, surfaces sharing an edge unjoined and a '
   'non-manifold mesh, each on its object, and leaves touching boxes with only a note' + (f' (missed {miss_})' if miss_ else ''))
lines_ = hl_lines_(svg_)
ok(hl_drawn_(lines_, td_, (8, 0, 0.1), (8, 0, 1.9)) > 0.95 and hl_drawn_(lines_, td_, (10, 0, 0.1), (10, 0, 1.9)) > 0.95,
   'hidden-lines: a face creased inside is split on the copy drawn, so the crease the engine would leave out is drawn')
# GetNextDiscontinuity's G1 test reports a NURBS sphere's double knots, which run into its poles, though its normal
# turns 0.0 degrees across them; both objects were added without Rhino's split
said_ = {o_['layer'].split('::')[-1]: o_['issues']
         for o_ in json.loads((FX / 'hidden-lines' / 'knots' / 'scene.json').read_text())['objects']}
knots_ = set(said_) == {'sphere', 'revolved'} and not any('crease' in i for i in said_['sphere']) \
    and any('creased inside' in i for i in said_['revolved'])
ok(knots_, 'hidden-lines: the model check finds no crease in a NURBS sphere, whose double knots run into its poles, and '
   'finds the creases of a tree revolved from a polyline' + ('' if knots_ else f': {said_}'))

# doubles: a line 0.15 pt beside the cut's top edge gives way to it; one leaving that edge's end at 3 degrees stays
def hl_doubles_(s):
    kf_ = s['view']['pt_per_unit'] * s['view']['true_factor']
    A_, B_ = s['rings'][0]['pts'][1], s['rings'][0]['pts'][2]  # the cut face's top edge, camera coordinates
    L_ = math.hypot(B_[0] - A_[0], B_[1] - A_[1])
    u_ = ((B_[0] - A_[0]) / L_, (B_[1] - A_[1]) / L_)
    n_ = (-u_[1], u_[0])                                # away from the cut face
    z_ = lambda x, y: A_[2] + ((x - A_[0]) * u_[0] + (y - A_[1]) * u_[1]) / L_ * (B_[2] - A_[2])
    o_ = 0.15 / kf_
    P_ = [(A_[0] + u_[0] * L_ * t + n_[0] * o_, A_[1] + u_[1] * L_ * t + n_[1] * o_) for t in (0.2, 0.8)]
    c_, si_ = math.cos(math.radians(3)), math.sin(math.radians(3))
    d_ = (c_ * u_[0] + si_ * n_[0], c_ * u_[1] + si_ * n_[1])
    Q_ = [(A_[0], A_[1]), (A_[0] + d_[0] * 2.5, A_[1] + d_[1] * 2.5)]
    for pts in (P_, Q_):
        s['segments'].append(dict(o=1, src='geom', sil='Crease', pts=[[x, y, z_(x, y)] for x, y in pts], sides='UU', scene=False))
    s['_test'] = dict(beside=P_, leaving=Q_, kf=kf_)
hl_dbl_ = {}
def hl_doubles_keep_(s):
    hl_doubles_(s)
    hl_dbl_.update(s.pop('_test'))
_, rep_d_, svg_d_, dxf_d_, td_d_ = hl_draw_('cut-box', hl_doubles_keep_, req=dict(simplify_doubles=True))
req_d_ = json.loads((td_d_ / 'request.json').read_text())
page_d_ = lambda x, y: (req_d_['frame']['w_pt'] / 2 + x * hl_dbl_['kf'], req_d_['frame']['h_pt'] / 2 - y * hl_dbl_['kf'])
fd_d_ = lint.check(lint.read_svg(svg_d_), load(svg_d_)) + lint.check(lint.read_dxf(dxf_d_, None), load(svg_d_))
beyond_d_ = hl_lines_(svg_d_, ('BEYOND',))
all_d_ = hl_lines_(svg_d_)
(pa_, pb_), (qa_, qb_) = hl_dbl_['beside'], hl_dbl_['leaving']
beside_gone_ = all(beyond_d_.distance(HPoint_(page_d_(pa_[0] + (pb_[0] - pa_[0]) * t, pa_[1] + (pb_[1] - pa_[1]) * t))) > 0.1
                   for t in (0.3, 0.5, 0.7))
leaving_kept_ = all(all_d_.distance(HPoint_(page_d_(qa_[0] + (qb_[0] - qa_[0]) * t, qa_[1] + (qb_[1] - qa_[1]) * t))) < 0.05
                    for t in (0.1, 0.5, 0.9))
dbl_runs_ = [float(re.search(r'for ([\d.]+) pt', x[2]).group(1)) for x in fd_d_ if x[1] == 'double']
ok(not [x for x in fd_d_ if x[0] == 'error'] and beside_gone_ and leaving_kept_ and dbl_runs_
   and all(10.5 < r_ < 12 for r_ in dbl_runs_)
   and any(x['beside'] == 'CUT' and 45 < x['length_pt'] < 56 for x in rep_d_['doubles']['examples']),
   'hidden-lines: simplified, a line 0.15 pt beside a cut gives way to it over its length (lint.double_pt), and a line leaving the '
   "cut's corner at 3 degrees stays whole, its first 11.4 pt under 0.6 pt off the cut the only double lint finds: "
   + str([(x['layer'], x['beside'], x['length_pt']) for x in rep_d_['doubles']['examples']]) + f' {dbl_runs_}')

# doubles by turns: two lines of one weight 0.3 pt apart beside cut-box's cut, each in three pieces of unequal length
# (a: 40, 20, 40 percent; b: 20, 60, 20). Ranked piece by piece, the longer piece won each stretch and the drawing
# zigzagged between them, as the model's skylight frame did; ranked by its chain, the longer line a is drawn whole and b goes
def hl_zigzag_(s):
    kf_ = s['view']['pt_per_unit'] * s['view']['true_factor']
    A_, B_ = s['rings'][0]['pts'][1], s['rings'][0]['pts'][2]
    L_ = math.hypot(B_[0] - A_[0], B_[1] - A_[1])
    u_ = ((B_[0] - A_[0]) / L_, (B_[1] - A_[1]) / L_)
    n_ = (-u_[1], u_[0])
    z_ = lambda x, y: A_[2] + ((x - A_[0]) * u_[0] + (y - A_[1]) * u_[1]) / L_ * (B_[2] - A_[2])
    at_ = lambda t, off: (A_[0] + u_[0] * L_ * t + n_[0] * off / kf_, A_[1] + u_[1] * L_ * t + n_[1] * off / kf_)
    for off, t0, t1, cuts in ((1.0, 0.08, 0.92, (0, 0.4, 0.6, 1)), (1.3, 0.1, 0.9, (0, 0.2, 0.8, 1))):
        ts = [t0 + (t1 - t0) * c for c in cuts]
        for a, b in zip(ts, ts[1:]):
            s['segments'].append(dict(o=1, src='geom', sil='Crease', pts=[[*at_(t, off), z_(*at_(t, off))] for t in (a, b)],
                                      sides='UU', scene=False))
    s['_zig'] = dict(kf=kf_, at=at_)
hl_zig_ = {}
def hl_zigzag_keep_(s):
    hl_zigzag_(s)
    hl_zig_.update(s.pop('_zig'))
_, _, svg_z_, _, td_z_ = hl_draw_('cut-box', hl_zigzag_keep_, req=dict(simplify_doubles=True))
req_z_ = json.loads((td_z_ / 'request.json').read_text())
page_z_ = lambda p: (req_z_['frame']['w_pt'] / 2 + p[0] * hl_zig_['kf'], req_z_['frame']['h_pt'] / 2 - p[1] * hl_zig_['kf'])
beyond_z_ = hl_lines_(svg_z_, ('BEYOND',))
a_kept_ = [beyond_z_.distance(HPoint_(page_z_(hl_zig_['at'](t, 1.0)))) for t in (0.12, 0.3, 0.5, 0.7, 0.88)]
b_gone_ = [beyond_z_.distance(HPoint_(page_z_(hl_zig_['at'](t, 1.3)))) for t in (0.14, 0.3, 0.5, 0.7, 0.86)]
ok(max(a_kept_) < 0.05 and min(b_gone_) > 0.25,
   'hidden-lines: simplified, of two lines of one weight 0.3 pt apart, each in pieces of unequal length, the longer line is drawn '
   f'whole and the other gives way along all of it, with no zigzag between them: {a_kept_} {b_gone_}')

# --explain: a Redline note over the line that gave way to the cut lists it with its reason, and the fates map draws it
fz_ = rep_d_['_fates']
mid_ = page_d_((pa_[0] + pb_[0]) / 2, (pa_[1] + pb_[1]) / 2)
md_ = ('Redline of out.svg.\n\n1. a line is missing here.\n   Where: x %.1f\u2013%.1f, y %.1f\u2013%.1f. Image: note-1.png\n'
       '   Marks: red dot\n2. nothing marked under this one\n   Where: page 2, x 0\u20131, y 0\u20131. Image: note-2.png\n'
       % (mid_[0] - 1, mid_[0] + 1, mid_[1] - 1, mid_[1] + 1))
ex_ = hl_.explain_notes(fz_, md_).split('\n')
hl_.write_fates(fz_, td_d_ / 'fates.svg', req_d_['frame']['w_pt'], req_d_['frame']['h_pt'])
fsvg_ = (td_d_ / 'fates.svg').read_text()
ok(ex_[0].startswith('note 1 (x ') and 'a double: gave way to a heavier line beside it' in ex_[1]
   and ex_[4].startswith('note 2 (page 2, x 0-1') and ex_[5] == '  taken out: nothing'
   and 'id="a double: gave way to a heavier line beside it"' in fsvg_ and 'id="drawn"' in fsvg_,
   'hidden-lines: --explain lists under a note the line that gave way to the cut, with its reason, and nothing under a '
   'note on a bare page; the fates map draws it in its reason\'s group: ' + ' | '.join(ex_)[:400])

# --check: the checks written from review notes, on a page of a heavy cut, two light lines 1 pt apart and a tile
td_ck_ = Path(tempfile.mkdtemp(prefix='hl-check-'))
(td_ck_ / 'page.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="100pt" height="100pt" viewBox="0 0 100 100">'
    '<g id="CUT"><path d="M10 10 L90 10" stroke="#000" stroke-width="0.9" fill="none"/></g>'
    '<g id="BEYOND"><path d="M10 50 L90 50" stroke="#000" stroke-width="0.2" fill="none"/>'
    '<path d="M10 51 L90 51" stroke="#000" stroke-width="0.2" fill="none"/></g>'
    '<g id="TEXTURE"><path d="M40 70 L60 70" stroke="#000" stroke-width="0.1" fill="none"/></g></svg>')
ck_ = [dict(kind='line', path=[[10, 10], [90, 10]], min_w=0.8), dict(kind='line', path=[[10, 30], [90, 30]]),
       dict(kind='line', path=[[10, 10], [90, 10]], min_w=1.0), dict(kind='clear', box=[30, 60, 70, 80]),
       dict(kind='clear', box=[30, 60, 70, 80], layers=['CUT']), dict(kind='clear', box=[30, 60, 70, 80], allow=['TEXTURE']),
       dict(kind='single', path=[[20, 50.5], [80, 50.5]]), dict(kind='lines', n=2, path=[[20, 50.5], [80, 50.5]]),
       dict(kind='single', path=[[20, 10], [80, 10]]), dict(kind='look', note=3)]
got_ck_ = [ok_ for _, ok_, _, _ in hl_.check_notes(td_ck_ / 'page.svg', ck_)]
ok(got_ck_ == [True, False, False, False, True, True, False, True, True, None],
   'hidden-lines: --check finds a heavy line along its path and none where there is none or not heavy enough, a region '
   'clear or not by its layers, and one line or two across a path: ' + str(got_ck_))

# converging lines: a line coming down to 0.045 pt off the cut's top edge and leaving it again, touching it without a
# node (the mounds' shell lines on the model), stays whole, where a line beside the cut at an even offset gives way
def hl_converge_(s):
    kf_ = s['view']['pt_per_unit'] * s['view']['true_factor']
    A_, B_ = s['rings'][0]['pts'][1], s['rings'][0]['pts'][2]
    L_ = math.hypot(B_[0] - A_[0], B_[1] - A_[1])
    u_ = ((B_[0] - A_[0]) / L_, (B_[1] - A_[1]) / L_)
    n_ = (-u_[1], u_[0])
    z_ = lambda x, y: A_[2] + ((x - A_[0]) * u_[0] + (y - A_[1]) * u_[1]) / L_ * (B_[2] - A_[2])
    at_ = lambda t, off: (A_[0] + u_[0] * L_ * t + n_[0] * off / kf_, A_[1] + u_[1] * L_ * t + n_[1] * off / kf_)
    V_ = [at_(0.2, 1.2), at_(0.5, 0.045), at_(0.8, 1.2)]
    for a, b in zip(V_, V_[1:]):
        s['segments'].append(dict(o=1, src='geom', sil='Crease', pts=[[*a, z_(*a)], [*b, z_(*b)]], sides='UU', scene=False))
    s['_cv'] = dict(kf=kf_, at=at_)
hl_cv_ = {}
def hl_converge_keep_(s):
    hl_converge_(s)
    hl_cv_.update(s.pop('_cv'))
_, _, svg_cv_, _, td_cv_ = hl_draw_('cut-box', hl_converge_keep_)
req_cv_ = json.loads((td_cv_ / 'request.json').read_text())
page_cv_ = lambda p: (req_cv_['frame']['w_pt'] / 2 + p[0] * hl_cv_['kf'], req_cv_['frame']['h_pt'] / 2 - p[1] * hl_cv_['kf'])
beyond_cv_ = hl_lines_(svg_cv_, ('BEYOND',))
near_cv_ = [beyond_cv_.distance(HPoint_(page_cv_(hl_cv_['at'](0.2 + 0.3 * f_, 1.2 - 1.155 * f_)))) for f_ in (0.7, 0.85, 0.95)]
ok(max(near_cv_) < 0.08,
   'hidden-lines: a line closing in on the cut to 0.045 pt and leaving it again is drawn to its closest point: '
   + str(near_cv_))

# a cut the engine left out: cut-box's ground is a surface, without a ring, and the engine already leaves out its cut under
# the box (Duplicate of the box's); with all its cut segments taken out of the export, its mesh's edges on the plane draw
# it again
def hl_nocut_(s):
    s['segments'] = [x for x in s['segments'] if not (x.get('cut') is not None and x['o'] == 0)]
_, rep_nc_, svg_nc_, _, _ = hl_draw_('cut-box', hl_nocut_)
len_nc_ = {(x['layer'], x['sublayer']): x['length_pt'] for x in rep_nc_['sublayers']}
len_cb_ = {(x['layer'], x['sublayer']): x['length_pt'] for x in hl_out_['cut-box'][1]['sublayers']}
ok(rep_nc_['mesh_cuts']['pieces'] >= 1 and len_cb_.get(('OUTLINE', 'ground open cuts'), 0) > 10
   and abs(len_nc_.get(('OUTLINE', 'ground open cuts'), 0) - len_cb_[('OUTLINE', 'ground open cuts')]) < 0.5,
   "hidden-lines: a surface's cut left out of the export is drawn again from its mesh's edges on the plane, as long as "
   f"before: {rep_nc_['mesh_cuts']} "
   f"{len_nc_.get(('OUTLINE', 'ground open cuts'))} {len_cb_.get(('OUTLINE', 'ground open cuts'))}")

# a slab of surfaces closing across a gap: with cut-box's ground on CUT, a band 1 pt thick beside the box drawn as four
# cut lines of the ground, its last 0.1 pt short of its first, is still closed into a region of the ground's cut
def hl_band_(s):
    kf_ = s['view']['pt_per_unit'] * s['view']['true_factor']
    A_, B_ = s['rings'][0]['pts'][0], s['rings'][0]['pts'][1]
    L_ = math.hypot(B_[0] - A_[0], B_[1] - A_[1])
    u_ = ((B_[0] - A_[0]) / L_, (B_[1] - A_[1]) / L_)
    n_ = (u_[1], -u_[0])                                # away from the box, on the plane
    z_ = lambda x, y: A_[2] + ((x - A_[0]) * u_[0] + (y - A_[1]) * u_[1]) / L_ * (B_[2] - A_[2])
    at_ = lambda t, off: (A_[0] + u_[0] * L_ * t + n_[0] * off / kf_, A_[1] + u_[1] * L_ * t + n_[1] * off / kf_)
    for a, b in ((at_(0.3, 3), at_(0.7, 3)), (at_(0.7, 3), at_(0.7, 4)), (at_(0.7, 4), at_(0.3, 4)), (at_(0.3, 4), at_(0.3, 3.1))):
        s['segments'].append(dict(o=0, src='geom', sil='SectionCut', cut=0, pts=[[*a, z_(*a)], [*b, z_(*b)]], sides='OS', scene=False))
td_bd_ = Path(tempfile.mkdtemp(prefix='hl-band-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'cut-box' / f_, td_bd_ / f_)
s_bd_ = json.loads((td_bd_ / 'scene.json').read_text())
hl_band_(s_bd_)
(td_bd_ / 'scene.json').write_text(json.dumps(s_bd_))
r_bd_ = json.loads((td_bd_ / 'request.json').read_text())
r_bd_['groups'] = [dict(g, layer='CUT') if g['id'] == 'ground' else g for g in r_bd_['groups']]
(td_bd_ / 'request.json').write_text(json.dumps(r_bd_))
_, rep_bd_ = hl_.build(td_bd_ / 'request.json')
ok(rep_bd_['cuts']['from_surfaces'] >= 1,
   "hidden-lines: a band of a body's cut lines whose last stops 0.1 pt short of its first closes into a region: "
   + str({k_: v for k_, v in rep_bd_['cuts'].items() if not isinstance(v, list)}))

# dashed classes: a roof slab and a beam marked above, seen looking up from a plan cut; a footing marked hidden
_, rep_a_, svg_a_, dxf_a_, td_a_ = hl_draw_('above')
fa_ = lint.check(lint.read_svg(svg_a_), load(svg_a_)) + lint.check(lint.read_dxf(dxf_a_, None), load(svg_a_))
ab_ = hl_lines_(svg_a_, ('ABOVE',))
subs_a_ = {(s['layer'], s['sublayer']): s['weight'] for s in rep_a_['sublayers']}
ok(not fa_ and subs_a_.get(('ABOVE', 'roof above')) == 'light'
   and hl_drawn_(ab_, td_a_, (-1, -1, 0), (7, -1, 0)) > 0.95 and hl_drawn_(ab_, td_a_, (-1, 5, 0), (-1, -1, 0)) > 0.95
   and hl_drawn_(ab_, td_a_, (2.85, 0.3, 0), (2.85, 3.7, 0)) > 0.95 and hl_drawn_(ab_, td_a_, (3.15, 0.3, 0), (3.15, 3.7, 0)) > 0.95,
   'hidden-lines: a roof slab and a beam marked above are drawn dashed on ABOVE as seen looking up from the plan cut, the '
   "roof's overhang all round and the beam across the room; lint finds nothing: " + '; '.join(m_ for _, _, m_, _ in fa_[:2]))
_, rep_h_, svg_h_, dxf_h_, td_h_ = hl_draw_('hidden')
fh_ = lint.check(lint.read_svg(svg_h_), load(svg_h_)) + lint.check(lint.read_dxf(dxf_h_, None), load(svg_h_))
hd_ = hl_lines_(svg_h_, ('HIDDEN',))
ok(not [x for x in fh_ if not (x[1] == 'duplicate' and ('CUT / CUT' in x[2]
                                                                  or 'CUT › earth cuts / CUT › house cuts' in x[2]))]
   and hl_drawn_(hd_, td_h_, (-0.5, 4, -1), (6.5, 4, -1)) > 0.95 and hl_drawn_(hd_, td_h_, (-0.5, 4, -0.9), (-0.5, 4, -0.1)) > 0.95
   and hl_drawn_(hd_, td_h_, (0, 4, 0), (6, 4, 0)) < 0.05,
   "hidden-lines: a footing marked hidden is drawn dashed on HIDDEN inside the earth's cut, its top giving way to the "
   "earth's cut line it lies on; lint finds only the house's and the earth's cuts sharing the ground line: "
   + '; '.join(m_ for _, _, m_, _ in fh_[:3]))

# Illustrator: the plan written as Illustrator's own document, a layer per layer, a sublayer per class at its weight
# and dash, in a global swatch named for it
from archkit import ainative as hl_ai_
d_a_ = hl_draw_('above')[0]
d_a_.to_ai(td_a_ / 'out.ai', canvas=(560, 400), origin=(0.0, 400))
c_a_ = hl_ai_.census(td_a_ / 'out.ai')
looks_a_ = {L['path']: [lk for lk, _ in L['own']['looks']] for L in c_a_['layers']}
ai_txt_ = hl_ai_.native(td_a_ / 'out.ai').decode('latin-1')
ok(set(looks_a_) == {'CONTEXT', 'CONTEXT/ground profiles', 'ABOVE', 'ABOVE/roof above', 'CUT', 'CUT/walls cuts'}
   and looks_a_['ABOVE/roof above'] == ['stroke K 0.8 0.15 pt dash 6,3'] and looks_a_['CUT/walls cuts'] == ['stroke K 1 0.8 pt']
   and '(ABOVE roof above) 0 0 Xk' in ai_txt_ and c_a_['totals']['paths'] == 6,
   'hidden-lines: the drawing written as an .ai has a layer per layer and a sublayer per class, each at its weight and '
   "dash (ABOVE's projection 6/3) in a global swatch named for it: " + str(looks_a_))

# joints: cut-rooms' rooms marked joints keep the lines between them, on OUTLINE, inside the one merged cut on CUT
td_j_ = Path(tempfile.mkdtemp(prefix='hl-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'cut-rooms' / f_, td_j_ / f_)
rq_j_ = json.loads((td_j_ / 'request.json').read_text())
for g_j_ in rq_j_['groups']:
    if g_j_['id'] == 'rooms':
        g_j_['joints'] = True
(td_j_ / 'request.json').write_text(json.dumps(rq_j_))
d_j_, rep_j_ = hl_.build(td_j_ / 'request.json')
d_j_.to_svg(td_j_ / 'out.svg', canvas=(560, 400), origin=(0.0, 400))
d_j_.to_dxf(td_j_ / 'out.dxf')
fj_ = lint.check(lint.read_svg(td_j_ / 'out.svg'), load(td_j_ / 'out.svg')) + \
      lint.check(lint.read_dxf(td_j_ / 'out.dxf', None), load(td_j_ / 'out.svg'))
jl_ = hl_lines_(td_j_ / 'out.svg', ('OUTLINE',))
subs_j_ = {(s['layer'], s['sublayer']): s['weight'] for s in rep_j_['sublayers']}
ok(not fj_ and rep_j_['cuts']['regions'] == 1 and subs_j_.get(('OUTLINE', 'rooms joints')) == 'heavy'
   and hl_drawn_(jl_, td_j_, (4, 3, 0.1), (4, 3, 2.9)) > 0.95 and hl_drawn_(jl_, td_j_, (0.1, 3, 3), (7.9, 3, 3)) > 0.95
   and hl_drawn_(jl_, td_j_, (0.5, 3, 0), (7.5, 3, 0)) < 0.05,
   'hidden-lines: rooms marked joints keep the lines between them on OUTLINE (rooms joints, at the cut\'s weight) inside '
   'their one merged cut, none along its outline, and lint finds nothing: ' + '; '.join(m_ for _, _, m_, _ in fj_[:2]))

def hl_req_(scene, extra):
    """a scene drawn with keys added to its request: (report, folder)"""
    td_ = Path(tempfile.mkdtemp(prefix='hl-'))
    for f_ in ('request.json', 'scene.json', 'meshes.bin'):
        shutil.copy(FX / 'hidden-lines' / scene / f_, td_ / f_)
    rq_ = json.loads((td_ / 'request.json').read_text())
    rq_.update(extra)
    (td_ / 'request.json').write_text(json.dumps(rq_))
    return hl_.build(td_ / 'request.json')[1], td_

# depth bands: the annex 5 m behind cut-rooms' plane keeps its class's weight in the second band, and steps lighter past
# both edges
td_b_ = Path(tempfile.mkdtemp(prefix='hl-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'cut-rooms' / f_, td_b_ / f_)
rq_b_ = json.loads((td_b_ / 'request.json').read_text())
rq_b_['depth_bands_m'] = [3, 8]
(td_b_ / 'request.json').write_text(json.dumps(rq_b_))
_, rep_b_ = hl_.build(td_b_ / 'request.json')
subs_b_ = {(s['layer'], s['sublayer']): s['weight'] for s in rep_b_['sublayers']}
rep_b2_ = hl_req_('cut-rooms', {'depth_bands_m': [1, 3]})[0]
subs_b2_ = {(s['layer'], s['sublayer']): s['weight'] for s in rep_b2_['sublayers']}
ok(subs_b_.get(('OUTLINE', 'annex profiles::middle (3–8 m)')) == 'heavy' and ('OUTLINE', 'annex profiles') not in subs_b_
   and subs_b2_.get(('OUTLINE', 'annex profiles::far (past 3 m)')) == 'medium' and subs_b_.get(('CUT', 'rooms cuts')) == 'heavy'
   and all(w_ in ('heavy', 'medium', 'light', 'fine') for w_ in subs_b_.values()),
   'hidden-lines: with depth_bands_m [3, 8] the annex 5 m past the plane, in the second band, keeps its heavy profile on '
   "'annex profiles::middle (3–8 m)'; with [1, 3], past both edges, it steps to medium; the cut keeps its weight: "
   + str(sorted(subs_b_.items())))

# what the engine hid (vis 'under') is kept where nothing but a surface it lies on, or nothing at all, is in front of it:
# stretches added to touching's export on a home's face seen from the camera, 3 m behind it, 3 m in front, and a sliver
import numpy as np
s_u_, V_u_, F_u_, to_u_ = hl_.read_scene(FX / 'hidden-lines' / 'touching')
rq_u_ = json.loads((FX / 'hidden-lines' / 'touching' / 'request.json').read_text())
k_u_ = s_u_['view']['pt_per_unit']
hx_u_, hy_u_ = rq_u_['frame']['w_pt'] / 2 / k_u_, rq_u_['frame']['h_pt'] / 2 / k_u_
T_u_ = V_u_[F_u_]
cen_u_ = T_u_.mean(1)
tr_u_ = hl_.Tris(V_u_, F_u_, to_u_, 1.0, (hx_u_, hy_u_), np.arange(len(s_u_['objects']) + 1), 0.0)
front_u_ = tr_u_.nearest(cen_u_[:, :2] + np.array([hx_u_, hy_u_]))
nz_u_ = np.abs(np.cross(T_u_[:, 1] - T_u_[:, 0], T_u_[:, 2] - T_u_[:, 0])[:, 2])
i_u_ = max((i for i in range(len(F_u_)) if to_u_[i] > 0 and front_u_[i] >= 0 and tr_u_.o[front_u_[i]] == to_u_[i]
            and abs(cen_u_[i, 2] - tr_u_.plane_z(np.array([front_u_[i]]), cen_u_[i:i + 1, :2] + np.array([hx_u_, hy_u_]))[0]) < 1e-6),
           key=lambda i: nz_u_[i])                    # a home's triangle that is itself the surface seen at its middle
a_u_, b_u_ = cen_u_[i_u_] + (T_u_[i_u_, 0] - cen_u_[i_u_]) * 0.1, cen_u_[i_u_] + (T_u_[i_u_, 1] - cen_u_[i_u_]) * 0.1
f_u_ = s_u_['view']['true_factor']
sl_u_ = a_u_ + (b_u_ - a_u_) * min(1.0, 0.3 / (np.linalg.norm((b_u_ - a_u_)[:2]) * k_u_ * f_u_))   # 0.3 pt along it

def hl_under_(sc):
    for dz_, b_ in ((0.0, b_u_), (-3.0, b_u_), (3.0, b_u_), (0.0, sl_u_)):
        sc['segments'].append(dict(o=int(to_u_[i_u_]), src='geom', sil='Crease', pass_='main', vis='under', sides='', scene=False,
                                   pts=[[float(a_u_[0]), float(a_u_[1]), float(a_u_[2] + dz_)], [float(b_[0]), float(b_[1]), float(b_[2] + dz_)]]))
_, rep_u_, svg_u_, _, td_u_ = hl_draw_('touching', hl_under_)
ok(rep_u_['under']['segments'] == 4 and rep_u_['under']['kept'] == 2
   and abs(rep_u_['under']['length_pt'] / (2 * np.linalg.norm((b_u_ - a_u_)[:2]) * k_u_ * f_u_) - 1) < 0.01,
   f'hidden-lines: of what the engine hid, a stretch on the face seen and one in front of everything are kept, one 3 m '
   f'behind the face and a 0.3 pt sliver are not: {rep_u_["under"]}')

# crease turns: with crease_turns_deg, a crease whose faces turn by less than an angle listed is a weight lighter for each
rep_t0_, _ = hl_req_('roof', {'crease_turns_deg': [0.01]})
rep_t1_, _ = hl_req_('roof', {'crease_turns_deg': [179.9]})
subs_t1_ = {(x['layer'], x['sublayer']): x['weight'] for x in rep_t1_['sublayers']}
n_cr_ = sum(rep_t1_['crease_turns']['edges'])
ok(n_cr_ > 0 and rep_t0_['crease_turns']['edges'] == [n_cr_, 0] and rep_t1_['crease_turns']['edges'] == [0, n_cr_]
   and any(sub_.endswith('creases under 179.9 deg') for _, sub_ in subs_t1_)
   and not any(sub_.endswith(' creases') for _, sub_ in subs_t1_),
   f'hidden-lines: with crease_turns_deg each crease under the angle steps a weight lighter on a sublayer of its own, and none '
   f'under 0.01 deg does ({n_cr_} creases)')

# a gap between parts of one body's cut narrower than twice its weight is closed: cut-rooms' top room, which spans the two
# below it, moved up off them
def hl_gap_(dy_pt):
    def edit(sc):
        k_ = sc['view']['pt_per_unit'] * sc['view']['true_factor']
        rooms_ = [r for r in sc['rings'] if sc['objects'][r['o']]['group'] == 'rooms']
        top_ = max(rooms_, key=lambda r: sum(p[1] for p in r['pts']) / len(r['pts']))
        for r in sc['rings']:
            if r['o'] == top_['o']:
                r['pts'] = [[p[0], p[1] + dy_pt / k_, p[2]] for p in r['pts']]
    return hl_draw_('cut-rooms', edit)[1]['cuts']
g03_, g3_ = hl_gap_(0.3), hl_gap_(3.0)
ok(g03_['regions'] == 1 and len(g03_['gaps_closed']) >= 1 and g3_['regions'] == 2 and not g3_['gaps_closed'],
   f'hidden-lines: a room 0.3 pt off the others is one cut with the gap closed, 3 pt off it is two: {g03_["regions"]}, '
   f'{len(g03_["gaps_closed"])} closed; {g3_["regions"]}')

def hl_pt_(td, q):
    """a point of a parallel view's export (camera coordinates) on the page, in points from the top-left, y down"""
    v_ = json.loads((td / 'scene.json').read_text())['view']
    fr_ = json.loads((td / 'request.json').read_text())['frame']
    kf_ = v_['pt_per_unit'] * v_['true_factor']
    return (fr_['w_pt'] / 2 + q[0] * kf_, fr_['h_pt'] / 2 - q[1] * kf_)

def hl_add_(sc, src, a, b):
    """a segment of the annex (cut-rooms' object 1) from a to b, export coordinates, a hair behind the clip plane"""
    sc['segments'].append(dict(o=1, src=src, sil='Boundary', sides='', scene=False,
                               pts=[[a[0], a[1], -2000.2], [b[0], b[1], -2000.2]]))

# the closed gap's new edge is in the graph (fuzz seed 32): with the room 0.3 pt off, a line seen in the gap from its
# mouth, its middle half a grid step inside, goes with the gap, and one running into the gap from outside is cut at the
# mouth and ends there on the cut drawn
hl_at_ = {}
def hl_mouth_(sc):
    kf_ = sc['view']['pt_per_unit'] * sc['view']['true_factor']
    g_ = 0.05 / kf_                                    # the noding grid, in the export's units
    rooms_ = [r for r in sc['rings'] if sc['objects'][r['o']]['group'] == 'rooms']
    top_ = max(rooms_, key=lambda r: sum(p[1] for p in r['pts']) / len(r['pts']))
    x0_, y0_ = min(p[0] for p in top_['pts']), min(p[1] for p in top_['pts'])   # the gap's mouth and foot
    for r in sc['rings']:
        if r['o'] == top_['o']:
            r['pts'] = [[p[0], p[1] + 6 * g_, p[2]] for p in r['pts']]
    hl_add_(sc, 'geom', (x0_, y0_ + g_), (x0_ + g_, y0_ + 5 * g_))
    hl_add_(sc, 'geom', (x0_ - 10 / kf_, y0_ + 3 * g_), (x0_ + 5 / kf_, y0_ + 3 * g_))
    hl_at_['mouth'] = (x0_, y0_ + 3 * g_)
_, rep_m_, svg_m_, dxf_m_, td_m_ = hl_draw_('cut-rooms', hl_mouth_)
cuts_m_ = hl_cuts_(svg_m_)
errs_m_ = [m_ for lv_, _, m_, _ in lint.check(lint.read_svg(svg_m_), load(svg_m_))
           + lint.check(lint.read_dxf(dxf_m_, None), load(svg_m_)) if lv_ == 'error']
in_m_ = hl_lines_(svg_m_).intersection(cuts_m_[0][1].buffer(-0.01)).length if len(cuts_m_) == 1 else None
ok(not errs_m_ and len(cuts_m_) == 1 and rep_m_['cuts']['gaps_closed'] and in_m_ == 0
   and any(math.dist(e_, hl_pt_(td_m_, hl_at_['mouth'])) < 0.05 for p in lint.read_svg(svg_m_)['paths'] if p.layer != 'CUT'
           for e_ in p.ends()),                     # within the noding grid of where it crosses the mouth
   f'hidden-lines: no line is drawn in a cut\'s closed gap, the one seen in its mouth included, and a line running into it '
   f'ends on the cut drawn: {len(cuts_m_)} cut, {in_m_} pt inside, {errs_m_[:2]}')

# a line's last stretch to a free end, in another class than the line it goes on from, its end within near_pt of that
# line, is a near miss of it drawn apart: lines of the annex in the empty space over cut-rooms, each stretch a curve of
# it, so in its lines' class. One leaving the line at 7.4 degrees for 1 pt (fuzz seed 180) is taken out, one turning
# 83 degrees for 0.3 pt (fuzz seed 73) cut back, and one going on at 10 degrees for 0.4 pt drawn as the line
def hl_tails_(sc):
    u_ = 1 / (sc['view']['pt_per_unit'] * sc['view']['true_factor'])      # a point on the page, in the export's units
    at_ = lambda p, deg, ln: (p[0] + ln * u_ * math.cos(math.radians(deg)), p[1] + ln * u_ * math.sin(math.radians(deg)))
    n1_, n2_, n3_ = (-10.0, 8.0), (-3.0, 8.0), (4.0, 8.0)
    hl_add_(sc, 'geom', n1_, at_(n1_, 0, 20))
    hl_add_(sc, 'curve', n1_, at_(n1_, 7.4, 1.0))
    hl_add_(sc, 'geom', at_(n2_, 180, 20), n2_)
    hl_add_(sc, 'curve', n2_, at_(n2_, 83, 0.3))
    hl_add_(sc, 'geom', at_(n3_, 180, 20), n3_)
    hl_add_(sc, 'curve', n3_, at_(n3_, 10, 0.4))
    hl_at_.update(hair=at_(n1_, 7.4, 1.0), stub=at_(n2_, 83, 0.3), on=at_(n3_, 10, 0.4))
_, rep_tl_, svg_tl_, dxf_tl_, td_tl_ = hl_draw_('cut-rooms', hl_tails_)
data_tl_ = lint.read_svg(svg_tl_)
errs_tl_ = [m_ for lv_, _, m_, _ in lint.check(data_tl_, load(svg_tl_))
            + lint.check(lint.read_dxf(dxf_tl_, None), load(svg_tl_)) if lv_ == 'error']
fx_tl_ = [(f_['kind'], f_['at_pt']) for f_ in rep_tl_['fixes']]
ends_tl_ = [(p.layer, e_) for p in data_tl_['paths'] for e_ in p.ends()]
near_tl_ = lambda w_: [kd_ for kd_, at_ in fx_tl_ if math.dist(at_, hl_pt_(td_tl_, hl_at_[w_])) < 0.1]
ok(not errs_tl_ and near_tl_('hair') == ['hair taken out'] and near_tl_('stub') == ['overshoot cut back']
   and not any(math.dist(e_, hl_pt_(td_tl_, hl_at_[w_])) < 0.1 for _, e_ in ends_tl_ for w_ in ('hair', 'stub'))
   and any(l_ == 'OUTLINE' and math.dist(e_, hl_pt_(td_tl_, hl_at_['on'])) < 0.1 for l_, e_ in ends_tl_),
   f'hidden-lines: a free end in another class within near_pt of the line it leaves is taken out at 7.4 degrees and 1 pt, '
   f'cut back at 83 degrees and 0.3 pt, and drawn as that line at 10 degrees and 0.4 pt: {errs_tl_[:2]}, {fx_tl_}')

# a cut region thinner than thin_cut.times_weight its weight all through is drawn at thin_cut.share of it, and one with a
# thick part keeps its weight whole: cut-rooms' top room squashed to a strip 1 pt tall and moved 3 m along, first on the
# rooms below it, where the poché runs on unbroken through it, then lifted 3 pt clear of them, a region of its own
def hl_squash_(sc, lift=0.0):
    k_ = sc['view']['pt_per_unit'] * sc['view']['true_factor']
    rooms_ = [r for r in sc['rings'] if sc['objects'][r['o']]['group'] == 'rooms']
    top_ = max(rooms_, key=lambda r: sum(p[1] for p in r['pts']) / len(r['pts']))
    y0_ = min(p[1] for p in top_['pts'])
    for r in sc['rings']:
        if r['o'] == top_['o']:
            r['pts'] = [[p[0] + 3.0, y0_ + lift / k_ + (p[1] - y0_) * (1.0 / k_) / 3.0, p[2]] for p in r['pts']]
_, rep_th_, svg_th_, _, td_th_ = hl_draw_('cut-rooms', hl_squash_)
_, rep_tl2_, svg_tl2_, _, _ = hl_draw_('cut-rooms', lambda sc: hl_squash_(sc, 3.0))
subs_th_ = {(x['layer'], x['sublayer']): x['weight'] for x in rep_th_['sublayers']}
subs_tl2_ = {(x['layer'], x['sublayer']): x['weight'] for x in rep_tl2_['sublayers']}
hw_th_ = load(svg_th_).weight('heavy', json.loads((td_th_ / 'request.json').read_text())['scale'])
errs_th_ = [m_ for sv_ in (svg_th_, svg_tl2_) for lv_, _, m_, _ in lint.check(lint.read_svg(sv_), load(sv_)) if lv_ == 'error']
ok(('CUT', 'rooms cuts thin') not in subs_th_ and subs_th_.get(('CUT', 'rooms cuts')) == 'heavy' and rep_th_['cuts']['thin'] == 0
   and subs_tl2_.get(('CUT', 'rooms cuts thin')) == round(hw_th_ * load(svg_th_)['hidden_lines']['thin_cut']['share'], 2)
   and rep_tl2_['cuts']['thin'] == 1 and not errs_th_,
   f'hidden-lines: a strip 1 pt tall on the rooms keeps the cut\'s weight, the poché unbroken; lifted clear of them it is '
   f'drawn at thin_cut.share of it, and lint finds no error: {sorted(subs_th_.items())} {sorted(subs_tl2_.items())} {errs_th_[:2]}')

# the same request drawn twice gives the same bytes whatever the hash seed: the squashed cut-rooms with its strip lifted
# clear, so its body has a cut and a thin cut sublayer, drawn by kit.py in three processes
td_seed_ = Path(tempfile.mkdtemp(prefix='hl-seed-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'cut-rooms' / f_, td_seed_ / f_)
s_seed_ = json.loads((td_seed_ / 'scene.json').read_text())
hl_squash_(s_seed_, 3.0)
(td_seed_ / 'scene.json').write_text(json.dumps(s_seed_))
outs_seed_ = []
for seed_ in ('1', '2', '3'):
    run_seed_ = td_seed_.parent / f'{td_seed_.name}-{seed_}'
    shutil.copytree(td_seed_, run_seed_)
    subprocess.run([sys.executable, '-B', str(KIT / 'kit.py'), 'hidden-lines', str(run_seed_ / 'request.json')],
                   capture_output=True, env=dict(os.environ, PYTHONHASHSEED=seed_), check=True)
    id_seed_ = json.loads((run_seed_ / 'request.json').read_text())['id']
    outs_seed_.append(tuple((run_seed_ / f'{id_seed_}{x_}').read_bytes() for x_ in ('.svg', '.dxf', '.ai')))
ok(len(set(outs_seed_)) == 1, 'hidden-lines: the same request drawn under three hash seeds writes the same SVG, DXF and AI, '
   f'byte for byte: {[len({o_[i_] for o_ in outs_seed_}) for i_ in range(3)]} versions of each')

# a wall modelled as surfaces, its section four lines of an object that is no closed solid, 0.3 m by 3 m beside
# cut-box's cut, is a cut region of the box's body (cut_surface_m), and a lone section line of it is drawn at the cut's
# weight on OUTLINE, since CUT holds closed paths
def hl_surfaces_(sc):
    M_ = sc['view']['xform']
    cam_ = lambda q: [sum(M_[i][j] * v for j, v in enumerate(list(q) + [1])) for i in range(3)]
    o_ = len(sc['objects'])
    sc['objects'].append(dict(i=o_, ids=['wall-surfaces'], group='box', layer='hl::cut-box::box', kind='brep', solid=False,
                              user={}, issues=[], parts=4))
    R_ = [(5, -2.3, 0.5), (5, -2.0, 0.5), (5, -2.0, 3.5), (5, -2.3, 3.5)]
    for a, b in list(zip(R_, R_[1:] + R_[:1])) + [((5, -2.3, 4.5), (5, -0.3, 4.5))]:
        sc['segments'].append(dict(o=o_, src='geom', sil='SectionCut', pts=[cam_(a), cam_(b)], sides='UU', scene=False, cut=0))
_, rep_sf_, svg_sf_, _, td_sf_ = hl_draw_('cut-box', hl_surfaces_)
subs_sf_ = {(x['layer'], x['sublayer']): x['weight'] for x in rep_sf_['sublayers']}
wall_sf_ = HPoly_([hl_page_(td_sf_, q) for q in [(5, -2.3, 0.5), (5, -2.0, 0.5), (5, -2.0, 3.5), (5, -2.3, 3.5)]])
cuts_sf_ = hl_cuts_(svg_sf_)
ok(rep_sf_['cuts']['from_surfaces'] == 1 and len(cuts_sf_) == 2
   and any(c_[0] and c_[1].symmetric_difference(wall_sf_).area < 0.02 * wall_sf_.area for c_ in cuts_sf_)
   and subs_sf_.get(('OUTLINE', 'box open cuts')) == 'heavy'
   and hl_drawn_(hl_lines_(svg_sf_, ('OUTLINE',)), td_sf_, (5, -2.2, 4.5), (5, -0.4, 4.5)) > 0.95,
   f'hidden-lines: a wall of surfaces beside the box is cut as a closed region of its body, and a lone section line of it '
   f'is drawn heavy on OUTLINE: {rep_sf_["cuts"]} {sorted(subs_sf_.items())}')

# what of a body's section is solid, from its surfaces' section lines and the side each surface faces (solid_cells), in
# drawing units, each case between two slabs that are closed solids: a wall 1 m thick of two skins facing away from it is
# solid by its sides, however thick; of a cavity wall, the cavity 0.3 m wide whose skins face into it is air though
# thinner than cut_surface_m, and the leaves either side solid; a cell 1 m wide whose skins face the same way is
# reported; two skins 0.2 m apart facing away from each other, their ends free and no slab, are capped across and solid
def sc_skin_(x, y0, y1, nx):
    return [(x, y0), (x, y1)], [(x, y0 + (y1 - y0) * i / 10, x, y0 + (y1 - y0) * (i + 1) / 10, nx, 0.0) for i in range(10)]
sc_lines_, sc_sides_, sc_rings_ = [], [], []
for xs_, x0_, x1_ in ((((0, -1), (1, 1)), -0.5, 1.5), (((5.5, -1), (6, 1), (6.3, -1), (6.8, 1)), 5.5, 6.8), (((8, -1), (9, -1)), 7.5, 9.5)):
    for x_, nx_ in xs_:
        l_, s_ = sc_skin_(x_, 0, 3, nx_)
        sc_lines_.append(l_)
        sc_sides_ += s_
    sc_rings_ += [HPoly_([(x0_, -0.2), (x1_, -0.2), (x1_, 0), (x0_, 0)]), HPoly_([(x0_, 3), (x1_, 3), (x1_, 3.2), (x0_, 3.2)])]
for x_, nx_ in ((11, -1), (11.2, 1)):
    l_, s_ = sc_skin_(x_, 1, 2.5, nx_)
    sc_lines_.append(l_)
    sc_sides_ += s_
sc_sol_, sc_unr_, sc_links_, _ = hl_.solid_cells(sc_lines_, sc_sides_, sc_rings_, 0.6, 0.01, 0.001, 0.05, 0.01)
from shapely import union_all as hl_union_
sc_u_ = hl_union_(sc_sol_) if sc_sol_ else HPoly_()
sc_in_ = lambda x, y: sc_u_.contains(HPoint_(x, y))
ok(sc_in_(0.5, 1.5) and not sc_in_(-0.25, 1.5) and not sc_in_(1.25, 1.5) and not sc_in_(6.15, 1.5) and sc_in_(5.75, 1.5)
   and sc_in_(6.55, 1.5) and not sc_in_(8.5, 1.5) and any(q.contains(HPoint_(8.5, 1.5)) for q in sc_unr_) and len(sc_unr_) == 1
   and sc_in_(11.1, 1.75) and len(sc_links_) == 2,
   f'hidden-lines: a wall of skins facing away from it is solid at 1 m thick, a cavity whose skins face into it air and '
   f'its leaves solid, a cell its skins leave mixed reported, and two skins with free ends capped: {len(sc_sol_)} solid, '
   f'{len(sc_unr_)} unresolved, {sc_links_}')

# the earth under a ground's open sheets (earth_under): a slab of ground closed in section, its top at 0 and bottom at -1,
# a mound on it from 2 to 4, and a pit from 10 to 12 with no line over it
er_ = hl_.earth_under([[(0, 0), (10, 0)], [(0, -1), (10, -1)], [(0, 0), (0, -1)], [(10, 0), (10, -1)],
                       [(2, 0), (3, 0.5), (4, 0)], [(12, 0), (15, 0)]], (0, 1), (0, -5, 15, 5))
ok(all(er_.contains(HPoint_(x, y)) for x, y in ((5, -0.5), (5, -3), (3, 0.2), (13, -2)))
   and not any(er_.contains(HPoint_(x, y)) for x, y in ((11, -3), (5, 0.5), (3, 0.6))),
   'hidden-lines: the earth runs on under a ground slab\'s bottom face and fills a mound on it, and a pit with no line '
   'over it stays open')

# the earth in a drawing: cut-rooms' ground, an open surface, given a bottom face 0.5 m under its top, a line of the annex
# 1 m under the ground 2 m past the plane, one 1 m over it, and one under it in front of the plane: the bottom face's cut
# and the buried line go, the others stay
def hl_earth_(sc):
    M_ = sc['view']['xform']
    cam_ = lambda q: [sum(M_[i][j] * v for j, v in enumerate(list(q) + [1])) for i in range(3)]
    sc['segments'].append(dict(o=0, src='geom', sil='SectionCut', pts=[cam_((-8, 3, -0.5)), cam_((-1, 3, -0.5))],
                               sides='UU', scene=False, cut=0))
    for y_, z_ in ((5, -1), (5, 1), (2, -1.5)):
        sc['segments'].append(dict(o=1, src='geom', sil='Boundary', pts=[cam_((-6, y_, z_)), cam_((-3, y_, z_))],
                                   sides='UU', scene=False))
_, rep_ea_, svg_ea_, _, td_ea_ = hl_draw_('cut-rooms', hl_earth_)
ln_ea_ = hl_lines_(svg_ea_)
ok(hl_drawn_(ln_ea_, td_ea_, (-7.5, 3, -0.5), (-1.5, 3, -0.5)) < 0.05 and hl_drawn_(ln_ea_, td_ea_, (-5.8, 5, -1), (-3.2, 5, -1)) < 0.05
   and hl_drawn_(ln_ea_, td_ea_, (-5.8, 5, 1), (-3.2, 5, 1)) > 0.95 and hl_drawn_(ln_ea_, td_ea_, (-5.8, 2, -1.5), (-3.2, 2, -1.5)) > 0.95
   and hl_drawn_(hl_lines_(svg_ea_, ('OUTLINE',)), td_ea_, (-8, 3, 0), (-1, 3, 0)) > 0.95
   and rep_ea_['earth']['cut_lines_pt'] > 0 and rep_ea_['earth']['behind_pt'] > 0,
   f'hidden-lines: under a ground of open sheets the earth takes its bottom face\'s cut and a line buried past the plane, '
   f'and keeps its top, a line over it and one in front of the plane: {rep_ea_["earth"]}')

# the massing: the earth of the hidden scene marked as ground, a closed solid cut heavy, runs on into the house's cut
# where they meet, one closed region drawn as the house's
def hl_req_ground_(td):
    r_ = json.loads((td / 'request.json').read_text())
    r_['groups'] = [dict(g, ground=True) if g['id'] == 'earth' else g for g in r_['groups']]
    (td / 'request.json').write_text(json.dumps(r_))
td_mg_ = Path(tempfile.mkdtemp(prefix='hl-massing-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'hidden' / f_, td_mg_ / f_)
hl_req_ground_(td_mg_)
d_mg_, rep_mg_ = hl_.build(td_mg_ / 'request.json')
d_mg_.to_svg(td_mg_ / 'out.svg', canvas=(560, 400), origin=(0.0, 400))
cuts_mg_ = [c_ for c_ in hl_cuts_(td_mg_ / 'out.svg')]
subs_mg_ = {(x['layer'], x['sublayer']) for x in rep_mg_['sublayers']}
ok(rep_mg_['cuts']['merged'] == [dict(body='earth', into='house')] and ('CUT', 'earth cuts') not in subs_mg_
   and not [m_ for _, k_, m_, _ in lint.check(lint.read_svg(td_mg_ / 'out.svg'), load(td_mg_ / 'out.svg')) if 'CUT / CUT' in m_],
   f'hidden-lines: a closed solid of the ground cut heavy runs on into the house\'s cut, one poché drawn as the house\'s, '
   f'with no cut drawn over another: {rep_mg_["cuts"]["merged"]} {sorted(subs_mg_)}')

# a lighter group in a heavier body is not massing: cut-lwall's post against the L-wall put in a group on DETAIL of the
# walls' body keeps its own cut, closed, a rung lighter, and the L-wall's is drawn without it
def hl_post_(sc):
    rk_ = {r['o']: r for r in sc['rings']}
    sc['objects'][max(rk_, key=lambda o: min(p[0] for p in rk_[o]['pts']) if sc['objects'][o]['group'] == 'walls' else -1e9)]['group'] = 'posts'
td_po_ = Path(tempfile.mkdtemp(prefix='hl-posts-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'cut-lwall' / f_, td_po_ / f_)
r_po_ = json.loads((td_po_ / 'request.json').read_text())
r_po_['groups'].insert(1, dict(id='posts', layers=['hl::cut-lwall::posts'], layer='DETAIL', body='walls'))
(td_po_ / 'request.json').write_text(json.dumps(r_po_))
s_po_ = json.loads((td_po_ / 'scene.json').read_text())
hl_post_(s_po_)
(td_po_ / 'scene.json').write_text(json.dumps(s_po_))
d_po_, rep_po_ = hl_.build(td_po_ / 'request.json')
subs_po_ = {(x['layer'], x['sublayer']): x['weight'] for x in rep_po_['sublayers']}
ok(subs_po_.get(('CUT', 'posts cuts')) == 'medium' and subs_po_.get(('CUT', 'walls cuts')) == 'heavy',
   f'hidden-lines: a post in a lighter group of the walls\' body keeps its own cut, a rung lighter: {sorted(subs_po_.items())}')

# paths: a loop leaving a junction and coming back to it through nodes of two lines alone closes on itself, and the line
# that meets it there, in line with one of its sides, ends on it (a door knob's ring and stem, the model at regression)
def hl_loop_(sc):
    v_ = sc['view']
    k_, f_ = v_['pt_per_unit'], v_['true_factor']
    at_ = lambda x, y: [(x / k_ - 280 / k_) / f_, (200 / k_ - y / k_) / f_, -100.0]   # page pt to the export's coordinates
    sq_ = [(60, 60), (64, 60), (64, 64), (60, 64), (60, 60)]
    for (x0, y0), (x1, y1) in list(zip(sq_, sq_[1:])) + [((52, 60), (60, 60))]:
        sc['segments'].append(dict(o=1, src='curve', sil='Boundary', pts=[at_(x0, y0), at_(x1, y1)], sides='UU', scene=False))
d_lp_, _, svg_lp_, _, _ = hl_draw_('cut-box', hl_loop_)
pl_lp_ = [e for es_ in d_lp_.ents.values() for e in es_ if e['k'] == 'pl'
          and all(abs(x * d_lp_.k - 62) < 3 and abs(400 - y * d_lp_.k - 62) < 3 for x, y in e['pts'])]
ok(any(e['closed'] and len(e['pts']) == 4 for e in pl_lp_),
   'hidden-lines: a loop leaving a junction and coming back to it closes on itself, the line meeting it there ending on it: '
   + str([(len(e['pts']), e['closed']) for e in pl_lp_]))

# --check's gap and regions: a heavy line with a 2 pt break in it, and two cut regions, one with a hole
td_cg_ = Path(tempfile.mkdtemp(prefix='hl-check2-'))
(td_cg_ / 'page.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="100pt" height="100pt" viewBox="0 0 100 100">'
    '<g id="OUTLINE"><path d="M10 10 L40 10 M42 10 L90 10" stroke="#000" stroke-width="0.9" fill="none"/></g>'
    '<g id="CUT"><path d="M10 40 L40 40 L40 70 L10 70 Z M20 50 L30 50 L30 60 L20 60 Z" stroke="#000" stroke-width="0.9" fill="none"/>'
    '<path d="M50 40 L60 40 L60 70 L50 70 Z" stroke="#000" stroke-width="0.25" fill="none"/></g></svg>')
ck2_ = [dict(kind='gap', path=[[10, 10], [90, 10]]), dict(kind='gap', path=[[10, 10], [40, 10]]),
        dict(kind='gap', path=[[10, 10], [90, 10]], max_pt=2.5), dict(kind='regions', box=[5, 35, 45, 75]),
        dict(kind='regions', box=[5, 35, 65, 75]), dict(kind='regions', box=[5, 35, 65, 75], min_w=0.5)]
got_cg_ = [(ok_, m_) for _, ok_, m_, _ in hl_.check_notes(td_cg_ / 'page.svg', ck2_)]
ok([g_[0] for g_ in got_cg_] == [False, True, True, True, False, True],
   'hidden-lines: --check measures the longest break along a line and counts the cut regions meeting a box, a hole not '
   'counted and a lighter region left out by min_w: ' + str(got_cg_))

# a curve among a group's solids is listed among the model's issues: persp's curbs put into the buildings' group
def hl_curbs_(sc):
    for o in sc['objects']:
        if o['group'] == 'curbs':
            o['group'] = 'buildings'
rep_c_ = hl_draw_('persp', hl_curbs_)[1]
ok(sum(1 for i in rep_c_['issues'] if i['issue'].startswith('a curve among')) == 2
   and not any(i['issue'].startswith('a curve among') for i in hl_out_['persp'][1]['issues']),
   'hidden-lines: curves put among a group of solids are listed as model issues, and none are where they have a group of their own')

# depth bands from the span: depth_bands_share puts the bands at shares of how far the subject runs beyond the plane
rep_sp_ = hl_req_('cut-rooms', {'depth_bands_share': [0.25, 0.6]})[0]
db_sp_ = rep_sp_.get('depth_bands') or {}
ok(db_sp_.get('from_span') and len(db_sp_.get('bands_m', [])) == 2 and 0 < db_sp_['bands_m'][0] < db_sp_['bands_m'][1]
   and abs(db_sp_['bands_m'][1] / db_sp_['bands_m'][0] - 2.4) < 0.15 and sum(db_sp_['edges']) > 0
   and hl_req_('cut-rooms', {'depth_bands_share': [0.25, 0.6], 'depth_bands_m': [3, 8]})[0]['depth_bands']['bands_m'] == [3.0, 8.0],
   f'hidden-lines: depth_bands_share sets the bands at a quarter and three fifths of the subject\'s depth beyond the '
   f'plane, and depth_bands_m in metres overrides it: {db_sp_}')

# --rhino: the drawing as rhino/hidden_lines.py adds it to the model, a sublayer a class at its print width, in model units
rh_ = {}
for sc_r_ in ('cut-rooms', 'coplanar'):
    td_r_ = Path(tempfile.mkdtemp(prefix='hl-'))
    for f_ in ('request.json', 'scene.json', 'meshes.bin'):
        shutil.copy(FX / 'hidden-lines' / sc_r_ / f_, td_r_ / f_)
    with contextlib.redirect_stdout(io.StringIO()):
        hl_.main([str(td_r_ / 'request.json'), '--rhino', str(td_r_ / 'rhino.json')])
    rq_r_ = json.loads((td_r_ / 'request.json').read_text())
    rep_r_ = json.loads((td_r_ / f'{rq_r_["id"]}-report.json').read_text())
    rh_[sc_r_] = (json.loads((td_r_ / 'rhino.json').read_text()), rep_r_, rq_r_)
rc_, rep_r_, rq_r_ = rh_['cut-rooms']
tk_r_ = load(FX / 'hidden-lines' / 'cut-rooms' / 'request.json')
subs_r_ = {(L['id'], s['name']): s for L in rc_['layers'] for s in L['subs']}
want_r_ = {(s['layer'], s['sublayer']): round(tk_r_.weight(s['weight'], rq_r_['scale']) / 72 * 25.4, 3) for s in rep_r_['sublayers']}
k_r_ = 72 / 25.4 * 1000 / rq_r_['scale']                # pt per metre
xy_r_ = [p for s in subs_r_.values() for ln in s['lines'] for p in ln['pts']]
ends_r_ = collections.Counter(tuple(p) for ln in subs_r_[('CUT', 'rooms cuts')]['lines'] if not ln['closed']
                              for p in (ln['pts'][0], ln['pts'][-1]))
ok({key: s['weight_mm'] for key, s in subs_r_.items()} == want_r_
   and all(n % 2 == 0 for n in ends_r_.values())
   and all(-0.01 <= x <= rq_r_['frame']['w_pt'] / k_r_ + 0.01 and -0.01 <= y <= rq_r_['frame']['h_pt'] / k_r_ + 0.01 for x, y in xy_r_),
   'hidden-lines: --rhino writes each sublayer at its print width in mm, cut rings closed across source splits, every point in the '
   'frame in model units: ' + str(sorted(want_r_.items())))
rf_, _, _ = rh_['coplanar']
fills_r_ = [f for L in rf_['layers'] for s in L['subs'] for f in s['fills']]
ok(fills_r_ and all(L['id'] == 'GROUND' and not any(s['lines'] for s in L['subs']) for L in rf_['layers'] if any(s['fills'] for s in L['subs']))
   and load(FX / 'hidden-lines' / 'coplanar' / 'request.json').hex('Accent') in {f['ink'] for f in fills_r_},
   f'hidden-lines: --rhino writes the fills on GROUND with their own inks and no outline ({len(fills_r_)} fills)')

# lint reads a sublayer's own weight, and a fill alone on a layer that strokes is no line
bad_ = re.sub(r'(data-weight="heavy" stroke="#000000" stroke-width=")[\d.]+', r'\g<1>0.2', (td_ / 'out.svg').read_text(), count=1)
(td_ / 'bad.svg').write_text(bad_)
ok(any(k == 'weight' for _, k, _, _ in lint.check(lint.read_svg(td_ / 'bad.svg'), load(td_ / 'bad.svg'))),
   'lint: a path whose sublayer says heavy but is drawn at 0.2 pt is a weight warning')

# the fuzz checker's lines inside a closed cut (fixtures/hidden-lines/fuzz.py, inside_cut), at 1:200 in metres: a block
# round a court, and a cut running out past the window's corner, where the window's clip would cut its ring open
import importlib.util
spec_fz_ = importlib.util.spec_from_file_location('hl_fuzz', FX / 'hidden-lines' / 'fuzz.py')
fz_ = importlib.util.module_from_spec(spec_fz_)
spec_fz_.loader.exec_module(fz_)
ic_ = HDrawing_(200, units='m', tokens=load(FX))
ic_.clip = (0.0, 0.0, 20.0, 14.0)
ic_.polygon('CUT', [[(2, 2), (10, 2), (10, 10), (2, 10)], [(4, 4), (8, 4), (8, 8), (4, 8)]])
ic_.polygon('CUT', [[(16, 10), (24, 10), (24, 18), (16, 18)]])
ic_.line('BEYOND', (2.5, 3), (9.5, 3))                        # in the block's wall, 7 m
ic_.line('BEYOND', (18, 12), (22, 16))                        # drawn to the window's corner, 2.83 m, all inside the cut
ic_.line('BEYOND', (5, 6), (7, 6))                            # in the court
ic_.line('BEYOND', (0.5, 6), (2, 6))                          # ending on the outline
ic_.line('BEYOND', (3, 2 + ic_.pt(0.005)), (9, 2 + ic_.pt(0.005)))
ic_.line('GROUND', (2.5, 9), (9.5, 9), stroke='K100', weight='fine')
ic_.polygon('BEYOND', [[(3, 3.5), (9, 3.5), (9, 3.8), (3, 3.8)]], fill='K6', stroke='none')
icd_ = Path(tempfile.mkdtemp(prefix='hl-'))
ic_.to_svg(icd_ / 'inside.svg', canvas=(20 * ic_.k, 14 * ic_.k), origin=(0.0, 14 * ic_.k))
ic_len_, ic_pcs_ = fz_.inside_cut(icd_ / 'inside.svg')
ic_want_ = (7 + 2 * math.sqrt(2)) * ic_.k
ok(abs(ic_len_ - ic_want_) < 0.02 and [p[0] for p in ic_pcs_] == ['BEYOND', 'BEYOND'],
   f'hidden-lines: the fuzz checker measures a line in a cut\'s wall and one in a cut running past the window, each '
   f'cut read whole and filled even-odd, and not one in its court, one ending on it, one 0.005 pt inside it, a line on '
   f'GROUND or a fill alone: {ic_len_:.3f} pt of {ic_want_:.3f}, {ic_pcs_}')

# hidden.py's own check of a drawing against its cut regions (inside_cut, the report's verify.inside_cut), on the same
# drawing with a joint and a dashed hidden line in the block's wall: it reads the cut whole and the lines as the window
# clips them, leaves out fills and the sublayers it is told to, and counts a stroked line on GROUND, which the fuzz
# checker leaves out with its layer
ic_.line('OUTLINE', (6, 2.2), (6, 3.8), sub='block joints')
ic_.line('HIDDEN', (2.5, 8.5), (9.5, 8.5), sub='block hidden')
ic_own_ = hl_.inside_cut(ic_, {('OUTLINE', 'block joints'), ('HIDDEN', 'block hidden')})
ic_all_ = hl_.inside_cut(ic_)
ic_wall_ = [p for p in ic_own_ if p[0] == 'BEYOND' and abs(p[2] - 7 * ic_.k) < 1e-6]
ok(abs(sum(p[2] for p in ic_own_) - ic_want_ - 7 * ic_.k) < 0.01 and abs(sum(p[2] for p in ic_all_) - ic_want_ - 15.6 * ic_.k) < 0.01
   and sorted((p[0], round(p[2] / ic_.k, 3)) for p in ic_own_) == [('BEYOND', 2.828), ('BEYOND', 7.0), ('GROUND', 7.0)]
   and len(ic_wall_) == 1 and math.dist(ic_wall_[0][3], (6, 3)) < 1e-9 and ic_own_[-1][2] < ic_own_[0][2],
   f'hidden-lines: the drawing\'s own check measures what the fuzz checker does and a line on GROUND, longest first with '
   f'each piece\'s middle, and leaves out the joints and the hidden lines it is told to: {ic_own_}')

# every scene drawn above, the dashed hidden footing and the rooms marked joints among them, has no line inside a cut
hl_ic_reps_ = dict({s_: hl_out_[s_][1] for s_ in hl_scenes_}, above=rep_a_, hidden=rep_h_, joints=rep_j_, bands=rep_b_,
                   doubles=rep_d_, mouth=rep_m_, tails=rep_tl_, thin=rep_th_)
ok(all(r_['verify']['inside_cut'] == dict(length_pt=0.0, pieces=0, longest=None) for r_ in hl_ic_reps_.values()),
   'hidden-lines: no scene draws a line inside a cut: '
   + str({s_: r_['verify']['inside_cut']['length_pt'] for s_, r_ in hl_ic_reps_.items() if r_['verify']['inside_cut']['pieces']}))

# a line a pass puts back inside a cut is reported and printed with where it is in the model: cut-rooms drawn with a copy
# of the annex's top edge (5 m past the plane, at y 8) moved into the rooms' cut, x 2 to 5, as the check reads the
# drawing; its depth is read from the annex line drawn on its sublayer
hl_ic_real_ = hl_.inside_cut
def hl_ic_plant_(d, skip=(), inset=0.01):
    a_, b_ = (hl_page_(FX / 'hidden-lines' / 'cut-rooms', p) for p in ((2, 8, 2.5), (5, 8, 2.5)))
    d.line('OUTLINE', (a_[0] / d.k, (400 - a_[1]) / d.k), (b_[0] / d.k, (400 - b_[1]) / d.k), sub='annex profiles')
    return hl_ic_real_(d, skip, inset)
td_ic_ = Path(tempfile.mkdtemp(prefix='hl-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'cut-rooms' / f_, td_ic_ / f_)
hl_.inside_cut = hl_ic_plant_
try:
    with contextlib.redirect_stdout(io.StringIO()) as said_ic_:
        hl_.main([str(td_ic_ / 'request.json')])
finally:
    hl_.inside_cut = hl_ic_real_
ic_r_ = json.loads((td_ic_ / 'cut-rooms-report.json').read_text())['verify']['inside_cut']
ok(ic_r_['pieces'] == 1 and abs(ic_r_['length_pt'] - 3000 / 200 / 25.4 * 72) < 0.01
   and ic_r_['longest']['layer'] == 'OUTLINE/annex profiles' and ic_r_['longest']['model'] == [3.5, 8.0, 2.5]
   and math.dist(ic_r_['longest']['at_pt'], hl_page_(FX / 'hidden-lines' / 'cut-rooms', (3.5, 8, 2.5))) < 0.01
   and 'in the model at [3.5, 8.0, 2.5]' in said_ic_.getvalue(),
   f'hidden-lines: a line drawn inside a cut is reported with its length, sublayer and place on the page and in the '
   f'model, and printed: {ic_r_}; ' + ' | '.join(x for x in said_ic_.getvalue().splitlines() if 'cut' in x))

# ---- visibility "faces": what is seen decided from the meshes' faces through an ID buffer (hiddenlines/idbuf.py)
from hiddenlines import idbuf as ib_

def hl_faces_(scene, edit=None, vis='faces'):
    """a scene drawn with visibility vis, edit(scene_json) changing its export first: (report, svg, folder)"""
    td_ = Path(tempfile.mkdtemp(prefix='hl-'))
    for f_ in ('request.json', 'scene.json', 'meshes.bin'):
        shutil.copy(FX / 'hidden-lines' / scene / f_, td_ / f_)
    if edit:
        s_ = json.loads((td_ / 'scene.json').read_text())
        edit(s_)
        (td_ / 'scene.json').write_text(json.dumps(s_))
    rq_ = json.loads((td_ / 'request.json').read_text())
    rq_['visibility'] = vis
    (td_ / 'request.json').write_text(json.dumps(rq_))
    d_, rep_ = hl_.build(td_ / 'request.json')
    W_, H_ = rq_['frame']['w_pt'], rq_['frame']['h_pt']
    d_.to_svg(td_ / 'out.svg', canvas=(W_, H_), origin=(0.0, H_))
    d_.to_dxf(td_ / 'out.dxf')
    return rep_, td_ / 'out.svg', td_

# every scene drawn with faces lints as the engine's drawing does: no errors, and warnings of the same kinds
hl_fl_ = {}
for sc_ in hl_scenes_ + ['above', 'curved', 'curved-cut', 'hidden']:
    found_ = {}
    for vis_ in ('engine', 'faces'):
        rep_f_, svg_f_, td_f_ = hl_faces_(sc_, vis=vis_)
        tk_ = load(svg_f_)
        found_[vis_] = lint.check(lint.read_svg(svg_f_), tk_) + lint.check(lint.read_dxf(td_f_ / 'out.dxf', None), tk_)
    errs_ = [m for lv, _, m, _ in found_['faces'] if lv == 'error']
    kinds_ = [sorted({k for lv, k, _, _ in found_[v_] if lv == 'warning' and k != 'beside'}) for v_ in ('engine', 'faces')]
    if errs_ or kinds_[0] != kinds_[1]:
        hl_fl_[sc_] = (errs_[:2], kinds_)
ok(not hl_fl_, f'hidden-lines: every scene drawn with visibility "faces" lints with no errors and the engine\'s kinds of '
   f'warning: {hl_fl_}')

# what is as long as the meshes is taken hidden.CHUNK vertices, triangles or points at a time, for the drawing step's
# peak memory: chunks of a few draw the same as one chunk
def hl_chunked_(scene, n):
    keep_ = hl_.CHUNK
    hl_.CHUNK = n
    try:
        rep_, svg_, _ = hl_faces_(scene)
    finally:
        hl_.CHUNK = keep_
    rep_.get('faces', {}).pop('seconds', None)
    return {k_: v_ for k_, v_ in rep_.items() if k_ not in ('seconds', 'request', 'scene')}, svg_.read_text()
hl_ch_ = [sc_ for sc_ in ('fuzz-146', 'curved-cut', 'cut-rooms') if hl_chunked_(sc_, 5) != hl_chunked_(sc_, 1 << 30)]
ok(not hl_ch_, f'hidden-lines: the meshes taken five vertices, triangles or points at a time draw the same '
   f'drawing and report as taken whole (a perspective cut, a curved cut, rooms cut): {hl_ch_}')

try:
    hl_faces_('tjunction', vis='raster')
    hl_vis_bad_ = None
except SystemExit as e_:
    hl_vis_bad_ = str(e_)
ok(hl_vis_bad_ and 'visibility' in hl_vis_bad_ and "'raster'" in hl_vis_bad_,
   f'hidden-lines: a request\'s visibility other than "engine" or "faces" is refused, named: {hl_vis_bad_}')

# Duplicate segments (vis 'dup') are lines the faces decide on and the engine's path leaves out: tjunction's box with
# every segment of it marked Duplicate, then with none at all, its front top edge drawn from its mesh
hl_box_o_ = lambda s: {o['i'] for o in s['objects'] if o['layer'].endswith('::box')}
def hl_dup_(s):
    for g in s['segments']:
        if g['o'] in hl_box_o_(s) and g.get('cut') is None and not g.get('vis'):
            g['vis'] = 'dup'
def hl_nobox_(s):
    s['segments'] = [g for g in s['segments'] if g['o'] not in hl_box_o_(s)]
hl_edge_ = ((5.1, 2, 3), (7.9, 2, 3))                  # the box's top edge toward the camera
hl_dd_ = {}
for name_, ed_ in (('dup', hl_dup_), ('none', hl_nobox_)):
    for vis_ in ('engine', 'faces'):
        rep_e_, svg_e_, td_e_ = hl_faces_('tjunction', ed_, vis=vis_)
        hl_dd_[name_, vis_] = round(hl_drawn_(hl_lines_(svg_e_), td_e_, *hl_edge_), 2)
ok(hl_dd_['dup', 'engine'] == 0 and hl_dd_['dup', 'faces'] >= 0.95 and hl_dd_['none', 'engine'] == 0
   and hl_dd_['none', 'faces'] >= 0.95,
   f'hidden-lines: an edge the engine marked Duplicate is drawn where the faces see it, and one the engine left out '
   f'altogether is drawn from the box\'s mesh; the engine\'s path draws neither: {hl_dd_}')

# what the engine hid is drawn where the faces see it, and nothing it called visible is drawn behind a surface:
# stretches planted on the box's top face (vis 'under') and inside the box under it, and a wall edge the engine called
# visible across the box (hl_plant_), which the faces take out with no mesh check run
def hl_seen_(s):
    M_ = s['view']['xform']
    cam_ = lambda p: [sum(M_[i][j] * v for j, v in enumerate(list(p) + [1])) for i in range(3)]
    box_ = min(hl_box_o_(s))
    for a_, b_ in (((5.5, 3.5, 3), (7.5, 3.5, 3)), ((5.2, 4.8, 2.2), (6.2, 4.8, 2.2))):
        s['segments'].append(dict(o=box_, src='geom', sil='Crease', pass_='main', vis='under', sides='', scene=False,
                                  pts=[cam_(a_), cam_(b_)]))
    hl_plant_(s)
rep_sn_, svg_sn_, td_sn_ = hl_faces_('tjunction', hl_seen_)
lines_sn_ = hl_lines_(svg_sn_)
ok(hl_drawn_(lines_sn_, td_sn_, (5.6, 3.5, 3), (7.4, 3.5, 3)) >= 0.95 and hl_drawn_(lines_sn_, td_sn_, (5.3, 4.8, 2.2), (6.1, 4.8, 2.2)) == 0
   and hl_drawn_(lines_sn_, td_sn_, (6.0, 2, 1.5), (7.0, 2, 1.5)) == 0 and rep_sn_['hidden_by_meshes']['count'] == 0
   and rep_sn_['under']['kept'] == 0 and not rep_sn_['verify']['occluded'],
   f'hidden-lines: with faces a hidden stretch on the face seen is drawn, one inside the box is not, and a line the engine '
   f'called visible behind the box is not, with no mesh check or revival run: {rep_sn_["faces"]}')

# the faces themselves, on cut-box's export: a solid's back faces, seen through its cut, stand for the cut face and hide
# what lies behind the plane; the cut's own outline, on the plane, is seen
s_cb_, V_cb_, F_cb_, to_cb_ = hl_.read_scene(FX / 'hidden-lines' / 'cut-box')
rq_cb_ = json.loads((FX / 'hidden-lines' / 'cut-box' / 'request.json').read_text())
k_cb_, f_cb_ = s_cb_['view']['pt_per_unit'], s_cb_['view']['true_factor']
W_cb_, H_cb_ = rq_cb_['frame']['w_pt'], rq_cb_['frame']['h_pt']
hx_cb_, hy_cb_ = W_cb_ / 2 / k_cb_, H_cb_ / 2 / k_cb_
tr_cb_ = hl_.Tris(V_cb_, F_cb_, to_cb_, f_cb_, (hx_cb_, hy_cb_), np.zeros(len(s_cb_['objects']) + 1, dtype=np.int64),
                  3 * s_cb_['bias'])
buf_cb_, E_cb_ = hl_.faces_of(s_cb_, V_cb_, F_cb_, tr_cb_, np.ones(len(tr_cb_.P), dtype=bool), {1}, k_cb_, W_cb_, H_cb_)
M_cb_ = s_cb_['view']['xform']
def hl_frame_(p):
    c_ = [sum(M_cb_[i][j] * v for j, v in enumerate(list(p) + [1])) for i in range(3)]
    return c_[0] * f_cb_ + hx_cb_, c_[1] * f_cb_ + hy_cb_, c_[2]
pts_cb_ = [hl_frame_(p) for p in ((4, 3.5, 1), (4, 4.0, 1), (4, 4.5, 1), (5, 3, 2), (5, 1, 3), (5, 5, 1))]
seen_cb_ = buf_cb_.seen(*[np.array(v) for v in zip(*pts_cb_)]).tolist()
cap_off_ = hl_.Tris(V_cb_, F_cb_, to_cb_, f_cb_, (hx_cb_, hy_cb_), np.zeros(len(s_cb_['objects']) + 1, dtype=np.int64), 3 * s_cb_['bias'])
s_nc_ = dict(s_cb_, objects=[dict(o, solid=False) for o in s_cb_['objects']])
buf_nc_, _ = hl_.faces_of(s_nc_, V_cb_, F_cb_, cap_off_, np.ones(len(cap_off_.P), dtype=bool), set(), k_cb_, W_cb_, H_cb_)
seen_nc_ = buf_nc_.seen(*[np.array(v) for v in zip(*pts_cb_[:3])]).tolist()
ok(seen_cb_ == [False, False, False, True, True, True] and seen_nc_ == [True, True, True],
   f'hidden-lines: through cut-box\'s cut its back faces hide three points 1 m behind the plane, and three on the plane '
   f'are seen; with the box not a closed solid the three are seen through the opening: {seen_cb_}, {seen_nc_}')

# the buffer on triangles placed by hand, a frame of 20 x 20 pt at a point a unit: two triangles sharing a diagonal
# leave no pixel centre out; a sample on a face, behind it, in front, and within the tolerance square to it
def ib_buf_(tris, objs=None, cap=None, planes=None):
    P_ = np.array(tris, dtype=float)
    o_ = np.zeros(len(P_), dtype=np.int64) if objs is None else np.array(objs, dtype=np.int64)
    return ib_.Buffer(P_, o_, np.ones(len(P_), dtype=bool), False, (10.0, 10.0, 1.0, 0.0, 0.0), 1.0, 20.0, 20.0, 0.01,
                      0.1, 0.0, np.zeros((0, 4)) if planes is None else np.array(planes, dtype=float),
                      np.zeros(int(o_.max()) + 2, dtype=bool) if cap is None else np.array(cap, dtype=bool))
sq_ = [[(2, 2, 0), (12, 2, 0), (12, 12, 0)], [(2, 2, 0), (12, 12, 0), (2, 12, 0)]]
b_sq_ = ib_buf_(sq_)
seen_sq_ = b_sq_.seen(np.array([7, 7, 7, 15, 7, 7.0]), np.array([7, 7, 7, 7, 7, 7.0]), np.array([-1, 0, 1, -1, -0.05, -0.2])).tolist()
ok(int((b_sq_.tri >= 0).sum()) == 1600 and set(np.unique(b_sq_.tri[b_sq_.tri >= 0]).tolist()) == {0, 1}
   and seen_sq_ == [False, True, True, True, True, False],
   f'hidden-lines: the ID buffer gives each of a square\'s 1,600 pixel centres one of its two triangles, those on their '
   f'shared edge included, and sees a point on the face, in front of it, off it and 0.05 pt behind it, not 1 pt or '
   f'0.2 pt behind it: {seen_sq_}')

# a solid's back face (wound clockwise as seen) behind a clip plane at z = 0 hides a point in front of it that is not on
# the plane; a back face of what is not a solid hides nothing in front of it
bk_ = [[(2, 2, -1), (12, 12, -1), (12, 2, -1)]]
cap_bk_ = ib_buf_(bk_, cap=[True, False], planes=[[0, 0, 1, 0]]).seen(np.array([7, 7.0]), np.array([5, 5.0]), np.array([-0.5, 0.0])).tolist()
open_bk_ = ib_buf_(bk_, planes=[[0, 0, 1, 0]]).seen(np.array([7.0]), np.array([5.0]), np.array([-0.5])).tolist()
ok(cap_bk_ == [False, True] and open_bk_ == [True],
   f'hidden-lines: a closed solid\'s back face stands for its cut face, hiding a point behind the plane and not one on it; '
   f'an open surface\'s back face hides nothing: {cap_bk_}, {open_bk_}')

# a face folded over another: the pixel centres round a point show a face that would hide it and does not reach it,
# while a sliver under a pixel wide, at the same depth, covers it; the exact query of the triangles in its cell finds
# the sliver. The ground behind covers everything
fold_ = [[(-5, -5, -2), (25, -5, -2), (10, 25, -2)],          # the ground, behind the point
         [(0, 0, 0), (4.99, 0, 0), (4.99, 10, 0)],            # in front, holding the pixel centre left of the point
         [(4.99, 4.9, 0), (5.06, 5.0, 0), (4.99, 5.1, 0)]]   # the sliver over the point, holding no pixel centre
fold_seen_ = [ib_buf_(fold_).seen(np.array([5.0]), np.array([5.0]), np.array([-1.0]))[0],
              ib_buf_(fold_[:2]).seen(np.array([5.0]), np.array([5.0]), np.array([-1.0]))[0]]
ok(fold_seen_ == [False, True],
   f'hidden-lines: a point covered by a sliver no pixel centre holds, beside a face that would hide it, is found hidden '
   f'by the exact query of its cell; without the sliver it is seen: {fold_seen_}')

# where a line turns hidden its end is found by halving: a line 1 pt behind a square whose edge is at x = 10
ln_ = [np.array([[2.0, 15, -1], [18.0, 15, -1]])]
b_ln_ = ib_buf_([[(10, 12, 0), (19, 12, 0), (19, 18, 0)], [(10, 12, 0), (19, 18, 0), (10, 18, 0)]])
S_ln_ = ib_.samples(ln_, 1.0, 20.0, 20.0)
seen_ln_ = b_ln_.seen(*ib_.at(S_ln_, False))
st_ln_ = ib_.stretches(S_ln_, b_ln_, seen_ln_, seen_ln_)
end_ln_ = ib_.stretch_points(S_ln_, False, st_ln_[0][0], ln_[0], st_ln_[0][1], st_ln_[0][2])[-1] if len(st_ln_) == 1 else None
ok(end_ln_ is not None and abs(end_ln_[0] - 10) < 1e-3 and end_ln_[2] == -1,
   f'hidden-lines: a line passing behind a face ends where the face begins, found by halving to under a thousandth of '
   f'a point: {end_ln_}')

# a mesh's own edges: a box seen square on, written as the export writes a clipped mesh (three vertices a triangle),
# has twelve, all creases; its top taken off, four of them are its open top's boundary; a vertex one float32 step off
# its neighbour is welded to it all the same
def ib_box_(top=True):
    q_ = lambda x, y, z: (float(x), float(y), float(z))
    faces_ = [[(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
              [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
              [(1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)], [(0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)]]
    if not top:
        faces_ = faces_[1:]
    T_ = [t for f4 in faces_ for t in ((f4[0], f4[1], f4[2]), (f4[0], f4[2], f4[3]))]
    V_ = np.array([q_(*p) for t in T_ for p in t]) * 10 + 5
    return V_, np.arange(len(V_)).reshape(-1, 3), [dict(o=0, v0=0, nv=len(V_), f0=0, nf=len(T_))]
mk_ = {}
for name_, top_ in (('closed', True), ('open', False)):
    V_m_, F_m_, it_m_ = ib_box_(top_)
    if name_ == 'closed':
        V_m_[3, 0] = np.nextafter(np.float32(V_m_[3, 0]), np.float32(100))   # one float32 step off its neighbours
    E_m_ = ib_.mesh_edges(V_m_, F_m_, it_m_, {0}, lambda X: X, False)
    mk_[name_] = sorted(collections.Counter(E_m_['kind'].tolist()).items())
ok(mk_ == {'closed': [(1, 12)], 'open': [(0, 4), (1, 8)]},
   f'hidden-lines: a box\'s mesh written a triangle apart gives its twelve edges as creases, one vertex a float32 step '
   f'off welded; open at the top, four of them are the boundary: {mk_}')

# the export from version 4 writes its meshes less an origin, which float32 would round 0.2 pt off at the model's depth:
# tjunction's meshes written so draw as before, and an older export, with none, reads as it did
s_or_ = json.loads((FX / 'hidden-lines' / 'tjunction' / 'scene.json').read_text())
_, V_or_, _, _ = hl_.read_scene(FX / 'hidden-lines' / 'tjunction')
org_ = [0.0, 0.0, float(np.round(V_or_[:, 2].mean()))]
td_or_ = Path(tempfile.mkdtemp(prefix='hl-'))
for f_ in ('request.json', 'scene.json', 'meshes.bin'):
    shutil.copy(FX / 'hidden-lines' / 'tjunction' / f_, td_or_ / f_)
raw_or_ = (td_or_ / 'meshes.bin').read_bytes()
nv_or_ = s_or_['meshes']['vertices']
(td_or_ / 'meshes.bin').write_bytes((V_or_ - org_).astype('<f4').tobytes() + raw_or_[nv_or_ * 12:])
s_or_['meshes']['origin'], s_or_['version'] = org_, 4
(td_or_ / 'scene.json').write_text(json.dumps(s_or_))
_, V_or2_, _, _ = hl_.read_scene(td_or_)
svg_or_ = {}
for name_, folder_ in (('v3', FX / 'hidden-lines' / 'tjunction'), ('v4', td_or_)):
    td_x_ = Path(tempfile.mkdtemp(prefix='hl-'))
    for f_ in ('request.json', 'scene.json', 'meshes.bin'):
        shutil.copy(folder_ / f_, td_x_ / f_)
    rq_x_ = json.loads((td_x_ / 'request.json').read_text())
    rq_x_['visibility'] = 'faces'
    (td_x_ / 'request.json').write_text(json.dumps(rq_x_))
    d_x_, _ = hl_.build(td_x_ / 'request.json')
    d_x_.to_svg(td_x_ / 'o.svg', canvas=(rq_x_['frame']['w_pt'], rq_x_['frame']['h_pt']), origin=(0.0, rq_x_['frame']['h_pt']))
    svg_or_[name_] = sorted(round(sum(math.dist(a, b) for a, b in p.segs), 1) for p in lint.read_svg(td_x_ / 'o.svg')['paths'])
ok(np.abs(V_or2_ - V_or_).max() < 1e-3 and svg_or_['v3'] == svg_or_['v4'],
   f'hidden-lines: meshes written less an origin read back to within float32 of the depth left over, and draw the same '
   f'{len(svg_or_["v4"])} paths as the older export')

# a mesh's own edge gives way only to a drawn line of its object lying along it: fuzz seeds 119 and 146, recorded as
# version 4 exports by fuzz.py's build (fixtures fuzz-119, fuzz-146). In 119 a box's edge, which the engine has no
# segment along, has its corners and middle on lines crossing it; in 146 a cylinder's silhouette, the engine's hidden
# and the mesh's seen 0.1 pt from it. Each went whole when any segment of the object near it stood for it
hl_fz_ = {}
for sc_ in ('fuzz-119', 'fuzz-146'):
    rep_fz_, svg_fz_, td_fz_ = hl_faces_(sc_)
    hl_fz_[sc_] = round(fz_.missing(td_fz_, svg_fz_)[0], 2)
ok(all(v_ <= fz_.MISS_PT for v_ in hl_fz_.values()),
   f'hidden-lines: with faces nothing seen is missing from fuzz seeds 119 (a box\'s edge crossed at its corners and '
   f'middle) and 146 (a cylinder\'s silhouette): longest missing {hl_fz_} pt')

# the fuzz checker's missing lines (fuzz.py, missing): tjunction drawn by the engine with the box's segments left out
# misses the box's edges; drawn with faces it misses nothing
hl_miss_ = {}
for vis_ in ('engine', 'faces'):
    _, svg_ms_, td_ms_ = hl_faces_('tjunction', hl_nobox_, vis=vis_)
    hl_miss_[vis_] = fz_.missing(td_ms_, svg_ms_)
ok(hl_miss_['engine'][0] > fz_.MISS_PT and hl_miss_['faces'][0] <= fz_.MISS_PT,
   f'hidden-lines: the fuzz checker finds the box\'s edges missing from the engine\'s drawing of an export without them, '
   f'and nothing missing from the faces\': longest {hl_miss_["engine"][0]:.1f} and {hl_miss_["faces"][0]:.1f} pt')

# ---- synthetic scenes written without Rhino (fixtures/hidden-lines/synth.py), drawn with faces: each drawing's answer
# is worked out from the model and the view alone, not from what the engine made of them
spec_sy_ = importlib.util.spec_from_file_location('hl_synth', FX / 'hidden-lines' / 'synth.py')
sy_ = importlib.util.module_from_spec(spec_sy_)
spec_sy_.loader.exec_module(sy_)

def hl_synth_(name, parts, view, groups, **kw):
    """a synthetic scene written and drawn in a temporary folder: (report, svg, folder)"""
    td_ = Path(tempfile.mkdtemp(prefix='hl-')) / name
    sy_.write(td_, parts, view, groups, **kw)
    d_, rep_ = hl_.build(td_ / 'request.json')
    rq_ = json.loads((td_ / 'request.json').read_text())
    d_.to_svg(td_ / 'out.svg', canvas=(rq_['frame']['w_pt'], rq_['frame']['h_pt']), origin=(0.0, rq_['frame']['h_pt']))
    return rep_, td_ / 'out.svg', td_

def hl_side_(td, a, b, e=0.05):
    """the page path of the model segment ab, less e at each end"""
    a_, b_ = np.array(a, float), np.array(b, float)
    u_ = (b_ - a_) / np.linalg.norm(b_ - a_)
    return [list(sy_.page(td, a_ + u_ * e)), list(sy_.page(td, b_ - u_ * e))]

def hl_widths_(svg, td, sides):
    """for each (a, b) model segment: the share drawn along it within 0.2 pt and the widths there (a line check)"""
    res_ = hl_.check_notes(svg, [dict(kind='line', path=hl_side_(td, a, b), tol_pt=0.2) for a, b in sides])
    return [(round(m, 2), w.split('widths ')[-1] if 'widths' in w else '-') for _, _, m, w in res_]

# openings : a wall 0.3 m thick seen
# from the left and above at 1:50, a wall 4 m behind it seen through, with a window; then one with a door cut from its
# foot; then one with a pier standing out of its face. An opening's rim on the near face is the nearer plane's outline,
# at the wall's profile weight (medium, 0.3 pt) on every side, though the sides where the reveal shows inside are
# creases; the reveal's far edges seen through it stay lighter (0.2 pt, overlaps). The pier's foot is a concave loop,
# not an opening: its edges stay creases (fine, 0.12 pt)
hl_op_v_ = dict(direction=(0.4, 1, -0.2), target=(3, 0, 1.5))
hl_op_g_ = [dict(id='building', layers=['hl::op::*'], layer='CUT')]
hl_op_back_ = dict(layer='hl::op::back', group='building', tris=sy_.box(-2, 4, 0, 8, 4.3, 3), solid=True)
_, svg_op_, td_op_ = hl_synth_('window', [dict(layer='hl::op::wall', group='building', solid=True,
                                                tris=sy_.wall_with_opening(0, 6, 0, 0.3, 0, 3, 2, 3.5, 0.8, 2.2)), hl_op_back_],
                               hl_op_v_, hl_op_g_)
w_op_ = hl_widths_(svg_op_, td_op_, [((2, 0, 0.8), (2, 0, 2.2)), ((2, 0, 2.2), (3.5, 0, 2.2)), ((3.5, 0, 2.2), (3.5, 0, 0.8)),
                                    ((3.5, 0, 0.8), (2, 0, 0.8)), ((3.5, 0.3, 0.8), (3.5, 0.3, 2.2)), ((2.1, 0.3, 0.8), (3.4, 0.3, 0.8))])
_, svg_dr_, td_dr_ = hl_synth_('door', [dict(layer='hl::op::wall', group='building', solid=True,
                                             tris=sy_.wall_with_door(0, 6, 0, 0.3, 0, 3, 2, 3, 2.1)), hl_op_back_], hl_op_v_, hl_op_g_)
w_dr_ = hl_widths_(svg_dr_, td_dr_, [((2, 0, 0.05), (2, 0, 2.1)), ((2, 0, 2.1), (3, 0, 2.1)), ((3, 0, 2.1), (3, 0, 0.05)),
                                    ((3, 0.3, 0.05), (3, 0.3, 2.1))])
_, svg_pr_, td_pr_ = hl_synth_('pier', [dict(layer='hl::op::wall', group='building', solid=True,
                                             tris=sy_.wall_with_pier(0, 6, 0, 0.3, 0, 3, 2, 3, 0.5, 2.5, -0.2)), hl_op_back_],
                               hl_op_v_, hl_op_g_)
w_pr_ = hl_widths_(svg_pr_, td_pr_, [((2, 0, 2.5), (3, 0, 2.5)), ((2, 0, 0.5), (2, 0, 2.5))])
ok(all(m_ >= 0.9 and w_ == '0.30 to 0.30 pt' for m_, w_ in w_op_[:4]) and all(m_ >= 0.9 and w_ == '0.20 to 0.20 pt' for m_, w_ in w_op_[4:])
   and all(m_ >= 0.9 and w_ == '0.30 to 0.30 pt' for m_, w_ in w_dr_[:3]) and w_dr_[3][0] >= 0.9 and w_dr_[3][1] == '0.20 to 0.20 pt'
   and all(m_ >= 0.9 and w_ == '0.12 to 0.12 pt' for m_, w_ in w_pr_),
   f'hidden-lines: an opening\'s rim on the nearer plane is drawn at that plane\'s outline weight on every side, a '
   f'window\'s and a door\'s cut from a wall\'s foot, the reveal\'s far edges lighter; a pier\'s foot is no opening '
   f'(window {w_op_}; door {w_dr_}; pier {w_pr_})')

# the cut at a valley : two roofs cut square at 1:100, steep, meeting in a V, as one
# solid and as two separate bands crossing in an X. The white wedge between their outer skins narrows to the valley's
# point, under twice the cut's weight for its last 3.5 pt or so; it is the outline's own corner, not a gap between
# parts, so the outline runs down both skins to the point (worked out from the rings: the point lies on the drawn cut)
# and nothing is drawn across the wedge above it
hl_v_ = {}
for name_, parts_, tip_ in (
        ('v', [dict(layer='hl::v::roof', group='house', solid=True,
                    tris=sy_.prism([(-1.0, 6.0), (0.0, 0.0), (1.0, 6.0), (0.85, 6.0), (0.0, 0.6), (-0.85, 6.0)], -1, 1))],
         (0.0, 0.0, 0.6)),
        ('x', [dict(layer='hl::v::left', group='house', solid=True,
                    tris=sy_.prism([(-1.0, 6.0), (-0.85, 6.0), (0.25, -0.6), (0.1, -0.6)], -1, 1)),
               dict(layer='hl::v::right', group='house', solid=True,
                    tris=sy_.prism([(1.0, 6.0), (0.85, 6.0), (-0.25, -0.6), (-0.1, -0.6)], -1, 1))],
         (0.0, 0.0, 0.9))):
    rep_v_, svg_v_, td_v_ = hl_synth_(name_, parts_, dict(direction=(0, 1, 0), target=(0, 0, 3)),
                                      [dict(id='house', layers=['hl::v::*'], layer='CUT')],
                                      clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(200, 300))
    tx_, ty_ = sy_.page(td_v_, tip_)
    cut_v_ = [p for p in lint.read_svg(svg_v_)['paths'] if p.layer == 'CUT']
    near_ = min((math.dist((tx_, ty_), b) for p in cut_v_ for _, b in p.segs), default=99)
    clear_v_ = hl_.check_notes(svg_v_, [dict(kind='clear', box=[tx_ - 0.15, ty_ - 4.0, tx_ + 0.15, ty_ - 1.2], layers=['CUT'],
                                             max_pt=0.05)])[0]
    hl_v_[name_] = (round(near_, 3), clear_v_[1], len(rep_v_['cuts']['gaps_closed']))
ok(all(n_ < 0.05 and c_ for n_, c_, _ in hl_v_.values()),
   f'hidden-lines: at a valley the cut\'s outline runs down both outer skins to the valley\'s point, the white wedge '
   f'between them left open, for one solid and for two bands crossing (tip to the outline in pt, wedge clear, gaps '
   f'closed: {hl_v_})')

# a floor skylight : a slab 0.3 m thick cut square at 1:100, a skylight's frame (two
# jambs 5 cm thick) and its glass (1 cm) in the slab's opening. Put in the windows' group, lighter than the house it
# is in, the skylight is cut as the wall's window is, frame and glass one region a rung lighter (0.25 pt), the slab's
# heavy outline (0.8 pt) drawn over the frame's outer side; put in the house's own group, as the model's request had it,
# the frame and glass run on into the slab's poché, the frame's inner side drawn heavy and its outer side not at all
hl_sk_ = {}
for gr_ in ('windows', 'house'):
    parts_ = [dict(layer='hl::sk::slab', group='house', solid=True, tris=sy_.box(0, -1, 3, 2, 1, 3.3)),
              dict(layer='hl::sk::slab', group='house', solid=True, tris=sy_.box(3.5, -1, 3, 6, 1, 3.3)),
              dict(layer='hl::sk::frame', group=gr_, solid=True, tris=sy_.box(2, -0.5, 3, 2.05, 0.5, 3.3)),
              dict(layer='hl::sk::frame', group=gr_, solid=True, tris=sy_.box(3.45, -0.5, 3, 3.5, 0.5, 3.3)),
              dict(layer='hl::sk::glass', group=gr_, solid=True, tris=sy_.box(2.05, -0.5, 3.28, 3.45, 0.5, 3.29))]
    groups_ = [dict(id='house', layers=['hl::sk::slab'] + (['hl::sk::frame', 'hl::sk::glass'] if gr_ == 'house' else []),
                    layer='CUT')] + ([dict(id='windows', layers=['hl::sk::frame', 'hl::sk::glass'], layer='DETAIL', body='house')]
                                     if gr_ == 'windows' else [])
    rep_sk_, svg_sk_, td_sk_ = hl_synth_(f'skylight-{gr_}', [p_ for p_ in parts_], dict(direction=(0, 1, 0), target=(3, 0, 3)),
                                         groups_, clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(300, 200))
    hl_sk_[gr_] = hl_widths_(svg_sk_, td_sk_, [((2.05, 0, 3.02), (2.05, 0, 3.26)), ((2.0, 0, 3.02), (2.0, 0, 3.28)),
                                              ((2.1, 0, 3.285), (3.4, 0, 3.285))])
ok(hl_sk_['windows'][0][1] == '0.25 to 0.25 pt' and hl_sk_['windows'][1][1].endswith('0.80 pt')
   and hl_sk_['windows'][2][1] == '0.25 to 0.25 pt' and hl_sk_['house'][0][1] == '0.80 to 0.80 pt' and hl_sk_['house'][1][0] == 0,
   f'hidden-lines: a floor skylight in the windows\' group is cut as a window is, a rung lighter, inside the slab\'s heavy '
   f'outline; in the house\'s own group it runs into the poché, heavy: {hl_sk_}')

# the depth bands' span by area (the adversarial tests critique, finding 2): a wall 10 by 4 m standing 2 m past the plane, and a small
# cylinder of 48 facets 8 m past it, above the wall, at 1:100 with depth_bands_share [0.25, 0.6]. The subject's surfaces
# as the buffer sees them lie 2 m past the plane but for 1.5% of them, so the span (their 95th percentile) is 2 m and
# the bands 0.5 and 1.2 m; counted by drawn edge, the cylinder's hundred-odd edges took the span to 8 m
rep_db_, _, _ = hl_synth_('depth-span', [dict(layer='hl::db::wall', group='house', solid=True, tris=sy_.box(-5, 2, 0, 5, 2.3, 4)),
                                         dict(layer='hl::db::far', group='house', solid=True,
                                              tris=sy_.cylinder(0, 8, 4.5, 5.5, 0.3, 48))],
                          dict(direction=(0, 1, 0), target=(0, 0, 3)), [dict(id='house', layers=['hl::db::*'], layer='CUT')],
                          clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(400, 300),
                          request=dict(depth_bands_share=[0.25, 0.6]))
ok(rep_db_.get('depth_bands', {}).get('bands_m') == [0.5, 1.2],
   f'hidden-lines: with faces the depth bands\' span is the subject\'s seen area\'s 95th percentile past the plane, 2 m '
   f'for a wall with a small far cylinder, not its edges\': {rep_db_.get("depth_bands")}')

# depth bands with no clip start at the subject's nearest line (the HL session's demo house, ): a box
# 10 by 6 by 4 m on a ground slab whose near edge runs 12 m in front of it, seen nearly square on and from the
# south-west above at 1:200 with depth_bands_share [0.25, 0.6]. Measured from the ground's edge, the box fell past the
# last band and its lines printed a weight lighter (its profile 0.25 pt for 0.8); from the box's own front, its bands
# and weights are those of the box drawn alone
dg_h_ = dict(layer='hl::dg::house', group='house', solid=True, tris=sy_.box(-5, 0, 0, 5, 6, 4))
dg_g_ = dict(layer='hl::dg::ground', group='ground', solid=True, tris=sy_.box(-14, -12, -0.3, 14, 14, 0))
dg_groups_ = [dict(id='house', layers=['hl::dg::house'], layer='DETAIL', profile_layer='OUTLINE'),
              dict(id='ground', layers=['hl::dg::ground'], layer='CONTEXT', ground=True)]
dg_ = {}
for vn_, view_, frame_, sides_ in (
        ('elevation', dict(direction=(0.05, 1, -0.05), target=(0, 0, 2)), (400, 200),
         [((-5, 0, 4), (5, 0, 4)), ((-5, 0, 0.3), (-5, 0, 4)), ((5, 0, 0.3), (5, 0, 4))]),
        ('isometric', dict(direction=(1, 1, -1), target=(0, 3, 2)), (400, 400),
         [((-5, 0, 0.3), (-5, 0, 4)), ((-5, 0, 4), (5, 0, 4)), ((-5, 0, 4), (-5, 6, 4)), ((5, 0, 0.3), (5, 0, 4)),
          ((5, 6, 4), (5, 0, 4))])):
    for g_ in (False, True):
        rep_dg_, svg_dg_, td_dg_ = hl_synth_(f'depth-start-{vn_}-{int(g_)}', [dg_h_] + ([dg_g_] if g_ else []), view_,
                                             dg_groups_ if g_ else dg_groups_[:1], scale=200, frame=frame_,
                                             request=dict(depth_bands_share=[0.25, 0.6]))
        dg_[vn_, g_] = (rep_dg_.get('depth_bands', {}).get('bands_m'), hl_widths_(svg_dg_, td_dg_, sides_))
ok(all(dg_[v_, True] == dg_[v_, False] for v_ in ('elevation', 'isometric'))
   and dg_['elevation', False][1][2][1] == '0.80 to 0.80 pt',
   f'hidden-lines: with no clip the depth bands start at the subject\'s nearest line, so a ground slab running 12 m in '
   f'front of a box leaves its bands and weights as they are drawn alone, in an elevation and an isometric: {dg_}')

# thin faces rank lines, not their pieces : a disc 8 m across, of 384
# facets, seen from just above at 1:100, with a context beam's foot 0.4 pt above its back point on the page and
# columns between whose edges come down to the disc. The faces between the disc's back edge and the beam are thinner
# than doubles_pt and keep their heaviest line, the disc's profile, whole along its facets: its back edge from x -1 to
# 1 m, worked out from the circle, has no gap
d_tf_ = np.array([0, 1, -0.15]) / np.linalg.norm([0, 1, -0.15])
u_tf_ = np.cross(np.cross(d_tf_, [0, 0, 1]), d_tf_)
u_tf_ /= np.linalg.norm(u_tf_)
zb_tf_ = (u_tf_ @ np.array([0, 6.0, 0.3]) + 0.4 / (72 / 25.4 * 10) - u_tf_[1] * 6.0) / u_tf_[2]
_, svg_tf_, td_tf_ = hl_synth_('thin-face', [dict(layer='hl::tf::disc', group='pavilion', solid=True, tris=sy_.cylinder(0, 2, 0, 0.3, 4, 384)),
                                             dict(layer='hl::tf::beam', group='context', solid=True, tris=sy_.box(-3, 6.0, zb_tf_, 3, 6.2, zb_tf_ + 0.5))]
                               + [dict(layer='hl::tf::col', group='context', solid=True, tris=sy_.box(x_, 6.2, -1, x_ + 0.15, 6.5, 3))
                                  for x_ in np.arange(-1.5, 1.5, 0.25)],
                               dict(direction=tuple(d_tf_), target=(0, 3, 0)),
                               [dict(id='pavilion', layers=['hl::tf::disc'], layer='CUT'),
                                dict(id='context', layers=['hl::tf::beam', 'hl::tf::col'], layer='CONTEXT')], scale=100, frame=(300, 200))
gap_tf_ = hl_.check_notes(svg_tf_, [dict(kind='gap', path=[list(sy_.page(td_tf_, (x_, 2 + math.sqrt(16 - x_ * x_), 0.3)))
                                                          for x_ in np.linspace(-1, 1, 41)], tol_pt=0.15, max_pt=0.1, min_w=0.2)])[0]
ok(gap_tf_[1], f'hidden-lines: a thin face keeps its heaviest line whole along its pieces, a disc\'s back edge unbroken '
   f'under a context beam 0.4 pt behind it: {gap_tf_[3]}')

# warnings traced to the model (agreed with the HL command's session, ): tjunction's export with one
# line end pulled 0.3 pt back from the line it meets, as above, its object reported as an open polysurface. The
# report's issues carry their kind and the object's centre; the line end run on is a suspect traced to that fault,
# where it was met, and lint, reading the report beside the drawing, gives the cause of a finding there; with no
# fault on the object the place is not listed
def hl_sus_(fault, on=None):
    def edit(s):
        kf = s['view']['pt_per_unit'] * s['view']['true_factor']
        for seg in s['segments']:
            P = seg['pts']
            L = math.dist(P[0][:2], P[-1][:2])
            if len(P) == 2 and seg['src'] == 'geom' and L * kf > 20 and not seg['scene']:
                u = ((P[0][0] - P[-1][0]) / L, (P[0][1] - P[-1][1]) / L)
                P[0][0] -= u[0] * 0.3 / kf
                P[0][1] -= u[1] * 0.3 / kf
                if fault:
                    o_ = seg['o'] if on is None else next(i for i, o in enumerate(s['objects']) if o['group'] == on)
                    s['objects'][o_]['issues'].append(fault if isinstance(fault, str) else 'open polysurface: 1 naked edges')
                return
    td_ = Path(tempfile.mkdtemp(prefix='hl-'))
    for f_ in ('request.json', 'scene.json', 'meshes.bin'):
        shutil.copy(FX / 'hidden-lines' / 'tjunction' / f_, td_ / f_)
    s_ = json.loads((td_ / 'scene.json').read_text())
    edit(s_)
    (td_ / 'scene.json').write_text(json.dumps(s_))
    return hl_.build(td_ / 'request.json')[1]
rep_su_, rep_su0_ = hl_sus_(True), hl_sus_(False)
fx_su_ = [f_ for f_ in rep_su_['fixes'] if f_['kind'] == 'end cut back clear']
row_su_ = [r_ for r_ in rep_su_['suspects'] if fx_su_ and r_['at_pt'] == fx_su_[0]['at_pt']]
iss_su_ = [i_ for i_ in rep_su_['issues'] if i_['issue'].startswith('open polysurface')]
lint_su_ = None
if row_su_:
    td_su_ = Path(tempfile.mkdtemp(prefix='hl-'))
    (td_su_ / 'd.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (td_su_ / 'd-report.json').write_text(json.dumps(rep_su_ | {'_fates': None}, default=str))
    lint_su_ = lint.cause_of((fx_su_[0]['at_pt'][0] + 0.2, fx_su_[0]['at_pt'][1]), td_su_ / 'd.svg', load(td_su_ / 'd.svg'))
ok(row_su_ and row_su_[0]['what'] == 'near miss' and row_su_[0]['confidence'] == 'traced' and row_su_[0]['kinds'] == ['open']
   and row_su_[0]['action'] == 'repaired' and iss_su_ and iss_su_[0]['kind'] == 'open' and len(iss_su_[0]['model']) == 3
   and lint_su_ and lint_su_['kinds'] == ['open']
   and not [r_ for r_ in rep_su0_['suspects'] if fx_su_ and r_['at_pt'] == fx_su_[0]['at_pt']],
   f'hidden-lines: a line end met on an open polysurface is a suspect traced to it, its issue has a kind and a place, and '
   f'lint names the cause of a finding there; without the fault it is not listed: {row_su_[:1]} {lint_su_}')
# an open sheet meant to be open, the ground's, is no suspect, though its issue keeps its kind; a duplicate, found by
# boxes and counts alike, is listed as a suspicion
rep_gr_, rep_dup_ = hl_sus_(True, on='ground'), hl_sus_('duplicate of 20e212d7: the same box and counts')
fx_gr_ = [f_ for f_ in rep_gr_['fixes'] if f_['kind'] == 'end cut back clear']
dup_ = [r_ for r_ in rep_dup_['suspects'] if r_['kinds'] == ['duplicate']]
ok(fx_gr_ and not [r_ for r_ in rep_gr_['suspects'] if r_['at_pt'] == fx_gr_[0]['at_pt']]
   and any(i_['kind'] == 'open' for i_ in rep_gr_['issues'])
   and dup_ and 'a suspicion' in dup_[0]['why'],
   f'hidden-lines: the ground\'s open sheet makes no suspect, and a duplicate\'s row says it is a suspicion: {dup_[:1]}')
# each object's points are grouped by a stable sort for its box and centre: two curve objects whose segments
# interleave in the scene get the centres they get when each object's segments run together, and different ones
def hl_centres_(order):
    td_ = Path(tempfile.mkdtemp(prefix='hl-'))
    for f_ in ('request.json', 'scene.json', 'meshes.bin'):
        shutil.copy(FX / 'hidden-lines' / 'tjunction' / f_, td_ / f_)
    s_ = json.loads((td_ / 'scene.json').read_text())
    n_, o0_ = len(s_['objects']), s_['objects'][0]
    s_['objects'] += [dict(i=n_ + j, ids=[f'curve-{j}'], group=o0_['group'], layer=o0_['layer'], kind='curve', solid=False,
                           user={}, issues=['open curve'], parts=1) for j in (0, 1)]
    runs = {0: [[[-20, 5, -1990], [-15, 5, -1990]], [[-15, 5, -1990], [-15, 9, -1990]]],
            1: [[[10, -5, -1990], [16, -5, -1990]], [[16, -5, -1990], [16, -1, -1990], [12, -1, -1990]]]}
    s_['segments'] += [dict(o=n_ + j, src='curve', sil='MiscellaneousFeature', pts=runs[j][k], sides='', scene=False,
                            **{'pass': 'main'}) for j, k in order]
    (td_ / 'scene.json').write_text(json.dumps(s_))
    return {i_['object']: i_['model'] for i_ in hl_.build(td_ / 'request.json')[1]['issues'] if i_['object'] >= n_}
ctr_run_, ctr_mix_ = hl_centres_([(0, 0), (0, 1), (1, 0), (1, 1)]), hl_centres_([(1, 0), (0, 0), (1, 1), (0, 1)])
ok(len(ctr_run_) == 2 and ctr_run_ == ctr_mix_ and len({tuple(v_) for v_ in ctr_run_.values()}) == 2,
   f'hidden-lines: two curve objects whose segments interleave get the centres they get with their segments together: '
   f'{ctr_run_} {ctr_mix_}')

# the notch signature : a line 0.5 pt beside a heavier one whose end turns 0.5 pt
# onto it is a notch; one whose end turns 2 pt onto a line, a line meeting one square on and a line ending free beside
# one are not
nt_ = Path(tempfile.mkdtemp(prefix='hl-')) / 'notch.svg'
nt_.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><g id="CUT" fill="none" stroke="#000000" '
               'stroke-width="0.5"><path d="M10 10 L110 10"/><path d="M10 50 L110 50"/><path d="M10 80 L110 80"/></g>'
               '<g id="BEYOND" fill="none" stroke="#000000" stroke-width="0.12"><path d="M20 10.5 L60 10.5 L60 10"/>'
               '<path d="M20 52 L60 52 L60 50"/><path d="M80 30 L80 50"/><path d="M20 80.5 L60 80.5"/></g></svg>',
               encoding='utf-8')
nt_found_ = [tuple(round(v_, 2) for v_ in q_) for q_ in hl_.notches(lint.read_svg(nt_)['paths'])]
ok(nt_found_ == [(60.0, 10.0)], f'hidden-lines: a line end turning 0.5 pt onto a line it ran beside is a notch, a 2 pt '
   f'step, a line meeting square on and one ending free are not: {nt_found_}')

# doubles taken by line, not piece by piece (the council's first step, for the review on regression of notches and
# converging lines). A slab 10 m long seen square on at 1:100, its thickness on the page running 0.3 to 0.9 pt and
# back: its foot cannot give way where the slab is thin without being joined onto its top or ending short beside it,
# so both lines are drawn all along , its top unbroken and no line ending in a notch.
# A box's top edge with a plate behind whose top edge
# meets it at 2, 5 and 10 degrees: both edges drawn whole, the plate's to 0.3 m short of the point. Six books 2 cm thick
# (0.57 pt) leaning 0 to 4 degrees on a shelf: no notch
pt_m_ = 25.4 / 72 / 1000 * 100                         # a point on paper, in metres, at 1:100
g_f1_ = [dict(id='b', layers=['hl::f1::*'], layer='CUT')]
th_ = lambda x: (0.6 + 0.3 * math.sin(2 * math.pi * x / 5)) * pt_m_
_, svg_sl_, td_sl_ = hl_synth_('slab', [dict(layer='hl::f1::slab', group='b', solid=True,
                                             tris=sy_.prism([(x_, -th_(x_)) for x_ in np.linspace(0, 10, 201)] + [(10, 0.0), (0, 0.0)], 0, 1))],
                               dict(direction=(0, 1, 0), target=(5, 0, 0)), g_f1_, scale=100, frame=(400, 120))
along_sl_ = lambda x: [list(sy_.page(td_sl_, (x, 0, 0))), list(sy_.page(td_sl_, (x + 0.05, 0, 0)))]
sl_ = hl_.check_notes(svg_sl_, [dict(kind='gap', path=[list(sy_.page(td_sl_, (x_, 0, 0))) for x_ in np.linspace(0.05, 9.95, 100)],
                                     tol_pt=1.0, max_pt=0.3), dict(kind='notches', box=[0, 0, 400, 120], n=0)]
                      + [dict(kind='lines', n=2, path=along_sl_(x_), tol_pt=1.2, cover=0.5) for x_ in np.linspace(0.3, 9.7, 95)])
cv_ = {}
for deg_ in (2, 5, 10):
    rise_ = 4.0 * math.tan(math.radians(deg_))
    _, svg_cv_, td_cv_ = hl_synth_(f'converging-{deg_}', [
        dict(layer='hl::f1::a', group='b', solid=True, tris=sy_.box(0, 0, 0, 4, 0.5, 1)),
        dict(layer='hl::f1::bb', group='b', solid=True, tris=sy_.prism([(0, 0), (4, 0), (4, 1), (0, 1 + rise_)], 2, 2.2))],
        dict(direction=(0, 1, 0), target=(2, 0, 1)), g_f1_, scale=100, frame=(200, 120))
    cv_[deg_] = [r_[3] for r_ in hl_.check_notes(svg_cv_, [
        dict(kind='line', path=[list(sy_.page(td_cv_, (x_, 0, 1))) for x_ in np.linspace(0.05, 3.95, 40)], tol_pt=0.15, cover=0.97),
        dict(kind='line', path=[list(sy_.page(td_cv_, (x_, 2, 1 + rise_ * (1 - x_ / 4)))) for x_ in np.linspace(0.05, 3.7, 40)],
             tol_pt=0.15, cover=0.97),
        dict(kind='notches', box=[0, 0, 200, 120], n=0)]) if not r_[1]]
bk_ = [dict(layer='hl::f1::book', group='b', solid=True,
            tris=sy_.prism([(x0_, 0), (x0_ + 0.02, 0), (x0_ + 0.02 + 0.25 * t_, 0.25), (x0_ + 0.25 * t_, 0.25)], 0, 0.2))
       for x0_, t_ in ((0.3 + i_ * 0.025, math.tan(math.radians(l_))) for i_, l_ in enumerate((0, 2, 4, 1, 3, 0)))]
_, svg_bk_, _ = hl_synth_('books', bk_ + [dict(layer='hl::f1::shelf', group='b', solid=True, tris=sy_.box(0, 0, -0.02, 1, 0.25, 0))],
                          dict(direction=(0, 1, 0), target=(0.4, 0, 0.12)), g_f1_, scale=100, frame=(120, 60))
bk_res_ = hl_.check_notes(svg_bk_, [dict(kind='notches', box=[0, 0, 120, 60], n=0)])[0]
ok(all(r_[1] for r_ in sl_) and not any(cv_.values()) and bk_res_[1],
   f'hidden-lines: doubles are taken by line: a slab 0.3 to 0.9 pt thick is two lines all along, its top '
   f'unbroken; converging edges are both drawn; no line ends in a notch (slab {sl_[0][3]}, {sl_[1][3]}, '
   f'{sum(1 for r_ in sl_[2:] if r_[1])} of {len(sl_) - 2} across; converging, failing {cv_}; books {bk_res_[3]})')

# a join crossing a line (the model's pipe frames, a rail left 0.25 pt off a join): curves at 1:100, a heavier line A
# along z = 0, a lighter line B 0.5 pt under it for 2 m that then turns down at 60 degrees, and a line C of B's group
# leaving B's turn 0.5 pt under B, level, for 3 pt. B gives way beside A and is joined onto it across C; the join is
# noded with C, and C's end left past it is cut back, so no line end is left a hair off another
pt_jx_ = 25.4 / 72 / 1000 * 100
u_jx_ = np.array([math.cos(math.radians(60)), -math.sin(math.radians(60))])
cn_jx_ = np.array([2.0, -0.5 * pt_jx_])
c0_jx_ = cn_jx_ + u_jx_ * (0.5 * pt_jx_ / math.sin(math.radians(60)))
P_jx_ = lambda q: (float(q[0]), 0.0, float(q[1]))
_, svg_jx_, _ = hl_synth_('join-cross', [
    dict(layer='hl::jx::a', group='a', curve=[(0, 0, 0), (4, 0, 0)]),
    dict(layer='hl::jx::b', group='b', curve=[(0, 0, -0.5 * pt_jx_), P_jx_(cn_jx_), P_jx_(cn_jx_ + u_jx_ * 0.3)]),
    dict(layer='hl::jx::c', group='b', curve=[P_jx_(c0_jx_), P_jx_(c0_jx_ + np.array([3 * pt_jx_, 0.0]))]),
    dict(layer='hl::jx::back', group='a', solid=True, tris=sy_.box(-10, 5, -10, 14, 5.1, 10))],
    dict(direction=(0, 1, 0), target=(2, 0, 0)),
    [dict(id='a', layers=['hl::jx::a', 'hl::jx::back'], layer='CUT'), dict(id='b', layers=['hl::jx::b', 'hl::jx::c'], layer='DETAIL')],
    scale=100, frame=(200, 120))
nm_jx_ = [x_ for x_ in lint.check(lint.read_svg(svg_jx_), load(svg_jx_)) if x_[1] == 'near-miss']
ok(not nm_jx_, f'hidden-lines: a doubles join crossing a line is noded with it, the line\'s end past it cut back: {nm_jx_}')

# the doubles A/B (the council's, for the review at regression; ): a slab cut heavy (0.8 pt) at 1:100 and,
# 0.55 pt under its cut, a lone edge (0.25 pt) beyond it, ending free under it; then a beam whose top edge runs there.
# With simplify_doubles, under doubles_pt (0.6 pt, centre to centre), the lone edge gives way whole to the cut. By default its stroke,
# 0.55 pt off, is not inside the cut's (0.4 pt either side of its middle), and its ends lie beside the cut, so it stays
# whole, as the model has it (the adversarial tests doubles-min-hair at regression). The beam's top edge stays under both: giving way, it would
# leave the beam's sides ending 0.55 pt short of the cut, which nothing in the model joins (the review on
# regression)
pt_in_ = 25.4 / 72 / 1000 * 100
in_ = {}
for b_ in (False, True):
    for shape_ in ('edge', 'beam'):
        z_in_ = 3.0 - 0.55 * pt_in_
        under_ = dict(layer='hl::in::beam', group='house', curve=[(0.5, 1.0, z_in_), (3.5, 1.0, z_in_)]) if shape_ == 'edge' else \
            dict(layer='hl::in::beam', group='house', solid=True, tris=sy_.box(0.5, 1, 2.0, 3.5, 1.3, z_in_))
        _, svg_in_, td_in_ = hl_synth_(f'inside-{b_}-{shape_}', [dict(layer='hl::in::slab', group='house', solid=True, tris=sy_.box(0, -1, 3.0, 4, 1, 3.3)), under_],
                                       dict(direction=(0, 1, 0), target=(2, 0, 3)), [dict(id='house', layers=['hl::in::*'], layer='CUT')],
                                       clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(200, 120),
                                       request=None if b_ else dict(simplify_doubles=True))
        in_[(b_, shape_)] = hl_.check_notes(svg_in_, [dict(kind='line', path=[list(sy_.page(td_in_, (x_, 1.0, z_in_)))
                                                                         for x_ in np.linspace(0.7, 3.3, 30)], tol_pt=0.1, layers=['BEYOND'])])[0][2]
ok(in_[(False, 'edge')] < 0.05 and in_[(True, 'edge')] > 0.95 and in_[(False, 'beam')] > 0.95 and in_[(True, 'beam')] > 0.95,
   f'hidden-lines: a lone edge 0.55 pt under a slab\'s cut, ending free, goes simplified and stays by default; a '
   f'beam\'s top edge there stays under both, its outline closed (share drawn: {in_})')

# ---- regression : outlines the doubles opened, and converging lines joined by a kink.
# Each answer is worked out from the construction. pt6_ is a point on paper at 1:100 in metres; the curve scenes have
# a box far behind them so they have meshes
pt6_ = 25.4 / 72 / 1000 * 100
xz6_ = lambda x, z: (float(x), 0.0, float(z))
pg6_ = lambda td, x, z, y=0.0: list(sy_.page(td, (x, y, z)))
ab6_ = lambda tag: [dict(id='a', layers=[f'hl::{tag}::a*'], layer='CUT'), dict(id='b', layers=[f'hl::{tag}::b*'], layer='DETAIL')]
back6_ = lambda tag: dict(layer=f'hl::{tag}::a back', group='a', solid=True, tris=sy_.box(-10, 5, -10, 14, 5.1, 10))
box6_ = lambda td, x0, z0, x1, z1: [pg6_(td, x0, z1)[0], pg6_(td, x0, z1)[1], pg6_(td, x1, z0)[0], pg6_(td, x1, z0)[1]]

# books with round tops : eight books 3.5 cm thick (0.99 pt) and 22 cm tall, each top a half circle,
# on a shelf, side by side touching, 0.11 and 0.34 pt apart (under doubles_pt) and 0.85 pt apart, some leaning. Where
# two books' sides lie under doubles_pt apart they print as one line and each book's top springs from it: every book
# stays a closed outline, its crown drawn whole from 30 to 150 degrees (nearer the springing two tops meet in one
# stroke), no line end left open, no notch and no join turning onto a line
def h6_books():
    def book(x0, lean, tb=0.035, h=0.22, n=16):
        r = tb / 2
        ring = [(0.0, 0.0), (tb, 0.0), (tb, h - r)] + [(r + r * math.cos(math.pi * i / n), h - r + r * math.sin(math.pi * i / n))
                                                      for i in range(1, n)] + [(0.0, h - r)]
        c, s = math.cos(math.radians(-lean)), math.sin(math.radians(-lean))
        return [(x0 + x * c - z * s, x * s + z * c) for x, z in ring]
    leans = [0.0, 0.0, 2.0, 0.0, 3.0, 0.0, 1.0, 0.0]
    xs = [0.1]
    for g in (0.0, 0.004, 0.012, 0.03, 0.0, 0.012, 0.004):
        xs.append(xs[-1] + 0.035 + g)
    parts = [dict(layer='hl::bk::b book', group='b', solid=True, tris=sy_.prism(book(x, l), 0, 0.15)) for x, l in zip(xs, leans)]
    parts.append(dict(layer='hl::bk::b shelf', group='b', solid=True, tris=sy_.box(0.0, 0.0, -0.02, 0.6, 0.3, 0.0)))
    _, svg, td = hl_synth_('books-round', parts, dict(direction=(0, 1, 0), target=(0.3, 0, 0.11)),
                           [dict(id='b', layers=['hl::bk::*'], layer='CUT')], scale=100, frame=(260, 120))
    box = box6_(td, xs[0] - 0.01, 0.005, xs[-1] + 0.05, 0.235)
    tops = []
    for x0, l in zip(xs, leans):
        c, s = math.cos(math.radians(-l)), math.sin(math.radians(-l))
        arc = [(0.0175 + 0.0175 * math.cos(math.radians(a)), 0.2025 + 0.0175 * math.sin(math.radians(a))) for a in range(30, 151, 6)]
        tops.append([pg6_(td, x0 + x * c - z * s, x * s + z * c) for x, z in arc])
    return hl_.check_notes(svg, [dict(kind='ends', box=box), dict(kind='notches', box=box), dict(kind='kinks', box=box)]
                           + [dict(kind='gap', path=t, tol_pt=0.15, max_pt=0.2) for t in tops])
r6_ = h6_books()
ok(all(r[1] for r in r6_), 'hidden-lines: books with round tops stay closed outlines, side by side under doubles_pt: '
   + '; '.join(r[3] for r in r6_[:3]) + '; longest gap in a crown ' + str(max(r[2] for r in r6_[3:])))

# the arch's springing : an arch 2 m wide drawn twice as curves, a heavier one (CUT's group, on
# BEYOND) left out for 5 cm (1.4 pt) where its left side meets its round head, and a lighter one (DETAIL) 0.05 pt
# outside it, whole. The lighter gives way only where the heavier is drawn beside it, so across the gap it is drawn
def h6_springing():
    def arch(off, gap=None):
        r = 1.0 + off
        pts = [(-off, 0.0), (-off, 2.0)] + [(1 - r * math.cos(math.pi * i / 64), 2 + r * math.sin(math.pi * i / 64))
                                            for i in range(1, 64)] + [(2 + off, 2.0), (2 + off, 0.0)]
        if gap is None:
            return [pts]
        return [pts[:1] + [(-off, gap[0])], [(-off, gap[1])] + pts[1:]]
    o = 0.05 * pt6_
    parts = [dict(layer='hl::sp::a', group='a', curve=[xz6_(x, z) for x, z in c]) for c in arch(0.0, (1.96, 2.01))]
    parts += [dict(layer='hl::sp::b', group='b', curve=[xz6_(x, z) for x, z in c]) for c in arch(o)] + [back6_('sp')]
    _, svg, td = hl_synth_('springing', parts, dict(direction=(0, 1, 0), target=(1, 0, 1.5)), ab6_('sp'), scale=100, frame=(200, 140))
    path = [pg6_(td, -o, z) for z in (1.9, 1.95, 2.0)] + [pg6_(td, 1 - (1 + o) * math.cos(a), 2 + (1 + o) * math.sin(a)) for a in (0.05, 0.1)]
    return hl_.check_notes(svg, [dict(kind='gap', path=path, tol_pt=0.1, max_pt=0.2), dict(kind='ends', box=box6_(td, -0.2, 1.8, 0.2, 2.2))])
r6_ = h6_springing()
ok(all(r[1] for r in r6_), 'hidden-lines: a lighter line is drawn across a break in the heavier line it gives way to: '
   + '; '.join(r[3] for r in r6_))

# fins : six wedge fins 1 m long and 4 cm thick, their top faces sloping 1 in 3, deep at one end and
# shallow at the other, on a post with a rod standing in front, all one weight, seen along the fins' slope from just
# under it, so a fin's two top lines close in from 0.51 pt apart to 0.02. The thin top faces keep a top line along
# each fin, the rod's long edges crossing them do not take it, and no line end is left open
def h6_fins():
    def hexa(c):
        q = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return [tr for a, b, c_, d in q for tr in sy_.quad(c[a], c[b], c[c_], c[d])]
    fins = []
    for i in range(6):
        z0 = 0.25 * i
        bot = [(0.0, 0.0, z0), (1.0, 0.0, z0), (1.0, 0.02, z0 + 0.02 / 3), (0.0, 0.56, z0 + 0.56 / 3)]
        fins += hexa(bot + [(x, y, z + 0.04) for x, y, z in bot])
    parts = [dict(layer='hl::fn::b fins', group='b', solid=True, tris=fins),
             dict(layer='hl::fn::b post', group='b', solid=True, tris=sy_.box(-0.05, -0.02, -0.1, 0.0, 0.6, 1.5)),
             dict(layer='hl::fn::b rod', group='b', solid=True, tris=sy_.box(0.49, -0.12, -0.1, 0.51, -0.1, 1.5))]
    g = [dict(id='b', layers=['hl::fn::*'], layer='CONTEXT', weights={c: 'fine' for c in ('profiles', 'bases', 'overlaps', 'steps', 'seams', 'creases')})]
    _, svg, td = hl_synth_('fins', parts, dict(direction=(0.15, 1.0, 0.30), target=(0.5, 0.15, 0.7)), g, scale=100, frame=(160, 160))
    return hl_.check_notes(svg, [dict(kind='line', path=[pg6_(td, x0, 0.25 * i + 0.04), pg6_(td, x1, 0.25 * i + 0.04)], tol_pt=0.5, cover=0.9)
                                 for i in range(6) for x0, x1 in ((0.05, 0.42), (0.58, 0.95))] + [dict(kind='ends', box=[0, 0, 160, 160])])
r6_ = h6_fins()
ok(all(r[1] for r in r6_), 'hidden-lines: wedge fins keep a top line where their top faces are thin, a long line crossing '
   f'them: {min(r[2] for r in r6_[:-1])} covered at least; {r6_[-1][3]}')

# lines in short pieces beside a heavier one (he kettle): a heavier line along z = 0 from x 0 to 1 m;
# a lighter one 0.34 pt above it from x 0.3 to 1.2 m in 0.04 pt pieces, then up 0.3 m; a small box 0.2 m wide sitting
# 0.34 pt above the heavier line; and a lighter line beside it from x 0.70 to 0.99 m that turns up there. The lighter
# lines give way beside the heavier and nowhere else, each is joined onto it or stays, and no outline is left open
def h6_pieces():
    parts = [dict(layer='hl::kt::a', group='a', curve=[xz6_(0, 0), xz6_(1, 0)]),
             dict(layer='hl::kt::b1', group='b', curve=[xz6_(x, 0.34 * pt6_) for x in np.arange(0.3, 1.2, 0.04 * pt6_)]
                  + [xz6_(1.2, 0.34 * pt6_), xz6_(1.2, 0.3)]),
             dict(layer='hl::kt::b2', group='b', curve=[xz6_(0.4, 0.34 * pt6_), xz6_(0.6, 0.34 * pt6_), xz6_(0.6, 0.04), xz6_(0.4, 0.04),
                                                         xz6_(0.4, 0.34 * pt6_)]),
             dict(layer='hl::kt::b3', group='b', curve=[xz6_(0.70, 0.3 * pt6_), xz6_(0.99, 0.3 * pt6_), xz6_(0.99, 0.2)]), back6_('kt')]
    _, svg, td = hl_synth_('pieces', parts, dict(direction=(0, 1, 0), target=(0.6, 0, 0.1)), ab6_('kt'), scale=100, frame=(200, 120))
    return hl_.check_notes(svg, [dict(kind='ends', box=box6_(td, 0.35, -0.01, 1.15, 0.05)),
                                 dict(kind='line', path=[pg6_(td, 1.06, 0.34 * pt6_), pg6_(td, 1.19, 0.34 * pt6_)], tol_pt=0.1, cover=0.95),
                                 dict(kind='line', path=[pg6_(td, 1.2, 0.02), pg6_(td, 1.2, 0.29)], tol_pt=0.1, cover=0.95),
                                 dict(kind='line', path=[pg6_(td, 0.4, 0.035), pg6_(td, 0.4, 0.02)], tol_pt=0.1, cover=0.95),
                                 dict(kind='line', path=[pg6_(td, 0.99, 0.19), pg6_(td, 0.99, 0.02)], tol_pt=0.1, cover=0.95)])
r6_ = h6_pieces()
ok(all(r[1] for r in r6_), 'hidden-lines: lighter lines in short pieces beside a heavier one stay joined, each outline '
   'closed: ' + '; '.join(r[3] for r in r6_))

# a pipe frame's corner : a heavier quarter circle of radius 0.57 pt turning down into a vertical, and
# a lighter line, the head's top in 0.04 pt pieces, level to the corner where it turns down round the same centre 0.1 pt
# outside the heavier, with a line coming down onto the head 0.7 pt short of the corner. The lighter gives way along
# the arc, its head stays whole to the corner and the line coming down still meets it. It passed before regression
# too and is kept as a guard
def h6_pipe():
    rh, rl = 0.02, 0.02 + 0.1 * pt6_
    q = lambda r, i: xz6_(-r * math.sin(math.pi / 2 * i / 16), r * math.cos(math.pi / 2 * i / 16))
    parts = [dict(layer='hl::pc::a', group='a', curve=[q(rh, i) for i in range(17)] + [xz6_(-rh, -0.3)]),
             dict(layer='hl::pc::b', group='b', curve=[xz6_(x, rl) for x in np.arange(-0.3, 0.0, 0.04 * pt6_)] + [q(rl, i) for i in range(17)]
                  + [xz6_(-rl, -0.3)]),
             dict(layer='hl::pc::b rail', group='b', curve=[xz6_(-0.024, rl + 0.3), xz6_(-0.024, rl)]), back6_('pc')]
    _, svg, td = hl_synth_('pipe-corner', parts, dict(direction=(0, 1, 0), target=(-0.1, 0, -0.1)), ab6_('pc'), scale=100, frame=(200, 120))
    return hl_.check_notes(svg, [dict(kind='line', path=[pg6_(td, -0.29, rl), pg6_(td, -0.005, rl)], tol_pt=0.08, cover=0.95),
                                 dict(kind='gap', path=[pg6_(td, -0.06, rl), pg6_(td, -0.002, rl)], tol_pt=0.08, max_pt=0.15),
                                 dict(kind='ends', box=box6_(td, -0.05, -0.05, 0.01, 0.04))])
r6_ = h6_pipe()
ok(all(r[1] for r in r6_), 'hidden-lines: a frame\'s head stays whole to its corner beside a heavier arc: ' + '; '.join(r[3] for r in r6_))

# a fan of tile lines into an edge (he model's 6): a heavier edge along z = 0 and eleven lighter
# lines meeting it at 1 to 5 degrees, each starting 1.2 pt above it, every other one ending 0.15 pt short of it. One
# meeting it runs on along its own path into it; one ending short, with nothing in the model between, is drawn whole,
# its end left 0.15 pt short as the model has it: running it on would draw what the model does not have (the review
# on regression), and cutting it back clear would take out up to 28 pt of it (his choice of B at regression), so lint
# counts its end beside the edge, not a near miss. No join turns onto the edge, no notch, no other end is left open
def h6_fan():
    fan, x = [], 0.2
    for n, deg in enumerate((1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 2, 4)):
        t = math.tan(math.radians(deg))
        span = 1.2 * pt6_ / t
        x += span + 0.05
        fan.append((x, t, 0.15 * pt6_ if n % 2 else 0.0, span))
    parts = [dict(layer='hl::fa::a', group='a', curve=[xz6_(0, 0), xz6_(x + 0.3, 0)])]
    parts += [dict(layer=f'hl::fa::b{n}', group='b', curve=[xz6_(xm - sp, sp * t + s), xz6_(xm - s / t, s)]) for n, (xm, t, s, sp) in enumerate(fan)]
    _, svg, td = hl_synth_('fan', parts + [back6_('fa')], dict(direction=(0, 1, 0), target=(x / 2, 0, 0.0)), ab6_('fa'), scale=100, frame=(360, 60))
    z_in = ((0.3 - 0.15) / 2 + 0.02) * pt6_            # a hair outside where the stroke goes inside the edge's

    def on_line(xm, t, s, sp, z):                      # the point of a fan line at height z, from its two ends
        x0, z0, x1, z1 = xm - sp, sp * t + s, xm - s / t, s
        u = (z0 - z) / (z0 - z1)
        return pg6_(td, x0 + (x1 - x0) * u, z)
    lines = [dict(kind='line', path=[on_line(xm, t, s, sp, 0.97 * sp * t + s), on_line(xm, t, s, sp, s * 1.05 if s else z_in)],
                  tol_pt=0.06, cover=0.97) for xm, t, s, sp in fan]
    nm_ = [x_ for x_ in lint.check(lint.read_svg(svg), load(svg)) if x_[1] == 'near-miss']
    lines.append(dict(kind='look', why=f'{len(nm_)} near misses'))
    return hl_.check_notes(svg, [dict(kind='kinks', box=[0, 0, 360, 60]), dict(kind='notches', box=[0, 0, 360, 60]),
                                 dict(kind='ends', n=sum(1 for f_ in fan if f_[2]), box=[pg6_(td, 0.3, 0)[0], pg6_(td, 0, 0.25 * pt6_)[1], pg6_(td, x, 0)[0], pg6_(td, 0, -0.25 * pt6_)[1]])] + lines)
r6_ = h6_fan()
ok(all(r[1] for r in r6_[:-1]) and r6_[-1][0]['why'] == '0 near misses', 'hidden-lines: tile lines converging into an edge at 1 to 5 '
   'degrees run on along their own paths into it, or stay whole to their own ends short of it: ' + '; '.join(r[3] for r in r6_[:3])
   + '; drawn ' + ', '.join(f'{r[2]:g}' for r in r6_[3:-1]) + '; ' + r6_[-1][0]['why'])

# two edges converging at 1, 3 and 5 degrees, the lesser ending 0.2 pt short : a box's top edge and a
# plate behind whose top edge closes in on it. The plate's edge is drawn along its own path to where it is clear of
# the box's edge, the model having nothing between , with no join turning onto it, no
# notch and no near miss
def h6_converge():
    out = {}
    for deg in (1, 3, 5):
        rise, s = 1.5 * math.tan(math.radians(deg)), 0.2 * pt6_
        parts = [dict(layer='hl::cv::b box', group='b', solid=True, tris=sy_.box(0, 0, 0, 2, 0.5, 1)),
                 dict(layer='hl::cv::b plate', group='b', solid=True, tris=sy_.prism([(0.2, 0.3), (1.7, 0.3), (1.7, 1 + s), (0.2, 1 + s + rise)], 2, 2.2))]
        _, svg, td = hl_synth_(f'converge6-{deg}', parts, dict(direction=(0, 1, 0), target=(1, 0, 1)),
                               [dict(id='b', layers=['hl::cv::*'], layer='CUT')], scale=100, frame=(200, 120))
        x_cl = 1.7 - (0.65 * pt6_ - s) * 1.5 / rise     # the plate's edge 0.65 pt off the box's there
        out[deg] = [r[3] for r in hl_.check_notes(svg, [
            dict(kind='line', path=[pg6_(td, 0.25, 1 + s + rise * (1.45 / 1.5)), pg6_(td, x_cl, 1 + s + rise * (1.7 - x_cl) / 1.5)], tol_pt=0.06, cover=0.97),
            dict(kind='kinks', box=[0, 0, 200, 120]), dict(kind='notches', box=[0, 0, 200, 120])]) if not r[1]]
        out[deg] += [x_[2] for x_ in lint.check(lint.read_svg(svg), load(svg)) if x_[1] == 'near-miss']
    return out
r6_ = h6_converge()
ok(not any(r6_.values()), f'hidden-lines: an edge converging on another at 1 to 5 degrees and ending short is drawn along '
   f'its own path to where it is clear of it, with no kink, notch or near miss: failing {r6_}')

# an edge converging on a heavier one slowly then faster (the model's fin, note 1 of regression): it meets the heavier
# line at x 0.05 m and rises from it at 2 degrees to x 0.45, then at 0.5 degrees to 0.69, 0.46 pt off it there, then at
# 2 degrees again to 1 pt off it at x 1.24, past doubles_pt, where it ends. It converges, so it runs on along its own
# path into the heavier line: drawn from where it is 0.07 pt off to its far end
def h6_slow():
    t2, t05 = math.tan(math.radians(2)), math.tan(math.radians(0.5))
    zb = lambda x: (x - 0.05) * t2 if x <= 0.45 else 0.4 * t2 + (x - 0.45) * t05 if x <= 0.69 else 0.4 * t2 + 0.24 * t05 + (x - 0.69) * t2
    parts = [dict(layer='hl::sl::a', group='a', curve=[xz6_(0, 0), xz6_(1.3, 0)]),
             dict(layer='hl::sl::b', group='b', curve=[xz6_(x, zb(x)) for x in (0.05, 0.45, 0.69, 1.24)]), back6_('sl')]
    _, svg, td = hl_synth_('slow6', parts, dict(direction=(0, 1, 0), target=(0.65, 0, 0)), ab6_('sl'), scale=100, frame=(60, 30))
    return hl_.check_notes(svg, [dict(kind='line', path=[pg6_(td, x, zb(x)) for x in (0.12, 0.3, 0.45, 0.6, 0.68, 0.9, 1.2)],
                                      tol_pt=0.04, cover=0.95, layers=['DETAIL'])])


# a line lying about the tolerance behind a surface (flicker), at 1:200, where the synthetic export's bias leaves 0.12 pt
# along the view, as Rhino's exports do: a slab faces the camera and a curve runs behind its face at 0.06 to 0.18 pt,
# waving every 0.4 m (5.7 pt), and another at 0.25 to 0.35 pt. Hidden past 2 MESH_PT and seen under 4 MESH_PT where
# the samples either side are seen, the first is drawn whole, not as dashes; the second is hidden
def h6_flicker():
    pt_ = 2 * pt6_

    def wave(lo, hi, z):
        return [(0.2 + i * 0.02, (lo + (hi - lo) * (0.5 - 0.5 * math.cos(2 * math.pi * i * 0.02 / 0.4))) * pt_, z) for i in range(81)]
    parts = [dict(layer='hl::fl::a slab', group='a', solid=True, tris=sy_.box(0, 0, 0, 2, 0.4, 1)),
             dict(layer='hl::fl::b near', group='b', curve=wave(0.06, 0.18, 0.4)),
             dict(layer='hl::fl::b far', group='b', curve=wave(0.25, 0.35, 0.7))]
    _, svg, td = hl_synth_('flicker6', parts, dict(direction=(0, 1, 0), target=(1, 0, 0.5)), ab6_('fl'), scale=200, frame=(60, 30))
    return hl_.check_notes(svg, [dict(kind='line', path=[pg6_(td, 0.22, 0.4), pg6_(td, 1.78, 0.4)], tol_pt=0.1, cover=0.97, layers=['DETAIL']),
                                 dict(kind='clear', box=box6_(td, 0.22, 0.67, 1.78, 0.73), layers=['DETAIL'], max_pt=0.1)])
r6_ = h6_slow()
ok(all(x[1] for x in r6_), f'hidden-lines: an edge converging on a heavier one at 0.5 degrees, then 2, runs on along its '
   f'own path into it: {[x[3] for x in r6_]}')
r6_ = h6_flicker()
ok(all(x[1] for x in r6_), f'hidden-lines: a line waving about the tolerance behind a surface is drawn whole, one past '
   f'twice it hidden: {[x[3] for x in r6_]}')

# a room between two walls of loose skins, closed floor and roof slabs. With each wall's two skins facing one way (the
# HL session's demo house: the left wall's -x, the right's +x), each inner skin faces into its wall, toward its pair
# 0.2 m off, and is turned; with both skins of each wall facing into it, all four are. Either way the turned skins
# are reported, each naming its pair by its whole id, and the room is a hole: its witness line drawn, its inner
# outline cut, the floor slab cut
def h6_skins(mode):
    def skin(x, sgn):
        q = sy_.quad((x, -1, 0), (x, 1, 0), (x, 1, 3), (x, -1, 3))       # faces +x
        return q if sgn > 0 else [tuple(reversed(t)) for t in q]
    faces = ((0.0, -1), (0.2, -1), (4.0, 1), (4.2, 1)) if mode == 'same' else ((0.0, 1), (0.2, -1), (4.0, 1), (4.2, -1))
    parts = [dict(layer=f'hl::sk::a wall {n}', group='a', tris=skin(x, s)) for n, (x, s) in enumerate(faces)]
    parts += [dict(layer='hl::sk::a floor', group='a', solid=True, tris=sy_.box(0, -1, -0.3, 4.2, 1, 0)),
              dict(layer='hl::sk::a roof', group='a', solid=True, tris=sy_.box(0, -1, 3, 4.2, 1, 3.3)),
              dict(layer='hl::sk::b witness', group='b', curve=[(1.5, 0.5, 1.5), (2.7, 0.5, 1.5)])]
    rep, svg, td = hl_synth_(f'skins6-{mode}', parts, dict(direction=(0, 1, 0), target=(2.1, 0, 1.5)),
                             [dict(id='a', layers=['hl::sk::a*'], layer='CUT', body='house'),
                              dict(id='b', layers=['hl::sk::b*'], layer='DETAIL')],
                             clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(200, 150))
    res = hl_.check_notes(svg, [dict(kind='line', path=[pg6_(td, 1.6, 1.5), pg6_(td, 2.6, 1.5)], tol_pt=0.1, cover=0.9, layers=['DETAIL']),
                                dict(kind='drawn', box=box6_(td, 0.17, 0.2, 0.23, 2.8), layers=['CUT'], min_pt=60),
                                dict(kind='drawn', box=box6_(td, 3.97, 0.2, 4.03, 2.8), layers=['CUT'], min_pt=60),
                                dict(kind='regions', box=box6_(td, 1.0, -0.25, 3.0, -0.05), n=1)])
    obs_ = json.loads((td / 'scene.json').read_text())['objects']
    tu_ = [i_ for i_ in rep['issues'] if hl_.fault_kind(i_['issue']) == 'turned']
    turned = sorted(obs_[i_['object']]['layer'] for i_ in tu_)
    # each names the skin it pairs with by its whole id, so HL's row selects both
    named = all(any(f"{ob['ids'][0]} beside" in i_['issue'] for ob in obs_ if ob['i'] != i_['object']) for i_ in tu_)
    return res, turned, named


# a recess 0.6 m deep in a wall 1 m thick (the review, ): a blind recess follows the depth rule, so its rim,
# past gap_m (0.5 m), is an overlap; with no back face the same pocket goes through the wall and its rim takes the
# wall's outline weight. The rim's left side is checked at each weight
def h6_recess():
    out = {}
    for blind in (True, False):
        t = sy_.wall_with_opening(-2, 2, 0, 1.0, -1.5, 1.5, -0.6, 0.6, -0.5, 0.5)
        if blind:
            t += sy_.quad((-0.6, 0.6, -0.5), (0.6, 0.6, -0.5), (0.6, 0.6, 0.5), (-0.6, 0.6, 0.5))
        rep, svg, td = hl_synth_(f'recess6-{int(blind)}', [dict(layer='hl::rc::a wall', group='a', tris=t)],
                                 dict(direction=(0, 1, 0), target=(0, 0, 0)),
                                 [dict(id='a', layers=['hl::rc::a*'], layer='BEYOND')], scale=100, frame=(200, 120))
        ws = sorted({round(p.width, 3) for p in lint.read_svg(str(svg))['paths'] if p.stroke not in (None, 'none')})
        out[blind] = (ws, hl_.check_notes(svg, [dict(kind='line', path=[pg6_(td, -0.6, -0.4), pg6_(td, -0.6, 0.4)], tol_pt=0.05, cover=0.95)]), rep['openings'])
    return out


# one triangle seen edge-on, the only thing in the scene: drawn as its edge, no error
def h6_edge_on():
    rep, svg, td = hl_synth_('edgeon6', [dict(layer='hl::eo::a', group='a', tris=[[(-1, 0, -1), (1, 0, -1), (0, 0, 1)]])],
                             dict(direction=(0, 0, -1), up=(0, 1, 0), target=(0, 0, 0)),
                             [dict(id='a', layers=['hl::eo::a*'], layer='BEYOND')], scale=100, frame=(120, 80))
    return hl_.check_notes(svg, [dict(kind='drawn', box=[0, 0, 120, 80], min_pt=10)])


# a request missing its frame, a scale that is no number, and meshes.bin shorter than scene.json says: a sentence
# saying so, not a traceback
def h6_bad_input():
    out = []
    for what in ('frame', 'scale', 'bin'):
        td = Path(tempfile.mkdtemp(prefix='hl-')) / f'bad6-{what}'
        sy_.write(td, [dict(layer='hl::bd::a', group='a', tris=sy_.quad((-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)))],
                  dict(direction=(0, 1, 0), target=(0, 0, 0)), [dict(id='a', layers=['hl::bd::a*'], layer='BEYOND')])
        rq = json.loads((td / 'request.json').read_text())
        if what == 'frame':
            rq.pop('frame')
        elif what == 'scale':
            rq['scale'] = 'wrong'
        else:
            (td / 'meshes.bin').write_bytes((td / 'meshes.bin').read_bytes()[:20])
        (td / 'request.json').write_text(json.dumps(rq))
        try:
            hl_.build(td / 'request.json')
            out.append((what, 'drew'))
        except SystemExit as x:
            out.append((what, str(x)))
        except Exception as x:
            out.append((what, f'{type(x).__name__}: {x}'))
    return out


# two chords of concentric arcs 0.61 pt apart, past doubles_pt, at four phases of the noding grid: noded they read
# 0.56 pt apart in places, but their gap is measured on the lines as given, so both stay whole at every phase
def h6_chords():
    r1 = 1 + 0.61 * pt6_
    out = []
    for ph in (0.0, 0.0125, 0.025, 0.0375):
        paths = [[(r * math.cos(t), 0, r * math.sin(t)) for t in (math.pi / 2, 33 * math.pi / 64)] for r in (1, r1)]
        parts = [dict(layer=f'hl::ch::a{n}', group='a', curve=p) for n, p in enumerate(paths)] + \
            [dict(layer='hl::ch::a back', group='a', solid=True, tris=sy_.box(-10, 5, -10, 14, 5.1, 10))]
        _, svg, td = hl_synth_(f'chords6-{ph}', parts, dict(direction=(0, 1, 0), target=(ph * pt6_, 0, ph * pt6_)),
                               [dict(id='a', layers=['hl::ch::a*'], layer='DETAIL')], scale=100, frame=(200, 120))
        out += hl_.check_notes(svg, [dict(kind='gap', path=[pg6_(td, x, z) for x, _, z in p], tol_pt=0.05, max_pt=0.3) for p in paths])
    return out


# a box whose ring is narrower than its clipped mesh (half as wide): the cut follows the mesh, its base drawn whole,
# and the disagreement is reported as the model's
def h6_ring():
    td = Path(tempfile.mkdtemp(prefix='hl-')) / 'ring6'
    sy_.write(td, [dict(layer='hl::rg::a box', group='a', solid=True, tris=sy_.box(-1, -1, -1, 1, 1, 1))],
              dict(direction=(0, 1, 0), target=(0, 0, 0)), [dict(id='a', layers=['hl::rg::a*'], layer='CUT')],
              clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(120, 100))
    sc = json.loads((td / 'scene.json').read_text())
    for r in sc['rings']:
        r['pts'] = [[p[0] * 0.5, p[1], p[2]] for p in r['pts']]
    (td / 'scene.json').write_text(json.dumps(sc))
    d_, rep = hl_.build(td / 'request.json')
    rq = json.loads((td / 'request.json').read_text())
    d_.to_svg(td / 'out.svg', canvas=(rq['frame']['w_pt'], rq['frame']['h_pt']), origin=(0.0, rq['frame']['h_pt']))
    res = hl_.check_notes(td / 'out.svg', [dict(kind='line', path=[pg6_(td, -0.95, -1), pg6_(td, 0.95, -1)], tol_pt=0.1, cover=0.97, min_w=0.79)])
    return res, [i['issue'][:60] for i in rep['issues'] if hl_.fault_kind(i['issue']) == 'ring-mismatch']


# a slab whose right side meets the plane at 15 degrees, its ring's right edge moved in 0.02 m (0.57 pt). A mesh lies
# off its surface by up to its tolerance, carried along the plane at that angle to 0.19 pt; four tolerances so carried,
# 0.77 pt, explain the gap, so the cut keeps to the ring and nothing is reported (the model's base profile, where the mesh
# ran 0.48 pt off the ring at a glancing side). Moved in 0.08 m (2.3 pt), the cut follows the mesh and it is reported
def h6_glance():
    th_ = math.radians(15)
    c_, s_ = math.cos(th_), math.sin(th_)
    P_ = [(-2.0, -0.2), (1.0 - 0.2 * c_ / s_, -0.2), (1.0 + 0.2 * c_ / s_, 0.2), (-2.0, 0.2)]   # its right side through (1, 0)

    def zprism(P, z0, z1):
        t = []
        for i in range(1, len(P) - 1):
            t += [((P[0][0], P[0][1], z0), (P[i + 1][0], P[i + 1][1], z0), (P[i][0], P[i][1], z0)),
                  ((P[0][0], P[0][1], z1), (P[i][0], P[i][1], z1), (P[i + 1][0], P[i + 1][1], z1))]
        for a, b in zip(P, P[1:] + P[:1]):
            t += sy_.quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1))
        return t
    out = {}
    for g_ in (0.02, 0.08):
        td = Path(tempfile.mkdtemp(prefix='hl-')) / f'glance6-{g_}'
        sy_.write(td, [dict(layer='hl::gl::a slab', group='a', solid=True, tris=zprism(P_, 0.0, 1.0))],
                  dict(direction=(0, 1, 0), target=(0, 0, 0.5)), [dict(id='a', layers=['hl::gl::a*'], layer='CUT')],
                  clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(160, 80))
        sc = json.loads((td / 'scene.json').read_text())
        x_r = max(q[0] for r in sc['rings'] for q in r['pts'])
        for r in sc['rings']:
            r['pts'] = [[q[0] - g_ if abs(q[0] - x_r) < 1e-9 else q[0], q[1], q[2]] for q in r['pts']]
        (td / 'scene.json').write_text(json.dumps(sc))
        d_, rep = hl_.build(td / 'request.json')
        rq = json.loads((td / 'request.json').read_text())
        d_.to_svg(td / 'out.svg', canvas=(rq['frame']['w_pt'], rq['frame']['h_pt']), origin=(0.0, rq['frame']['h_pt']))
        x_ = 1.0 - g_ if g_ < 0.05 else 1.0
        res = hl_.check_notes(td / 'out.svg', [dict(kind='line', path=[pg6_(td, x_, 0.05), pg6_(td, x_, 0.95)], tol_pt=0.1, cover=0.95, min_w=0.79)])
        out[g_] = (res[0][1], res[0][3], [i['issue'][:40] for i in rep['issues'] if hl_.fault_kind(i['issue']) == 'ring-mismatch'])
    return out


for mode_, want_ in (('same', ['hl::sk::a wall 1', 'hl::sk::a wall 2']), ('in', [f'hl::sk::a wall {n}' for n in range(4)])):
    r6_, tu6_, nm6_ = h6_skins(mode_)
    ok(all(x[1] for x in r6_) and tu6_ == want_ and nm6_, f'hidden-lines: a room between walls of loose skins ({mode_}) is a '
       f'hole, its outline cut and the slab cut, the turned skins reported naming their pairs whole: {[x[3] for x in r6_]}; '
       f'turned {tu6_}, named {nm6_}')
r6_ = h6_recess()
ok(r6_[True][1][0][1] and r6_[True][2]['rims'] == 0 and r6_[False][1][0][1] and r6_[False][2]['rims'] == 4,
   f'hidden-lines: a recess 0.6 m deep keeps its rim an overlap, the same pocket through the wall takes the outline: '
   f'{r6_[True][1][0][3]}, {r6_[False][1][0][3]}')
try:
    r6_ = [x[3] for x in h6_edge_on() if not x[1]]
except Exception as x_:
    r6_ = [f'{type(x_).__name__}: {x_}']
ok(not r6_, f'hidden-lines: one triangle seen edge-on draws its edge: {r6_}')
r6_ = h6_bad_input()
ok(all(m_.startswith('hidden-lines:') for _, m_ in r6_), f'hidden-lines: a request with no frame or a bad scale, and a short '
   f'meshes.bin, are refused in a sentence: {r6_}')
r6_ = h6_chords()
ok(all(x[1] for x in r6_), f'hidden-lines: chords 0.61 pt apart both stay at four phases of the grid: {[x[3] for x in r6_]}')
r6_ = h6_glance()
ok(r6_[0.02][0] and not r6_[0.02][2] and r6_[0.08][0] and r6_[0.08][2], f'hidden-lines: a ring 0.57 pt off its mesh at a '
   f'side meeting the plane at 15 degrees stands, unreported; 2.3 pt off, the cut follows the mesh and it is reported: {r6_}')
r6_, i6_ = h6_ring()
ok(all(x[1] for x in r6_) and i6_, f'hidden-lines: a ring narrower than its clipped mesh is reported and the cut follows the '
   f'mesh: {[x[3] for x in r6_]}; {i6_}')

# ---- regression : nothing drawn that the model does not have, every drawn point on
# one of the export's lines; a dropped line's reason named; the doubles simplified (A) and kept (B, the default). pt7_ is a
# point on paper at 1:100 in metres
pt7_ = 25.4 / 72 / 1000 * 100
xz7_ = lambda x, z: (float(x), 0.0, float(z))
pg7_ = lambda td, x, z: list(sy_.page(td, (x, 0.0, z)))
cl7_ = ('profiles', 'bases', 'overlaps', 'steps', 'seams', 'creases', 'lines')
ab7_ = lambda tag: [dict(id='a', layers=[f'hl::{tag}::a*'], layer='CUT', weights={c: 'light' for c in cl7_}),
                    dict(id='b', layers=[f'hl::{tag}::b*'], layer='DETAIL', weights={c: 'fine' for c in cl7_})]
back7_ = lambda tag: dict(layer=f'hl::{tag}::a back', group='a', solid=True, tris=sy_.box(-10, 5, -10, 14, 5.1, 10))
rules7_ = dict(A=dict(simplify_doubles=True), B=None)

def h7_lint(svg):
    return [x_[2] for x_ in lint.check(lint.read_svg(svg), load(svg)) if x_[0] == 'error']

# an inset drawer frame : a front 0.4 by 0.15 m (0.15 pt) and a frame (0.1 pt)
# inset 0.24 pt at the sides and 0.42 pt at top and bottom, as the model's dresser has them at 1:100. By default the frame's
# stroke lies inside the front's nowhere, so it stays whole; simplified, the whole loop lies under doubles_pt of the front
# and goes whole, not side by side; neither leaves a line end open or draws off the model
def h7_frame(rule):
    si, tb = 0.24 * pt7_, 0.42 * pt7_
    parts = [dict(layer='hl::fr::a front', group='a', curve=[xz7_(0, 0), xz7_(0.4, 0), xz7_(0.4, 0.15), xz7_(0, 0.15), xz7_(0, 0)]),
             dict(layer='hl::fr::b frame', group='b', curve=[xz7_(si, tb), xz7_(0.4 - si, tb), xz7_(0.4 - si, 0.15 - tb), xz7_(si, 0.15 - tb), xz7_(si, tb)]),
             back7_('fr')]
    rep, svg, td = hl_synth_(f'frame7-{rule}', parts, dict(direction=(0, 1, 0), target=(0.2, 0, 0.075)), ab7_('fr'), scale=100,
                             frame=(60, 40), request=rules7_[rule])
    sides = [((si + 0.01, tb), (0.4 - si - 0.01, tb)), ((0.4 - si, tb + 0.01), (0.4 - si, 0.15 - tb - 0.01)),
             ((0.4 - si - 0.01, 0.15 - tb), (si + 0.01, 0.15 - tb)), ((si, 0.15 - tb - 0.01), (si, tb + 0.01))]
    res = hl_.check_notes(svg, [dict(kind='line', path=[pg7_(td, *a), pg7_(td, *b)], tol_pt=0.05, cover=0.95, layers=['DETAIL']) for a, b in sides]
                          + [dict(kind='ends', box=[0, 0, 60, 40]), dict(kind='kinks', box=[0, 0, 60, 40])])
    return rep, res, h7_lint(svg)
f7_ = {r_: h7_frame(r_) for r_ in 'AB'}
ok(all(x_[1] for x_ in f7_['B'][1]) and not any(x_[1] for x_ in f7_['A'][1][:4]) and all(f7_[r_][1][4][1] and f7_[r_][1][5][1] for r_ in 'AB')
   and all(f7_[r_][0]['model']['off_pt'] == 0 for r_ in 'AB') and not any(f7_[r_][2] for r_ in 'AB'),
   'hidden-lines: an inset drawer frame stays whole by default and goes whole simplified, never in part: '
   + '; '.join(f'{r_}: drawn {[x_[2] for x_ in f7_[r_][1][:4]]}, {f7_[r_][1][4][3]}, off {f7_[r_][0]["model"]["off_pt"]}, lint {f7_[r_][2]}' for r_ in 'AB'))

# a disc's two stacked rims : a rim seen at a slant, an ellipse 0.6 by 0.2 m, and a lighter rim 0.1 pt
# outside it all round. Simplified, the lighter rim lies under doubles_pt all round and goes whole, so one line is
# drawn round the disc; by default its stroke lies outside the heavier one's and both are drawn
def h7_rims(rule):
    ell = lambda dr: [xz7_((0.3 + dr) * math.cos(a), (0.1 + dr) * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 97)]
    parts = [dict(layer='hl::rm::a rim', group='a', curve=ell(0.0)), dict(layer='hl::rm::b rim', group='b', curve=ell(0.1 * pt7_)), back7_('rm')]
    rep, svg, td = hl_synth_(f'rims7-{rule}', parts, dict(direction=(0, 1, 0), target=(0, 0, 0)), ab7_('rm'), scale=100,
                             frame=(80, 40), request=rules7_[rule])
    res = hl_.check_notes(svg, [dict(kind='single', path=[pg7_(td, 0.3 * math.cos(a), 0.1 * math.sin(a)) for a in np.linspace(0.3, 2.8, 12)], tol_pt=0.5),
                                dict(kind='ends', box=[0, 0, 80, 40])])
    return rep, res, h7_lint(svg)
r7_ = {r_: h7_rims(r_) for r_ in 'AB'}
ok(r7_['A'][1][0][1] and not r7_['B'][1][0][1] and all(r7_[r_][1][1][1] and not r7_[r_][2] for r_ in 'AB'),
   'hidden-lines: a disc\'s second rim 0.1 pt outside the first goes whole simplified, one line round it, and stays by '
   'default: ' + '; '.join(f'{r_}: {r7_[r_][1][0][3]}, {r7_[r_][1][1][3]}' for r_ in 'AB'))

# a line beside a heavier one for part of its length: a heavier line from x 0.5 to 1.5 m and a lighter one 0.3 pt above
# it from x 0 to 2 m. Giving way in its middle would leave two ends a hair off the heavier line, to be joined onto it
# or cut back: under every rule the lighter line is drawn whole, and nothing off the model
def h7_part(rule):
    parts = [dict(layer='hl::pt::a', group='a', curve=[xz7_(0.5, 0), xz7_(1.5, 0)]),
             dict(layer='hl::pt::b', group='b', curve=[xz7_(0, 0.3 * pt7_), xz7_(2, 0.3 * pt7_)]), back7_('pt')]
    rep, svg, td = hl_synth_(f'part7-{rule}', parts, dict(direction=(0, 1, 0), target=(1, 0, 0)), ab7_('pt'), scale=100,
                             frame=(80, 20), request=rules7_[rule])
    res = hl_.check_notes(svg, [dict(kind='line', path=[pg7_(td, 0.02, 0.3 * pt7_), pg7_(td, 1.98, 0.3 * pt7_)], tol_pt=0.05, cover=0.98, layers=['DETAIL'])])
    return rep, res, h7_lint(svg)
p7_ = {r_: h7_part(r_) for r_ in 'AB'}
ok(all(p7_[r_][1][0][1] and p7_[r_][0]['model']['off_pt'] == 0 and not p7_[r_][2] for r_ in 'AB'),
   'hidden-lines: a line beside a heavier one for part of its length is drawn whole: '
   + '; '.join(f'{r_}: {p7_[r_][1][0][3]}, off {p7_[r_][0]["model"]["off_pt"]}, lint {p7_[r_][2]}' for r_ in 'AB'))

# converging lines : a heavier line along z = 0 and three lighter ones
# closing on it at 2, 4 and 8 degrees from 1.5 pt above it, one ending on it, one crossing it to 0.3 pt below, one
# ending 0.1 pt short. Each runs along its own path into the heavier line: the first drawn to where it meets it, its
# end on it; no join or kink, no near miss, and nothing off the model
def h7_conv(rule):
    parts = [dict(layer='hl::cg::a', group='a', curve=[xz7_(0, 0), xz7_(3, 0)])]
    ends = []
    for n_, (deg, x1, z1) in enumerate(((2, 0.8, 0.0), (4, 1.7, -0.3 * pt7_), (8, 2.6, 0.1 * pt7_))):
        t_ = math.tan(math.radians(deg))
        x0 = x1 - 1.5 * pt7_ / t_
        parts.append(dict(layer=f'hl::cg::b{n_}', group='b', curve=[xz7_(x0, z1 + (x1 - x0) * t_), xz7_(x1, z1)]))
        ends.append((x0, z1 + (x1 - x0) * t_, x1, z1, t_))
    rep, svg, td = hl_synth_(f'conv7-{rule}', parts + [back7_('cg')], dict(direction=(0, 1, 0), target=(1.5, 0, 0)), ab7_('cg'), scale=100,
                             frame=(160, 30), request=rules7_[rule])
    x0, z0, x1, z1, t_ = ends[0]
    res = hl_.check_notes(svg, [dict(kind='line', path=[pg7_(td, x0 + 0.02, z0 - 0.02 * t_), pg7_(td, x1 - 0.06 * pt7_ / t_, 0.06 * pt7_)], tol_pt=0.05, cover=0.97, layers=['DETAIL']),
                                dict(kind='kinks', box=[0, 0, 160, 30]), dict(kind='notches', box=[0, 0, 160, 30])])
    return rep, res, h7_lint(svg)
c7_ = {r_: h7_conv(r_) for r_ in 'AB'}
ok(all(all(x_[1] for x_ in c7_[r_][1]) and c7_[r_][0]['model']['off_pt'] == 0 and not c7_[r_][2] for r_ in 'AB'),
   'hidden-lines: lines converging on a heavier one run on along their own paths to it, nothing off the model: '
   + '; '.join(f'{r_}: {[x_[3] for x_ in c7_[r_][1]]}, off {c7_[r_][0]["model"]["off_pt"]}, lint {c7_[r_][2]}' for r_ in 'AB'))

# a tile line tangent to a roof's curved outline : an arc of radius 3 m sagging to its lowest point at
# x 0, and a lighter straight line along its tangent there, z = 0, from x -0.6 m (1.7 pt under the arc) to x 0.08 m
# (0.03 pt under it). The lighter line runs on along its own path to where the two meet, the rest given way: nothing is
# joined onto the outline and no end is left a hair off it
def h7_tangent():
    R = 3.0
    parts = [dict(layer='hl::tg::a roof', group='a', curve=[xz7_(R * math.sin(a), R - R * math.cos(a)) for a in np.linspace(-0.3, 0.3, 61)]),
             dict(layer='hl::tg::b tile', group='b', curve=[xz7_(-0.6, 0.0), xz7_(0.08, 0.0)]), back7_('tg')]
    rep, svg, td = hl_synth_('tangent7', parts, dict(direction=(0, 1, 0), target=(0, 0, 0.1)), ab7_('tg'), scale=100, frame=(100, 30))
    res = hl_.check_notes(svg, [dict(kind='line', path=[pg7_(td, -0.55, 0.0), pg7_(td, -0.2, 0.0)], tol_pt=0.05, cover=0.97, layers=['DETAIL']),
                                dict(kind='kinks', box=[0, 0, 100, 30])])
    return rep, res, h7_lint(svg)
t7_ = h7_tangent()
ok(all(x_[1] for x_ in t7_[1]) and not t7_[2] and t7_[0]['model']['off_pt'] == 0,
   f'hidden-lines: a line tangent to a curved outline runs on to where they meet, no end a hair off it: {[x_[3] for x_ in t7_[1]]}, lint {t7_[2]}')

# a tile's line lying on an outline : a box 1 m wide, and a tile group's line along its top edge for its
# middle half, in front of it. The tiles hide nothing and are marks on their host, so the edge is drawn at its own
# weight through the stretch the tile's line lies on, not in the tile's
def h7_tile_on():
    parts = [dict(layer='hl::to::a box', group='a', solid=True, tris=sy_.box(0, 0, 0, 1, 0.5, 0.5)),
             dict(layer='hl::to::t tile', group='t', curve=[(0.25, -0.001, 0.5), (0.75, -0.001, 0.5)])]
    g = [dict(id='a', layers=['hl::to::a*'], layer='CUT'), dict(id='t', layers=['hl::to::t*'], layer='TEXTURE')]
    rep, svg, td = hl_synth_('tile-on7', parts, dict(direction=(0, 1, 0), target=(0.5, 0, 0.25)), g, scale=100, frame=(60, 40),
                             request=dict(visibility='faces'))
    return hl_.check_notes(svg, [dict(kind='line', path=[pg7_(td, 0.02, 0.5), pg7_(td, 0.98, 0.5)], tol_pt=0.05, cover=0.97, layers=['BEYOND', 'OUTLINE']),
                                 dict(kind='clear', box=box6_(td, 0.3, 0.45, 0.7, 0.55), max_pt=0.0, layers=['TEXTURE'])])
to7_ = h7_tile_on()
ok(all(x_[1] for x_ in to7_), f'hidden-lines: an outline keeps its weight where a tile\'s line lies on it: {[x_[3] for x_ in to7_]}')

# a near miss in the model (the model's counter, the mullions of the model's door): a line ending 0.3 pt short of a heavier one
# square to it, nothing in the model running on between them. No link is drawn: the end is cut back clear of the
# heavier line, so lint finds no near miss and nothing is drawn off the model
def h7_short():
    parts = [dict(layer='hl::sh::a', group='a', curve=[xz7_(0, 0), xz7_(1, 0)]),
             dict(layer='hl::sh::b', group='b', curve=[xz7_(0.5, 0.3), xz7_(0.5, 0.3 * pt7_)]), back7_('sh')]
    rep, svg, td = hl_synth_('short7', parts, dict(direction=(0, 1, 0), target=(0.5, 0, 0.1)), ab7_('sh'), scale=100, frame=(60, 30))
    res = hl_.check_notes(svg, [dict(kind='clear', box=box6_(td, 0.49, 0.0, 0.51, 0.6 * pt7_), max_pt=0.0, layers=['DETAIL']),
                                dict(kind='line', path=[pg7_(td, 0.5, 0.29), pg7_(td, 0.5, 0.8 * pt7_)], tol_pt=0.05, cover=0.97, layers=['DETAIL'])])
    fx_ = [f_['kind'] for f_ in rep['fixes']]
    return rep, res, h7_lint(svg), fx_
s7_ = h7_short()
ok(all(x_[1] for x_ in s7_[1]) and not s7_[2] and s7_[0]['model']['off_pt'] == 0 and 'end cut back clear' in s7_[3],
   f'hidden-lines: a line ending 0.3 pt short of another is cut back clear, not joined to it: {[x_[3] for x_ in s7_[1]]}, '
   f'lint {s7_[2]}, fixes {s7_[3]}')

# drawn from the model (the review 2 on the model, the grid's steps): a circle 0.1 m across at 1:100, alone. Decided on
# the 0.05 pt grid and drawn where the model has it, no drawn point lies over 0.01 pt off the circle's own polyline
def h7_round():
    parts = [dict(layer='hl::rd::b', group='b', curve=[xz7_(0.05 * math.cos(a), 0.05 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 49)]),
             back7_('rd')]
    rep, svg, td = hl_synth_('round7', parts, dict(direction=(0, 1, 0), target=(0, 0, 0)), ab7_('rd'), scale=100, frame=(30, 30))
    return rep
rd7_ = h7_round()
ok(rd7_['model']['off_grid_pt'] == 0 and rd7_['model']['off_pt'] == 0,
   f'hidden-lines: a small circle is drawn along its own polyline, not the grid\'s steps: {rd7_["model"]}')

# every dropped line named (the third of regression's tasks): a line passing behind a box, and a lighter line beside
# a heavier one that gives way. The report names the box as what hides the first and the heavier line's object as what
# the second gave way to, and leaves nothing unexplained
def h7_named():
    parts = [dict(layer='hl::nm::a box', group='a', solid=True, tris=sy_.box(0.4, -0.5, -0.2, 0.6, -0.3, 0.2)),
             dict(layer='hl::nm::a line', group='a', solid=True, tris=sy_.box(0, 0.2, -0.01, 1, 0.3, 0.01)),
             dict(layer='hl::nm::b near', group='b', curve=[(0.1, 0.19, 0.01 + 0.1 * pt7_), (0.9, 0.19, 0.01 + 0.1 * pt7_)])]
    rep, svg, td = hl_synth_('named7', parts, dict(direction=(0, 1, 0), target=(0.5, 0, 0)), ab7_('nm'), scale=100, frame=(60, 30),
                             request=dict(visibility='faces'))
    return rep['model']
n7_ = h7_named()
ok(any('hl::nm::a box' in nm_ for nm_ in n7_.get('named', {}).get('behind a face', {})) and n7_['unexplained_pt'] == 0,
   f'hidden-lines: a line behind a box is dropped as behind it, named: {n7_.get("named")}, unexplained {n7_["unexplained_pt"]}')

# a thin closed outline (the adversarial scenes' shells): a rectangle 2 m long and 0.3 pt tall drawn as one curve,
# one weight. Under A its second long side lies under doubles_pt of its first, the line's own earlier part, and gives
# way from corner to corner, the short sides running into the first, so one line is drawn across it
def h7_thin(rule):
    t_ = 0.3 * pt7_
    parts = [dict(layer='hl::th::b', group='b', curve=[xz7_(0, 0), xz7_(2, 0), xz7_(2, t_), xz7_(0, t_), xz7_(0, 0)]), back7_('th')]
    rep, svg, td = hl_synth_(f'thin7-{rule}', parts, dict(direction=(0, 1, 0), target=(1, 0, 0)), ab7_('th'), scale=100, frame=(80, 20),
                             request=rules7_[rule])
    return hl_.check_notes(svg, [dict(kind='single', path=[pg7_(td, 0.2, t_ / 2), pg7_(td, 1.8, t_ / 2)], tol_pt=0.9),
                                 dict(kind='ends', box=[0, 0, 80, 20])]) + [(None, not h7_lint(svg), 0, f'lint {h7_lint(svg)}')]
th7_ = {r_: h7_thin(r_) for r_ in 'AB'}
ok(th7_['A'][0][1] and th7_['A'][2][1] and not th7_['B'][0][1] and th7_['B'][1][1] and th7_['B'][2][1],
   f'hidden-lines: a thin closed outline is one line simplified, its second side giving way corner to corner, and keeps both '
   f'sides closed by default: ' + '; '.join(f'{r_}: {[x_[3] for x_ in th7_[r_]]}' for r_ in 'AB'))

# a curved wall's mesh folds : a cylinder of 12 facets lying across the view,
# its long folds left out of the export as Rhino leaves a smooth surface's out. The mesh's own folds are no edge of the
# model and are not drawn; its rims and its mesh's silhouettes are, one closed outline
def h7_folds():
    td = Path(tempfile.mkdtemp(prefix='hl-')) / 'folds7'
    ring = [(0.3 * math.cos(a), 0.3 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)[:-1]]
    sy_.write(td, [dict(layer='hl::fd::b col', group='b', solid=True, tris=sy_.prism(ring, 0, 1.0)), back7_('fd')],
              dict(direction=(1, 0, 0), target=(0, 0.5, 0)), ab7_('fd'), scale=100, frame=(60, 40), request=dict(visibility='faces'))
    sc = json.loads((td / 'scene.json').read_text())
    level = lambda s_: abs(s_['pts'][-1][1] - s_['pts'][0][1]) < 1e-6 * abs(s_['pts'][-1][0] - s_['pts'][0][0])
    sc['segments'] = [s_ for s_ in sc['segments'] if not (s_['o'] == 0 and s_['sil'] == 'Crease' and level(s_))]
    (td / 'scene.json').write_text(json.dumps(sc))
    d_, rep = hl_.build(td / 'request.json')
    d_.to_svg(td / 'out.svg', canvas=(60, 40), origin=(0.0, 40))
    paths = [q for q in lint.read_svg(td / 'out.svg')['paths'] if q.stroke not in (None, 'none')]
    return hl_.check_notes(td / 'out.svg', [dict(kind='clear', box=[17, 13.5, 43, 26.5], max_pt=0.0, layers=['DETAIL'])]), \
        [q.closed for q in paths]
fd7_ = h7_folds()
ok(fd7_[0][0][1] and fd7_[1] == [True], f'hidden-lines: a smooth cylinder\'s mesh folds are not drawn, its outline is, closed: '
   f'{fd7_[0][0][3]}, paths closed {fd7_[1]}')

# a gap in a line the engine drew as visible that only its own object's mesh hides (f
# regression): a box seen from the front and above, its far top edge as the engine gives it moved 8 mm down the page,
# behind the box's own top face, for its middle fifth (a gap, 5.7 pt) or whole, its other edges the engine's hidden
# ones, for the faces to judge. The gap is drawn from the engine's line; the edge moved whole stays the faces' to judge,
# behind a face, and the mesh's own edge is drawn there
def h7_own(whole):
    td = Path(tempfile.mkdtemp(prefix='hl-')) / 'own7'
    sy_.write(td, [dict(layer='hl::ow::b box', group='b', solid=True, tris=sy_.box(0, 0, 0, 1, 0.5, 0.5)), back7_('ow')],
              dict(direction=(0, 1, -0.4), target=(0.5, 0.25, 0.25)), ab7_('ow'), scale=100, frame=(60, 40), request=dict(visibility='faces'))
    sc = json.loads((td / 'scene.json').read_text())
    top = max((s_ for s_ in sc['segments'] if s_['o'] == 0 and s_['sil'] == 'Crease'), key=lambda s_: min(q[1] for q in s_['pts']))
    a_, b_ = np.array(top['pts'][0]), np.array(top['pts'][-1])
    moved = ((0, 1), (1, 1)) if whole else ((0, 0), (0.4, 0), (0.4, 1), (0.6, 1), (0.6, 0), (1, 0))
    top['pts'] = [list(a_ + (b_ - a_) * t_ - np.array([0.0, 0.008 * m_, 0.0])) for t_, m_ in moved]
    for s_ in sc['segments']:
        if s_['o'] == 0 and s_ is not top:
            s_['vis'] = 'under'
    (td / 'scene.json').write_text(json.dumps(sc))
    d_, rep = hl_.build(td / 'request.json')
    d_.to_svg(td / 'out.svg', canvas=(60, 40), origin=(0.0, 40))
    far = [list(sy_.page(td, (x_, 0.5, 0.5))) for x_ in (0.05, 0.95)]
    return (hl_.check_notes(td / 'out.svg', [dict(kind='line', path=far, tol_pt=0.6, cover=0.95)])[0], rep.get('faces_own'),
            rep['model']['dropped'].get('behind a face', 0))
ow7_ = h7_own(False)
ok(ow7_[0][1] and 4 < (ow7_[1] or 0) < 8 and ow7_[2] < 1, f'hidden-lines: a gap in an edge the engine drew as visible, under its own '
   f'object\'s mesh, is drawn from the engine\'s line: {ow7_[0][3]}, {ow7_[1]} pt taken from the engine, {ow7_[2]} pt behind a face')
ow7_ = h7_own(True)
ok(ow7_[0][1] and not ow7_[1] and 27 < ow7_[2] < 30, f'hidden-lines: an edge the engine drew as visible, under its own object\'s mesh '
   f'whole, stays the faces\' to judge: {ow7_[0][3]}, {ow7_[1]} pt taken from the engine, {ow7_[2]} pt behind a face')

# ---- regression
# a gap in one object's outline (the model's pillows, note 1: two tangent edges 0.19 pt apart at each corner, nothing of the
# export's between): along z = 0, one object's line in two pieces 0.19 pt apart, and past its end, 0.19 pt on, another
# object's line; above it at z = 1 m, one object's line in two pieces 0.3 pt apart. The first gap is under min_len_pt and
# its ends face each other, so it is closed, the one stretch drawn off the model; the gap between two objects is not,
# nor the one of 0.3 pt
def h8_gap():
    g_ = 0.19 * pt7_
    parts = [dict(layer='hl::gp::b one', group='b', curve=[xz7_(0, 0), xz7_(1, 0)]), dict(layer='hl::gp::b one', group='b', curve=[xz7_(1 + g_, 0), xz7_(2, 0)]),
             dict(layer='hl::gp::b two', group='b', curve=[xz7_(2 + g_, 0), xz7_(3, 0)]),
             dict(layer='hl::gp::b three', group='b', curve=[xz7_(0, 1), xz7_(1, 1)]), dict(layer='hl::gp::b three', group='b', curve=[xz7_(1 + 0.3 * pt7_, 1), xz7_(2, 1)]),
             back7_('gp')]
    td = Path(tempfile.mkdtemp(prefix='hl-')) / 'gap8'
    sy_.write(td, parts, dict(direction=(0, 1, 0), target=(1.5, 0, 0.5)), ab7_('gp'), scale=100, frame=(120, 60))
    sc = json.loads((td / 'scene.json').read_text())
    for s_ in sc['segments']:                          # each line's second piece, one object with its first
        s_['o'] = {1: 0, 4: 3}.get(s_['o'], s_['o'])
    (td / 'scene.json').write_text(json.dumps(sc))
    d_, rep = hl_.build(td / 'request.json')
    svg = td / 'out.svg'
    d_.to_svg(svg, canvas=(120, 60), origin=(0.0, 60))
    (td / 'out-report.json').write_text(json.dumps({k_: v_ for k_, v_ in rep.items() if k_ != '_fates'}, default=str))
    res = hl_.check_notes(svg, [dict(kind='line', path=[pg7_(td, 0.9, 0), pg7_(td, 1.1, 0)], tol_pt=0.05, cover=1.0, layers=['DETAIL']),
                                dict(kind='line', path=[pg7_(td, 1.95, 0), pg7_(td, 2.05, 0)], tol_pt=0.05, cover=0.99, layers=['DETAIL']),
                                dict(kind='line', path=[pg7_(td, 0.95, 1), pg7_(td, 1.05, 1)], tol_pt=0.05, cover=0.99, layers=['DETAIL'])])
    return rep, res, h7_lint(svg), svg
gp8_ = h8_gap()
ok(gp8_[1][0][1] and not gp8_[1][1][1] and not gp8_[1][2][1] and not gp8_[2] and gp8_[0]['model']['off_pt'] <= 0.2
   and sum(1 for f_ in gp8_[0]['fixes'] if f_['kind'] == 'gap closed') == 1,
   f'hidden-lines: a 0.19 pt gap in one object\'s line, its ends facing, is closed; not one between two objects, nor one of 0.3 pt: '
   f'{[x_[3] for x_ in gp8_[1]]}, lint {gp8_[2]}, off {gp8_[0]["model"]["off_pt"]}, fixes {sorted({f_["kind"] for f_ in gp8_[0]["fixes"]})}')

# adversarial scenes for the drawing rules (tests/fixtures/hidden-lines/adversarial/doubles.py), in paper
# points at 1:100: with the doubles kept, a model line goes only where it is hidden, under poche, clipped or inside a
# heavier stroke. doubles-min-hair: a 2 pt line 0.42 pt beside a 4 pt one, strokes clear, both ends free: drawn whole by
# default, given way simplified. doubles-min-convergence: a 2 pt line converging at 8 degrees onto a heavier one it meets:
# drawn whole either way, its free end left 0.28 pt off the heavier as the model has it
def h8_pair(name, heavy, light, rule):
    P_ = lambda x, z: xz7_(x * pt7_, z * pt7_)
    parts = [dict(layer=f'hl::{name}::a', group='a', curve=[P_(*q) for q in heavy]),
             dict(layer=f'hl::{name}::b', group='b', curve=[P_(*q) for q in light]), back7_(name)]
    rep, svg, td = hl_synth_(f'{name}8-{rule}', parts, dict(direction=(0, 1, 0), target=(0, 0, 0)), ab7_(name), scale=100,
                             frame=(40, 20), request=rules7_[rule])
    res = hl_.check_notes(svg, [dict(kind='line', path=[pg7_(td, *(c_ * pt7_ for c_ in light[0])), pg7_(td, *(c_ * pt7_ for c_ in light[-1]))],
                                     tol_pt=0.05, cover=0.98, layers=['DETAIL'])])
    return rep, res, h7_lint(svg)
hr8_ = {r_: h8_pair('hr', [(-2, 0), (2, 0)], [(-1, 0.42), (1, 0.42)], r_) for r_ in 'AB'}
ok(hr8_['B'][1][0][1] and not hr8_['A'][1][0][1] and not hr8_['B'][2] and not hr8_['A'][2]
   and 'a double: gave way to a heavier line beside it' in hr8_['A'][0]['model']['dropped'],
   'hidden-lines: a 2 pt line 0.42 pt beside a heavier one is kept whole by default and gives way simplified (doubles-min-hair): '
   + '; '.join(f'{r_}: {hr8_[r_][1][0][3]}, dropped {hr8_[r_][0]["model"]["dropped"]}, lint {hr8_[r_][2]}' for r_ in 'AB'))
t8_ = math.tan(math.radians(8))
cv8_ = {r_: h8_pair('cv', [(-3, 0), (1, 0)], [(-2, 2 * t8_), (0, 0)], r_) for r_ in 'AB'}
ok(all(cv8_[r_][1][0][1] and not cv8_[r_][2] for r_ in 'AB'),
   'hidden-lines: a line converging at 8 degrees onto one it meets is drawn whole, not cut back as a stub (doubles-min-convergence): '
   + '; '.join(f'{r_}: {cv8_[r_][1][0][3]}, dropped {cv8_[r_][0]["model"]["dropped"]}, lint {cv8_[r_][2]}' for r_ in 'AB'))

# doubles-occluder-0.24-phase0: a line along z = 0 behind a triangle 1 m in front of it whose sides cross the line 0.24 pt
# apart, narrower than the faces' 0.25 pt step between samples. A sample between the two crossings, judged against
# every triangle in its cell, finds the line hidden there, behind the face, and not given way to a thin face
def h8_occluder(rule, w=0.24):
    P_ = lambda x, z, y=0.0: (x * pt7_, y, z * pt7_)
    parts = [dict(layer='hl::oc::b line', group='b', curve=[P_(-12, 0), P_(12, 0)]),
             dict(layer='hl::oc::a front', group='a', tris=[[P_(-w, -8, -1.0), P_(w, -8, -1.0), P_(0, 8, -1.0)]]), back7_('oc')]
    rep, svg, td = hl_synth_(f'occ8-{rule}', parts, dict(direction=(0, 1, 0), target=(0, 0, 0)), ab7_('oc'), scale=100,
                             frame=(40, 30), request=dict(rules7_[rule] or {}, visibility='faces'))
    lo, hi = pg7_(td, -0.4 * w * pt7_, 0), pg7_(td, 0.4 * w * pt7_, 0)
    res = hl_.check_notes(svg, [dict(kind='clear', box=[lo[0], lo[1] - 0.001, hi[0], hi[1] + 0.001], layers=['DETAIL'], max_pt=0.002),
                                dict(kind='line', path=[pg7_(td, -11 * pt7_, 0), pg7_(td, -4 * pt7_, 0)], tol_pt=0.05, cover=0.98, layers=['DETAIL']),
                                dict(kind='line', path=[pg7_(td, 4 * pt7_, 0), pg7_(td, 11 * pt7_, 0)], tol_pt=0.05, cover=0.98, layers=['DETAIL'])])
    return rep, res, h7_lint(svg)
oc8_ = {r_: h8_occluder(r_) for r_ in 'AB'}
ok(all(all(x_[1] for x_ in oc8_[r_][1]) and not oc8_[r_][2] and 'behind a face' in oc8_[r_][0]['model']['dropped'] for r_ in 'AB')
   and 'a thin face: only its heaviest line kept' not in oc8_['B'][0]['model']['dropped'],
   'hidden-lines: a line behind a triangle 0.24 pt wide is hidden there, behind the face (doubles-occluder-0.24): '
   + '; '.join(f'{r_}: {[x_[3] for x_ in oc8_[r_][1]]}, dropped {oc8_[r_][0]["model"]["dropped"]}, lint {oc8_[r_][2]}' for r_ in 'AB'))

# doubles-min-last-stroke: one 0.08 pt segment and no mesh draws an empty drawing, the segment left out as a stray (it
# crashed building the drawn lines' tree from nothing)
try:
    rep_, svg_, _ = hl_synth_('last8', [dict(layer='hl::ls::b', group='b', curve=[xz7_(-0.04 * pt7_, 0), xz7_(0.04 * pt7_, 0)])],
                              dict(direction=(0, 1, 0), target=(0, 0, 0)), ab7_('ls'), scale=100, frame=(40, 20))
    ok(rep_['model']['dropped'].get('a stray', 0) > 0 and not h7_lint(svg_),
       f'hidden-lines: a lone 0.08 pt segment draws an empty drawing, named a stray: {rep_["model"]["dropped"]}')
except SystemExit as e_:
    ok(False, f'hidden-lines: a lone 0.08 pt segment draws an empty drawing: refused, {e_}')

# a check written for one way of drawing doubles applies only to a drawing drawn that way, as its report says
md8_ = hl_.check_notes(gp8_[3], [dict(kind='ends', box=[0, 0, 120, 60], n=99, mode=m_) for m_ in ('simplified', 'kept')])
ok(md8_[0][1] is None and md8_[1][1] is True, f'hidden-lines: a check with a doubles mode applies only to its mode: {[x_[3] for x_ in md8_]}')

# simplify_doubles is true or false; anything else is refused, naming it
try:
    hl_synth_('simplify-bad', [dict(layer='hl::cb::a', group='a', curve=[xz7_(0, 0), xz7_(1, 0)]), back7_('cb')],
              dict(direction=(0, 1, 0), target=(0.5, 0, 0)), ab7_('cb'), scale=100, frame=(40, 20), request=dict(simplify_doubles='yes'))
    ok(False, 'hidden-lines: simplify_doubles "yes" is refused: it drew')
except SystemExit as e_:
    ok('simplify_doubles' in str(e_), f'hidden-lines: simplify_doubles "yes" is refused with its name: {e_}')

# show_hidden adds only the face-hidden complement after the visible paths are fixed
sh_g_ = [dict(id='a', layer='CUT', weights=dict(hidden='heavy'))]
sh_v_ = dict(direction=(0, 1, 0), target=(0.5, 0, 0.5))
sh_wall_ = dict(layer='wall', group='a', solid=True, tris=sy_.box(0.4, -1, -0.2, 0.6, -0.8, 1.2))
sh_box_ = dict(layer='box', group='a', solid=True, tris=sy_.box(0, 0, 0, 1, 1, 1))

def sh_compare_(name, parts, view=sh_v_, **kw):
    rep, svg, td = hl_synth_(name, parts, view, sh_g_, scale=100, frame=(120, 100),
                             request=dict(show_hidden=True, depth_bands_m=[1, 2]), **kw)
    rq = json.loads((td / 'request.json').read_text())
    off, roff = hl_.build(td / 'request.json', req=dict(rq, show_hidden=False))
    off.to_svg(td / 'off.svg', canvas=(120, 100), origin=(0, 100))
    off.to_dxf(td / 'off.dxf')
    on, _ = hl_.build(td / 'request.json')
    on.to_dxf(td / 'out.dxf')
    ok({lid: es for lid, es in on.ents.items() if lid != 'HIDDEN'} ==
       {lid: es for lid, es in off.ents.items() if lid != 'HIDDEN'},
       f'hidden-lines: show_hidden leaves every visible entity unchanged in {name}')
    findings = lint.check(lint.read_svg(svg), on.t) + lint.check(lint.read_dxf(td / 'out.dxf', None), on.t)
    ok(not [x for x in findings if x[0] == 'error' or x[1] == 'double' and 'HIDDEN /' in x[2]],
       f'hidden-lines: show_hidden SVG and DXF lint in {name}: {findings}')
    ok(rep['model']['off_pt'] == roff['model']['off_pt'] and rep['model']['unexplained_pt'] == 0,
       f'hidden-lines: show_hidden keeps off-model and unexplained accounting in {name}: {rep["model"]}')
    return rep, svg, td, on

sh_r_, sh_svg_, sh_td_, sh_d_ = sh_compare_('show-wall', [sh_box_, sh_wall_])
sh_lines_ = hl_lines_(sh_svg_, ['HIDDEN'])
sh_expected_ = HMulti_([[sy_.page(sh_td_, (x, 0, z)) for x in (0.4, 0.6)] for z in (0, 1)])
ok(abs(sh_lines_.length - sh_expected_.length) < 0.02 and sh_lines_.hausdorff_distance(sh_expected_) < 0.01,
   f'hidden-lines: a box behind a wall has hidden edges only across the wall: {sh_lines_.wkt}')
ok(set(sh_d_.subs[st] for st in sh_d_.subs if st[0] == 'HIDDEN') == {'light'}
   and {e['sub'] for e in sh_d_.ents['HIDDEN']} == {'a hidden'}
   and sh_d_.look('HIDDEN')['dash'] == load()['dashes']['hidden'],
   'hidden-lines: hidden lines share the token weight and dash in one group sublayer, ignoring group and depth weights')

sh_r_, sh_svg_, sh_td_, _ = sh_compare_('show-own-back', [sh_box_],
                                       view=dict(direction=(1, 2, -1), target=(0.5, 0.5, 0.5)))
sh_expected_ = HMulti_([[sy_.page(sh_td_, p) for p in edge] for edge in
                      [((1, 1, 0), (0, 1, 0)), ((1, 1, 0), (1, 0, 0)), ((1, 1, 0), (1, 1, 1))]])
sh_lines_ = hl_lines_(sh_svg_, ['HIDDEN'])
ok(sh_r_['hidden_drawn']['count'] == 3 and sh_lines_.hausdorff_distance(sh_expected_) < 0.15,
   f'hidden-lines: a box shows its three own back edges: {sh_lines_.wkt}')

sh_full_wall_ = dict(layer='wall', group='a', solid=True, tris=sy_.box(-0.2, 0, -1, 1.2, 0.1, 2))
sh_curve_ = dict(layer='back', group='a', curve=[(0, 0.5, 0.5), (1, 0.5, 0.5)])
sh_r_, sh_svg_, sh_td_, _ = sh_compare_('show-coincident', [sh_full_wall_, sh_curve_, dict(sh_curve_, layer='copy')])
ok(sh_r_['hidden_drawn'] == dict(count=1, length_pt=28.3),
   f'hidden-lines: two coincident hidden edges draw once: {sh_r_["hidden_drawn"]}')
sh_offset_ = 0.3 / (72 / 25.4 * 1000 / 100)
sh_near_ = dict(layer='front', group='a', curve=[(0, -0.1, 0.5 + sh_offset_), (1, -0.1, 0.5 + sh_offset_)])
sh_r_, _, _, _ = sh_compare_('show-near-visible', [sh_full_wall_, sh_curve_, sh_near_])
ok(sh_r_['hidden_drawn']['count'] == 0,
   f'hidden-lines: a hidden edge 0.3 pt beside a visible one is suppressed: {sh_r_["hidden_drawn"]}')

sh_r_, sh_svg_, _, _ = sh_compare_('show-poche', [sh_box_, dict(sh_curve_, curve=[(0.2, 0.8, 0.5), (0.8, 0.8, 0.5)])],
                                  clip=dict(origin=(0, 0.5, 0), normal=(0, 1, 0)))
ok(sh_r_['hidden_drawn']['count'] == 0 and not hl_lines_(sh_svg_, ['HIDDEN']).length,
   'hidden-lines: a section through a box draws no hidden line under its poche')

for visibility_ in ('engine', 'faces'):
    d_, r_, svg_, _, td_ = hl_draw_('hidden', req=dict(show_hidden=True, visibility=visibility_))
    ok(r_['hidden_drawn']['count'] > 0 and not [x for x in lint.check(lint.read_svg(svg_), d_.t) if x[0] == 'error'],
       f'hidden-lines: a group marked hidden still draws once with show_hidden and {visibility_}')
    hp_ = hl_lines_(svg_, ['HIDDEN'])
    ok(abs(hp_.length - hl_union_(list(hp_.geoms)).length) < 0.01,
       f'hidden-lines: the legacy and requested hidden paths have no overlapping length with {visibility_}')
    d_, r_, svg_, _, td_ = hl_draw_('fuzz-119', req=dict(show_hidden=True, visibility=visibility_))
    ok(r_['hidden_drawn']['count'] > 0 and r_['model']['unexplained_pt'] == 0,
       f'hidden-lines: show_hidden draws the face-hidden stretches with {visibility_}: {r_["hidden_drawn"]}')
sh_cut_ = HDrawing_(100, units='m')
sh_cut_.clip = (0, 0, 10, 10)
sh_cut_.polygon('CUT', [[(1, 1), (4, 1), (4, 3), (1, 3)]])
sh_paths_, _ = hl_.draw_hidden(sh_cut_, [('a', HLine_([(0, 2), (6, 2)]), False)],
                               [HPoly_([(1, 1), (3, 1), (3, 3), (1, 3)])], 0.6)
ok(all(HLine_(P).intersection(HPoly_([(1, 1), (4, 1), (4, 3), (1, 3)])).length == 0 for _, P in sh_paths_),
   'hidden-lines: hidden lines avoid the drawn cut as well as its logical region when their boundaries differ')

sh_stop_ = HDrawing_(100, units='m', meta=dict(doubles='kept'))
sh_stop_.line('HIDDEN', (0, 0), (1, 0))
sh_stop_.line('HIDDEN', (1 + 0.3 / sh_stop_.k, -1), (1 + 0.3 / sh_stop_.k, 1))
sh_stop_.to_svg(sh_td_ / 'hidden-stops.svg')
ok(not [x for x in lint.check(lint.read_svg(sh_td_ / 'hidden-stops.svg'), sh_stop_.t) if x[0] == 'error'],
   'hidden-lines: hidden endpoints are visibility stops, including beside another hidden line')

sh_tokens_ = type(load())(json.loads(json.dumps(load())))
sh_tokens_['roles']['hidden'].pop('weight')
sh_fine_ = HDrawing_(100, units='m', tokens=sh_tokens_)
sh_fine_.clip = (0, 0, 10, 10)
_, sh_fine_report_ = hl_.draw_hidden(sh_fine_, [('a', HLine_([(1, 1), (9, 1)]), False)], [], 0.6)
ok(sh_fine_report_['count'] == 1 and sh_fine_.subs[('HIDDEN', 'a hidden')] == 'fine',
   "hidden-lines: a HIDDEN layer and role without a weight use the scale's finest weight")

try:
    hl_.build(sh_td_ / 'request.json', req=dict(json.loads((sh_td_ / 'request.json').read_text()), show_hidden='yes'))
    ok(False, 'hidden-lines: show_hidden refuses a non-boolean')
except SystemExit as e_:
    ok('show_hidden' in str(e_), f'hidden-lines: show_hidden refuses a non-boolean by name: {e_}')
# hl: the HL command's choices without Rhino (rhino/hl.py): roles guessed from the layer names of representative
# requests, resolved against roles kept on layers, the request the dialog writes, the standard views' frames, and the
# model's faults in plain words
import fnmatch as fnm_
import hl as hlc_
hl_cases_ = {'Walls Combined': 'building', 'Elevator Shaft': 'building', 'Floorplate': 'building', 'Stair': 'building',
             'Railing': 'detail', 'Mullion Border': 'detail', 'Glass Door': 'detail', 'PROJECT::Roof::Roof Beams': 'detail',
             'Tables and Chairs': 'furniture', 'PROJECT::Bedrooms::Bed 1': 'furniture', 'Roof Tiles': 'texture',
             'PROJECT::Roof::Roof Tiling': 'texture', 'Neighbouring Massing': 'context', 'sitebuildings::B1': 'context',
             'Site Geo::Main Context Masses::Masses': 'context', 'Base': 'ground', 'design::base/ground': 'ground',
             'Site Geo::Curb 3D': 'ground', 'Door Swing': 'lines', 'Grid': 'lines', 'Trees': 'trees',
             'Plans::Dining Grid': 'skip', 'Section::Poche::Poche Light': 'skip', 'Scale Figures': 'skip',
             'Construction::Arrow': 'skip', 'Geometry': None, 'Up Faces': None}
hl_miss_ = {p_: hlc_.guess(p_) for p_, r_ in hl_cases_.items() if hlc_.guess(p_) != r_}
ok(not hl_miss_, f'hl: roles guessed from the layer names of representative requests, none missed {hl_miss_}')
hl_res_ = hlc_.resolve(['Railing', 'Old::Walls', 'PROJECT::Utility', 'Up Faces', 'Roofs::Roof Tiles', 'Plans::Walls',
                        'Plans::Anno'], {'Railing': 'furniture', 'Old': 'skip', 'PROJECT': 'context', 'Roofs': 'building',
                                         'Plans': 'context'})
ok(hl_res_ == {'Railing': ('furniture', 'set'), 'Old::Walls': ('skip', 'parent'), 'PROJECT::Utility': ('context', 'parent'),
               'Up Faces': ('building', 'default'), 'Roofs::Roof Tiles': ('texture', 'name'),
               'Plans::Walls': ('building', 'name'), 'Plans::Anno': ('skip', 'name')},
   f'hl: a role kept on a layer wins, a parent\'s Leave out covers its sublayers, a sublayer\'s own name beats its '
   f'parent\'s kept role, a parent given a role stops its own name leaving its sublayers out, and a layer nothing '
   f'names draws as building: {hl_res_}')
hl_odd_ = 'Walls [old]*?'
ok(fnm_.fnmatchcase(hl_odd_, hlc_.glob_escape(hl_odd_)) and not fnm_.fnmatchcase('Walls o*?', hlc_.glob_escape(hl_odd_)),
   'hl: a layer path with [, * and ? becomes a pattern matching it alone')
hl_req_ = hlc_.request_from('plan', 2, {'Geometry': 'building', 'Grid': 'lines', 'Base': 'ground', 'Axo::Base': 'skip'},
                           objects=['b', 'a'], cut='building')
hl_cp_ = {'building': ('CUT', None, None), 'lines': ('FLOOR', None, None), 'ground': ('CONTEXT', True, None)}
ok([g_['id'] for g_ in hl_req_['groups']] == ['building', 'ground', 'lines']
   and all((g_['layer'], g_.get('ground'), g_.get('profile_layer')) == hl_cp_[g_['id']] for g_ in hl_req_['groups'])
   and hl_req_['groups'][0]['layers'] == ['Geometry'] and hl_req_['groups'][0]['body'] == 'building'
   and hl_req_['objects'] == ['a', 'b'] and hl_req_['depth_bands_share'] == [0.25, 0.6] and hl_req_['scale'] == 2,
   f'hl: the request from the dialog\'s roles for the model the model\'s plan holds the groups of its review request, in '
   f'the roles\' order, the cut group on CUT without its outline, Leave out collecting nothing, the objects drawn: '
   f'{[(g_["id"], g_["layers"], g_["layer"]) for g_ in hl_req_["groups"]]}')
hl_box_ = [(x_, y_, z_) for x_ in (0, 10) for y_ in (0, 4) for z_ in (0, 3)]
hl_top_ = hlc_.frame_round(hl_box_, (0, 0, -1), (0, 1, 0), 10.0)
hl_front_ = hlc_.frame_round(hl_box_, (0, 1, 0), (0, 0, 1), 10.0)
hl_right_ = hlc_.axes((-1, 0, 0), (0, 0, 1))
ok(hl_top_[1] == {'w_pt': 136.0, 'h_pt': 76.0} and hl_top_[0]['target'][:2] == [5.0, 2.0]
   and hl_front_[1] == {'w_pt': 136.0, 'h_pt': 66.0} and hl_front_[0]['target'] == [5.0, 2.0, 1.5]
   and [round(v_, 9) for v_ in hl_right_[0]] == [0, 1, 0],
   f'hl: a standard view\'s frame holds what is drawn with 18 pt round it, its target in the middle, and the Right view '
   f'has y to the right as Rhino\'s does: {hl_top_[1]}, {hl_front_[1]}')
hl_g1_, hl_g2_ = '11111111-2222-3333-4444-555555555555', '66666666-7777-8888-9999-000000000000'
hl_rows_ = hlc_.fault_rows([
    {'ids': [hl_g1_], 'layer': 'Stair', 'issue': f'lies on {hl_g2_}, face on face facing the same way (6.67 ft2): x'},
    {'ids': ['c'], 'layer': 'Stair', 'issue': 'lies on d, face on face facing the same way (1 ft2): x'},
    {'ids': ['e'], 'layer': 'Walls', 'issue': 'open polysurface: 3 naked edges'},
    {'ids': ['f'], 'layer': 'Walls', 'issues': ['something new', '2 edges under 0.01 m']}])
ok([(r_['kind'], r_['layer'], len(r_['objects'])) for r_ in hl_rows_]
   == [('open', 'Walls', 1), ('lies-on', 'Stair', 2), ('short-edges', 'Walls', 1), ('other', 'Walls', 1)]
   and hl_g2_ in hl_rows_[1]['ids'] and hl_rows_[3]['say'] == 'Something new.' and hl_rows_[0]['fix'],
   f'hl: the model\'s faults, from the report or check.json, a row a kind and layer in order of harm, with the other '
   f'object an issue names, each with its fix, and one of no known kind said as written: '
   f'{[(r_["kind"], r_["layer"]) for r_ in hl_rows_]}')
hl_open_ = [{'ids': ['g'], 'layer': 'Site::Ground', 'issue': 'open polysurface: 4 naked edges'},
            {'ids': ['t'], 'layer': 'Roof Tiles', 'issue': 'open polysurface: 9 naked edges'},
            {'ids': ['w'], 'layer': 'Walls', 'issue': 'open polysurface: 2 naked edges'},
            {'ids': ['d'], 'layer': 'Walls', 'issue': 'duplicate of x'}]
hl_oreq_ = hlc_.request_from('s', 100, {'Site::Ground': 'ground', 'Roof Tiles': 'texture', 'Walls': 'building'})
hl_orows_ = hlc_.fault_rows(hl_open_, hl_oreq_)
ok([(r_['kind'], r_['layer']) for r_ in hl_orows_] == [('open', 'Walls'), ('duplicate', 'Walls')]
   and hl_orows_[1]['short'] == 'Possible duplicate' and len(hlc_.fault_rows(hl_open_)) == 4,
   f'hl: an open sheet of the ground or on TEXTURE is not a fault, and a duplicate is worded as a suspicion: '
   f'{[(r_["kind"], r_["layer"]) for r_ in hl_orows_]}')
hl_rq_ = hlc_.request_from('p', 100, {'Walls': 'building'})
hl_lw_ = [hlc_.with_lines(hl_rq_, d_, m_) for d_, m_ in ((True, False), (False, True))]
hl_own_ = hlc_.with_lines(dict(hl_rq_, depth_bands_share=None, depth_bands_m=[3, 8], simplify_doubles=True), True, False)
ok(hl_lw_[0]['depth_bands_share'] == list(hlc_.DEPTH_SHARE) and 'simplify_doubles' not in hl_lw_[0]
   and 'depth_bands_share' not in hl_lw_[1] and hl_lw_[1]['simplify_doubles'] is True
   and hl_own_['depth_bands_m'] == [3, 8] and not hl_own_.get('depth_bands_share') and 'simplify_doubles' not in hl_own_
   and 'depth_bands_share' not in hlc_.with_weights(hl_lw_[0], 'single', band_of=lambda l_: 'light')
   and 'show_hidden' not in hl_lw_[0] and hlc_.with_lines(hl_rq_, True, False, True)['show_hidden'] is True
   and 'show_hidden' not in hlc_.with_lines(dict(hl_rq_, show_hidden=True), True, False, False),
   f'hl: lines lighter with distance keep a request\'s own bands or take the house\'s, and off drop them; merging '
   f'close lines sets simplify_doubles and unticked leaves the engine\'s default; drawing hidden lines sets '
   f'show_hidden, off by default; one weight per role has no bands: {hl_lw_}')
ok([hlc_.why('set'), hlc_.why('name', 1), hlc_.why('default', 2)]
   == ['set by you', 'its name; 1 sublayer differs', 'not a name HL knows; 2 sublayers differ']
   and all(hlc_.WEIGHTS_SAY.get(k_) for k_, _ in hlc_.WEIGHTS),
   'hl: the layer list says why a layer has its role, and each line-weight choice says what it does')
hl_wc_ = [hlc_.weights_choice(None, None, [0, 0, -1]), hlc_.weights_choice(None, None, [0.35, 0.5, 0]),
          hlc_.weights_choice('single', 'house', [0.35, 0.5]), hlc_.weights_choice(None, 'single', [0.5, 0.5, 0]),
          hlc_.weights_choice(None, None, [0.5])]
ok(hl_wc_ == ['house', 'layers', 'single', 'single', 'house'],
   f'hl: the line weights open on the model\'s saved choice, else from my layers where layers drawn have differing '
   f'set print widths, else the user\'s last choice, else HL\'s: {hl_wc_}')
hl_iu_ = hlc_.issue_url('0.1.3', '8.35.26251.13002', 'macOS-26.6.2-arm64')
ok(hlc_.short_version('0.1.3.13300') == '0.1.3' and hlc_.short_version('0.1.4+31563') == '0.1.4'
   and hlc_.short_version(None) is None
   and [hlc_.newer(t_, '0.1.3') for t_ in ('v0.1.4', 'v0.1.3', 'v0.0.9', 'v1.0.0', '', None)]
   == [True, False, False, True, False, False]
   and hl_iu_.startswith(hlc_.REPO + '/issues/new?body=HL%200.1.3%0ARhino%208.35') and 'title' not in hl_iu_,
   f'hl: the footer\'s version, whether a release is newer, and an issue with the versions filled in: {hl_iu_}')
ok([hlc_.update_due(c_, 1e9) for c_ in ({}, None, {'checked': 1e9 - 3600}, {'checked': 1e9 - 90000},
                                       {'checked': 1e9 + 90000})] == [True, True, False, True, True]
   and hlc_.LATEST == hlc_.REPO.replace('github.com/', 'api.github.com/repos/') + '/releases/latest',
   'hl: GitHub is asked for the latest release at most once a day, answered or not, and again after a clock '
   'set wrong')
hl_un_ = ['Layer 01', 'Layer 02', 'Default']
hl_unr_ = hlc_.resolve(hl_un_, {})
hl_mix_ = ['Walls', 'Layer 01', 'Trees', 'Plans::old']
hl_mixr_ = hlc_.resolve(hl_mix_, {})
hl_note_ = [hlc_.unknown_notice(hl_unr_, hl_un_), hlc_.unknown_notice(hl_mixr_, hl_mix_),
            hlc_.unknown_notice(hlc_.resolve(['Walls', 'Trees'], {}), ['Walls', 'Trees'])]
ok(hl_note_[0].startswith('HL recognised none') and "didn't recognise 1 of" in hl_note_[1] and 'set its role' in hl_note_[1]
   and hl_note_[2] is None,
   f'hl: layers HL knows no name of are said, more strongly when it knows none, and not when it knows all: {hl_note_}')
hl_rm_ = [hlc_.removal(*a_) for a_ in ((0, False), (12, True), (1, False), (0, True))]
ok(hl_rm_[0] is None and 'the roles HL kept on 12 layers and the dialog\'s remembered choices' in hl_rm_[1][0]
   and 'the role HL kept on 1 layer from' in hl_rm_[2][0] and hl_rm_[3][1].startswith('Removed the dialog\'s remembered')
   and all('drawings on HL\'s layers' in q_ and 'drawings on HL\'s layers' in d_ for q_, d_ in hl_rm_[1:]),
   f'hl: removing HL\'s settings from a model asks first, saying what it removes and that the drawings stay, and has '
   f'nothing to ask of a model with none: {hl_rm_}')
hl_so_ = sorted(['building creases 1.42-3.42 m', 'detail profiles past 3.42 m', 'building creases past 3.42 m', '',
                 'building creases under 1.42 m', 'building open cuts', 'building cuts', 'building profiles 1.42-3.42 m'],
                key=hlc_.sublayer_order)
hl_st_ = hlc_.stale_layers({'HL::p': 0, 'HL::p::BEYOND': 0, 'HL::p::BEYOND::a 1-2 m': 0, 'HL::p::BEYOND::a under 1 m': 3,
                            'HL::p::CUT': 0, 'HL::p::CUT::x cuts': 0, 'HL::q::CUT': 0}, 'HL::p')
ok(hl_so_ == ['', 'building cuts', 'building open cuts', 'building profiles 1.42-3.42 m', 'building creases under 1.42 m',
              'building creases 1.42-3.42 m', 'building creases past 3.42 m', 'detail profiles past 3.42 m']
   and hl_st_ == ['HL::p::BEYOND::a 1-2 m', 'HL::p::CUT::x cuts', 'HL::p::CUT'],
   f'hl: a drawing\'s sublayers come into Rhino by group, class as the standard weights them and depth band near to '
   f'far, and a run again removes the layers it left empty, deepest first, and no other drawing\'s: {hl_so_} {hl_st_}')
hl_dest_ = [hlc_.destination('plan', a_, 'HL', '/Users/a/Documents/m HL/plan', '/Users/a', s_)
            for a_, s_ in ((True, ()), (True, ('ai',)), (True, ('dxf', 'ai', 'svg')), (False, ('svg',)), (False, ()))]
ok(hl_dest_ == ['Adds the drawing to this model under the layer HL::plan.',
                'Adds the drawing to this model under the layer HL::plan, and saves an Illustrator file in '
                '~/Documents/m HL/plan.',
                'Adds the drawing to this model under the layer HL::plan, and saves an Illustrator file, an SVG and a '
                'DXF in ~/Documents/m HL/plan.',
                'Saves an SVG in ~/Documents/m HL/plan. Nothing is added to the model.',
                'Nothing to make: tick Add the drawing to this model, or a file under Also save.'],
   f'hl: the dialog says where the drawing goes, the model alone unless files are ticked under Also save, and when it '
   f'would make nothing: {hl_dest_}')
hl_lint_ = hlc_.lint_rows([
    'a2-plan-4.svg: 56 paths, 0 labels, 1:48',
    'warning double     DETAIL / DETAIL: two lines run side by side under 0.6 pt apart for 8.3 pt near (184.1, 998.9)',
    'warning double     DETAIL / DETAIL: two lines run side by side under 0.6 pt apart for 7.8 pt near (189.0, 1000.5)',
    'warning double     DETAIL / DETAIL: two lines run side by side under 0.6 pt apart for 8.3 pt near (184.1, 998.9)',
    'error near-miss  CUT: line end 0.120 pt from other linework at (28.35, 10.0)',
    'warning frobnicate  X: something new at (1.0, 2.0)',
    '0 errors, 4 warnings'], k=28.35, h_pt=100.0)
ok([(r_['short'], len(r_['places'])) for r_ in hl_lint_]
   == [('Line stops short', 1), ('Lines side by side (2)', 2), ('Frobnicate', 1)]
   and hl_lint_[0]['places'] == [(1.0, 90.0 / 28.35)] and 'Merge close lines' in hl_lint_[1]['fix']
   and hl_lint_[2]['say'] == 'X: something new at (1.0, 2.0)',
   f'hl: what the drawing\'s check finds is a row a kind, errors first, each place once and where it lies in the '
   f'drawing as added to the model, in plain words with what to do: {[(r_["short"], r_["places"]) for r_ in hl_lint_]}')
ok([hlc_.where(r_) for r_ in hl_lint_[:2] + hl_rows_[:2]]
   == ['1 place in the drawing', '2 places in the drawing', '1 object', '2 objects'],
   'hl: the results window says where a row is: objects in the model, or places in the drawing')
hl_mem_ = [hlc_.memory_problem(t_, s_, g_) for t_, s_, g_ in ((6837591, 116333, 8.0), (6837591, 116333, 16.0),
                                                                (100, 10, None), (6837591, 116333, None))]
ok(abs(hlc_.need_gb(6837591, 116333) - 7.0) < 0.1 and hl_mem_[0] and '6,837,591' in hl_mem_[0] and hl_mem_[1:] == [None] * 3,
   f'hl: a drawing that would need over 0.8 of the computer\'s memory is asked about first, the model\'s section 7.0 GB of 8, '
   f'and not where the memory is unknown: {hl_mem_}')
# the drawing step's highest peak in three runs, GB, on the regression exports that peaked over 1 GB: triangles,
# segments, GB (, rhino/hl.py)
hl_peaks_ = [(151179, 48610, 1.63), (2249657, 132278, 3.43), (2506243, 153477, 3.41), (3115053, 79709, 2.35),
             (6196825, 98429, 5.32), (6837591, 116333, 4.92)]
ok(all(hlc_.need_gb(t_, s_) >= g_ for t_, s_, g_ in hl_peaks_),
   f'hl: the memory HL expects a drawing to need is over each regression drawing\'s measured peak: '
   f'{[(round(hlc_.need_gb(t_, s_), 2), g_) for t_, s_, g_ in hl_peaks_]}')
ok([hlc_.damaged(s_) for s_ in ("ModuleNotFoundError: No module named 'shapely'", 'error: Failed to fetch: `https://x`',
                                'ImportError: dlopen(lib.so): Library not loaded', 'FileNotFoundError: scene.json',
                                'wrote x.svg', '')] == [True, True, True, False, False, False],
   'hl: the drawing step\'s output tells packages damaged or missing from other failures')
hl_far_ = hlc_.far_ones([('wall', (0, 0, 0)), ('roof', (5, 3, 6)), ('tree', (13, 2, 2)), ('stair', (2, 1, 1)),
                         ('stray', (1e7, 0, 0))])
hl_fr_ = [hlc_.frame_problem(*a_) for a_ in ((1863.35, 1354.7), (283464639.78, 299.62, 1), (20000, 300),
                                             (85039.4, 56692.9, 0, 1))]
ok(hl_far_ == ['stray'] and hl_fr_[0] is None and '100 km' in hl_fr_[1] and '1 object far from the rest' in hl_fr_[1]
   and 'true size' not in hl_fr_[1]
   and "the model's true size whatever the scale" in hl_fr_[2] and 'Set the scale you print at, or' in hl_fr_[2]
   and '30 m across' in hl_fr_[3] and 'such as 1:50, where it would be 0.6 m across' in hl_fr_[3],
   f'hl: a sheet wider than Illustrator takes is refused, naming the objects far from the rest that make it so, or '
   f'saying the drawing in Rhino and its DXF are at true size whatever the scale, with a print scale that fits A0: '
   f'{hl_far_}, {hl_fr_}')
hl_long_ = [hlc_.long_path('C:\\Users\\a\\' + 'x' * n_, 'plan') for n_ in (200, 240)]
ok(hl_long_[0] is None and '260' in hl_long_[1] and 'Save files in' in hl_long_[1],
   f'hl: a drawing whose files would pass Windows\' 260 characters is said so, with what to change: {hl_long_}')
# one issue a kind, as the export (rhino/hidden_lines.py) and the engine (hiddenlines/hidden.py) write them
hl_said_ = {
    'invalid': 'invalid brep: face 3 is bad', 'open': 'open polysurface: 3 naked edges',
    'self-crossing-face': '2 faces cross their own boundary (a profile that crosses itself)',
    'non-manifold': '4 non-manifold edges', 'inside-out': 'inside out: its faces point inward',
    'turned': f'faces the same way as Walls {hl_g2_} beside it, 0.25 m apart, so one of the two is turned; read as '
              f'facing out of the wall between',
    'runs-into': f'runs into {hl_g2_} by 1.2 m3',
    'lies-on': f'lies on {hl_g2_}, face on face facing the same way (6.67 ft2): the earlier group\'s is drawn',
    'unjoined-edge': f'shares an edge with {hl_g2_}: join them', 'union-failed': 'union with 2 parts (open); kept apart',
    'cut-open': 'the cut by clip plane 0 does not close',
    'ring-mismatch': 'its ring and its clipped mesh disagree: 2.0 pt of the mesh\'s section lies up to 0.48 pt off the '
                     'ring; the cut follows the mesh there',
    'nearly-planar': '2 faces nearly planar: flat within 0.01 m, not within 0.001',
    'creased': '1 faces creased inside (split them at the crease: the engine draws no line there)',
    'short-edges': '3 edges under 0.01 m', 'duplicate': f'duplicate of {hl_g2_}',
    'curve-in-solids': 'a curve among its group\'s solids, drawn as a line', 'both-ways': 'mesh faces point both ways',
    'far': 'more than 10 km from the origin, where precision suffers', 'no-mesh': 'no mesh'}
hl_word_ = {k_: hlc_.plain(s_) for k_, s_ in hl_said_.items()}
ok(sorted(hl_said_) == sorted(k_ for k_, _, _, _, _ in hlc_.FAULTS)
   and all(w_[0] == k_ and all(w_[1:]) for k_, w_ in hl_word_.items()),
   f'hl: every kind of fault is worded, a few words, what is wrong and the fix, and the issue as the export or the '
   f'engine writes it is read as its kind: {[(k_, w_[0]) for k_, w_ in hl_word_.items() if w_[0] != k_]}')
hl_turn_ = hlc_.fault_rows([{'ids': [hl_g1_], 'layer': 'Walls', 'issue': hl_said_['turned']}])
ok(hl_turn_[0]['kind'] == 'turned' and hl_turn_[0]['ids'] == [hl_g1_, hl_g2_],
   f'hl: a turned surface\'s row selects the surface beside it too, which its issue names by its whole id: '
   f'{hl_turn_[0]["ids"]}')
if hasattr(hl_, 'FAULT_KINDS'):
    ok(all(hl_.fault_kind(s_) == k_ for k_, s_ in hl_said_.items()),
       f'hl: the engine reads each issue as the kind the results window words it by: '
       f'{[(k_, hl_.fault_kind(s_)) for k_, s_ in hl_said_.items() if hl_.fault_kind(s_) != k_]}')
hl_sus_ = hlc_.suspect_rows([
    {'what': 'near miss', 'why': 'a face crosses itself', 'ids': ['a'], 'kinds': ['self-crossing-face'],
     'confidence': 'near', 'measure': 0.2, 'action': 'repaired', 'at_pt': [1, 2]},
    {'what': 'open cut', 'why': 'an open polysurface', 'ids': ['b', 'c'], 'kinds': ['open'], 'confidence': 'traced',
     'measure': 14.0, 'action': 'left'},
    {'what': 'unresolved cell', 'why': 'Floor d1: open polysurface', 'ids': ['d'], 'kinds': ['open'],
     'confidence': 'traced', 'measure': 3.5, 'action': 'repaired'}], {'a': 'Stair', 'b': 'Walls', 'd': 'Floor'}.get)
ok([r_['short'] for r_ in hl_sus_] == ['Open cut', 'Unresolved cell', 'Near miss, near a fault']
   and hl_sus_[0]['layer'] == 'Walls' and hl_sus_[0]['ids'] == ['b', 'c'] and hl_sus_[0]['say'].startswith('Caused by')
   and '3.5 pt2' in hl_sus_[1]['say'] and hl_sus_[2]['say'].startswith('Not traced') and hl_sus_[0]['fix'],
   f'hl: the engine\'s suspects, what is left in the drawing first and traced causes before near ones, each with its '
   f'objects\' layer, its measure in pt or pt2 and the fix of its fault: {[r_["short"] for r_ in hl_sus_]}')
ok(hlc_.out_folder('/m/the model/Final.3dm', 'top', '/u') == os.path.join('/m/the model', 'Final HL', 'top')
   and hlc_.out_folder('', 'top', '/u/OneDrive/Documents') == os.path.join('/u/OneDrive/Documents', 'HL', 'top')
   and hlc_.slug('Section: plane A') == 'section-plane-a',
   'hl: a drawing without a request file goes beside its model in "<model> HL", or in Documents/HL for one never saved')

hl_cnt_ = {'PROJECT::Walls': 4, 'PROJECT::Roof::Roof Tiling': 9, 'PROJECT::Roof': 2, 'Plans::Walls': 7}
hl_rres_ = hlc_.resolve(list(hl_cnt_) + ['PROJECT', 'Plans'], {'PROJECT': 'building'})
hl_top_ = hlc_.top_rows(list(hl_cnt_), hl_rres_, hl_cnt_)
ok(hl_top_ == [('PROJECT', 15, 'building', 'set', 1), ('Plans', 7, 'skip', 'name', 0)],
   f'hl: the streamlined list has a row a top-level layer, counting what lies under it and how many of its sublayers '
   f'draw in another role (roof tiles as texture under a building): {hl_top_}')
hl_wreq_ = hlc_.request_from('s', 100, {'Walls': 'building', 'Glass': 'detail', 'Site': 'ground'})
hl_wroles_ = {'Walls': 'building', 'Glass': 'detail', 'Site': 'ground'}
hl_house_ = hlc_.with_weights(hl_wreq_, 'house')
hl_lay_ = hlc_.with_weights(hl_wreq_, 'layers', hl_wroles_, {'Walls': 0.5, 'Glass': 0.0, 'Site': -1})
hl_one_ = hlc_.with_weights(hlc_.with_cut(hl_wreq_, 'building'), 'single', hl_wroles_, None,
                            {'BEYOND': 'medium', 'DETAIL': 'light', 'CONTEXT': 'fine'}.get)
hl_g_ = {g_['id']: g_ for g_ in hl_one_['groups']}
hl_lg_ = {g_['id']: g_ for g_ in hl_lay_['groups']}
hl_un2_ = hlc_.with_cut(hlc_.with_weights(hlc_.request_from('u', 100, {'Layer 01': 'building', 'Layer 02': 'building'}),
                                          'layers', {'Layer 01': 'building', 'Layer 02': 'building'},
                                          {'Layer 01': 0.5, 'Layer 02': 0.35}), 'building')
ok([(g_['id'], g_.get('profile_weight'), g_.get('body'), g_['layer']) for g_ in hl_un2_['groups']]
   == [('building', None, 'building', 'CUT'), ('building Layer 01', 1.417, 'building', 'CUT'),
       ('building Layer 02', 0.992, 'building', 'CUT')]
   and hl_un2_['groups'][0]['not_layers'] == ['Layer 01', 'Layer 02'],
   f'hl: from my layers, each layer with a print width of its own is a group of its role outlined at that width, '
   f'its body and the cut kept, so the poché joins across them: {hl_un2_["groups"]}')
ok(hl_house_ is hl_wreq_ and [hl_lg_[k_].get('profile_weight') for k_ in ('building', 'building Walls', 'detail', 'ground')]
   == [None, 1.417, None, None] and hl_lg_['building']['not_layers'] == ['Walls']
   and hl_g_['building']['weights']['profile'] == 'medium' and 'cut' not in hl_g_['building']['weights']
   and hl_g_['detail']['weights']['crease'] == 'light' and hl_g_['ground']['weights']['line'] == 'fine'
   and 'depth_bands_share' not in hl_one_ and 'weights' not in hl_wreq_['groups'][0],
   'hl: line weights: the house\'s leaves the request as it is; from my layers outlines a layer at its own set print '
   'width (0.5 mm, 1.42 pt), a layer at the default or not printing keeping the house\'s; one weight per role '
   'gives every visible class its layer\'s house weight, a cut group\'s that of BEYOND, keeps the cut and drops the '
   'depth bands')

hl_names_ = {n_: hlc_.name_problem(n_) for n_ in ('', 'a/b', 'plan::1', 'CON', 'con.svg', 'Plan.', 'x' * 81, 'é plan',
                                                    'section A-2.5')}
ok([k_ for k_, v_ in hl_names_.items() if v_ is None] == ['é plan', 'section A-2.5'],
   f'hl: a drawing\'s name is refused empty, with a slash or ::, as a name Windows keeps (CON), ending in a dot, or over '
   f'80 characters, and taken with accents, spaces, dots and dashes: {hl_names_}')
hl_gone_ = hlc_.folder_problem('/Volumes/test-drive/x/plan', PermissionError(13, 'Permission denied'), exists=lambda p_: False)
hl_ro_ = hlc_.folder_problem('/tmp/ro/plan', PermissionError(13, 'Permission denied'), exists=lambda p_: True)
hl_full_ = hlc_.folder_problem('/tmp/x/plan', OSError(28, 'No space left on device'), exists=lambda p_: True)
ok('drive test-drive is not connected' in hl_gone_ and 'not allowed' in hl_ro_ and 'No space left' in hl_full_
   and all('Save files in' in m_ for m_ in (hl_gone_, hl_ro_, hl_full_)),
   'hl: a folder HL cannot write in is said plainly: a drive not connected, a folder not to write in, the system\'s '
   'own reason, each with where to choose another')
hl_tcc_ = [hlc_.folder_problem('/Users/a/Documents/m HL/plan', PermissionError(1, 'Operation not permitted'),
                               exists=lambda p_: True, mac=m_) for m_ in (True, False)]
ok('Files & Folders' in hl_tcc_[0] and 'Save files in' in hl_tcc_[0] and 'Files & Folders' not in hl_tcc_[1]
   and 'Files & Folders' not in hl_ro_,
   f'hl: a Mac refusing Rhino a folder (EPERM, after Don\'t Allow) names the setting that allows it, and other '
   f'refusals do not: {hl_tcc_}')

# the fault kinds the export's issues are classed into (hiddenlines/hidden.py, the engine's) are the ones the results
# window words; hidden.FAULT_KINDS arrives with the stage 3 branch
if hasattr(hl_, 'FAULT_KINDS'):
    hl_kinds_ = ({k_ for k_, _ in hl_.FAULT_KINDS}, {k_ for k_, _, _, _, _ in hlc_.FAULTS})
    ok(hl_kinds_[0] == hl_kinds_[1], f'hl: the engine\'s fault kinds and the results window\'s are one list: only the '
       f'engine\'s {sorted(hl_kinds_[0] - hl_kinds_[1])}, only the window\'s {sorted(hl_kinds_[1] - hl_kinds_[0])}')

# readable names are assigned after the geometry is finished
import ezdxf as rename_dxf_
from archkit.draw import Drawing as RenameDrawing_


def rename_scene_(units, bands, own=False):
    dr = RenameDrawing_(100, units=units)
    for i in range(len(bands) + 1 if bands else 1):
        tail = ('' if not bands else f' under {bands[0]:g} m' if i == 0 else
                f' past {bands[-1]:g} m' if i == len(bands) else f' {bands[i - 1]:g}-{bands[i]:g} m')
        sub = ('base bases' if own else 'building profiles') + tail
        dr.sublayer('OUTLINE', sub, ('heavy', 'medium', 'light', 'fine')[min(i, 3)])
        dr.line('OUTLINE', (0, i * 10), (10, i * 10), sub=sub)
    hl_.name_sublayers(dr, bands, {'m': 1000, 'ft': 304.8}[units])
    return dr


rename_dir_ = Path(tempfile.mkdtemp(prefix='hl-names-'))
rename_ns_ = '{http://www.inkscape.org/namespaces/inkscape}'
for rename_units_, rename_bands_, rename_own_ in [('m', [2.05, 4.92], False), ('ft', [2.05, 4.92], False),
                                                ('m', [], False), ('m', [1, 2, 3], False), ('m', [1, 2], True)]:
    rename_d_ = rename_scene_(rename_units_, rename_bands_, rename_own_)
    rename_d_.to_svg(rename_dir_ / 'out.svg')
    rename_d_.to_dxf(rename_dir_ / 'out.dxf')
    rename_d_.to_ai(rename_dir_ / 'out.ai')
    rename_root_ = ET_.parse(rename_dir_ / 'out.svg').getroot()
    rename_leaves_ = [g for g in rename_root_.iter() if g.get('data-weight')]
    rename_labels_ = [g.get(rename_ns_ + 'label') for g in rename_leaves_]
    rename_expected_ = [p[-1][0] for p in rename_d_.subpaths.values()]
    rename_class_ = 'base' if rename_own_ else 'building profiles'
    rename_top_ = next(g for g in rename_root_ if g.get('id') == 'OUTLINE')
    rename_x_ = rename_dxf_.readfile(rename_dir_ / 'out.dxf')
    rename_ai_ = hl_ai_.census(rename_dir_ / 'out.ai')
    rename_ai_paths_ = [l['path'] for l in rename_ai_['layers'] if l['own']['paths']]
    rename_paths_ = ['OUTLINE/' + '/'.join(p[0] for p in path) for path in rename_d_.subpaths.values()]
    ok(rename_labels_ == rename_expected_ and all(g.get(rename_ns_ + 'label') == rename_class_ for g in rename_top_)
       and all(len(list(g)) == (len(rename_bands_) + 1 if rename_bands_ else 1) for g in rename_top_)
       and rename_ai_paths_ == rename_paths_
       and [e.dxf.layer for e in rename_x_.modelspace()] == [p.replace('/', ' › ') for p in rename_paths_]
       and all(e.dxf.lineweight > 0 for e in rename_x_.modelspace()),
       f'hidden-lines names: SVG, DXF and AI class/distance tree in {rename_units_}, {len(rename_bands_) + 1} bands, own class {rename_own_}: {rename_labels_}')
    rename_lint_ = lint.check(lint.read_svg(rename_dir_ / 'out.svg'), rename_d_.t)
    ok(not any(code == 'weight' for _, code, *_ in rename_lint_),
       f'hidden-lines names: nested leaf weights lint in {rename_units_}, {rename_bands_}, own class {rename_own_}')
    if rename_units_ == 'ft':
        ok(rename_labels_ == ['near (under 6.73 ft)', 'middle (6.73–16.1 ft)', 'far (past 16.1 ft)'],
           'hidden-lines names: feet ranges convert metre thresholds at three significant figures')
    if len(rename_bands_) == 3:
        ok(rename_labels_ == ['near (under 1 m)', 'middle 1 (1–2 m)', 'middle 2 (2–3 m)', 'far (past 3 m)'],
           'hidden-lines names: four bands number their middle leaves in order')
rename_a_, rename_b_ = rename_scene_('m', [2.05, 4.92]), rename_scene_('m', [2.1, 5])
ok(list(rename_a_.subids.values()) == list(rename_b_.subids.values())
   == ['OUTLINE-building-profiles-near', 'OUTLINE-building-profiles-middle', 'OUTLINE-building-profiles-far'],
   'hidden-lines names: leaf ids remain identical when both band edges move')
rename_collision_ = RenameDrawing_(100, units='m')
for rename_sub_ in ['a b profiles', 'a-b profiles', 'a.b profiles']:
    rename_collision_.sublayer('OUTLINE', rename_sub_, 'light')
    rename_collision_.line('OUTLINE', (0, 0), (1, 0), sub=rename_sub_)
hl_.name_sublayers(rename_collision_, [], 1000)
rename_collision_.to_svg(rename_dir_ / 'collision.svg')
rename_ids_ = [g.get('id') for g in ET_.parse(rename_dir_ / 'collision.svg').getroot().iter() if g.get('id')]
ok(len(rename_ids_) == len(set(rename_ids_)), 'hidden-lines names: colliding sanitised group names never share SVG ids')
rename_a_.to_svg(rename_dir_ / 'bad.svg')
rename_bad_ = (rename_dir_ / 'bad.svg').read_text().replace('data-weight="heavy"', 'data-weight="fine"')
(rename_dir_ / 'bad.svg').write_text(rename_bad_)
ok(any(code == 'weight' for _, code, *_ in lint.check(lint.read_svg(rename_dir_ / 'bad.svg'), rename_a_.t)),
   'hidden-lines names: lint still detects a wrong weight on a nested leaf')
rename_sorted_ = sorted(['base::far (past 3 ft)', 'building profiles::middle 2 (2–3 m)',
                         'building profiles::far (past 3 m)', 'building profiles::near (under 1 m)',
                         'base::near (under 1 ft)', 'building profiles::middle 1 (1–2 m)',
                         'building overlaps::near (under 1 m)'], key=hlc_.sublayer_order)
ok(rename_sorted_ == ['base::near (under 1 ft)', 'base::far (past 3 ft)', 'building profiles::near (under 1 m)',
                       'building profiles::middle 1 (1–2 m)', 'building profiles::middle 2 (2–3 m)',
                       'building profiles::far (past 3 m)', 'building overlaps::near (under 1 m)'],
   f'hl: nested names sort by group, standard class and ordinal distance regardless of units: {rename_sorted_}')
rename_stale_ = hlc_.stale_layers({'HL::p::BEYOND': 0, 'HL::p::BEYOND::building profiles': 0,
                                   'HL::p::BEYOND::building profiles::near (under 2 m)': 1,
                                   'HL::p::BEYOND::building profiles::near (under 1 m)': 0,
                                   'HL::p::BEYOND::building overlaps': 0,
                                   'HL::p::BEYOND::building overlaps::far (past 2 m)': 0,
                                   'HL::q::BEYOND::building profiles': 0}, 'HL::p')
ok(set(rename_stale_) == {'HL::p::BEYOND::building profiles::near (under 1 m)',
                           'HL::p::BEYOND::building overlaps::far (past 2 m)', 'HL::p::BEYOND::building overlaps'}
   and rename_stale_[-1].endswith('building overlaps'),
   'hl: moved ranges and unused classes are removed deepest first, live ancestors and other drawings kept')
shutil.rmtree(rename_dir_)

# interleaved classes retain their original paint order
rename_inter_ = RenameDrawing_(100, units='m')
for rename_i_, (rename_sub_, rename_w_) in enumerate([('building profiles past 2 m', 'light'),
                                                     ('building overlaps past 2 m', 'light'),
                                                     ('building profiles under 1 m', 'heavy')]):
    rename_inter_.sublayer('OUTLINE', rename_sub_, rename_w_)
    rename_inter_.line('OUTLINE', (0, rename_i_ * 10), (10, rename_i_ * 10), sub=rename_sub_, dash='hidden')
rename_inter_dir_ = Path(tempfile.mkdtemp(prefix='hl-order-'))
rename_inter_.to_svg(rename_inter_dir_ / 'before.svg')
rename_inter_.to_ai(rename_inter_dir_ / 'before.ai')
hl_.name_sublayers(rename_inter_, [1, 2], 1000)
rename_inter_.to_svg(rename_inter_dir_ / 'after.svg')
rename_inter_.to_ai(rename_inter_dir_ / 'after.ai')
rename_before_paths_ = lint.read_svg(rename_inter_dir_ / 'before.svg')['paths']
rename_after_paths_ = lint.read_svg(rename_inter_dir_ / 'after.svg')['paths']
rename_before_ai_ = hl_ai_.native(rename_inter_dir_ / 'before.ai')
rename_after_ai_ = hl_ai_.native(rename_inter_dir_ / 'after.ai')
rename_geometry_ = lambda data: re.findall(rb'[^\r\n]+ (?:m|L|S|s)\r', data)
ok([(p.segs, p.width, p.stroke, p.want) for p in rename_before_paths_]
   == [(p.segs, p.width, p.stroke, p.want) for p in rename_after_paths_]
   and rename_geometry_(rename_before_ai_) == rename_geometry_(rename_after_ai_)
   and hl_ai_.census(rename_inter_dir_ / 'before.ai')['totals']['looks']
       == hl_ai_.census(rename_inter_dir_ / 'after.ai')['totals']['looks'],
   'hidden-lines names: interleaved classes preserve SVG and AI geometry, weight, dash, colour and paint order')
rename_inter_.to_dxf(rename_inter_dir_ / 'after.dxf')
rename_inter_paths_ = rename_inter_.subpaths
rename_inter_.subpaths = {}
rename_inter_.to_dxf(rename_inter_dir_ / 'before.dxf')
rename_inter_.subpaths = rename_inter_paths_
rename_dxf_styles_ = []
for rename_phase_ in ('before', 'after'):
    rename_doc_ = rename_dxf_.readfile(rename_inter_dir_ / (rename_phase_ + '.dxf'))
    rename_dxf_styles_.append([(e.dxftype(), list(e.get_points()) if e.dxftype() == 'LWPOLYLINE' else
                               (tuple(e.dxf.start), tuple(e.dxf.end)), e.dxf.lineweight,
                               rename_doc_.layers.get(e.dxf.layer).dxf.linetype,
                               rename_doc_.layers.get(e.dxf.layer).dxf.true_color) for e in rename_doc_.modelspace()])
ok(rename_dxf_styles_[0] == rename_dxf_styles_[1],
   'hidden-lines names: flat DXF leaf paths preserve geometry, entity lineweight, inherited dash, ink and order')
shutil.rmtree(rename_inter_dir_)

# source ownership changes only the Rhino payload
src_td_ = Path(tempfile.mkdtemp(prefix='hl-source-'))
sy_.write(src_td_, [dict(layer='Model::Windows', group='a', curve=[(-1, 0, 0), (0, 0, 0)]),
                   dict(layer='Model::Furniture::Chairs', group='a', curve=[(0, 0, 0), (1, 0, 0)])],
          dict(direction=(0, 1, 0), target=(0, 0, 0)), [dict(id='a', layer='DETAIL')], scale=100, frame=(120, 100))
src_d_, _ = hl_.build(src_td_ / 'request.json')
src_scene_ = json.loads((src_td_ / 'scene.json').read_text())
src_files_ = {}
for src_phase_ in ('before', 'after'):
    src_d_.to_svg(src_td_ / (src_phase_ + '.svg'), canvas=(120, 100), origin=(0, 100))
    src_d_.to_dxf(src_td_ / (src_phase_ + '.dxf'))
    src_d_.to_ai(src_td_ / (src_phase_ + '.ai'), canvas=(120, 100), origin=(0, 100))
    src_files_[src_phase_] = [(src_td_ / (src_phase_ + '.' + ext)).read_bytes() for ext in ('svg', 'dxf', 'ai')]
    if src_phase_ == 'before':
        src_data_ = hl_.for_rhino(src_d_)
src_lines_ = [ln for L in src_data_['layers'] for sub in L['subs'] for ln in sub['lines']]
ok(len([e for es in src_d_.ents.values() for e in es]) == 1 and len(src_lines_) == 2
   and src_data_['split_paths'] == 1 and {ln['source'] for ln in src_lines_} == {0, 1}
   and src_lines_[0]['pts'][-1] == src_lines_[1]['pts'][0]
   and all(all(x <= 60 / src_d_.k + 1e-6 if ln['source'] == 0 else x >= 60 / src_d_.k - 1e-6
               for x, y in ln['pts']) for ln in src_lines_),
   'hidden-lines sources: a single drawn path over two objects splits only in for_rhino at their shared endpoint')
ok(src_data_['objects'] == [dict(ids=o['ids'], layer=o['layer']) for o in src_scene_['objects']]
   and {o['layer'] for o in src_data_['objects']} == {'Model::Windows', 'Model::Furniture::Chairs'},
   'hidden-lines sources: the table preserves object ids and full nested layer paths in scene index order')
ok(src_files_['before'] == src_files_['after'],
   'hidden-lines sources: producing the Rhino payload leaves SVG, DXF and AI byte for byte unchanged')

src_closed_ = hl_.source_runs([(0, 0), (1, 0), (1, 1), (0, 1)], True, [0, 1, 1, 0])
ok(len(src_closed_) == 2 and all(not ln['closed'] for ln in src_closed_)
   and src_closed_[0]['pts'] == [(0, 1), (0, 0), (1, 0)]
   and hl_.source_runs([(0, 0), (1, 0), (1, 1)], True, [2, 2, 2]) ==
       [dict(pts=[(0, 0), (1, 0), (1, 1)], closed=True, source=2)],
   'hidden-lines sources: closed paths join their first and last source run without losing the closing edge')

src_cut_td_ = src_td_ / 'cut'
sy_.write(src_cut_td_, [dict(layer='Building::Left', group='a', solid=True, tris=sy_.box(-1, -1, -1, 0, 1, 1)),
                       dict(layer='Building::Right', group='a', solid=True, tris=sy_.box(0, -1, -1, 1, 1, 1))],
          dict(direction=(0, 1, 0), target=(0, 0, 0)), [dict(id='a', layer='CUT')],
          clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), scale=100, frame=(120, 100))
src_cut_d_, _ = hl_.build(src_cut_td_ / 'request.json')
src_cut_data_ = hl_.for_rhino(src_cut_d_)
src_cuts_ = [ln for L in src_cut_data_['layers'] if L['id'] == 'CUT' for sub in L['subs'] for ln in sub['lines']]
src_mid_ = 60 / src_cut_d_.k
ok({ln['source'] for ln in src_cuts_} == {0, 1}
   and all(all(x <= src_mid_ + 1e-6 if ln['source'] == 0 else x >= src_mid_ - 1e-6 for x, y in ln['pts']) for ln in src_cuts_),
   'hidden-lines sources: a merged cut outline is split at its two source objects, including straight shared runs')

src_hidden_td_ = src_td_ / 'hidden'
sy_.write(src_hidden_td_, [dict(layer='Model::Left', group='a', curve=[(-1, 0, 0), (0, 0, 0)]),
                          dict(layer='Model::Right', group='a', curve=[(0, 0, 0), (1, 0, 0)]),
                          dict(layer='Model::Cover', group='b', solid=True, tris=sy_.box(-1.1, -1, -1, 1.1, -0.5, 1))],
          dict(direction=(0, 1, 0), target=(0, 0, 0)), [dict(id='a', layer='DETAIL'), dict(id='b', layer='CONTEXT')],
          scale=100, frame=(120, 100), request=dict(show_hidden=True))
src_hidden_d_, _ = hl_.build(src_hidden_td_ / 'request.json')
src_hidden_data_ = hl_.for_rhino(src_hidden_d_)
src_hidden_lines_ = [ln for L in src_hidden_data_['layers'] if L['id'] == 'HIDDEN'
                     for sub in L['subs'] for ln in sub['lines']]
ok({ln['source'] for ln in src_hidden_lines_} >= {0, 1}
   and all(sub['kind'] == 'hidden' for L in src_hidden_data_['layers'] if L['id'] == 'HIDDEN' for sub in L['subs'])
   and all(all(x <= 60 / src_hidden_d_.k + 1e-6 if ln['source'] == 0 else x >= 60 / src_hidden_d_.k - 1e-6
               for x, y in ln['pts']) for ln in src_hidden_lines_ if ln['source'] in (0, 1)),
   'hidden-lines sources: hidden paths retain their hidden source objects and split at the source boundary')

src_all_ = [hl_.for_rhino(pair[0]) for pair in hl_out_.values()]
ok(all(isinstance(ln['source'], int) and 0 <= ln['source'] < len(data['objects'])
       for data in src_all_ for L in data['layers'] for sub in L['subs'] for ln in sub['lines']),
   'hidden-lines sources: every line in every recorded visible, cut and perspective scene has one valid source')

src_kinds_ = ('profiles', 'bases', 'overlaps', 'steps', 'creases', 'seams', 'lines', 'cuts', 'hidden', 'above')
src_tree_data_ = dict(scale=100, objects=[dict(ids=['window-id'], layer='Model::Windows'),
                                         dict(ids=['chair-id', 'joined-id'], layer='Model::Furniture::Chairs')],
                      layers=[dict(id='DETAIL', ink='#808080', print=True, dash='hidden', dash_model=[0.1, 0.05],
                                   subs=[dict(name='building ' + kind + '::' + band, kind=kind, weight_mm=weight,
                                              lines=[dict(pts=[[0, 0], [1, 0]], closed=False, source=i % 2)], fills=[])
                                         for i, kind in enumerate(src_kinds_) for band, weight in
                                         [('near (under 1 m)', 0.3), ('middle (1–2 m)', 0.2), ('far (past 2 m)', 0.1)]])])
src_role_tree_ = hlc_.layer_tree(src_tree_data_)
src_model_tree_ = hlc_.layer_tree(src_tree_data_, 'model')
ok(len(src_role_tree_) == 30 and all(leaf['path'][0] == 'DETAIL' and len(leaf['path']) == 3 for leaf in src_role_tree_)
   and len(src_model_tree_) == 10 and {leaf['path'][-1] for leaf in src_model_tree_} == set(src_kinds_)
   and all(leaf['path'][:-1] in [['Model', 'Windows'], ['Model', 'Furniture', 'Chairs']] for leaf in src_model_tree_),
   'hl: model tree nests source paths and every standard class, with no role or distance levels; role tree is unchanged')
ok(all(sorted(ln['attributes']['weight_mm'] for ln in leaf['lines']) == [0.1, 0.2, 0.3]
       and all(ln['attributes']['dash'] == 'hidden' and ln['attributes']['dash_model'] == [0.1, 0.05]
               and ln['attributes']['ink'] == '#808080' for ln in leaf['lines']) for leaf in src_model_tree_),
   "hl: model tree retains each curve's leaf print width, dash pattern and ink across all distances and classes")
ok(all(ln['attributes']['user_text'] == {'hl.layer': src_tree_data_['objects'][ln['source']]['layer'],
                                        'hl.object': ', '.join(src_tree_data_['objects'][ln['source']]['ids'])}
       for tree in (src_role_tree_, src_model_tree_) for leaf in tree for ln in leaf['lines'])
   and all(set(ln['attributes']) == {'user_text'} for leaf in src_role_tree_ for ln in leaf['lines']),
   'hl: both trees attach full source layer and every source id, with inherited print attributes only in role mode')
ok([leaf['path'] for leaf in src_model_tree_][:2] == [['Model', 'Furniture', 'Chairs', 'cuts'],
                                                      ['Model', 'Furniture', 'Chairs', 'bases']]
   and [leaf['path'][:-1] for leaf in hlc_.layer_tree(src_tree_data_, 'model', {
       'Model': 0, 'Model::Windows': 1, 'Model::Furniture': 2, 'Model::Furniture::Chairs': 3})][::5]
   == [['Model', 'Windows'], ['Model', 'Furniture', 'Chairs']],
   "hl: model tree orders source layers by the model's sort order, else by name, and classes as the standard does")
src_tree_data_['layers'][0]['print'] = False
ok(all(ln['attributes']['weight_mm'] == -1.0 for leaf in hlc_.layer_tree(src_tree_data_, 'model') for ln in leaf['lines']),
   'hl: a non-printing source leaf remains non-printing with object print attributes')
ok(hlc_.layer_tree_choice(None, None) == 'role' and hlc_.layer_tree_choice('model', 'role') == 'model'
   and hlc_.layer_tree_choice(None, 'model') == 'model' and hlc_.layer_tree_choice('old', 'old') == 'role',
   'hl: layer tree defaults to role, remembers the model choice before the user choice and ignores unknown choices')
src_stale_ = hlc_.stale_layers({'HL::p::DETAIL': 0, 'HL::p::DETAIL::building profiles': 0,
                                'HL::p::Model': 0, 'HL::p::Model::Windows': 0, 'HL::p::Model::Windows::profiles': 3,
                                'HL::q::DETAIL': 0}, 'HL::p')
ok(set(src_stale_) == {'HL::p::DETAIL', 'HL::p::DETAIL::building profiles'}
   and src_stale_[0].endswith('building profiles'),
   'hl: switching layer trees removes the old empty tree deepest first and preserves the live model tree and other drawings')
shutil.rmtree(src_td_)


if __name__ == '__main__':
    print(f'\n{len(fails)} failed' if fails else '\nall passed')
    sys.exit(1 if fails else 0)
