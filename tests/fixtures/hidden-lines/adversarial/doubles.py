"""regression constructions in paper points, converted to metres before export.

The oracles use these coordinates and analytic projection, never a drawn reference.
Equal weights use the earlier group's priority to identify the lesser line.
Equations in reasons use local coordinates before phase, translation and projection;
page applies those transformations to every check.
"""
import copy
import json
import math
from pathlib import Path

import numpy as np

from scenes import PT, curve, mesh, page, scene, sy

CLASSES = ('profiles', 'bases', 'overlaps', 'steps', 'seams', 'creases', 'lines', 'cuts')
RULES = dict(A=dict(simplify_doubles=True), B={})   # B, the doubles kept, is the default; C was taken out at regression
GAP = 0.1 * 72 / 25.4
PAIRS = dict(tt=(0.1, 0.1), th=(0.8, 0.1), hh=(0.8, 0.8))


def construction(name, family, paths, reason, weights=(0.15, 0.1), phase=0,
                 scale=100, perspective=False, translated=False, **kw):
    pt = PT * scale / 100
    shift = np.array([1e6, -1e6, 1e6]) if translated else np.zeros(3)

    def point(p):
        x, z, *y = p
        return (shift + [pt * (x + phase), y[0] if y else 0, pt * (z + phase)]).tolist()

    parts = [curve([point(p) for p in points], group=g) for g, points in paths]
    # the supporting face has no edge inside the 80 by 60 pt frame
    parts.append(mesh([[point((-200, -200, 5)), point((200, -200, 5)), point((0, 200, 5))]], group='back'))
    groups = [dict(id=g, layers=['adv::' + g], layer=layer, weights={c: w for c in CLASSES})
              for g, layer, w in [('h', 'BEYOND', weights[0]), ('l', 'DETAIL', weights[1]), ('back', 'CONTEXT', 0.1)]]
    s = scene('doubles-' + name, family, parts, reason, checkpoint=7, frame=(80, 60),
              groups=groups, view=dict(direction=(0, 1, 0), target=shift.tolist()),
              scale=scale, perspective=perspective, depth=8 if perspective else 1000,
              report_checks=[dict(field='model.off_pt', max=0), dict(field='model.unexplained_pt', max=0)], **kw)
    return s, point


def witness(s, points, group='l', absent=False, c_only=False, tol=0.008, cover=0.99):
    if c_only and tol == 0.008:
        tol = 0.075
    if absent:
        # narrow polygon around the source, excluding neighbouring strokes
        import shapely
        area = shapely.LineString(page(s, points)).buffer(tol, cap_style='flat', join_style='mitre')
        c = dict(kind='clear', area=list(area.exterior.coords), max_pt=0.01, layers=['DETAIL' if group == 'l' else 'BEYOND'])
    else:
        c = dict(kind='line', model=points, tol_pt=tol, cover=cover, layers=['DETAIL' if group == 'l' else 'BEYOND'])
    s.setdefault('c_checks' if c_only else 'checks', []).append(c)


