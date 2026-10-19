"""What a hidden-line drawing sees, decided from the faces of rhino/hidden_lines.py's meshes through an ID buffer, for
kit.py hidden-lines under a request's "visibility": "faces" (docs/hidden-lines-plan.md, stage 1). hiddenlines/hidden.py
hands it the projected triangles and the lines that may be drawn, and takes back each line's seen stretches.

  raster  the triangles of the groups that hide, those on TEXTURE left out (a roof's tiles do not hide the roof's own
          edges), at R_PX pixels a point over the frame: each pixel centre's nearest triangle. A pixel centre on an edge
          two triangles share goes to one of them. A triangle is turned to the camera if it is wound anticlockwise on
          the page
  probe   a line sampled every STEP_PT on the page, each sample tried against the nearest triangle that covers it: of
          those the 3 x 3 pixels round it hold, or, where one of those would hide it but does not reach it (an edge of
          something in front is near: a face folded over another, a sliver under a pixel wide), of all the triangles
          in its cell of CELL_PX pixels; of two lying level within delta, the one turned to the camera. It is seen if
          none covers it, or if that triangle's plane lies behind it or within delta in front of it along the view, or
          within tol of it measured square to the plane, which keeps a curve drawn on a faceted roof and an edge beside
          a face seen edge-on. tol is a length on the page, so in a perspective it grows with depth. With clip planes
          a closed solid's back face stands for the cut face its clipped mesh lacks, and hides every sample not on a
          clip plane
  ends    where a line turns from seen to hidden, the point found by halving to a thousandth of a step
  edges   each meshed object's own edges, its vertices welded: boundaries, creases (faces turning by more than
          CREASE_DEG), silhouettes (one face turned to the camera, one away) and edges of more than two faces; those on
          a clip plane, or on a perspective's near plane, left out, since the cuts draw them

Coordinates are hidden.py's frame units (the frame's lower left corner at the origin, a point on the page k of them)
with the camera's z for depth, nearer larger; a perspective's triangles carry 1 / z, which is affine on the page. The
compiled functions are cached in NUMBA_CACHE_DIR, ~/.cache/kit-numba unless set, off the drive, where every file
takes half a megabyte.
"""
import math, os
from pathlib import Path

os.environ.setdefault('NUMBA_CACHE_DIR', str(Path.home() / '.cache' / 'kit-numba'))

import numpy as np
from numba import njit, prange

R_PX = 4.0                                             # pixels a point on the page
STEP_PT = 0.25                                         # between a line's samples
HALVINGS = 10                                          # a step halved to under a thousandth of it
CELL_PX = 8                                            # the exact query's cells, doubled while they would hold more
CELL_ITEMS = 200_000_000                               # entries than this
CREASE_DEG = 20.0
EDGE_ON = 1e-4                                         # |cos| between a face's normal and the view: under it, edge-on


# ---------------------------------------------------------------- the buffer

@njit(cache=True, error_model='numpy')
def _nearest_points(P, area, rank, tie, persp, Q, live, tl, th, t0, nx, ny, order, starts, best, bz, br):
    """triangle-order point queries; ties use the group rank, as hidden.Tris.nearest does; tl and th the cells of
    triangles t0 on"""
    for t in live:
        x0, y0 = max(tl[t - t0, 0], 0), max(tl[t - t0, 1], 0)
        x1, y1 = min(th[t - t0, 0], nx - 1), min(th[t - t0, 1], ny - 1)
        for row in range(y0, y1 + 1):
            for j in range(starts[row * nx + x0], starts[row * nx + x1 + 1]):
                q = order[j]
                x, y = Q[q, 0], Q[q, 1]
                l1 = ((x - P[t, 0, 0]) * (P[t, 2, 1] - P[t, 0, 1]) -
                      (P[t, 2, 0] - P[t, 0, 0]) * (y - P[t, 0, 1])) / area[t]
                l2 = ((P[t, 1, 0] - P[t, 0, 0]) * (y - P[t, 0, 1]) -
                      (x - P[t, 0, 0]) * (P[t, 1, 1] - P[t, 0, 1])) / area[t]
                if not (l1 >= -1e-9 and l2 >= -1e-9 and l1 + l2 <= 1 + 1e-9):
                    continue
                z = P[t, 0, 2] + l1 * (P[t, 1, 2] - P[t, 0, 2]) + l2 * (P[t, 2, 2] - P[t, 0, 2])
                if persp:
                    z = 1.0 / z
                r, b = rank[t], bz[q]
                if z > b + tie or (z > b - tie and r < br[q]) or (z > b and r == br[q]):
                    bz[q], br[q], best[q] = z, r, t


@njit(cache=True)
def _raster(P, use, persp, s, tri):
    """the nearest of the triangles P (m x 3 x 3) with use set at each pixel centre, s pixels a unit"""
    ny, nx = tri.shape
    depth = np.full((ny, nx), -np.inf)
    for t in range(P.shape[0]):
        if not use[t]:
            continue
        x0, y0, z0 = P[t, 0, 0] * s, P[t, 0, 1] * s, P[t, 0, 2]
        x1, y1, z1 = P[t, 1, 0] * s, P[t, 1, 1] * s, P[t, 1, 2]
        x2, y2, z2 = P[t, 2, 0] * s, P[t, 2, 1] * s, P[t, 2, 2]
        A = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if A == 0.0:
            continue
        if A < 0.0:                                    # wound clockwise as seen: a back face, rasterized reversed
            x1, y1, z1, x2, y2, z2 = x2, y2, z2, x1, y1, z1
            A = -A
        i0 = max(int(math.floor(min(x0, x1, x2) - 0.5)), 0)
        i1 = min(int(math.ceil(max(x0, x1, x2) - 0.5)), nx - 1)
        j0 = max(int(math.floor(min(y0, y1, y2) - 0.5)), 0)
        j1 = min(int(math.ceil(max(y0, y1, y2) - 0.5)), ny - 1)
        if i0 > i1 or j0 > j1:
            continue
        # two triangles sharing an edge run it in opposite directions: a pixel centre exactly on it goes to the one
        # for which it runs down, or right when level
        e0 = (y2 - y1) < 0 or ((y2 - y1) == 0 and (x2 - x1) > 0)
        e1 = (y0 - y2) < 0 or ((y0 - y2) == 0 and (x0 - x2) > 0)
        e2 = (y1 - y0) < 0 or ((y1 - y0) == 0 and (x1 - x0) > 0)
        for j in range(j0, j1 + 1):
            py = j + 0.5
            for i in range(i0, i1 + 1):
                px = i + 0.5
                w0 = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
                w1 = (x0 - x2) * (py - y2) - (y0 - y2) * (px - x2)
                w2 = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                if (w0 == 0 and not e0) or (w1 == 0 and not e1) or (w2 == 0 and not e2):
                    continue
                zz = (w0 * z0 + w1 * z1 + w2 * z2) / A
                if persp:
                    if zz == 0.0:
                        continue
                    zz = 1.0 / zz
                if zz > depth[j, i]:
                    depth[j, i] = zz
                    tri[j, i] = t


