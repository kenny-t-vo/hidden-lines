"""Geometry-derived adversarial exports; all dimensions are metres unless marked pt."""
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location('synth', Path(__file__).resolve().parent.parent / 'synth.py')
sy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sy)
PT = 25.4 / 72 / 1000 * 100
GROUPS = [dict(id='b', layers=['adv::*'], layer='CUT')]
VIEW = dict(direction=(0, 1, 0), target=(0, 0, 0))


def mesh(tris, solid=False, group='b'):
    return dict(layer='adv::' + group, group=group, solid=solid, tris=tris)


def curve(points, group='b'):
    return dict(layer='adv::' + group, group=group, curve=points)


def scene(name, family, parts, reason, checks=None, **kw):
    return dict(name=name, family=family, parts=parts, reason=reason, checks=checks or [], **kw)


def camera(s, points):
    v = s.get('view', VIEW)
    d = np.array(v['direction'], float)
    d /= np.linalg.norm(d)
    r = np.cross(d, v.get('up', (0, 0, 1)))
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    return (np.array(points, float) - v['target']) @ np.array([r, u, -d]).T - [0, 0, s.get('depth', 1000)]


def page(s, points):
    c = camera(s, points)
    if s.get('perspective'):
        c[:, :2] *= s.get('depth', 1000) / -c[:, 2, None]
    k = 72 / 25.4 * 1000 / s.get('scale', 100)
    w, h = s.get('frame', (200, 120))
    return np.c_[w / 2 + c[:, 0] * k, h / 2 - c[:, 1] * k].tolist()


def line(points, **kw):
    return dict(kind='line', model=points, tol_pt=0.08, cover=0.98, **kw)


def gap(points, **kw):
    return dict(kind='gap', model=points, tol_pt=0.08, max_pt=0.15, **kw)


def area_box(s, a, b):
    p = page(s, [a, b])
    return [min(p[0][0], p[1][0]), min(p[0][1], p[1][1]), max(p[0][0], p[1][0]), max(p[0][1], p[1][1])]


def checks_for(s):
    out = []
    for i, check in enumerate(s['checks']):
        c = dict(check)
        if 'model' in c:
            c['path'] = page(s, c.pop('model'))
        if 'model_box' in c:
            c['box'] = area_box(s, *c.pop('model_box'))
        c.update(note=i + 1)
        out.append(c)
    return out


def split_quad(t):
    a, b, c = t[0]
    _, _, d = t[1]
    return [(a, b, d), (b, c, d)]