def held_scenes():
    for i, off in enumerate((0.02, 0.04, 0.06, 0.074, 0.076, 0.08, 0.12)):
        for phase in (0, 0.024):
            deg = (0, 1, 8)[i % 3]
            u = np.array([math.cos(math.radians(deg)), math.sin(math.radians(deg))])
            n = np.array([-u[1], u[0]])
            paths = [(g, [(-12 * u + d * n).tolist(), (12 * u + d * n).tolist()]) for g, d in [('h', 0), ('l', off)]]
            s, _ = construction(f'grid-{off:g}-phase{phase:g}', 'held', paths,
                f'Two straight sources are {off:g} pt apart along their common normal; drawing either or both must stay within 0.075 pt of their union.',
                weights=list(PAIRS.values())[i % 3], phase=phase, perspective=i % 2 == 1, translated=i == 6)
            yield s
    for deg in (0.2, 1, 3, 8):
        paths = [(g, [(x, x * math.tan(math.radians(a))) for x in (-15, 15)])
                 for g, a in [('h', -deg), ('l', 0), ('l', deg)]]
        s, _ = construction(f'meeting-{deg:g}', 'held', paths,
            f'Three distinct supporting lines meet exactly at (0,0), with angles {deg:g} degrees; there is no source for a chord between them.',
            phase=0.023, perspective=deg == 3, translated=deg == 8)
        yield s
    for deg in (0, 0.5, 2, 8):
        for end in ('free', 'corner', 'junction'):
            z = lambda x: 0.3 + (x + 12) * math.tan(math.radians(deg))
            lesser = [(-12, z(-12)), (6, z(6))]
            if end == 'corner':
                lesser.append((6, 5))
            paths = [('h', [(-15, 0), (15, 0)]), ('l', lesser)]
            if end == 'junction':
                paths.append(('l', [(0, z(0)), (0, 5)]))
            s, _ = construction(f'part-{deg:g}-{end}', 'held', paths,
                f'The lesser source makes {deg:g} degrees with z=0 and has a {end}; any suppression must shorten its own polyline, with no diagonal connector.',
                weights=(0.8, 0.1), phase=0.019, perspective=end == 'junction')
            yield s
    for short in (0.55, 0.59, 0.61):
        for support in (False, True):
            paths = [('h', [(0, -5), (0, 5)]), ('l', [(-10, 0), (-short, 0)])]
            if support:
                paths.append(('l', [(-short, 0), (0, 0)]))
            s, _ = construction(f'end-{short:g}-support{int(support)}', 'held', paths,
                f'The free end is {short:g} pt short of x=0; ' + ('a hidden exported source supplies the entire possible run-on.' if support else 'no exported source exists beyond it, so only shortening is legal.'), phase=0.021)
            if support:
                s['parts'][2]['hidden'] = True
            yield s
    for power in (2, 3):
        p = [(float(x), 0.8 * (-x / 15) ** power) for x in np.linspace(-15, 0, 121)]
        s, _ = construction(f'converging-curve-{power}', 'held', [('h', [(-18, 0), (3, 0)]), ('l', p)],
            f'The sampled z=0.8(-x/15)^{power} source meets z=0 at x=0; a straight connector would have no model underneath.', phase=0.024)
        yield s


