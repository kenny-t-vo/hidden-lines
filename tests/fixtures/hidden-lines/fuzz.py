#! python3
"""Random scenes for kit.py hidden-lines, built and exported in Rhino, then drawn and linted on the Mac.

In an empty Rhino document, through the connector's run_python:
  ns = {'__rhino_doc__': __rhino_doc__, '__name__': 'fuzz', 'FUZZ_DIR': DIR, 'SEEDS': range(0, 20)}
  exec(open(PATH).read, ns); print(ns['build'])
writes DIR/<seed>/request.json, scene.json and meshes.bin for each seed, in calls under the router's timeout (BUDGET
seconds, 30 unless ns sets it; call again while it prints a line starting 'more'). Then, on a Python with shapely,
numpy and ezdxf:
  uv run --no-project --python 3.12 --with shapely --with numpy --with ezdxf --with numba --with scipy \
      python tests/fixtures/hidden-lines/fuzz.py DIR [--faces]
draws and lints every seed and prints a line each and a summary: lint errors, open cuts, edges the meshes see
hidden and any length of line inside a closed cut are failures, measured here from the SVG (inside_cut) and by the
drawing's own check (its report's verify.inside_cut), which should agree; so is a line missing (missing): a stretch
over MISS_PT of a mesh's own edge that the exact query of the nearest triangle sees, with no drawn line within lint's
double_pt and a hair of it. With --faces each seed is drawn with "visibility": "faces" (kit.py hidden-lines); the
checker then needs numba and scipy too (--with numba --with scipy).

A seed makes 4 to 10 boxes, some turned, stacked, touching or running into another, up to two cylinders and a
sphere on a 60 m ground; a parallel view seven times in ten, else a perspective from 25 to 50 m away; and four times
in ten a clip plane, level at 0.5 to 4 m or upright through the middle, facing the camera.
"""
import json, math, os, random, sys, time

MISS_PT = 1.0             # a stretch of edge seen and not drawn, longer than this, is a missing line


def scene(rng):
    """(objects [(part, geometry)], view, clip or None) for one seed"""
    import Rhino.Geometry as G
    box = lambda x0, y0, z0, x1, y1, z1: G.Brep.CreateFromBox(G.BoundingBox(G.Point3d(x0, y0, z0), G.Point3d(x1, y1, z1)))
    objs, tops = [], []
    for n in range(rng.randint(4, 10)):
        w, d, h = rng.uniform(1, 8), rng.uniform(1, 8), rng.uniform(1, 9)
        x, y, z = rng.uniform(-10, 10), rng.uniform(-10, 10), 0.0
        kind = rng.random()
        if kind < 0.2 and tops:                          # stacked on an earlier box's top
            bx = rng.choice(tops)
            x, y, z = rng.uniform(bx.Min.X, bx.Max.X - 1), rng.uniform(bx.Min.Y, bx.Max.Y - 1), bx.Max.Z
            w, d, h = min(w, bx.Max.X - x), min(d, bx.Max.Y - y), rng.uniform(1, 4)
        elif kind < 0.35 and tops:                       # touching an earlier box's side
            bx = rng.choice(tops)
            x, y = bx.Max.X, rng.uniform(bx.Min.Y - d / 2, bx.Max.Y - d / 2)
        b = box(x, y, z, x + max(w, 0.5), y + max(d, 0.5), z + h)
        if rng.random() < 0.3 and z == 0:                # turned about its own corner
            b.Rotate(math.radians(rng.uniform(5, 85)), G.Vector3d.ZAxis, G.Point3d(x, y, 0))
        objs.append(('masses', b))
        tops.append(b.GetBoundingBox(True))
    for n in range(rng.randint(0, 2)):
        c = G.Point3d(rng.uniform(-12, 12), rng.uniform(-12, 12), 0)
        objs.append(('masses', G.Cylinder(G.Circle(G.Plane(c, G.Vector3d.ZAxis), rng.uniform(0.5, 3)), rng.uniform(1, 8)).ToBrep(True, True)))
    if rng.random() < 0.5:
        r = rng.uniform(0.8, 3)
        objs.append(('masses', G.Sphere(G.Point3d(rng.uniform(-12, 12), rng.uniform(-12, 12), r), r).ToBrep()))
    objs.append(('ground', G.Brep.CreateFromCornerPoints(G.Point3d(-30, -30, 0), G.Point3d(30, -30, 0), G.Point3d(30, 30, 0),
                                                         G.Point3d(-30, 30, 0), 0.001)))
    if rng.random() < 0.7:
        bearing, elevation = rng.uniform(0, 360), rng.uniform(15, 75)
        view = dict(bearing=bearing, elevation=elevation, target=[0, 0, 2])
        b, e = math.radians(bearing), math.radians(elevation)
        look = [-math.sin(b) * math.cos(e), -math.cos(b) * math.cos(e), -math.sin(e)]
        cam = None
    else:
        a, dist = rng.uniform(0, 2 * math.pi), rng.uniform(25, 50)
        cam = [dist * math.cos(a), dist * math.sin(a), rng.uniform(1.6, 30)]
        view = dict(lens_mm=rng.choice([24, 28, 35, 50]), camera=cam, target=[0, 0, 2], two_point=rng.random() < 0.5)
        n_ = math.dist(cam, [0, 0, 2])
        look = [(0 - cam[0]) / n_, (0 - cam[1]) / n_, (2 - cam[2]) / n_]
    clip = None
    if rng.random() < 0.4:
        if rng.random() < 0.5 and look[2] < -0.2:        # a plan cut, seen from above
            clip = dict(origin=[0, 0, rng.uniform(0.5, 4)], normal=[0, 0, -1])
        else:                                            # upright, through the middle, facing the camera
            h = math.hypot(look[0], look[1]) or 1.0
            clip = dict(origin=[0, 0, 0], normal=[look[0] / h, look[1] / h, 0])
    return objs, view, clip