def near_scenes():
    for deg in (0.5, 1, 2, 5, 10):
        rise = 4 * math.tan(math.radians(deg))
        for split in (False, True):
            a = mesh(sy.quad((0, 0, -1), (4, 0, -1), (4, 0, 0), (0, 0, 0)))
            q = sy.quad((0, 1, -1), (4, 1, -1), (4, 1, 0), (0, 1, rise))
            b = mesh(split_quad(q) if split else q)
            yield scene(f'plates-{deg:g}-diag{int(split)}', 'near', [a, b],
                        'The front edge is z=0 and the rear edge z=(4-x)tan(angle); they intersect exactly at x=4.',
                        [gap([(0.02, 0, 0), (3.98, 0, 0)]),
                         gap([(0.02, 1, rise * 0.995), (3.98, 1, rise * 0.005)]),
                         dict(kind='notches', box=[0, 0, 200, 120])],
                        view=dict(direction=(0, 1, 0), target=(2, 0, 0)))
    for thick in (0.3, 0.5, 0.59, 0.61, 0.8):
        p = [(0, 0, 0), (2, 0, 0), (2, 0, thick * PT), (0, 0, thick * PT), (0, 0, 0)]
        for split in (False, True):
            parts = [curve(p)] if not split else [curve([a, b]) for a, b in zip(p, p[1:])]
            yield scene(f'shell-{thick:g}-split{int(split)}', 'near', parts,
                        'Opposite long edges are exactly thickness pt apart, their strokes apart: by default both remain.',
                        [dict(kind='lines', n=2, model=[(0.2, 0, thick * PT / 2), (1.8, 0, thick * PT / 2)], tol_pt=0.9),
                         dict(kind='notches', box=[0, 0, 200, 120])],
                        view=dict(direction=(0, 1, 0), target=(1, 0, 0)))
            yield scene(f'shell-{thick:g}-split{int(split)}-simplified', 'near', parts,
                        'Opposite long edges are exactly thickness pt apart; simplified, below 0.6 pt one centreline is sufficient, above it both remain.',
                        [dict(kind='single' if thick < 0.6 else 'lines', n=2,
                              model=[(0.2, 0, thick * PT / 2), (1.8, 0, thick * PT / 2)], tol_pt=0.9),
                         dict(kind='notches', box=[0, 0, 200, 120])],
                        view=dict(direction=(0, 1, 0), target=(1, 0, 0)), request=dict(simplify_doubles=True))
    for count in (1, 2, 3, 6):
        parts, checks = [], []
        for i in range(count):
            x, w, h = i * 0.08, 0.025, 0.4
            lean = h * math.tan(math.radians(i * 0.5))
            ring = [(x, 0), (x + w, 0), (x + w + lean, h), (x + lean, h)]
            parts.append(mesh(sy.prism(ring, 0, 0.15), True))
            checks += [gap([(x + lean + 0.003, 0, h), (x + w + lean - 0.003, 0, h)])]
        yield scene(f'books-{count}', 'near', parts,
                    'Each book is a closed parallelogram; its 0.709 pt top is longer than the 0.2 pt stray floor and must join both sides.',
                    checks + [dict(kind='notches', box=[0, 0, 200, 120])],
                    view=dict(direction=(0, 1, 0), target=(0.2, 0, 0.2)))
    for count in (1, 3, 5):
        parts = [curve([(-2, 0, 0), (2, 0, 0)], 'a')]
        checks = []
        for i in range(count):
            deg = 0.5 + i
            z = 4 * math.tan(math.radians(deg))
            p = [(-2, 0, z), (2, 0, 0)]
            parts += [curve(p)]
            checks += [gap(p)]
        yield scene(f'fan-{count}', 'near', parts,
                    'Each ray is a straight segment ending at (2,0,0); its construction contains no kink.', checks,
                    groups=[dict(id='a', layers=['adv::a'], layer='CUT'), dict(id='b', layers=['adv::b'], layer='DETAIL')])
    for off in (0.59, 0.61, 0.8):
        p = [(0, 0, off * PT), (0.2, 0, off * PT), (0.2, 0, (off + 2) * PT), (0, 0, (off + 2) * PT), (0, 0, off * PT)]
        for heavy in (False, True):
            yield scene(f'closed-box-{off:g}-heavy{int(heavy)}', 'near',
                        [curve(p)] + ([curve([(-1, 0, 0), (1, 0, 0)], 'a')] if heavy else []),
                        'The rectangle is closed and 2 pt high; proximity to another line cannot remove its lower side without closing it elsewhere.',
                        [gap(p), dict(kind='notches', box=[0, 0, 200, 120])],
                        groups=[dict(id='a', layers=['adv::a'], layer='CUT'), dict(id='b', layers=['adv::b'], layer='DETAIL')])
    for delta in (0.59, 0.61, 0.8):
        parts, checks = [], []
        for r in (1, 1 + delta * PT):
            p = [(r * math.cos(t), 0, r * math.sin(t)) for t in np.linspace(0, math.pi, 65)]
            p = [(p[0][0], 0, -0.4)] + p + [(p[-1][0], 0, -0.4)]
            parts.append(curve(p))
            if delta > 0.6:
                checks += [gap(p)]
        yield scene(f'arches-{delta:g}', 'near', parts,
                    'Concentric semicircles have constant radial separation delta pt, including their tangent joins to the vertical jambs.',
                    checks + [dict(kind='notches', box=[0, 0, 200, 120])])
    for count in (2, 4):
        parts, checks = [], []
        for i in range(count):
            x = i * 0.08
            p = [(x, 0), (x + 0.03, 0), (x + 0.15, 1), (x + 0.12, 1)]
            parts.append(mesh(sy.prism(p, i * 0.2, i * 0.2 + 0.1), True))
            checks.append(gap([(x + 0.12, i * 0.2, 1), (x + 0.15, i * 0.2, 1)]))
        yield scene(f'fins-{count}', 'near', parts, 'Every fin has an exposed 0.85 pt horizontal cap, separated from the next cap by 2.27 pt.', checks)