@njit(cache=True)
def _cam(x, y, z, persp, hx, hy, f, L, sy):
    """a frame point at camera depth z, in camera space"""
    if persp:
        return (x - hx) * -z / L, (y - hy + sy) * -z / L, z
    return (x - hx) / f, (y - hy) / f, z


@njit(cache=True)
def _on_plane(x, y, z, planes, persp, hx, hy, f, L, sy, tol):
    """does a frame point at depth z lie within tol of a clip plane (rows: camera-space unit normal, offset)"""
    cx, cy, cz = _cam(x, y, z, persp, hx, hy, f, L, sy)
    for p in range(planes.shape[0]):
        if abs(planes[p, 0] * cx + planes[p, 1] * cy + planes[p, 2] * cz - planes[p, 3]) <= tol:
            return True
    return False


@njit(cache=True)
def _sees(t, fc, x, y, z, P, tri_o, cap_o, persp, hx, hy, f, L, sy, delta, tol, on_cut):
    """is a point (frame x, y at camera depth z) seen past triangle t, the surface nearest the camera over it, whose
    facing is fc: its plane behind the point or within delta in front along the view, or within tol of it square to
    the plane; a back face of an object with cap_o set hides it unless it is on a clip plane"""
    if fc < 0 and cap_o[tri_o[t]] and not on_cut:
        return False
    x0, y0, x1, y1, x2, y2 = P[t, 0, 0], P[t, 0, 1], P[t, 1, 0], P[t, 1, 1], P[t, 2, 0], P[t, 2, 1]
    A = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if A == 0.0:
        return True
    l1 = ((x - x0) * (y2 - y0) - (x2 - x0) * (y - y0)) / A
    l2 = ((x1 - x0) * (y - y0) - (x - x0) * (y1 - y0)) / A
    zz = P[t, 0, 2] + l1 * (P[t, 1, 2] - P[t, 0, 2]) + l2 * (P[t, 2, 2] - P[t, 0, 2])
    if persp:
        if zz == 0.0:
            return True
        zz = 1.0 / zz
    if zz <= z + delta:
        return True
    za, zb, zc = P[t, 0, 2], P[t, 1, 2], P[t, 2, 2]
    if persp:
        za, zb, zc = 1.0 / za, 1.0 / zb, 1.0 / zc
    ax, ay, az = _cam(x0, y0, za, persp, hx, hy, f, L, sy)
    bx, by, bz = _cam(x1, y1, zb, persp, hx, hy, f, L, sy)
    cx, cy, cz = _cam(x2, y2, zc, persp, hx, hy, f, L, sy)
    nx = (by - ay) * (cz - az) - (bz - az) * (cy - ay)
    ny = (bz - az) * (cx - ax) - (bx - ax) * (cz - az)
    nz = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    nn = math.sqrt(nx * nx + ny * ny + nz * nz)
    if nn == 0.0:
        return True
    px, py, pz = _cam(x, y, z, persp, hx, hy, f, L, sy)
    return abs(nx * (px - ax) + ny * (py - ay) + nz * (pz - az)) / nn <= tol


@njit(cache=True)
def _covers(P, t, x, y, persp):
    """triangle t's depth at (x, y) if it covers the point, else -inf, and its facing: 1 turned to the camera"""
    x0, y0, x1, y1, x2, y2 = P[t, 0, 0], P[t, 0, 1], P[t, 1, 0], P[t, 1, 1], P[t, 2, 0], P[t, 2, 1]
    A = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if A == 0.0:
        return -np.inf, 1
    fc = 1 if A > 0 else -1
    l1 = ((x - x0) * (y2 - y0) - (x2 - x0) * (y - y0)) / A
    l2 = ((x1 - x0) * (y - y0) - (x - x0) * (y1 - y0)) / A
    if l1 < -1e-9 or l2 < -1e-9 or l1 + l2 > 1 + 1e-9:
        return -np.inf, fc
    zz = P[t, 0, 2] + l1 * (P[t, 1, 2] - P[t, 0, 2]) + l2 * (P[t, 2, 2] - P[t, 0, 2])
    if persp:
        if zz == 0.0:
            return -np.inf, fc
        zz = 1.0 / zz
    return zz, fc


@njit(cache=True)
def _bin_count(P, use, s, cs, cnx, cny, count):
    """each used triangle counted in every cell of cs pixels its box meets"""
    for t in range(P.shape[0]):
        if not use[t]:
            continue
        i0 = int(math.floor(min(P[t, 0, 0], P[t, 1, 0], P[t, 2, 0]) * s / cs))
        i1 = int(math.floor(max(P[t, 0, 0], P[t, 1, 0], P[t, 2, 0]) * s / cs))
        j0 = int(math.floor(min(P[t, 0, 1], P[t, 1, 1], P[t, 2, 1]) * s / cs))
        j1 = int(math.floor(max(P[t, 0, 1], P[t, 1, 1], P[t, 2, 1]) * s / cs))
        if i1 < 0 or j1 < 0 or i0 >= cnx or j0 >= cny:
            continue
        for j in range(max(j0, 0), min(j1, cny - 1) + 1):
            for i in range(max(i0, 0), min(i1, cnx - 1) + 1):
                count[j * cnx + i] += 1


