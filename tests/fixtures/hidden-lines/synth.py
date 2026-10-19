"""Scenes for kit.py hidden-lines written without Rhino, as rhino/hidden_lines.py would export them, for tests whose
expected drawing is worked out by hand from the model.

  write(folder, parts, view, groups, clip=None, scale=50, frame=(400, 300), request=None)

parts are [dict(layer, group, tris, solid)] in model metres, tris n x 3 x 3 wound anticlockwise seen from outside, or
[dict(layer, group, curve)] for a polyline. The view is parallel: dict(direction, up, target). The export written is
version 4: its segments are each part's own edges (a boundary, or a crease over 20 degrees) and its curves, all
visible, so only visibility "faces" decides what is seen; with a clip plane (origin, normal: the half the normal points
into is kept), each part's section is a cut segment, a solid's also a ring, and the meshes are clipped to the half
kept. Models in metres, drawn at 1:scale.
"""
import json, math
from pathlib import Path

import numpy as np

DEPTH = 1000.0                                         # the target's depth from the camera


def quad(a, b, c, d):
    """a quadrilateral's two triangles, wound as given"""
    return [(a, b, c), (a, c, d)]


def box(x0, y0, z0, x1, y1, z1):
    """a box's twelve triangles, wound anticlockwise seen from outside"""
    p = lambda i, j, k: ((x0, x1)[i], (y0, y1)[j], (z0, z1)[k])
    return (quad(p(0, 0, 1), p(1, 0, 1), p(1, 1, 1), p(0, 1, 1)) + quad(p(0, 0, 0), p(0, 1, 0), p(1, 1, 0), p(1, 0, 0))
            + quad(p(0, 0, 0), p(1, 0, 0), p(1, 0, 1), p(0, 0, 1)) + quad(p(1, 0, 0), p(1, 1, 0), p(1, 1, 1), p(1, 0, 1))
            + quad(p(1, 1, 0), p(0, 1, 0), p(0, 1, 1), p(1, 1, 1)) + quad(p(0, 1, 0), p(0, 0, 0), p(0, 0, 1), p(0, 1, 1)))


def wall_with_opening(x0, x1, y0, y1, z0, z1, ox0, ox1, oz0, oz1):
    """a wall from x0 to x1, y0 (its face toward -y) to y1, z0 to z1, with a rectangular opening ox0..ox1 by oz0..oz1
    through it: a closed solid, its faces wound anticlockwise seen from outside"""
    t = []
    for y, flip in ((y0, False), (y1, True)):          # the two faces, each a frame of four quadrilaterals round the hole
        P = lambda x, z: (x, y, z)
        rings = [quad(P(x0, z0), P(x1, z0), P(ox1, oz0), P(ox0, oz0)), quad(P(x1, z0), P(x1, z1), P(ox1, oz1), P(ox1, oz0)),
                 quad(P(x1, z1), P(x0, z1), P(ox0, oz1), P(ox1, oz1)), quad(P(x0, z1), P(x0, z0), P(ox0, oz0), P(ox0, oz1))]
        for q in rings:
            t += [tuple(reversed(tr)) for tr in q] if flip else q
    t += quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))          # the outer sides
    t += quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
    t += quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0))
    t += quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))
    t += quad((ox0, y0, oz0), (ox1, y0, oz0), (ox1, y1, oz0), (ox0, y1, oz0))  # the reveals, facing into the opening
    t += quad((ox0, y0, oz1), (ox0, y1, oz1), (ox1, y1, oz1), (ox1, y0, oz1))
    t += quad((ox0, y0, oz0), (ox0, y1, oz0), (ox0, y1, oz1), (ox0, y0, oz1))
    t += quad((ox1, y0, oz0), (ox1, y0, oz1), (ox1, y1, oz1), (ox1, y1, oz0))
    return t