def build():
    import Rhino
    import Rhino.Geometry as G
    doc = globals()['__rhino_doc__']
    root = os.path.expanduser(globals()['FUZZ_DIR'])
    here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.expanduser(
        globals().get('FIXTURES', '.'))
    kit = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    budget = float(globals().get('BUDGET', 30.0))
    doc.AdjustModelUnitSystem(Rhino.UnitSystem.Meters, False)
    doc.ModelAbsoluteTolerance = 0.001
    t0, done = time.time(), []
    for seed in globals()['SEEDS']:
        folder = os.path.join(root, '%03d' % seed)
        if os.path.isfile(os.path.join(folder, 'scene.json')):
            continue
        if time.time() - t0 > budget:
            return 'more: %d seeds done this call' % len(done)
        s = Rhino.DocObjects.ObjectEnumeratorSettings()
        s.HiddenObjects = True
        for o in list(doc.Objects.GetObjectList(s)):
            if doc.Layers[o.Attributes.LayerIndex].FullPath.startswith('hl::fuzz'):
                doc.Objects.Delete(o, True)
        objs, view, clip = scene(random.Random(seed))
        for part, g in objs:
            path = 'hl::fuzz::%s' % part
            li = doc.Layers.FindByFullPath(path, -1)
            if li < 0:
                parent = doc.Layers.FindByFullPath('hl::fuzz', -1)
                if parent < 0:
                    top = doc.Layers.FindByFullPath('hl', -1)
                    if top < 0:
                        L = Rhino.DocObjects.Layer()
                        L.Name = 'hl'
                        top = doc.Layers.Add(L)
                    L = Rhino.DocObjects.Layer()
                    L.Name = 'fuzz'
                    L.ParentLayerId = doc.Layers[top].Id
                    parent = doc.Layers.Add(L)
                L = Rhino.DocObjects.Layer()
                L.Name = part
                L.ParentLayerId = doc.Layers[parent].Id
                li = doc.Layers.Add(L)
            a = Rhino.DocObjects.ObjectAttributes()
            a.LayerIndex = li
            doc.Objects.AddBrep(g, a)
        os.makedirs(folder, exist_ok=True)
        req = dict(id='fuzz-%03d' % seed, title='hidden-lines fuzz %d' % seed, scale=200, out='.', view=view,
                   frame=dict(w_pt=560, h_pt=400), groups=[
                       dict(id='masses', layers=['hl::fuzz::masses'], layer='CUT' if clip else 'DETAIL',
                            **({} if clip else dict(profile_layer='OUTLINE'))),
                       dict(id='ground', layers=['hl::fuzz::ground'], layer='CONTEXT', ground=True, fill='K6')])
        if clip:
            req['clip'] = clip
        with open(os.path.join(folder, 'request.json'), 'w') as fh:
            json.dump(req, fh, indent=1)
        ns = {'__rhino_doc__': doc, '__name__': 'hidden_lines', 'HIDDEN': os.path.join(folder, 'request.json'),
              'RESET': True, 'BUDGET': 1e9}
        exec(open(os.path.join(kit, 'rhino', 'hidden_lines.py')).read(), ns)
        r = ns['main']()
        done.append('%d: %s' % (seed, r[:60]))
    return 'done: %d seeds this call' % len(done)