def dropped_scenes():
    for wi, width in enumerate((0.04, 0.12, 0.24, 0.26)):
        for phase in (0, 0.0625, 0.125, 0.1875):
            s, p = construction(f'occluder-{width:g}-phase{phase:g}', 'dropped', [('l', [(-12, 0), (12, 0)])],
                f'The front triangle intersects z=0 in [-{width / 2:g},+{width / 2:g}] pt, by linear interpolation of its two sides; the rear line is hidden there and visible outside.', phase=phase,
                perspective=phase == 0.1875, translated=phase == 0.125, weights=list(PAIRS.values())[wi % 3])
            s['parts'].insert(1, mesh([[p((-width, -8, -1)), p((width, -8, -1)), p((0, 8, -1))]], group='h'))
            s['parts'].pop()
            lo, hi = page(s, [p((-width * 0.4, 0)), p((width * 0.4, 0))])
            s['checks'].append(dict(kind='clear', box=[lo[0], lo[1] - 0.001, hi[0], hi[1] + 0.001], layers=['DETAIL'], max_pt=0.002))
            witness(s, [p((-11, 0)), p((-4, 0))])
            witness(s, [p((4, 0)), p((11, 0))])
            s['allowed_reasons'] = ['behind a face', 'a sliver: seen for under near_pt', 'an end cut back clear of a line beside it']
            yield s
    for length in (0.08, 0.19, 0.21, 0.61):
        s, p = construction(f'stray-{length:g}', 'dropped', [('l', [(-length / 2, 0), (length / 2, 0)])],
            f'One isolated segment is {length:g} pt long, ' + ('below the 0.2 pt stray floor and must be named a stray.' if length < 0.2 else 'above the 0.2 pt stray floor and must be drawn.'), phase=0.024)
        s['parts'].pop()
        witness(s, [p((-length / 2, 0)), p((length / 2, 0))], absent=length < 0.2)
        if length < 0.2:
            s['report_checks'].append(dict(field='model.dropped.a stray', min=round(length, 1), max=round(length, 1)))
            s['allowed_reasons'] = ['a stray']
        yield s
    for width in (0.19, 0.59, 0.61, 0.9):
        s, p = construction(f'sliver-{width:g}', 'dropped', [('l', [(-12, 0), (12, 0)])],
            f'Two front half-planes leave exactly {width:g} pt of the rear line visible; ' + ('it may go only as a named sliver under near_pt=0.6.' if width < 0.6 else 'the central visible stretch exceeds near_pt=0.6 and must stay.'), phase=0.017)
        for a, b in ((-20, -width / 2), (width / 2, 20)):
            s['parts'].insert(-1, mesh(sy.quad(p((a, -20, -1)), p((b, -20, -1)), p((b, 20, -1)), p((a, 20, -1))), group='h'))
        witness(s, [p((-width * 0.4, 0)), p((width * 0.4, 0))], absent=width < 0.6)
        s['allowed_reasons'] = ['behind a face', 'a sliver: seen for under near_pt', 'a stray', 'hair taken whole', 'an end cut back clear of a line beside it']
        if width < 0.6:
            s['report_checks'].append(dict(field='model.dropped.a sliver: seen for under near_pt', min=0.1 if width > 0.5 else 0))
        yield s
    for side in (-1, 1):
        s, p = construction(f'frame-edge-{side}', 'dropped', [('l', [(side * 45, 0), (side * 25, 0)])],
            'Clipping a segment spanning |x|=25..45 to the 80 pt frame leaves exactly 15 pt, from |x|=25 to 40.', phase=0)
        witness(s, [p((side * 39.9, 0)), p((side * 25.1, 0))])
        s['allowed_reasons'] = []
        yield s
    for edge in (False, True):
        s, p = construction(f'cut-{"edge" if edge else "inside"}', 'dropped', [('l', [(-4, 5 if edge else 0), (4, 5 if edge else 0)]), ('l', [(8, 0), (15, 0)])],
            'The solid section is the square [-5,5]^2; the first curve is ' + ('exactly on its top edge and may coincide with its outline.' if edge else 'strictly inside the opaque section and must be under poche.') + ' The separate x=8..15 witness is outside it and visible.')
        s['clip'] = dict(origin=(0, 0, 0), normal=(0, 1, 0))
        s['parts'].insert(0, mesh(sy.box(-5 * PT, -1, -5 * PT, 5 * PT, 1, 5 * PT), solid=True, group='h'))
        witness(s, [p((8.2, 0)), p((14.8, 0))])
        if not edge:
            witness(s, [p((-3.8, 0)), p((3.8, 0))], absent=True)
            s['report_checks'].append(dict(field='model.dropped.under poche', min=7.5))
        yield s
    for side in (-1, 0, 1):
        y = side * 0.01
        s, p = construction(f'clip-plane-{side}', 'dropped', [('l', [(-10, 0, y), (10, 0, y)])],
            f'The curve is at y={y:g} m and clipping keeps y>=0; it ' + ('is entirely removed.' if side < 0 else 'lies in the kept closed half-space and is visible.'))
        s['clip'] = dict(origin=(0, 0, 0), normal=(0, 1, 0))
        s['clip_curves'] = True
        if side < 0:
            s['error_ok'] = True
        witness(s, [p((-9, 0, y)), p((9, 0, y))], absent=side < 0)
        yield s
    s, p = construction('visible-control', 'dropped', [('h', [(-12, -4), (12, -4)]), ('l', [(-12, 4), (12, 4)])],
        'Two 24 pt segments are 8 pt apart, face the camera and have nothing in front, so both must be drawn in full.', translated=True, perspective=True)
    for g, z in [('h', -4), ('l', 4)]:
        witness(s, [p((-11.9, z)), p((11.9, z))], group=g)
    s['allowed_reasons'] = []
    yield s


def rectangle(x, z):
    return [(-x, -z), (x, -z), (x, z), (-x, z), (-x, -z)]