def surface_scenes():
    for orient in ('out', 'in', 'same', 'mixed'):
        for rotate in (False, True):
            parts = []
            for j, ring in enumerate(([(0, -1.5), (2.4, -1.5), (2.4, 1.5), (0, 1.5)],
                                      [(0.2, -1.3), (2.2, -1.3), (2.2, 1.3), (0.2, 1.3)])):
                tris = []
                for side, ((x, z), (xx, zz)) in enumerate(zip(ring, ring[1:] + ring[:1])):
                    q = sy.quad((x, -1, z), (x, 1, z), (xx, 1, zz), (xx, -1, zz))
                    flip = (j == 1) if orient == 'out' else (j == 0) if orient == 'in' else False if orient == 'same' else (j == side % 2)
                    if flip:
                        q = [tuple(reversed(t)) for t in q]
                    if rotate:
                        q = [[(-p[2], p[1], p[0]) for p in t] for t in q]
                    tris += q
                parts.append(mesh(tris))
            axis = (lambda x, z: (-z, 0, x)) if rotate else (lambda x, z: (x, 0, z))
            mark = [axis(1, -0.5), axis(1, 0.5)]
            parts.append(curve([(x, 0.5, z) for x, _, z in mark], 'detail'))
            parts.append(mesh(sy.quad((-4, 3, -4), (4, 3, -4), (4, 3, 4), (-4, 3, 4))))
            c = [line(mark, layers=['DETAIL']),
                 dict(kind='drawn', model_box=[axis(0.19, -1.31), axis(2.21, 1.31)], layers=['CUT'], min_pt=100)]
            if orient == 'out':
                c += [dict(kind='regions', model_box=[axis(-0.05, -0.8), axis(0.25, 0.8)], n=1)]
            yield scene(f'skins-{orient}-rot{int(rotate)}', 'surfaces', parts,
                        'Outer 2.4 by 3 m and inner 2 by 2.6 m rectangular skins bound a 0.2 m wall and a room; its centred line and inner boundary must remain. Conflicting normals must leave the room empty or unresolved.',
                        c, clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)),
                        view=dict(direction=(0, 1, 0), target=axis(1.2, 0)),
                        groups=GROUPS + [dict(id='detail', layers=['adv::detail'], layer='DETAIL')],
                        unresolved=(orient in ('same', 'mixed')))
    for n in (1, 2):
        parts = [mesh(sy.quad((-2, -1, z), (2, -1, z), (2, 1, z), (-2, 1, z))) for z in (0, -0.2)[:n]]
        if n == 2:
            parts[1]['tris'] = [tuple(reversed(t)) for t in parts[1]['tris']]
        yield scene(f'slab-{n}-skins', 'surfaces', parts,
                    'The horizontal top cuts to a 4 m line; with the lower skin 0.2 m below, opposite normals bound a slab.',
                    [line([(-1.9, 0, 0), (1.9, 0, 0)], min_w=0.79)] +
                    ([dict(kind='regions', model_box=[(-1.9, 0, -0.15), (1.9, 0, -0.05)], n=1)] if n == 2 else []),
                    clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)))
    parts = [mesh(sy.box(x, -1, -1, x + 0.15, 1, 1), True) for x in (0, 0.4)]
    parts += [curve([(0.27, 0.5, -0.5), (0.27, 0.5, 0.5)], 'detail')]
    yield scene('cavity', 'surfaces', parts, 'Two closed 0.15 m leaves have a 0.25 m empty cavity; its centred witness line is not in either solid.',
                [line([(0.27, 0, -0.4), (0.27, 0, 0.4)], layers=['DETAIL'])],
                clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), groups=GROUPS + [dict(id='detail', layers=['adv::detail'], layer='DETAIL')])
    yield scene('foundation', 'surfaces', [mesh(sy.box(-1, -1, -1, 1, 1, 0), True), mesh(sy.box(-0.15, -1, -0.4, 0.15, 1, 2), True)],
                'The two boxes overlap by 0.4 m, so their exact union is one T-shaped section with no internal horizontal seam.',
                [dict(kind='regions', box=[0, 0, 200, 120], n=1), dict(kind='clear', model_box=[(-0.13, 0, -0.38), (0.13, 0, -0.02)], layers=['CUT'], max_pt=0.05)],
                clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)))
    yield scene('ground-basement', 'surfaces', [mesh(sy.quad((-2, -1, 0), (2, -1, 0), (2, 1, 0), (-2, 1, 0)), group='ground'),
                mesh(sy.box(-0.5, 0.5, -1, 0.5, 0.8, -0.2), True)],
                'An open ground sheet cuts to z=0; the basement behind the section is below that line and therefore behind earth.',
                [line([(-1.9, 0, 0), (1.9, 0, 0)], min_w=0.79), dict(kind='clear', model_box=[(-0.6, 0, -1.1), (0.6, 0, -0.1)], max_pt=0.05)],
                clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), groups=GROUPS + [dict(id='ground', layers=['adv::ground'], layer='CUT', ground=True)])