@njit(cache=True)
def _bin_fill(P, use, s, cs, cnx, cny, start, items):
    at = start[:-1].copy()
    for t in range(P.shape[0]):
        if not use[t]:
            continue
        i0 = int(math.floor(min(P[t, 0, 0], P[t, 1, 0], P[t, 2, 0]) * s / cs))
        i1 = int(math.floor(max(P[t, 0, 0], P[t, 1, 0], P[t, 2, 0]) * s / cs))
        j0 = int(math.floor(min(P[t, 0, 1], P[t, 1, 1], P[t, 2, 1]) * s / cs))
        j1 = int(math.floor(max(P[t, 0, 1], P[t, 1, 1], P[t, 2, 1]) * s / cs))
        if i1 < 0 or j1 < 0 or i0 >= cnx or j0 >= cny:
            continue
        for j in range(max(j0, 0), min(j1, cny - 1) + 1):
            for i in range(max(i0, 0), min(i1, cnx - 1) + 1):
                c = j * cnx + i
                items[at[c]] = t
                at[c] += 1


@njit(cache=True)
def _better(zt, fc, bz, bf, tie):
    """is a surface at depth zt facing fc nearer than the best so far: by more than tie, or level within it and turned
    to the camera where the best is not (a capped solid standing on the ground: its back face at the foot of its walls
    would hide the ground's edge there on some samples and not others)"""
    return zt > bz + tie or (zt >= bz - tie and (fc > bf or (fc == bf and zt > bz)))


@njit(cache=True)
def _nearest(P, persp, s, cs, cnx, cny, start, items, x, y, tie):
    """the triangle nearest the camera covering (x, y), of all those in its cell: (t or -1, depth, facing)"""
    ci = int(math.floor(x * s / cs))
    cj = int(math.floor(y * s / cs))
    best, bz, bf = -1, -np.inf, 1
    if ci < 0 or cj < 0 or ci >= cnx or cj >= cny:
        return best, bz, bf
    c = cj * cnx + ci
    for q in range(start[c], start[c + 1]):
        zt, fc = _covers(P, items[q], x, y, persp)
        if zt > -np.inf and (best < 0 or _better(zt, fc, bz, bf, tie)):
            best, bz, bf = items[q], zt, fc
    return best, bz, bf


@njit(cache=True)
def _exact(tri, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a, tol_b, planes, cs, cnx, cny, start, items,
           x, y, z):
    """is the point seen, against the nearest triangle covering it: of those the 3 x 3 pixels round it hold, or, where
    one of them would hide it but does not reach it (an edge of something in front is near: a face folded over
    another, a sliver), of all those in its cell"""
    tol = tol_a + tol_b * abs(z)
    oc = _on_plane(x, y, z, planes, persp, hx, hy, f, L, sy, tol)
    ny, nx = tri.shape
    i = int(math.floor(x * s))
    j = int(math.floor(y * s))
    best, bz, bf = -1, -np.inf, 1
    edge = False
    for dj in range(-1, 2):
        for di in range(-1, 2):
            ii, jj = i + di, j + dj
            if ii < 0 or jj < 0 or ii >= nx or jj >= ny:
                continue
            t = tri[jj, ii]
            if t < 0 or t == best:
                continue
            zt, fc = _covers(P, t, x, y, persp)
            if zt > -np.inf:
                if best < 0 or _better(zt, fc, bz, bf, delta):
                    best, bz, bf = t, zt, fc
            elif not edge and not _sees(t, fc, x, y, z, P, tri_o, cap_o, persp, hx, hy, f, L, sy, delta, tol, oc):
                edge = True
    if edge:
        best, bz, bf = _nearest(P, persp, s, cs, cnx, cny, start, items, x, y, delta)
    if best < 0:
        return True
    return _sees(best, bf, x, y, z, P, tri_o, cap_o, persp, hx, hy, f, L, sy, delta, tol, oc)


@njit(cache=True, parallel=True)
def _exact_all(tri, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a, tol_b, planes, cs, cnx, cny, start, items,
               X, Y, Z, out):
    for q in prange(X.shape[0]):
        out[q] = _exact(tri, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a, tol_b, planes, cs, cnx, cny,
                        start, items, X[q], Y[q], Z[q])


@njit(cache=True)
def _front_all(tri, P, persp, s, cs, cnx, cny, start, items, delta, X, Y, out):
    """the triangle nearest the camera covering each point, as _exact finds it, -1 for none"""
    ny, nx = tri.shape
    for q in range(X.shape[0]):
        x, y = X[q], Y[q]
        i = int(math.floor(x * s))
        j = int(math.floor(y * s))
        best, bz, bf = -1, -np.inf, 1
        for dj in range(-1, 2):
            for di in range(-1, 2):
                ii, jj = i + di, j + dj
                if ii < 0 or jj < 0 or ii >= nx or jj >= ny:
                    continue
                t = tri[jj, ii]
                if t < 0 or t == best:
                    continue
                zt, fc = _covers(P, t, x, y, persp)
                if zt > -np.inf and (best < 0 or _better(zt, fc, bz, bf, delta)):
                    best, bz, bf = t, zt, fc
        if best < 0:
            best, bz, bf = _nearest(P, persp, s, cs, cnx, cny, start, items, x, y, delta)
        out[q] = best


@njit(cache=True)
def _front_cell_all(P, persp, s, cs, cnx, cny, start, items, delta, X, Y, out):
    """the triangle nearest the camera covering each point of all those in its cell, the pixels not consulted: a
    triangle narrower than a pixel that wins none of them is found too"""
    for q in range(X.shape[0]):
        best, bz, bf = _nearest(P, persp, s, cs, cnx, cny, start, items, X[q], Y[q], delta)
        out[q] = best


@njit(cache=True)
def _sees_given(T, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a, tol_b, planes, X, Y, Z, out):
    for q in range(X.shape[0]):
        t = T[q]
        if t < 0:
            out[q] = True
            continue
        A = (P[t, 1, 0] - P[t, 0, 0]) * (P[t, 2, 1] - P[t, 0, 1]) - (P[t, 2, 0] - P[t, 0, 0]) * (P[t, 1, 1] - P[t, 0, 1])
        tol = tol_a + tol_b * abs(Z[q])
        oc = _on_plane(X[q], Y[q], Z[q], planes, persp, hx, hy, f, L, sy, tol)
        out[q] = _sees(t, 1 if A > 0 else -1, X[q], Y[q], Z[q], P, tri_o, cap_o, persp, hx, hy, f, L, sy, delta, tol, oc)