def doubles_scenes():
    for pair, weights in PAIRS.items():
        threshold = GAP + sum(weights) / 2
        for kind in ('under', 'over', 'partial'):
            dx = threshold + (0.006 if kind == 'over' else -0.006)
            dz = threshold + (0.03 if kind == 'partial' else 0.006 if kind == 'over' else -0.006)
            inner = rectangle(12 - dx, 6 - dz)
            s, p = construction(f'frame-{pair}-{kind}', 'doubles-C', [('h', rectangle(12, 6)), ('l', inner)],
                f'The centre offsets are ({dx:.9f},{dz:.9f}) pt; subtracting half the weights ({sum(weights) / 2:g} pt) gives the white gaps. C must ' + ('remove the entire inner loop.' if kind == 'under' else 'keep the entire inner loop because at least one side exceeds 0.1 mm.'), weights=weights,
                phase=0.024, translated=pair == 'hh')
            for a, b in zip(inner, inner[1:]):
                a, b = np.array(a), np.array(b)
                witness(s, [p(a * 0.95 + b * 0.05), p(a * 0.05 + b * 0.95)], absent=kind == 'under', c_only=True)
            yield s
    d = GAP + 0.125
    for mode in ('partial-run', 'endpoint', 'excursion', 'perspective'):
        if mode == 'partial-run':
            lesser = [(-12, d - 0.03), (12, d + 0.03)]
            paths = [('h', [(-15, 0), (15, 0)]), ('l', lesser),
                     ('l', [lesser[0], (-12, 5)]), ('l', [lesser[-1], (12, 5)])]
            why = 'The straight run between its two junctions has endpoint gaps 0.1 mm minus/plus 0.03 pt; its maximum exceeds the gap, so C keeps the whole run.'
        elif mode == 'endpoint':
            lesser = [(-1, d - 0.01), (1, d + 0.001)]
            paths = [('h', [(-2, 0), (2, 0)]), ('l', lesser)]
            why = 'Two segments suffice: the lesser run ends 0.001 pt outside C\'s exact gap, so the whole run must remain even if its last sample is inside.'
        elif mode == 'excursion':
            lesser = [(-5, d - 0.02), (-0.02, d - 0.02), (0, d + 0.02), (0.02, d - 0.02), (5, d - 0.02)]
            paths = [('h', [(-6, 0), (6, 0)]), ('l', lesser)]
            why = 'The 0.04 pt wide excursion has an apex 0.02 pt outside C\'s gap; a maximum over the whole run rejects suppression regardless of sampling phase.'
        else:
            lesser = [(-12, d, -2), (12, d, 2)]
            paths = [('h', [(-15, 0, -2.5), (15, 0, 2.5)]), ('l', lesser)]
            why = f'Pinhole projection multiplies the model gap {d:.9f} pt by 8/(8+y); at y=-2 the white gap exceeds 0.1 mm, so C must keep the whole run.'
        s, p = construction('run-' + mode, 'doubles-C', paths, why, perspective=mode == 'perspective', phase=0.017)
        witness(s, [p(a) for a in lesser], c_only=True)
        yield s
    for count in (2, 3):
        ell = lambda dr: [((12 + dr) * math.cos(t), (0.6 + dr) * math.sin(t), 2 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 129)]
        paths = [('h' if i == 0 else 'l', ell(i * 0.1)) for i in range(count)]
        s, p = construction(f'rims-{count}', 'doubles-C', paths,
            f'The {count} nested near-edge-on rims have corresponding vertices at most 0.2 pt apart, below C\'s 0.408465 pt centre threshold; all lesser loops must go whole.', perspective=count == 3, phase=0.024)
        for _, path in paths[1:]:
            witness(s, [p(q) for q in path], absent=True, c_only=True)
        yield s
    for deg in (0.5, 1, 2, 5, 8):
        lesser = [(-15, 15 * math.tan(math.radians(deg))), (0, 0)]
        s, p = construction(f'converge-{deg:g}', 'doubles-C', [('h', [(-18, 0), (3, 0)]), ('l', lesser)],
            f'Two exact segments meet at (0,0) at {deg:g} degrees; the convergence rule keeps the lesser along its own path to that meeting, not cut short.', phase=0.024, perspective=deg == 5)
        witness(s, [p(lesser[0]), p((0, 0))], c_only=True, tol=0.015, cover=0.98)
        yield s