def visibility_scenes():
    for width in (0.04, 0.12, 0.24):
        for phase in (0, 0.0625, 0.125, 0.1875):
            x0, x1 = phase * PT, (phase + width) * PT
            parts = [mesh(sy.quad((x0, 0, -1), (x1, 0, -1), (x1, 0, 1), (x0, 0, 1))),
                     curve([((x0 + x1) / 2, 1, -0.8), ((x0 + x1) / 2, 1, 0.8)], 'detail')]
            yield scene(f'subpixel-{width:g}-phase{phase:g}', 'visibility', parts,
                        'A ray through the mullion midpoint meets its face at y=0 before the witness at y=1, regardless of pixel phase.',
                        [dict(kind='clear', model_box=[(x0 - 0.2 * PT, 0, -0.7), (x1 + 0.2 * PT, 0, 0.7)], layers=['DETAIL'], max_pt=0.05)],
                        groups=GROUPS + [dict(id='detail', layers=['adv::detail'], layer='DETAIL')])
    for angle in (0.01, 0.1, 1):
        w = math.sin(math.radians(angle))
        yield scene(f'grazing-{angle:g}', 'visibility',
                    [mesh(sy.quad((-w, 0, -1), (w, 2, -1), (w, 2, 1), (-w, 0, 1))), curve([(0, 3, -0.8), (0, 3, 0.8)], 'detail')],
                    'At x=0 the grazing face is at y=1, two metres in front of the witness; exact ray intersection hides the witness.',
                    [dict(kind='clear', model_box=[(-0.1 * PT, 0, -0.7), (0.1 * PT, 0, 0.7)], layers=['DETAIL'], max_pt=0.05)],
                    groups=GROUPS + [dict(id='detail', layers=['adv::detail'], layer='DETAIL')])
    q = sy.quad((-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1))
    for reverse in (False, True):
        yield scene(f'coincident-{int(reverse)}', 'visibility', [mesh(q), mesh([tuple(reversed(t)) for t in q] if reverse else q)],
                    'Both quads occupy the same square, so the exposed top is a single line at z=1.',
                    [dict(kind='single', model=[(-0.8, 0, 1), (0.8, 0, 1)], tol_pt=0.3)])
    for off in (0.05, 0.1, 0.3, 1):
        # a cylinder rotated onto the x axis, with a front-facing longitudinal curve
        t = sy.cylinder(0, 0, -1, 1, 1, 64)
        t = [[(p[2], p[1], p[0]) for p in tri] for tri in t]
        for sign in (-1, 1):
            y = -1 - sign * off * PT
            c = [(x, y, 0) for x in np.linspace(-0.8, 0.8, 9)]
            check = line(c, layers=['DETAIL']) if sign == 1 or off <= 0.1 else dict(kind='clear', model_box=[(-0.7, 0, -0.01), (0.7, 0, 0.01)], layers=['DETAIL'], max_pt=0.05)
            yield scene(f'host-{off:g}-side{sign}', 'visibility', [mesh(t, True), curve(c, 'detail')],
                        'The host front is y=-1 at z=0. Positive side offsets lie in front; negative offsets beyond the documented 0.1 pt surface tolerance lie inside.',
                        [check], groups=GROUPS + [dict(id='detail', layers=['adv::detail'], layer='DETAIL')])
    yield scene('cap-ring-mismatch', 'visibility', [mesh(sy.box(-1, -1, -1, 1, 1, 1), True)],
                'The true clipped box spans x=-1..1; shrinking only its supplied ring to +/-0.5 contradicts that mesh and must be reported.',
                [line([(-0.9, 0, 1), (0.9, 0, 1)], min_w=0.79)],
                clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), mutation='ring', mismatch=True)


def opening_scenes():
    for angle in (0, 15, -15, 45):
        for persp in (False, True):
            tris = sy.wall_with_door(-2, 0, 0, 0.3, -1.5, 1.5, -1.4, -0.6, 0.6)
            tris += sy.wall_with_opening(0, 2, 0, 0.3, -1.5, 1.5, 0.5, 1.5, -0.5, 0.6)
            p = [(-1.4, 0, -1.4), (-1.4, 0, 0.6), (-0.6, 0, 0.6), (-0.6, 0, -1.4)]
            w = [(0.5, 0, -0.5), (1.5, 0, -0.5), (1.5, 0, 0.6), (0.5, 0, 0.6), (0.5, 0, -0.5)]
            checks = [line([a, b], min_w=0.249, max_w=0.251) for path in (p, w) for a, b in zip(path, path[1:])]
            yield scene(f'openings-{angle}-persp{int(persp)}', 'openings', [mesh(tris, True)],
                        'The near face at y=0 is a rectangle minus the specified door and window; every near rim is its 0.25 pt profile.', checks,
                        view=dict(direction=(math.tan(math.radians(angle)), 1, -0.15 if angle else 0), target=(0, 0, 0)),
                        perspective=persp, depth=8 if persp else 1000)
    for depth in (0.02, 0.2):
        t = sy.wall_with_opening(-2, 2, 0, 0.3, -1.5, 1.5, -0.6, 0.6, -0.5, 0.5)
        t += sy.quad((-0.6, depth, -0.5), (0.6, depth, -0.5), (0.6, depth, 0.5), (-0.6, depth, 0.5))
        yield scene(f'recess-{depth:g}', 'openings', [mesh(t)],
                    'The recess has a back face before the rear plane y=0.3, so it is not an opening through the wall; the rim is a crease.',
                    [line([(-0.6, 0, -0.4), (-0.6, 0, 0.4)], min_w=0.099, max_w=0.101)])