@njit(cache=True)
def _halve(tri, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a, tol_b, planes, cs, cnx, cny, start, items,
           A, B, tk, tl, cell, out):
    """for each piece A -> B (frame x, y, camera z), the point between parameters tk (seen) and tl (not) where it
    turns, by halving: the last parameter seen; where cell is set, each point judged against every triangle in its
    cell, as a sample between an outline's crossings was"""
    for e in range(A.shape[0]):
        a, b = tk[e], tl[e]
        for _ in range(HALVINGS):
            m = 0.5 * (a + b)
            x = A[e, 0] + m * (B[e, 0] - A[e, 0])
            y = A[e, 1] + m * (B[e, 1] - A[e, 1])
            if persp:
                z = 1.0 / ((1.0 - m) / A[e, 2] + m / B[e, 2])
            else:
                z = A[e, 2] + m * (B[e, 2] - A[e, 2])
            if cell[e]:
                t, zt, fc = _nearest(P, persp, s, cs, cnx, cny, start, items, x, y, delta)
                tol = tol_a + tol_b * abs(z)
                ok = t < 0 or _sees(t, fc, x, y, z, P, tri_o, cap_o, persp, hx, hy, f, L, sy, delta, tol,
                                    _on_plane(x, y, z, planes, persp, hx, hy, f, L, sy, tol))
            else:
                ok = _exact(tri, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a, tol_b, planes, cs, cnx, cny,
                            start, items, x, y, z)
            if ok:
                a = m
            else:
                b = m
        out[e] = a


class Buffer:
    """the frame rasterized: tri (ny x nx), the index into P of the triangle nearest the camera at each pixel centre,
    -1 for none, row j the page's y from j / R_PX to (j + 1) / R_PX pt from its foot.
      P       the triangles (m x 3 x 3), frame x and y with z, or 1 / z in a perspective; tri_o each one's object
      use     the triangles that hide
      view    (hx, hy, f, L, sy): the frame's half width and height, the true-length factor, a perspective's focal
              depth and shift (0 in a parallel view)
      k       pt a frame unit; W, H the frame in pt
      delta   depth along the view within which a surface in front still shows what lies on it
      tol_pt  the tolerance square to the surface, on the page; err a length added to it in camera units (the
              meshes' float32 rounding)
      planes  the clip planes in camera space, rows of unit normal and offset
      cap_o   per object: a closed solid whose back faces stand for its missing cut face"""

    def __init__(self, P, tri_o, use, persp, view, k, W, H, delta, tol_pt, err, planes, cap_o):
        self.P = np.ascontiguousarray(P, dtype=np.float64)
        self.tri_o = np.ascontiguousarray(tri_o, dtype=np.int64)
        self.persp = bool(persp)
        self.hx, self.hy, self.f, self.L, self.sy = (float(v) for v in view)
        self.k = float(k)
        self.s = R_PX * self.k                         # pixels a frame unit
        self.delta = float(delta)
        self.err = float(err)
        self.tol_a, self.tol_b = self.tols(tol_pt)
        self.planes = np.ascontiguousarray(np.reshape(planes, (-1, 4)), dtype=np.float64)
        self.cap_o = np.ascontiguousarray(cap_o, dtype=np.bool_)
        self.tri = np.full((int(math.ceil(H * R_PX)), int(math.ceil(W * R_PX))), -1, dtype=np.int32)
        use = np.ascontiguousarray(use, dtype=np.bool_)
        _raster(self.P, use, self.persp, self.s, self.tri)
        self.cs = float(CELL_PX)                       # the triangles by cells of cs pixels, for the exact query
        while True:
            self.cnx = int(math.ceil(self.tri.shape[1] / self.cs))
            self.cny = int(math.ceil(self.tri.shape[0] / self.cs))
            count = np.zeros(self.cnx * self.cny, dtype=np.int64)
            _bin_count(self.P, use, self.s, self.cs, self.cnx, self.cny, count)
            if count.sum() <= CELL_ITEMS or self.cs >= 1024:
                break
            self.cs *= 2
        self.start = np.zeros(len(count) + 1, dtype=np.int64)
        np.cumsum(count, out=self.start[1:])
        self.items = np.zeros(int(self.start[-1]), dtype=np.int32)
        _bin_fill(self.P, use, self.s, self.cs, self.cnx, self.cny, self.start, self.items)

    def tols(self, tol_pt):
        """the tolerance square to the surface, tol_pt on the page, as the exact query takes it: (tol_a, tol_b)"""
        if self.persp:
            return self.err, float(tol_pt) / (self.k * self.L)
        return float(tol_pt) / (self.k * self.f) + self.err, 0.0

    def _args(self):
        return (self.P, self.tri_o, self.cap_o, self.persp, self.hx, self.hy, self.f, self.L, self.sy, self.s,
                self.delta, self.tol_a, self.tol_b, self.planes, self.cs, self.cnx, self.cny, self.start, self.items)

    def seen(self, X, Y, Z, tol_pt=None):
        """each point seen (_exact), within tol_pt square to the surface where given, else the buffer's"""
        out = np.zeros(len(X), dtype=np.bool_)
        f64 = lambda a: np.ascontiguousarray(a, dtype=np.float64)
        a = self._args()
        if tol_pt is not None:
            a = a[:11] + self.tols(tol_pt) + a[13:]
        _exact_all(self.tri, *a, f64(X), f64(Y), f64(Z), out)
        return out

    def front(self, X, Y):
        """the triangle nearest the camera over each point (an index into P, -1 for none): what hides a point the
        buffer does not see"""
        out = np.full(len(X), -1, dtype=np.int64)
        f64 = lambda a: np.ascontiguousarray(a, dtype=np.float64)
        _front_all(self.tri, self.P, self.persp, self.s, self.cs, self.cnx, self.cny, self.start, self.items, self.delta,
                   f64(X), f64(Y), out)
        return out

    def front_cell(self, X, Y):
        """the triangle nearest the camera over each point of all those in its cell (-1 for none), however narrow"""
        out = np.full(len(X), -1, dtype=np.int64)
        f64 = lambda a: np.ascontiguousarray(a, dtype=np.float64)
        _front_cell_all(self.P, self.persp, self.s, self.cs, self.cnx, self.cny, self.start, self.items, self.delta,
                        f64(X), f64(Y), out)
        return out

    def sees(self, T, X, Y, Z):
        """each point seen past the triangle T given for it (-1 for none) by the same rules: a check of the buffer
        against an exact query of the nearest triangle"""
        out = np.zeros(len(X), dtype=np.bool_)
        f64 = lambda a: np.ascontiguousarray(a, dtype=np.float64)
        _sees_given(np.ascontiguousarray(T, dtype=np.int64), *self._args()[:14], f64(X), f64(Y), f64(Z), out)
        return out

    def halve(self, A, B, tk, tl, cell=None):
        """the last parameter seen between tk and tl on each piece A -> B (n x 3); where cell is set, against every
        triangle in each point's cell"""
        out = np.zeros(len(A), dtype=np.float64)
        f64 = lambda a: np.ascontiguousarray(a, dtype=np.float64)
        cell = np.zeros(len(A), dtype=np.bool_) if cell is None else np.ascontiguousarray(cell, dtype=np.bool_)
        _halve(self.tri, *self._args(), f64(A), f64(B), f64(tk), f64(tl), cell, out)
        return out