def smooth_scenes():
    for scale in (20, 100, 500, 2000):
        for shape in ('circle', 'ellipse', 'spline'):
            if shape == 'spline':
                path = [(float(x), 3 * ((x / 12) ** 3 - x / 12)) for x in np.linspace(-12, 12, 257)]
                equation = 'z=3[(x/12)^3-x/12]'
            else:
                path = [(12 * math.cos(t), (12 if shape == 'circle' else 3) * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 257)]
                equation = 'x=12cos(t), z=' + ('12' if shape == 'circle' else '3') + 'sin(t)'
            for kind in ('alone', 'cross', 'duplicate'):
                size = 100 / (3 * scale)
                scaled = [(x * size, z * size) for x, z in path]
                paths = [('l', scaled)]
                if kind == 'cross':
                    paths.append(('h', [(0, -18 * size), (0, 18 * size)]))
                elif kind == 'duplicate':
                    paths.append(('l', [(x, z + 0.03) for x, z in scaled]))
                s, p = construction(f'smooth-{shape}-{scale}-{kind}', 'smooth', paths,
                    f'The fixed model is the 256-chord polyline of {equation}, scaled by 100/(3*{scale}) on paper at 1:{scale}; its own chords are the oracle.' + (' The second source is translated 0.03 pt, so off_grid_pt is observational here.' if kind == 'duplicate' else ' No duplicate source permits averaging away from it.'),
                    scale=scale, phase=0.023, perspective=scale == 500, translated=scale == 2000,
                    weights=list(PAIRS.values())[(20, 100, 500, 2000).index(scale) % 3])
                s['exact_model_tol'] = 0.075 if kind == 'duplicate' else 0.01
                if kind != 'duplicate':
                    s['report_checks'].append(dict(field='model.off_grid_pt', max=0))
                yield s