def wall_with_door(x0, x1, y0, y1, z0, z1, ox0, ox1, oz1):
    """a wall as wall_with_opening with a door ox0..ox1 cut from its foot to oz1, its faces meshed without T-junctions"""
    t = []
    for y, flip in ((y0, False), (y1, True)):
        P = lambda x, z: (x, y, z)
        q = (quad(P(x0, z0), P(ox0, z0), P(ox0, oz1), P(x0, oz1)) + quad(P(x0, oz1), P(ox0, oz1), P(ox0, z1), P(x0, z1))
             + quad(P(ox0, oz1), P(ox1, oz1), P(ox1, z1), P(ox0, z1))
             + quad(P(ox1, z0), P(x1, z0), P(x1, oz1), P(ox1, oz1)) + quad(P(ox1, oz1), P(x1, oz1), P(x1, z1), P(ox1, z1)))
        t += [tuple(reversed(tr)) for tr in q] if flip else q
    t += quad((x0, y0, z0), (x0, y1, z0), (ox0, y1, z0), (ox0, y0, z0)) + quad((ox1, y0, z0), (ox1, y1, z0), (x1, y1, z0), (x1, y0, z0))
    t += quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
    t += quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)) + quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))
    t += quad((ox0, y0, oz1), (ox0, y1, oz1), (ox1, y1, oz1), (ox1, y0, oz1))
    t += quad((ox0, y0, z0), (ox0, y1, z0), (ox0, y1, oz1), (ox0, y0, oz1)) + quad((ox1, y0, z0), (ox1, y0, oz1), (ox1, y1, oz1), (ox1, y1, z0))
    return t


def wall_with_pier(x0, x1, y0, y1, z0, z1, px0, px1, pz0, pz1, py):
    """a wall as wall_with_opening with a pier px0..px1 by pz0..pz1 standing out of its face at y0 to py (py < y0),
    one closed solid: its face's loop round the pier's foot is concave, not an opening"""
    t = []
    P = lambda x, z: (x, y0, z)
    t += (quad(P(x0, z0), P(x1, z0), P(px1, pz0), P(px0, pz0)) + quad(P(x1, z0), P(x1, z1), P(px1, pz1), P(px1, pz0))
          + quad(P(x1, z1), P(x0, z1), P(px0, pz1), P(px1, pz1)) + quad(P(x0, z1), P(x0, z0), P(px0, pz0), P(px0, pz1)))
    t += quad((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0))
    t += quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))
    t += quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
    t += quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0))
    t += quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))
    t += quad((px0, py, pz0), (px1, py, pz0), (px1, py, pz1), (px0, py, pz1))         # the pier's face
    t += quad((px0, y0, pz0), (px1, y0, pz0), (px1, py, pz0), (px0, py, pz0))         # its sides, facing out
    t += quad((px0, y0, pz1), (px0, py, pz1), (px1, py, pz1), (px1, y0, pz1))
    t += quad((px0, y0, pz0), (px0, py, pz0), (px0, py, pz1), (px0, y0, pz1))
    t += quad((px1, y0, pz0), (px1, y0, pz1), (px1, py, pz1), (px1, py, pz0))
    return t


def prism(ring, y0, y1):
    """a polygon ring in x-z, its vertices in either order, extruded from y0 to y1: a closed solid's triangles, wound
    anticlockwise seen from outside; its two caps triangulated (shapely's Delaunay, kept inside the polygon)"""
    import shapely
    from shapely.ops import triangulate
    poly = shapely.Polygon(ring)
    if not poly.exterior.is_ccw:                        # anticlockwise in x-z, each side's outward normal on its right
        ring = ring[::-1]
        poly = shapely.Polygon(ring)
    t = []
    for tr in triangulate(poly):
        if not poly.contains(tr.representative_point()):
            continue
        c = list(tr.exterior.coords)[:3]
        a, b, d = [(x, y0, z) for x, z in c]
        tri = (a, b, d) if np.cross(np.subtract(b, a), np.subtract(d, a))[1] < 0 else (a, d, b)
        t += [tri, tuple((p[0], y1, p[2]) for p in reversed(tri))]
    for (x0, z0), (x1, z1) in zip(ring, ring[1:] + ring[:1]):
        t += quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z1), (x1, y0, z1))
    return t