# ---------------------------------------------------------------- lines against it

def samples(lines, k, W, H):
    """lines (polylines n x 3: frame x, y and camera z) sampled every STEP_PT on the page, in order along each line:
    each piece from its start, the last also at its end; a piece wholly outside the frame (W x H pt) is one sample, at
    its start. A dict: the pieces A and B (each n x 3) and each line's first piece (pc0); a row a sample, its line, its
    piece (pc, an index into A and B, piece p of a line running from its point p to p + 1) and t along it"""
    if not lines:
        z = np.zeros(0, dtype=np.int64)
        return dict(A=np.zeros((0, 3)), B=np.zeros((0, 3)), pc0=z, line=z, pc=z, t=np.zeros(0))
    n_pc = np.array([len(P) - 1 for P in lines], dtype=np.int64)
    A = np.concatenate([P[:-1] for P in lines])
    B = np.concatenate([P[1:] for P in lines])
    pc0 = np.cumsum(n_pc) - n_pc
    li = np.repeat(np.arange(len(lines)), n_pc)
    last = np.arange(len(A)) == np.repeat(pc0 + n_pc - 1, n_pc)
    ln = np.hypot(B[:, 0] - A[:, 0], B[:, 1] - A[:, 1]) * k
    W_, H_ = W / k, H / k
    out_ = ((A[:, 0] < 0) & (B[:, 0] < 0)) | ((A[:, 0] > W_) & (B[:, 0] > W_)) | \
        ((A[:, 1] < 0) & (B[:, 1] < 0)) | ((A[:, 1] > H_) & (B[:, 1] > H_))
    parts = np.where(out_, 1, np.maximum(1, np.ceil(ln / STEP_PT))).astype(np.int64)
    n = parts + last
    pc = np.repeat(np.arange(len(A)), n)
    i = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    return dict(A=A, B=B, pc0=pc0, line=li[pc], pc=pc, t=i / parts[pc])


def between(S, OA, OB, k):
    """S (samples) with a sample added between two crossings of a piece with the outline segments OA OB (n x 2, frame
    units: the meshes' boundaries, creases and silhouettes, where what is behind can turn seen or hidden) that lie
    under STEP_PT apart with no sample between them, marked extra, to be judged against every triangle in its cell
    (Buffer.front_cell): an object narrower than a step in front of a line (a mullion seen far off, an occluding
    triangle 0.24 pt wide, the adversarial tests doubles-occluder scenes) is then seen in front of it"""
    import shapely
    A, B = S['A'], S['B']
    if not len(A) or not len(OA):
        return S
    pl = shapely.linestrings(np.stack([A[:, :2], B[:, :2]], 1))
    ol = shapely.linestrings(np.stack([OA, OB], 1))
    ip, io = shapely.STRtree(ol).query(pl, predicate='intersects')
    if not len(ip):
        return S
    d1 = B[ip, :2] - A[ip, :2]
    d2 = OB[io] - OA[io]
    den = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    w0 = OA[io] - A[ip, :2]
    ok = np.abs(den) > 1e-300
    tc = np.where(ok, (w0[:, 0] * d2[:, 1] - w0[:, 1] * d2[:, 0]) / np.where(ok, den, 1.0), -1.0)
    keep = ok & (tc > 0) & (tc < 1)
    ip, tc = ip[keep], tc[keep]
    if not len(ip):
        return S
    o_ = np.lexsort((tc, ip))
    ip, tc = ip[o_], tc[o_]
    same = ip[1:] == ip[:-1]
    t1, t2, pcs = tc[:-1][same], tc[1:][same], ip[:-1][same]
    ln = np.hypot(B[pcs, 0] - A[pcs, 0], B[pcs, 1] - A[pcs, 1]) * k
    parts = np.maximum(1, np.ceil(np.hypot(B[:, 0] - A[:, 0], B[:, 1] - A[:, 1]) * k / STEP_PT))[pcs]
    # no sample of the piece's own, at i / parts, strictly between the two crossings
    lone = ((t2 - t1) * ln < STEP_PT) & (np.floor(t2 * parts - 1e-9) < np.ceil(t1 * parts + 1e-9))
    if not lone.any():
        return S
    pc_n, t_n = pcs[lone], (t1[lone] + t2[lone]) / 2
    line_of = np.repeat(np.arange(len(S['pc0'])), np.diff(np.r_[S['pc0'], len(A)]))
    pc = np.r_[S['pc'], pc_n]
    t = np.r_[S['t'], t_n]
    extra = np.r_[np.zeros(len(S['t']), dtype=bool), np.ones(len(t_n), dtype=bool)]
    o_ = np.lexsort((t, pc))
    return dict(S, pc=pc[o_], t=t[o_], line=line_of[pc[o_]], extra=extra[o_])