def inside_cut(svg, inset=0.01):
    """stroked lines but those on CUT and GROUND inside the SVG's closed CUT paths shrunk by inset pt: (length in pt,
    [(layer, pt, a point of it on the page)] longest first). A CUT path's closed parts fill even-odd, as the SVG fills
    them, and are read whole past the frame, whose clip cuts only the lines"""
    import xml.etree.ElementTree as ET
    import shapely
    from archkit import lint
    ns = '{http://www.w3.org/2000/svg}'
    regs = []
    for g in ET.parse(svg).getroot().iter(ns + 'g'):
        if g.get('id') != 'CUT':
            continue
        for el in g.iter(ns + 'path'):
            reg = None
            for pts, closed in lint._path_subpaths(el.get('d', '')):
                if closed and len(pts) > 2:
                    q = shapely.make_valid(shapely.Polygon(pts))
                    reg = q if reg is None else shapely.symmetric_difference(reg, q)
            if reg is not None:
                regs.append(reg)
    zone = shapely.union_all(regs).buffer(-inset)
    pieces = []
    for p in lint.read_svg(svg)['paths']:
        if p.stroke != 'none' and p.layer not in ('CUT', 'GROUND'):
            ins = shapely.MultiLineString([[a, b] for a, b in p.segs]).intersection(zone)
            if ins.length > 0:
                pieces.append((p.layer, ins.length, tuple(shapely.get_coordinates(ins)[0].tolist())))
    pieces.sort(key=lambda x: -x[1])
    return sum(x[1] for x in pieces), pieces


def missing(folder, svg):
    """the meshes' own edges (hiddenlines/idbuf.py, mesh_edges) of the groups that hide and are drawn, sampled every
    STEP_PT inside the frame and seen where the exact query of the nearest triangle (hidden.Tris) and the faces' rules
    see them, against the SVG's stroked lines: (the longest stretch seen with no drawn line within reach, in pt, its
    middle on the page, the total in pt). Reach is lint's double_pt and a hair, since a line that close to a heavier one
    gives way to it; a stretch inside a closed cut (cut regions are opaque) or within near_pt of the frame's edge
    is not counted"""
    import numpy as np
    import shapely
    from hiddenlines import hidden, idbuf
    from archkit import lint
    from archkit.draw import Drawing
    from archkit.project import load
    req = json.loads((folder / 'request.json').read_text())
    tk = load(folder / 'request.json')
    scene, V, F, tri_o = hidden.read_scene(folder)
    k = Drawing(float(req['scale']), units=hidden.UNITS[round(float(scene['unit_mm']), 6)]).k
    W, H = float(req['frame']['w_pt']), float(req['frame']['h_pt'])
    hx, hy = W / 2 / k, H / 2 / k
    v = scene['view']
    f, persp = float(v['true_factor']), v.get('projection') == 'perspective'
    groups = {g['id']: g for g in req['groups']}
    objs = scene['objects']
    hides = np.array([groups[o['group']].get('hides', True) and groups[o['group']].get('layer') != 'TEXTURE' for o in objs] + [False])
    drawn = {o['i'] for o in objs if hides[o['i']] and groups[o['group']].get('draw', True)}
    delta = 3 * scene['bias']
    tris = hidden.Tris(V, F, tri_o, f, (hx, hy), np.zeros(len(objs) + 1, dtype=np.int64), delta, persp)
    allow = hides[tris.o]
    buf, E = hidden.faces_of(scene, V, F, tris, allow, drawn, k, W, H)
    if not len(E['obj']):
        return 0.0, None, 0.0
    S = idbuf.samples(list(np.stack([E['a'], E['b']], 1) * [f, f, 1.0] + [hx, hy, 0.0]), k, W, H)
    X, Y, Z = idbuf.at(S, persp)
    near_pt = float(tk['lint']['near_pt'])
    inside = (X * k > near_pt) & (X * k < W - near_pt) & (Y * k > near_pt) & (Y * k < H - near_pt)
    seen = np.zeros(len(X), dtype=bool)
    seen[inside] = buf.sees(tris.nearest(np.stack([X[inside], Y[inside]], 1), allow), X[inside], Y[inside], Z[inside])
    page = np.stack([X * k, H - Y * k], 1)
    data = lint.read_svg(svg)
    segs = [[a, b] for p in data['paths'] if p.stroke not in (None, 'none') and p.layer not in ('GROUND',) for a, b in p.segs]
    hit = np.zeros(len(X), dtype=bool)
    if segs:
        tree = shapely.STRtree(shapely.linestrings(np.array(segs, dtype=float)))
        q, _ = tree.query(shapely.points(page[seen]), predicate='dwithin', distance=float(tk['lint']['double_pt']) + 0.05)
        hit[np.nonzero(seen)[0][np.unique(q)]] = True
    miss = seen & ~hit
    if miss.any():                                     # a cut region hides what lies in it
        import xml.etree.ElementTree as ET
        regs = []
        for g in ET.parse(svg).getroot().iter('{http://www.w3.org/2000/svg}g'):
            if g.get('id') == 'CUT':
                for el in g.iter('{http://www.w3.org/2000/svg}path'):
                    for pts, closed in lint._path_subpaths(el.get('d', '')):
                        if closed and len(pts) > 2:
                            regs.append(shapely.make_valid(shapely.Polygon(pts)))
        if regs:
            zone = shapely.union_all(regs)
            j = np.nonzero(miss)[0]
            miss[j[shapely.contains_xy(zone, page[j, 0], page[j, 1])]] = False
    li = S['line']
    m = miss.astype(np.int8)
    brk = np.concatenate([[True], li[1:] != li[:-1]])
    st = np.nonzero((m == 1) & (brk | np.concatenate([[True], m[:-1] == 0])))[0]
    en = np.nonzero((m == 1) & (np.concatenate([brk[1:], [True]]) | np.concatenate([m[1:] == 0, [True]])))[0]
    if not len(st):
        return 0.0, None, 0.0
    ln = np.hypot(page[en, 0] - page[st, 0], page[en, 1] - page[st, 1])
    j = int(np.argmax(ln))
    return float(ln[j]), tuple(np.round((page[st[j]] + page[en[j]]) / 2, 2).tolist()), float(ln.sum())