def robustness_scenes():
    yield scene('empty', 'robustness', [], 'No geometry projects to any stroke; an empty drawing or a clear rejection is acceptable.', [dict(kind='clear', box=[0, 0, 200, 120], max_pt=0)], error_ok=True)
    for shift in (0, 1e6):
        for scale in (0.001, 100, 1e9):
            size = scale / 100
            p = [(shift + x * size, shift + y * size, shift + z * size) for x, y, z in ((-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1))]
            yield scene(f'one-offset{shift:g}-scale{scale:g}', 'robustness', [mesh(sy.quad(*p))],
                        'Scaling geometry and drawing denominator by the same factor leaves a 56.69 pt square; translating both target and geometry preserves it.',
                        [line([p[0], p[1]])], view=dict(direction=(0, 1, 0), target=(shift, shift, shift)), scale=scale)
    q = sy.quad((-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1))
    for defect in ('zero', 'duplicate', 'winding', 'nonmanifold'):
        tris = q + [((0, 0, 0),) * 3] if defect == 'zero' else q * 2 if defect == 'duplicate' else [q[0], tuple(reversed(q[1]))] if defect == 'winding' else q + [q[0]]
        yield scene(f'mesh-{defect}', 'robustness', [mesh(tris)],
                    'The degenerate or duplicated triangle changes no covered area; a boundary of the original square remains.',
                    [line([(-0.8, 0, -1), (0.8, 0, -1)])])
    for mutation in ('missing-groups', 'missing-frame', 'bad-scale', 'bad-view', 'bad-visibility', 'short-bin'):
        yield scene(mutation, 'robustness', [],
                    'The malformed input has no drawable geometry; rejection must be a concise diagnostic without a Python traceback.',
                    [dict(kind='clear', box=[0, 0, 200, 120], max_pt=0)], mutation=mutation, error_ok=True)


def performance_scenes():
    for n in (100000, 1000000):
        yield scene(f'triangles-{n}', 'performance', [],
                    'A regular triangulation tiles exactly one rectangle; internal diagonals are coplanar and only its perimeter should remain.',
                    [line([(-0.9, 0, -0.7), (0.9, 0, -0.7)])], perf=('triangles', n))
    yield scene('objects-10000', 'performance', [],
                'Ten thousand edge-touching coplanar unit cells tile one rectangle; their shared edges are internal, not extra silhouettes.',
                [line([(-0.9, 0, -0.7), (0.9, 0, -0.7)])], perf=('objects', 10000))


def all_scenes():
    scenes = list(near_scenes()) + list(surface_scenes()) + list(visibility_scenes()) + list(opening_scenes()) + list(robustness_scenes()) + list(performance_scenes()) + list(reduced_scenes())
    scenes += list(reduction_controls(scenes))
    for s in scenes:
        if s['parts'] and all('curve' in p for p in s['parts']):
            s['parts'].append(mesh(sy.quad((-4, 5, -4), (4, 5, -4), (4, 5, 4), (-4, 5, 4))))
    # translation and phase are independent of topology
    base = next(s for s in scenes if s['name'] == 'plates-1-diag0')
    import copy
    for offset, phase, persp in ((1e6, 0, False), (0, 0.125, False), (0, 0, True)):
        s = copy.deepcopy(base)
        s['name'] = f'plates-1-offset{offset:g}-phase{phase:g}-persp{int(persp)}'
        for p in s['parts']:
            p['tris'] = (np.array(p['tris']) + [offset + phase * PT, offset, offset]).tolist()
        s['view']['target'] = (np.array(s['view']['target']) + [offset, offset, offset]).tolist()
        for c in s['checks']:
            if 'model' in c:
                c['model'] = (np.array(c['model']) + [offset + phase * PT, offset, offset]).tolist()
        s.update(perspective=persp, depth=8 if persp else 1000)
        scenes.append(s)
    from doubles import regression_scenes
    return scenes + list(regression_scenes())