def at(S, persp, pc=None, t=None):
    """points on the pieces, frame x, y and camera z: the samples', or pieces pc at parameters t"""
    pc = S['pc'] if pc is None else pc
    t = S['t'] if t is None else t
    A, B = S['A'][pc], S['B'][pc]
    X = A[:, 0] + t * (B[:, 0] - A[:, 0])
    Y = A[:, 1] + t * (B[:, 1] - A[:, 1])
    Z = 1.0 / ((1 - t) / A[:, 2] + t / B[:, 2]) if persp else A[:, 2] + t * (B[:, 2] - A[:, 2])
    return X, Y, Z


def stretches(S, buf, ok, seen):
    """runs of ok samples along each line: [(line, (piece, t) start, (piece, t) end)], pieces as S indexes them. A
    run's end next to a sample not seen is found by halving; next to one seen, not ok for another reason, it is that
    sample, so the stretch runs a step on into what stands for it; at a line's own start or end it is that"""
    li, pc, tt = S['line'], S['pc'], S['t']
    m = ok.astype(np.int8)
    brk = np.concatenate([[True], li[1:] != li[:-1]])
    st = np.nonzero((m == 1) & (brk | np.concatenate([[True], m[:-1] == 0])))[0]
    en = np.nonzero((m == 1) & (np.concatenate([brk[1:], [True]]) | np.concatenate([m[1:] == 0, [True]])))[0]
    pos = ([(int(pc[j]), float(tt[j])) for j in st], [(int(pc[j]), float(tt[j])) for j in en])
    todo = []                                          # (run, 0 its start or 1 its end, piece, t kept, t lost, cell)
    ex = S.get('extra', np.zeros(len(li), dtype=bool))
    for r, (j0, j1) in enumerate(zip(st.tolist(), en.tolist())):
        for side, j, jn in ((0, j0, j0 - 1), (1, j1, j1 + 1)):
            if jn < 0 or jn >= len(li) or li[jn] != li[j]:
                continue
            if seen[jn]:
                pos[side][r] = (int(pc[jn]), float(tt[jn]))
            elif pc[j] == pc[jn]:
                todo.append((r, side, int(pc[j]), float(tt[j]), float(tt[jn]), bool(ex[jn])))
            elif side == 1:                            # the lost sample starts the next piece, where this one ends
                todo.append((r, side, int(pc[j]), float(tt[j]), 1.0, bool(ex[jn])))
            else:                                      # the kept sample starts its piece: the turn is on the one before
                todo.append((r, side, int(pc[jn]), 1.0, float(tt[jn]), bool(ex[jn])))
    if todo:
        T = np.array([x[2] for x in todo], dtype=np.int64)
        tk = buf.halve(S['A'][T], S['B'][T], np.array([x[3] for x in todo]), np.array([x[4] for x in todo]),
                       np.array([x[5] for x in todo]))
        for (r, side, p, _, _, _), t_ in zip(todo, tk.tolist()):
            pos[side][r] = (p, t_)
    return [(int(li[j0]), a, b) for j0, a, b in zip(st.tolist(), pos[0], pos[1])]


def stretch_points(S, persp, line, P, a, b):
    """the points of a stretch of line (its points P) from (piece, t) a to b"""
    (pa, ta), (pb, tb) = a, b
    X, Y, Z = at(S, persp, np.array([pa, pb]), np.array([ta, tb]))
    va, vb = pa - int(S['pc0'][line]), pb - int(S['pc0'][line])
    return [[float(X[0]), float(Y[0]), float(Z[0])]] + P[va + 1:vb + 1].tolist() + [[float(X[1]), float(Y[1]), float(Z[1])]]


# ---------------------------------------------------------------- lines from the meshes

def weld(C, r):
    """an id for each point of C (n x 3), equal for points within r of each other, through chains of them"""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    U, inv = np.unique(C, axis=0, return_inverse=True)
    inv = inv.ravel()
    pairs = cKDTree(U).query_pairs(r, output_type='ndarray')
    if not len(pairs):
        return inv
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(U), len(U)))
    return connected_components(g, directed=False)[1][inv]