def cylinder(cx, cy, z0, z1, r, n):
    """an upright cylinder of n facets, its two caps fans: a closed solid's triangles, wound anticlockwise seen from
    outside"""
    P = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    t = []
    for (x0, y0), (x1, y1) in zip(P, P[1:] + P[:1]):
        t += quad((x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1))
        t += [((cx, cy, z1), (x0, y0, z1), (x1, y1, z1)), ((cx, cy, z0), (x1, y1, z0), (x0, y0, z0))]
    return t


def xform(view):
    """the model-to-camera transform of a parallel view, 4 x 4: the camera looks down -z, the target at depth -DEPTH"""
    d = np.array(view['direction'], dtype=float)
    d /= np.linalg.norm(d)
    up = np.array(view.get('up', (0, 0, 1)), dtype=float)
    r = np.cross(d, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    R = np.array([r, u, -d])
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = -R @ np.array(view['target'], dtype=float) + [0.0, 0.0, -DEPTH]
    return M


def edges(T):
    """a triangle mesh's own edges, its vertices welded: [(a, b, kind)], kind 'Boundary' or 'Crease' (over 20 degrees)"""
    key = lambda p: tuple(np.round(p, 9))
    by = {}
    for i, t in enumerate(T):
        for j in range(3):
            a, b = key(t[j]), key(t[(j + 1) % 3])
            by.setdefault(tuple(sorted((a, b))), []).append(i)
    nrm = [np.cross(np.subtract(t[1], t[0]), np.subtract(t[2], t[0])) for t in T]
    nrm = [n / np.linalg.norm(n) for n in nrm]
    out = []
    for (a, b), ts in by.items():
        if len(ts) == 1:
            out.append((a, b, 'Boundary'))
        elif len(ts) == 2 and float(nrm[ts[0]] @ nrm[ts[1]]) < math.cos(math.radians(20)):
            out.append((a, b, 'Crease'))
    return out


def clip_tris(T, o, n):
    """triangles clipped to the half of the plane (o, n) that n points into: [triangles], [(a, b)] the section"""
    out, cut = [], []
    for t in T:
        s = [float(np.dot(np.subtract(p, o), n)) for p in t]
        if min(s) >= 0:
            out.append(t)
            continue
        if max(s) <= 0:
            continue
        poly, on = [], []
        for j in range(3):
            p, q, sp, sq = t[j], t[(j + 1) % 3], s[j], s[(j + 1) % 3]
            if sp >= 0:
                poly.append(tuple(p))
            if (sp >= 0) != (sq >= 0):
                x = tuple(np.add(p, np.multiply(np.subtract(q, p), sp / (sp - sq))))
                poly.append(x)
                on.append(x)
        out += [(poly[0], poly[k], poly[k + 1]) for k in range(1, len(poly) - 1)]
        if len(on) == 2:
            cut.append(tuple(on))
    return out, cut


def chain(segs):
    """section segments joined end to end: [[points]], closed rings repeating no point"""
    key = lambda p: tuple(np.round(p, 7))
    left = [list(s) for s in segs]
    out = []
    while left:
        run = left.pop()
        grown = True
        while grown:
            grown = False
            for i, s in enumerate(left):
                if key(s[0]) == key(run[-1]):
                    run.append(s[1])
                elif key(s[1]) == key(run[-1]):
                    run.append(s[0])
                else:
                    continue
                left.pop(i)
                grown = True
                break
        if key(run[0]) == key(run[-1]):
            run = run[:-1]
        out.append(run)
    return out


def write(folder, parts, view, groups, clip=None, scale=50, frame=(400, 300), request=None):
    """the export of parts seen in view into folder: scene.json, meshes.bin and request.json, the request's groups and
    any other request keys given"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    M = xform(view)
    cam = lambda P: (M @ np.c_[np.asarray(P, dtype=float).reshape(-1, 3), np.ones(len(np.asarray(P).reshape(-1, 3)))].T).T[:, :3]
    origin = [0.0, 0.0, -DEPTH]
    objects, segments, rings, items, Vs, Fs = [], [], [], [], [], []
    nv = nf = 0
    for i, p in enumerate(parts):
        objects.append(dict(i=i, ids=[f'synth-{i:04d}'], group=p['group'], layer=p['layer'],
                            kind='curve' if 'curve' in p else 'brep', solid=bool(p.get('solid')), user={}, issues=[], parts=1))
        if 'curve' in p:
            segments.append(dict(o=i, src='curve', sil='MiscellaneousFeature', pass_='main', pts=cam(p['curve']).tolist(),
                                 sides='', scene=False))
            continue
        T = [tuple(map(tuple, t)) for t in p['tris']]
        for a, b, kind in edges(T):
            P = [a, b]
            if clip:
                sa, sb = (float(np.dot(np.subtract(q, clip['origin']), clip['normal'])) for q in (a, b))
                if max(sa, sb) <= 0:
                    continue
                if min(sa, sb) < 0:
                    x = tuple(np.add(a, np.multiply(np.subtract(b, a), sa / (sa - sb))))
                    P = [a, x] if sa > 0 else [x, b]
            segments.append(dict(o=i, src='geom', sil=kind, pass_='main', pts=cam(P).tolist(), sides='', scene=False))
        if clip:
            T, cut = clip_tris(T, clip['origin'], clip['normal'])
            for a, b in cut:
                segments.append(dict(o=i, src='geom', sil='SectionCut', pass_='main', pts=cam([a, b]).tolist(), sides='',
                                     scene=False, cut=0))
            if p.get('solid'):
                rings += [dict(o=i, cut=0, pts=cam(r).tolist()) for r in chain(cut) if len(r) > 2]
        if not T:
            continue
        C = cam(np.array(T).reshape(-1, 3))
        Vs.append(C - origin)
        Fs.append(np.arange(len(C)).reshape(-1, 3))
        items.append(dict(o=i, v0=nv, nv=len(C), f0=nf, nf=len(T)))
        nv += len(C)
        nf += len(T)
    for s in segments:                                 # 'pass' is a keyword in Python only
        s['pass'] = s.pop('pass_')
    d = np.array(view['direction'], dtype=float)
    scene = dict(version=4, request='request.json', model='', units='Meters', unit_mm=1000.0, tolerance=0.001,
                 bias=0.0028, view=dict(xform=M.tolist(), half_w=frame[0] / 2, half_h=frame[1] / 2,
                                        pt_per_unit=72 / 25.4 * 1000 / scale, true_factor=1.0,
                                        direction=(d / np.linalg.norm(d)).tolist(), projection='parallel'),
                 clip=[dict(origin=list(clip['origin']), normal=list(clip['normal']))] if clip else [],
                 objects=objects, rings=rings, contacts=0, segments=segments,
                 meshes=dict(file='meshes.bin', vertices=nv, triangles=nf, items=items, origin=origin), log=[], seconds={})
    V = np.concatenate(Vs) if Vs else np.zeros((0, 3))
    F = np.concatenate(Fs) if Fs else np.zeros((0, 3), dtype=np.int64)
    (folder / 'meshes.bin').write_bytes(V.astype('<f4').tobytes() + F.astype('<i4').tobytes())
    (folder / 'scene.json').write_text(json.dumps(scene), encoding='utf-8')
    req = dict(id=folder.name, title=f'hidden-lines synthetic scene: {folder.name}', scale=scale, out='.',
               view=dict(direction=list(view['direction']), target=list(view['target'])),
               frame=dict(w_pt=frame[0], h_pt=frame[1]), groups=groups, visibility='faces')
    if clip:
        req['clip'] = dict(origin=list(clip['origin']), normal=list(clip['normal']))
    req.update(request or {})
    (folder / 'request.json').write_text(json.dumps(req, indent=1), encoding='utf-8')
    return folder


def page(folder, p):
    """a model point on the page of a scene written here, in points from the top-left, y down"""
    s = json.loads((Path(folder) / 'scene.json').read_text())
    r = json.loads((Path(folder) / 'request.json').read_text())
    c = np.array(s['view']['xform']) @ np.array(list(p) + [1.0])
    k = s['view']['pt_per_unit']
    return (r['frame']['w_pt'] / 2 + c[0] * k, r['frame']['h_pt'] / 2 - c[1] * k)