def write_performance(folder, s, data):
    kind, count = s['perf']
    nx, ny = (250, count // 500) if kind == 'triangles' else (100, 100)
    if kind == 'triangles':
        x, z = np.meshgrid(np.linspace(-1, 1, nx + 1), np.linspace(-0.7, 0.7, ny + 1))
        V = np.c_[x.ravel(), z.ravel(), np.zeros(x.size)]
        a = (np.arange(ny)[:, None] * (nx + 1) + np.arange(nx)).ravel()
        F = np.concatenate([np.c_[a, a + 1, a + nx + 2], np.c_[a, a + nx + 2, a + nx + 1]])
        objects = [dict(i=0, ids=['grid'], group='b', layer='adv::b', kind='mesh', solid=False, user={}, issues=[], parts=1)]
        items = [dict(o=0, v0=0, nv=len(V), f0=0, nf=len(F))]
    else:
        x, z = np.meshgrid(np.linspace(-1, 1, nx, endpoint=False), np.linspace(-0.7, 0.7, ny, endpoint=False))
        corners = np.array([[0, 0], [2 / nx, 0], [2 / nx, 1.4 / ny], [0, 1.4 / ny]])
        C = np.c_[x.ravel(), z.ravel()][:, None, :] + corners
        V = np.c_[C.reshape(-1, 2), np.zeros(count * 4)]
        F = np.tile([[0, 1, 2], [0, 2, 3]], (count, 1))
        objects = [dict(i=i, ids=[f'cell-{i}'], group='b', layer='adv::b', kind='mesh', solid=False, user={}, issues=[], parts=1) for i in range(count)]
        items = [dict(o=i, v0=4 * i, nv=4, f0=2 * i, nf=2) for i in range(count)]
    data['objects'] = objects
    data['meshes'].update(vertices=len(V), triangles=len(F), items=items)
    (folder / 'meshes.bin').write_bytes(V.astype('<f4').tobytes() + F.astype('<i4').tobytes())


def write(folder, s):
    folder = Path(folder)
    sy.write(folder, s['parts'], s.get('view', VIEW), s.get('groups', GROUPS), clip=s.get('clip'),
             scale=s.get('scale', 100), frame=s.get('frame', (200, 120)))
    data = json.loads((folder / 'scene.json').read_text())
    req = json.loads((folder / 'request.json').read_text())
    if s.get('clip_curves'):
        origin, normal = np.array(s['clip']['origin']), np.array(s['clip']['normal'])
        kept = []
        for seg in data['segments']:
            part = s['parts'][seg['o']]
            if 'curve' not in part:
                kept.append(seg)
                continue
            for a, b in zip(part['curve'], part['curve'][1:]):
                a, b = np.array(a), np.array(b)
                sa, sb = (a - origin) @ normal, (b - origin) @ normal
                if max(sa, sb) < 0:
                    continue
                if min(sa, sb) < 0:
                    q = a + (b - a) * sa / (sa - sb)
                    a, b = (a, q) if sa >= 0 else (q, b)
                kept.append(dict(seg, pts=camera(s, [a, b]).tolist()))
        data['segments'] = kept
    req['id'] = s['name']
    req.update(s.get('request', {}))
    for seg in data['segments']:
        if s['parts'][seg['o']].get('hidden'):
            seg['vis'] = 'under'
    if s.get('perf'):
        write_performance(folder, s, data)
    if s.get('perspective'):
        depth = s.get('depth', 8)
        data['view'].update(projection='perspective', focal=depth, near=0.01, shift=0)
        data['view']['xform'][2][3] += 1000 - depth
        data['meshes']['origin'][2] = -depth
        for seg in data['segments']:
            for p in seg['pts']:
                p[2] += 1000 - depth
                p[:2] = [q * depth / -p[2] for q in p[:2]]
        for ring in data['rings']:
            for p in ring['pts']:
                p[2] += 1000 - depth
                p[:2] = [q * depth / -p[2] for q in p[:2]]
        raw = (folder / 'meshes.bin').read_bytes()
        nv = data['meshes']['vertices']
        V = np.frombuffer(raw, dtype='<f4', count=nv * 3).reshape(-1, 3).copy()
        V[:, :2] *= depth / (depth - V[:, 2, None])
        (folder / 'meshes.bin').write_bytes(V.tobytes() + raw[nv * 12:])
        req['view'].update(lens_mm=50)
    mutation = s.get('mutation')
    if mutation == 'ring':
        for ring in data['rings']:
            for p in ring['pts']:
                p[0] *= 0.5
    elif mutation == 'missing-groups':
        del req['groups']
    elif mutation == 'missing-frame':
        del req['frame']
    elif mutation == 'bad-scale':
        req['scale'] = 'wrong'
    elif mutation == 'bad-view':
        req['view'] = []
    elif mutation == 'bad-visibility':
        req['visibility'] = 'wrong'
    elif mutation == 'short-bin':
        data['meshes'].update(vertices=1, triangles=0)
    (folder / 'scene.json').write_text(json.dumps(data))
    (folder / 'request.json').write_text(json.dumps(req, indent=2))
    (folder / 'checks.json').write_text(json.dumps(dict(checks=checks_for(s)), indent=2))
    (folder / 'expected.txt').write_text(s['reason'] + '\n')
    if s.get('checkpoint') == 7:
        assertions = list(s.get('report_checks', []))
        if 'allowed_reasons' in s:
            assertions.append(dict(field='model.dropped', allowed=s['allowed_reasons']))
        (folder / 'report-checks.json').write_text(json.dumps(assertions, indent=2))
        (folder / 'observations.json').write_text(json.dumps(checks_for(dict(s, checks=s.get('observations', []))), indent=2))


def reduced_scenes():
    backdrop = mesh([[(-5, 5, -5), (5, 5, -5), (0, 5, 5)]])
    for chords in (1, 2, 4, 8, 16):
        paths = [[(r * math.cos(t), 0, r * math.sin(t))
                  for t in np.arange(32, 33 + chords) * math.pi / 64]
                 for r in (1, 1 + 0.61 * PT)]
        yield scene(f'min-arc-{chords}-chords', 'near', [curve(p) for p in paths] + [backdrop],
                    'These are retained chords of the concentric-arch construction; parallel corresponding chords are 0.61 cos(pi/128)=0.609816 pt apart, above the merge threshold.',
                    [gap(p) for p in paths])
    for off in (0.59, 0.61):
        for deg in (0, 15, 30, 45):
            for length in (1.9, 2.1, 10):
                u = np.array([math.cos(math.radians(deg)), math.sin(math.radians(deg))])
                n = np.array([-u[1], u[0]])
                to3 = lambda p: (float(p[0]), 0, float(p[1]))
                a, b = -u * length * PT / 2, u * length * PT / 2
                paths = [[to3(a + n * offset * PT), to3(b + n * offset * PT)] for offset in (0, off)]
                middle = [to3(a * 0.8 + n * off * PT / 2), to3(b * 0.8 + n * off * PT / 2)]
                yield scene(f'min-pair-{off:g}-deg{deg}-len{length:g}', 'near',
                            [curve(paths[0]), curve(paths[1]), backdrop],
                            'Two straight parallel segments are exactly offset pt apart by their common normal, their strokes apart: by default both remain.',
                            [dict(kind='lines', n=2, model=middle, tol_pt=0.9)])
                yield scene(f'min-pair-{off:g}-deg{deg}-len{length:g}-simplified', 'near',
                            [curve(paths[0]), curve(paths[1]), backdrop],
                            'Two straight parallel segments are exactly offset pt apart by their common normal; simplified, the 0.6 pt rule requires one below and two above that distance.',
                            [dict(kind='single' if off < 0.6 else 'lines', n=2, model=middle, tol_pt=0.9)], request=dict(simplify_doubles=True))
    for width in (0.04, 0.12, 0.24):
        for phase in (0, 0.0625, 0.125, 0.1875):
            x0, x1 = phase * PT, (phase + width) * PT
            # one triangle is sufficient to cover the probe at z=0
            triangle = [(x0 - width * PT, 0, -1), (x1 + width * PT, 0, -1), ((x0 + x1) / 2, 0, 1)]
            # its horizontal section has width 1.5 times the input width
            lo, hi = (1.5 * x0 + 0.5 * x1) / 2, (0.5 * x0 + 1.5 * x1) / 2
            rear = mesh([[(-1, 1, 0), (1, 1, 0), (0, 1, -1)]], group='detail')
            yield scene(f'min-crossing-{width:g}-phase{phase:g}', 'visibility', [mesh([triangle]), rear],
                        'At z=0 barycentric interpolation gives a triangle interval wider than [lo,hi]; the rear horizontal line must have no ink in that interior interval.',
                        [dict(kind='clear', model_box=[(lo, 0, -0.001), (hi, 0, 0.001)], layers=['DETAIL'], max_pt=0.002),
                         line([(-0.8, 1, 0), (-0.2, 1, 0)], layers=['DETAIL'])],
                        groups=GROUPS + [dict(id='detail', layers=['adv::detail'], layer='DETAIL')])
    for fixed in (False, True):
        inner = [(-1, -1), (1, -1), (0, 1)]
        outer = [(x * 1.4, z * 1.4) for x, z in inner]
        parts = []
        for j, ring in enumerate((outer, inner)):
            ts = []
            for a, b in zip(ring, ring[1:] + ring[:1]):
                m = (np.array(a) + b) / 2
                p, q = 2 * np.array(a) - m, 2 * np.array(b) - m
                t = [(float(p[0]), -1, float(p[1])), (float(m[0]), 1, float(m[1])), (float(q[0]), -1, float(q[1]))]
                if j and fixed:
                    t = t[::-1]
                ts.append(t)
            parts.append(mesh(ts))
        parts += [backdrop]
        yield scene(f'min-room-fixed{int(fixed)}', 'surfaces', parts,
                    'At y=0 the six triangle intersections are two nested triangular rings; the inner triangle is the room and its rim must survive even when its normals are ambiguous.',
                    [gap([(x, 0, z) for x, z in inner + inner[:1]])],
                    groups=GROUPS + [dict(id='detail', layers=['adv::detail'], layer='DETAIL')],
                    clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)))
    yield scene('min-edge-on', 'robustness', [mesh([[(-1, -1, 0), (1, -1, 0), (0, 1, 0)]])],
                'A single nondegenerate triangle projects edge-on to the segment x=-1..1 at z=0; a line or clear diagnostic is required.',
                [line([(-0.4, 0, 0), (0.4, 0, 0)])], error_ok=True)
    vertices = np.array([(-1, -1, -1), (1, -1, -1), (0, 1, -1), (0, 0, 1)], float)
    tetra = []
    for ids in ((0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0)):
        tri = vertices[list(ids)]
        if np.dot(np.cross(tri[1] - tri[0], tri[2] - tri[0]), tri.mean(0) - vertices.mean(0)) < 0:
            tri = tri[::-1]
        tetra.append(tri.tolist())
    for mismatch in (False, True):
        yield scene(f'min-cap-mismatch{int(mismatch)}', 'visibility', [mesh(tetra, True)],
                    'The tetrahedron section at y=0 has base x=-0.5..0.5, z=-1 and tip (0,0,1); its supplied ring may not silently replace that section with a narrower triangle.',
                    [line([(-0.45, 0, -1), (0.45, 0, -1)], min_w=0.79)],
                    clip=dict(origin=(0, 0, 0), normal=(0, 1, 0)), mutation='ring' if mismatch else None, mismatch=mismatch)
    outer = [(-2, -1.5), (2, -1.5), (0, 2)]
    inner = [(-0.5, -0.5), (0.5, -0.5), (0, 0.5)]
    front, sides = [], []
    for i in range(3):
        a, b = outer[i], outer[(i + 1) % 3]
        aa, bb = inner[i], inner[(i + 1) % 3]
        P = lambda p, y=0: (p[0], y, p[1])
        front += sy.quad(P(a), P(b), P(bb), P(aa))
        sides += sy.quad(P(aa), P(bb), P(bb, 0.02), P(aa, 0.02))
    for blind in (False, True):
        tris = front + sides + ([[(x, 0.02, z) for x, z in inner]] if blind else [])
        yield scene(f'min-recess-blind{int(blind)}', 'openings', [mesh(tris)],
                    'Six coplanar front triangles surround a triangular rim; connected reveals lead 0.02 m to a closed back in the blind case, and to a through-opening otherwise.',
                    [line([(-0.4, 0, -0.5), (0.4, 0, -0.5)], min_w=0.099 if blind else 0.249, max_w=0.101 if blind else 0.251)])