def openings(Vp, C, Fw, Fl, T, nrm, tt, wa, wb, la, lb, start, cnt):
    """for each edge of an object's mesh (the runs start, cnt of its half-edges sorted by edge, as mesh_edges sorts
    them): 1 where it lies on the rim of a hole through a smooth patch turned to the camera, -1 on one through a patch
    turned away, else 0. A patch is the triangles T joined across edges of two triangles wound alike that do not
    crease; its boundary falls into loops, and a loop wound against the patch on the page is a hole. A hole is an
    opening (a window, a door) where at least 0.7 of its rim, by length on the page, is the mesh's boundary or a convex
    crease, the triangle across it lying behind the patch, and not a concave one (the foot of a pilaster on a face).
    A patch seen nearly edge-on, its triangles' areas on the page cancelling to under half their sum, has none.
      Vp      the object's vertices on the page (n x 2), C in camera space, both by its own vertex index
      Fw, Fl  its triangles by welded vertex and by its own vertex index, nrm their unit normals in camera space
      tt      each half-edge's triangle; wa, wb its welded ends and la, lb its own, in the order it runs"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    flag = np.zeros(len(start), dtype=np.int8)
    if not len(start):
        return flag
    grp = np.repeat(np.arange(len(start)), cnt)
    other = np.full(len(tt), -1, dtype=np.int64)
    two = np.nonzero(cnt == 2)[0]
    other[start[two]], other[start[two] + 1] = start[two] + 1, start[two]
    t0, t1 = tt[start[two]], tt[start[two] + 1]
    smooth = (wa[start[two]] != wa[start[two] + 1]) & \
        ((nrm[t0] * nrm[t1]).sum(1) >= math.cos(math.radians(CREASE_DEG)))
    n_t = len(Fl)
    lab = connected_components(coo_matrix((np.ones(int(smooth.sum())), (t0[smooth], t1[smooth])), shape=(n_t, n_t)),
                               directed=False)[1]
    P0, P1, P2 = Vp[Fl[:, 0]], Vp[Fl[:, 1]], Vp[Fl[:, 2]]
    A = ((P1[:, 0] - P0[:, 0]) * (P2[:, 1] - P0[:, 1]) - (P2[:, 0] - P0[:, 0]) * (P1[:, 1] - P0[:, 1])) / 2
    ps = np.bincount(lab[T], A[T], minlength=n_t)
    pa = np.bincount(lab[T], np.abs(A[T]), minlength=n_t)
    side = np.where((pa > 0) & (np.abs(ps) >= 0.5 * pa), np.sign(ps), 0.0)
    bnd = (cnt[grp] != 2) | ((other >= 0) & (lab[tt[np.maximum(other, 0)]] != lab[tt]))
    B = np.nonzero(bnd & (side[lab[tt]] != 0))[0]
    if not len(B):
        return flag
    # convex where the corner of the triangle across that is off the edge lies behind this triangle's plane
    convex = np.zeros(len(tt), dtype=bool)
    o2 = B[cnt[grp[B]] == 2]
    if len(o2):
        tw = Fw[tt[other[o2]]]
        far = (tw != wa[o2][:, None]) & (tw != wb[o2][:, None])
        third = Fl[tt[other[o2]]][np.arange(len(o2)), np.argmax(far, 1)]
        convex[o2] = far.any(1) & ((nrm[tt[o2]] * (C[third] - C[la[o2]])).sum(1) < 0)
    rim = (cnt[grp] == 1) | convex
    # the loops: each patch's boundary half-edges joined through their welded ends; a loop's signed area on the page,
    # summed edge by edge, needs no order
    pb = lab[tt[B]].astype(np.int64)
    w1 = int(max(wa.max(), wb.max())) + 1
    u, inv = np.unique(np.concatenate([pb * w1 + wa[B], pb * w1 + wb[B]]), return_inverse=True)
    ia, ib = inv[:len(B)], inv[len(B):]
    comp = connected_components(coo_matrix((np.ones(len(B)), (ia, ib)), shape=(len(u), len(u))), directed=False)[1][ia]
    qa, qb = Vp[la[B]], Vp[lb[B]]
    seg = np.hypot(*(qb - qa).T)
    nc = int(comp.max()) + 1
    area = np.bincount(comp, (qa[:, 0] * qb[:, 1] - qb[:, 0] * qa[:, 1]) / 2, minlength=nc)
    ln = np.bincount(comp, seg, minlength=nc)
    rim_ln = np.bincount(comp, seg * rim[B], minlength=nc)
    c_side = np.zeros(nc)
    c_side[comp] = side[pb]
    hole = (np.sign(area) == -c_side) & (area != 0) & (rim_ln >= 0.7 * ln)
    f_h = np.where(hole[comp], c_side[comp], 0.0)
    # a patch's outer loop with a pocket, its convex hull on the page less the loop, whose rim is over twice the
    # mouth across it and mostly the mesh's boundary or convex creases, as a door cut from a wall's foot is: the rim
    # is an opening's too. The loop is put in order through its welded ends only where its area is under its hull's
    import shapely
    from scipy.spatial import ConvexHull, QhullError
    outer = np.nonzero((np.sign(area) == c_side) & (c_side != 0))[0]
    by_c = np.argsort(comp, kind='stable')
    cut = np.searchsorted(comp[by_c], np.arange(nc + 1))
    for c in outer.tolist():
        hs = by_c[cut[c]:cut[c + 1]]
        if len(hs) < 4:
            continue
        try:
            hull_a = ConvexHull(qa[hs]).volume
        except (QhullError, ValueError):
            continue
        if hull_a <= 1.02 * abs(area[c]):
            continue
        nxt = {}
        for j in hs.tolist():
            nxt.setdefault(int(wa[B[j]]), []).append(j)
        ring, j = [], hs[0]
        for _ in range(len(hs)):
            ring.append(j)
            more = nxt.get(int(wb[B[j]]))
            if not more:
                break
            j = more.pop()
            if j == ring[0]:
                break
        if len(ring) < 3:
            continue
        poly = shapely.make_valid(shapely.Polygon(qa[ring]))
        hull = shapely.convex_hull(poly)
        eps = 1e-5 * math.sqrt(max(hull.area, 1e-300))
        mids = shapely.points((qa[ring] + qb[ring]) / 2)
        on_hull = shapely.dwithin(mids, hull.boundary, 2 * eps)
        # opened by eps, a pocket loses the zero-width spikes the difference leaves along collinear edges
        for pk in shapely.get_parts(shapely.difference(hull, poly).buffer(-eps).buffer(eps)):
            if pk.geom_type != 'Polygon' or pk.area <= 0:
                continue
            on = shapely.dwithin(mids, pk.boundary, 2 * eps) & ~on_hull
            r_ln = float(seg[ring][on].sum())
            mouth = pk.boundary.length - r_ln
            if mouth > 0 and r_ln >= 2 * mouth and float((seg[ring] * rim[B[ring]])[on].sum()) >= 0.7 * r_ln:
                f_h[np.array(ring)[on]] = c_side[c]
    # a blind recess (a niche, a groove) is no opening: where faces of the object turned to the camera as the patch is,
    # lying behind it no deeper than the reveal reaches, cover half the hull of the rim on the page, the pocket stops at
    # that back face, and its rim keeps its class by depth
    cosb = math.cos(math.radians(25))
    cen = (P0 + P1 + P2) / 3
    for c in np.unique(comp[f_h > 0]).tolist():
        hs = np.nonzero((comp == c) & (f_h > 0))[0]
        o_ = other[B[hs]]
        rev = np.unique(tt[o_[o_ >= 0]])
        if not len(rev):
            continue                                   # a hole in an open surface goes through
        inP = lab == pb[hs[0]]
        nP = nrm[inP].sum(0)
        nP = nP / max(float(np.linalg.norm(nP)), 1e-300)
        x0 = C[la[B[hs[0]]]]
        D = float(((x0 - C[Fl[rev].ravel()]) @ nP).max())          # how deep behind the patch the reveal reaches
        hull = shapely.convex_hull(shapely.multipoints(np.concatenate([qa[hs], qb[hs]])))
        if D <= 0 or hull.area <= 0:
            continue
        cand = np.nonzero(~inP & ((nrm @ nP) >= cosb))[0]
        cand = cand[~np.isin(cand, rev)]
        if not len(cand):
            continue
        db = ((x0 - C[Fl[cand]].reshape(-1, 3)) @ nP).reshape(-1, 3)
        cand = cand[(db.min(1) > 0.01 * D) & (db.max(1) <= 1.05 * D)]
        if len(cand) and float(np.abs(A[cand[shapely.contains_xy(hull, cen[cand, 0], cen[cand, 1])]]).sum()) >= 0.5 * hull.area:
            f_h[hs] = 0
    flag[grp[B][f_h < 0]] = -1
    flag[grp[B][f_h > 0]] = 1
    return flag


def mesh_edges(V, F, items, objects, cam, persp, near=None, on_clip=None):
    """the edges of the meshes of objects (a set). Each object's vertices are welded within 1e-6 of its size or two
    float32 steps of its largest coordinate, whichever is more (the export writes a clipped triangle's vertices apart);
    an edge is kept that is a boundary (one triangle), a crease (normals more than CREASE_DEG apart), a silhouette (one
    triangle turned to the camera, one away, neither within EDGE_ON of edge-on) or shared by more than two triangles.
    cam(points of V) gives camera space; an edge with both ends on a clip plane (on_clip(camera points)), or with near
    on a perspective's near plane, is left out. A dict of arrays: a, b (each edge's ends as V holds them), obj, kind
    (0 boundary, 1 crease, 2 silhouette, 3 more than two), turn (degrees between its two triangles' normals, 180 for
    an edge of one or of more than two), hole (openings: 1 on the rim of an opening through a face turned to the
    camera, -1 through one turned away)"""
    out_a, out_b, out_o, out_k, out_h, out_t = [], [], [], [], [], []
    for it in items:
        o = it['o']
        if o not in objects or not it['nf']:
            continue
        Fo = F[it['f0']:it['f0'] + it['nf']]
        vs, inv = np.unique(Fo.ravel(), return_inverse=True)
        Fl = inv.reshape(-1, 3)                        # the object's own vertex indices
        C = cam(V[vs])
        size = float(np.linalg.norm(C.max(0) - C.min(0))) or 1.0
        r = max(size * 1e-6, float(np.abs(C).max()) * 2 ** -22)
        Fw = weld(C, r)[Fl]
        T0 = C[Fl[:, 0]]
        nrm = np.cross(C[Fl[:, 1]] - T0, C[Fl[:, 2]] - T0)
        nl = np.linalg.norm(nrm, axis=1)
        good = (nl > 0) & (Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 0] != Fw[:, 2])
        if not good.any():
            continue
        nrm = nrm / np.maximum(nl, 1e-300)[:, None]
        view = -C[Fl].mean(1) if persp else np.array([[0.0, 0.0, 1.0]])    # towards the camera
        cosv = (nrm * view).sum(1) / np.linalg.norm(view, axis=1)
        facing = np.where(np.abs(cosv) < EDGE_ON, 0, np.sign(cosv)).astype(np.int8)
        T = np.nonzero(good)[0]
        a = Fw[T][:, [0, 1, 2]].ravel()
        b = Fw[T][:, [1, 2, 0]].ravel()
        la = Fl[T][:, [0, 1, 2]].ravel()
        lb = Fl[T][:, [1, 2, 0]].ravel()
        tt = np.repeat(T, 3)
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        fwd = a < b
        order = np.lexsort((hi, lo))
        lo, hi, fwd, tt, la, lb, a, b = lo[order], hi[order], fwd[order], tt[order], la[order], lb[order], a[order], b[order]
        start = np.nonzero(np.concatenate([[True], (lo[1:] != lo[:-1]) | (hi[1:] != hi[:-1])]))[0]
        cnt = np.diff(np.concatenate([start, [len(lo)]]))
        kind = np.full(len(start), -1, dtype=np.int8)
        kind[cnt == 1] = 0
        kind[cnt > 2] = 3
        two = np.nonzero(cnt == 2)[0]
        s2 = start[two]
        flip = np.where(fwd[s2] == fwd[s2 + 1], -1.0, 1.0)   # both run the edge one way: wound inconsistently
        cosang = (nrm[tt[s2]] * nrm[tt[s2 + 1]]).sum(1) * flip
        f1, f2 = facing[tt[s2]] * flip, facing[tt[s2 + 1]]
        k2 = np.full(len(s2), -1, dtype=np.int8)
        k2[cosang < math.cos(math.radians(CREASE_DEG))] = 1
        k2[(f1 != 0) & (f2 != 0) & (f1 != f2)] = 2
        kind[two] = k2
        turn = np.full(len(start), 180.0)
        turn[two] = np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
        hole = openings(V[vs][:, :2], C, Fw, Fl, T, nrm, tt, a, b, la, lb, start, cnt)[kind >= 0]
        s = start[kind >= 0]
        kk = kind[kind >= 0]
        tn_ = turn[kind >= 0]
        ca, cb = C[la[s]], C[lb[s]]
        drop = np.zeros(len(s), dtype=bool)
        if on_clip is not None:
            drop |= on_clip(ca) & on_clip(cb)
        if near is not None:                           # the meshes are clipped at a perspective's near plane too
            tn = max(near * 1e-6, r)
            drop |= (np.abs(ca[:, 2] + near) <= tn) & (np.abs(cb[:, 2] + near) <= tn)
        s, kk, hole, tn_ = s[~drop], kk[~drop], hole[~drop], tn_[~drop]
        out_a.append(V[vs[la[s]]])
        out_b.append(V[vs[lb[s]]])
        out_o.append(np.full(len(s), o, dtype=np.int64))
        out_k.append(kk)
        out_h.append(hole)
        out_t.append(tn_)
    if not out_a:
        return dict(a=np.zeros((0, 3)), b=np.zeros((0, 3)), obj=np.zeros(0, dtype=np.int64), kind=np.zeros(0, dtype=np.int8),
                    hole=np.zeros(0, dtype=np.int8), turn=np.zeros(0))
    return dict(a=np.concatenate(out_a), b=np.concatenate(out_b), obj=np.concatenate(out_o), kind=np.concatenate(out_k),
                hole=np.concatenate(out_h), turn=np.concatenate(out_t))