def check(root, faces=False):
    """every seed in root drawn and linted: a line each, and the failures summed"""
    import tempfile, shutil
    from pathlib import Path
    kit = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(kit))
    from hiddenlines import hidden
    from archkit import lint
    from archkit.project import load
    fails, rows = 0, []
    for folder in sorted(p for p in Path(root).iterdir() if (p / 'scene.json').is_file()):
        td = Path(tempfile.mkdtemp(prefix='fuzz-'))
        for f in ('request.json', 'scene.json', 'meshes.bin'):
            shutil.copy(folder / f, td / f)
        req = json.loads((td / 'request.json').read_text())
        if faces:
            req['visibility'] = 'faces'
            (td / 'request.json').write_text(json.dumps(req))
        t0 = time.time()
        try:
            d, rep = hidden.build(td / 'request.json')
        except SystemExit as e:
            rows.append(f'{folder.name}: {e}')
            continue
        d.to_svg(td / 'o.svg', canvas=(560, 400), origin=(0.0, 400))
        d.to_dxf(td / 'o.dxf')
        t = load(td / 'o.svg')
        found = lint.check(lint.read_svg(td / 'o.svg'), t) + lint.check(lint.read_dxf(td / 'o.dxf', None), t)
        errs = [m for lv, _, m, _ in found if lv == 'error']
        warns = sorted(k for lv, k, _, _ in found if lv == 'warning')
        opened = len(rep.get('cuts', {}).get('open', []))
        occl = rep.get('verify', {}).get('occluded', 0)
        inside, pieces = inside_cut(td / 'o.svg')
        own = rep['verify']['inside_cut']
        lost, lost_at, lost_all = missing(td, td / 'o.svg')
        bad = bool(errs) or opened or occl or inside > 0 or own['pieces'] or lost > MISS_PT
        fails += bool(bad)
        why = errs[:2] + [f'{ln:.3f} pt of {lay} inside a cut at ({at[0]:.1f}, {at[1]:.1f})' for lay, ln, at in pieces[:1]]
        if lost > MISS_PT:
            why.append(f'a line missing: {lost:.2f} pt seen and not drawn at {lost_at}')
        if own['pieces']:
            why.append(f'its own check {own["length_pt"]} pt, the longest at {own["longest"]["at_pt"]}')
        kind = ('persp' if 'lens_mm' in req['view'] else 'par') + ('+cut' if req.get('clip') else '')
        rows.append(f'{folder.name} {kind:9s} {rep["counts"]["edges"]:5d} edges {len(errs)} errors {opened} open {occl} hidden '
                    f'{inside:.3f} pt inside cuts ({own["length_pt"]:.3f} by its own check) {lost_all:.1f} pt missing '
                    f'warnings {dict((k, warns.count(k)) for k in set(warns))} '
                    f'{time.time() - t0:.1f} s' + ('  FAIL ' + '; '.join(why) if bad else ''))
        shutil.rmtree(td, ignore_errors=True)
    print('\n'.join(rows))
    print(f'{len(rows)} seeds, {fails} failing')
    return fails


if __name__ == '__main__' and len(sys.argv) > 1:
    sys.exit(1 if check(sys.argv[1], '--faces' in sys.argv) else 0)