def minimal_scenes():
    for kind in ('hair', 'convergence', 'last-stroke', 'loop-spike'):
        d = GAP + 0.125
        if kind == 'hair':
            paths = [('h', [(-2, 0), (2, 0)]), ('l', [(-1, d + 0.01), (1, d + 0.01)])]
            reason = f'The two segments are parallel at {d + 0.01:.9f} pt centres, giving 0.103528 mm white; C must keep the lesser whole.'
        elif kind == 'convergence':
            paths = [('h', [(-3, 0), (1, 0)]), ('l', [(-2, 2 * math.tan(math.radians(8))), (0, 0)])]
            reason = 'Two segments meet at (0,0) at 8 degrees, with 0.281082 pt between their other ends; convergence requires the lesser to run along its source to the meeting.'
        elif kind == 'last-stroke':
            paths = [('l', [(-0.04, 0), (0.04, 0)])]
            reason = 'One 0.08 pt segment is below the 0.2 pt floor and may be removed only with a stray reason and a completed empty drawing or concise rejection.'
        else:
            a = d - 0.02
            inner = [(-10 + a, -6 + a), (10 - a, -6 + a), (10 - a, 6 - a), (0.02, 6 - a),
                     (0, 6 - a - 0.04), (-0.02, 6 - a), (-10 + a, 6 - a), (-10 + a, -6 + a)]
            paths = [('h', rectangle(10, 6)), ('l', inner)]
            reason = 'A closed inner loop has a single 0.04 by 0.04 pt inward excursion; its apex exceeds the whole-loop gap by 0.02 pt, so C must keep every side.'
        s, p = construction('min-' + kind, 'dropped' if kind == 'last-stroke' else 'doubles-C', paths, reason, phase=0.024)
        s['parts'].pop()
        s['minimal_kind'] = kind
        if kind == 'last-stroke':
            witness(s, [p(q) for q in paths[0][1]], absent=True)
            s['error_ok'] = True
        else:
            witness(s, [p(q) for q in paths[1][1]], c_only=True, tol=0.015 if kind == 'convergence' else 0.008, cover=0.98)
        yield s
        if kind != 'last-stroke':
            for remove in (0, 1):
                v = copy.deepcopy(s)
                v.update(name=s['name'] + f'-delete{remove}', checks=[], c_checks=[], minimal_kind=None)
                del v['parts'][remove]
                remaining = paths[1 - remove]
                witness(v, [p(q) for q in remaining[1]], group=remaining[0], cover=0.98)
                v['reason'] = f'Deleting curve {remove} leaves one source with no competitor, which must be drawn along its own polyline.'
                yield v
        else:
            v = copy.deepcopy(s)
            del v['parts'][0]
            v.update(name=s['name'] + '-delete0', checks=[], minimal_kind=None,
                     reason='Deleting the only stroke leaves no visible line in the frame; a concise empty-scene diagnostic is sufficient.')
            yield v
        if kind == 'loop-spike':
            for i in range(len(paths[1][1]) - 1):
                reduced = paths[1][1][:-1].copy()
                del reduced[i]
                reduced.append(reduced[0])
                max_gap = rectangle_gap(reduced, 10, 6)
                v = copy.deepcopy(s)
                v.update(name=s['name'] + f'-vertex{i}', checks=[], c_checks=[], minimal_kind=None,
                         reason=f'Deleting inner vertex {i} gives exact maximum centre gap {max_gap:.9f} pt against the outer rectangle; C must ' + ('keep' if max_gap > d else 'remove') + ' the whole remaining loop.')
                v['parts'][1]['curve'] = [p(q) for q in reduced]
                witness(v, [p(q) for q in reduced], absent=max_gap <= d, c_only=True)
                yield v
    for n in (3, 4, 8, 16, 32, 64, 128):
        ell = lambda dr: [((12 + dr) * math.cos(t), (0.6 + dr) * math.sin(t)) for t in np.linspace(0, 2 * math.pi, n + 1)]
        paths = [('h', ell(0)), ('l', ell(0.1))]
        s, p = construction(f'min-rim-{n}', 'doubles-C', paths,
            f'Two closed {n}-gons sample nested ellipses at corresponding parameters; their corresponding vertices are 0.1 pt apart, and convex interpolation bounds every chord\'s distance by 0.1 pt, under C\'s 0.408465 pt centre gap.', phase=0.024)
        s['parts'].pop()
        witness(s, [p(q) for q in paths[1][1]], absent=True, c_only=True)
        yield s


def rectangle_gap(path, x, z):
    best = 0
    for a, b in zip(path, path[1:]):
        v0 = np.array([x + a[0], x - a[0], z + a[1], z - a[1]])
        dv = np.array([b[0] - a[0], a[0] - b[0], b[1] - a[1], a[1] - b[1]])
        ts = [0, 1] + [(v0[j] - v0[i]) / (dv[i] - dv[j]) for i in range(4) for j in range(i) if dv[i] != dv[j]]
        best = max(best, *(float(min(v0 + t * dv)) for t in ts if 0 <= t <= 1))
    return best


def regression_scenes():
    constructions = list(held_scenes()) + list(dropped_scenes()) + list(doubles_scenes()) + list(smooth_scenes()) + list(minimal_scenes())
    for path in sorted(Path(__file__).parent.glob('reduced-*.json')):
        s = json.loads(path.read_text())
        s['c_checks'], s['checks'] = s['checks'], []
        constructions.append(s)
        for remove in (0, 1):
            v = copy.deepcopy(s)
            del v['parts'][remove]
            remaining = next(p for p in v['parts'] if 'curve' in p)
            v.update(name=s['name'] + f'-delete{remove}', checks=[], c_checks=[], minimal_kind=None,
                     reason=f'Deleting source loop {remove} leaves one loop and no competing curve; it must remain drawn along its source within 0.075 pt.')
            witness(v, remaining['curve'], group=remaining['group'], c_only=True)
            constructions.append(v)
    for s in constructions:
        if s['family'] == 'held':
            s['exact_model_tol'] = 0.075
        for rule, request in RULES.items():
            v = copy.deepcopy(s)
            v.update(name=s['name'] + '-' + rule, rule=rule, request=request)
            v['observations'] = v.pop('c_checks', [])
            yield v