def reduction_controls(scenes):
    import copy
    for source, name, parts, checks, reason in (
        ('min-pair-0.59-deg0-len1.9', 'control-pair-one-line', (0, 2),
         [dict(kind='single', model=[(-0.7 * PT, 0, 0), (0.7 * PT, 0, 0)], tol_pt=0.9)],
         'Deleting either parallel line leaves exactly one line.'),
        ('min-crossing-0.04-phase0', 'control-crossing-one-triangle', (1,),
         [line([(-0.8, 1, 0), (0.8, 1, 0)], layers=['DETAIL'])],
         'Removing the front triangle exposes the entire rear top edge.'),
        ('min-room-fixed0', 'control-room-one-skin', (0, 2),
         [dict(kind='regions', box=[0, 0, 200, 120], n=1)],
         'Removing the inner skin leaves a single outward-facing triangular shell; the surface-cut rule assigns its whole interior to solid.'),
        ('min-edge-on', 'control-edge-on-empty', (),
         [dict(kind='clear', box=[0, 0, 200, 120], max_pt=0)],
         'Removing the only triangle leaves an empty input, for which a concise rejection is sufficient.'),
    ):
        s = copy.deepcopy(next(s for s in scenes if s['name'] == source))
        s.update(name=name, parts=[s['parts'][i] for i in parts], checks=checks, reason=reason)
        yield s
    s = copy.deepcopy(next(s for s in scenes if s['name'] == 'min-arc-1-chords'))
    s.update(name='control-arc-one-line', parts=[s['parts'][0], s['parts'][2]], checks=s['checks'][:1],
             reason='Deleting the outer chord leaves the inner chord whole; there is no near pair to simplify.')
    yield s
