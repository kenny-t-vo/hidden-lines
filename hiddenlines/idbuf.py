"""What a hidden-line drawing sees, decided from the faces of rhino/hidden_lines.py's meshes through an ID buffer, for
kit.py hidden-lines under a request's "visibility": "faces" (docs/hidden-lines-plan.md, stage 1). hiddenlines/hidden.py
hands it the projected triangles and the lines that may be drawn, and takes back each line's seen stretches.

  raster  the triangles of the groups that hide, those on TEXTURE left out (a roof's tiles do not hide the roof's own
          edges), at R_PX pixels a point over the frame: each pixel centre's nearest triangle. A pixel centre on an edge
          two triangles share goes to one of them. A triangle is turned to the camera if it is wound anticlockwise on
          the page. It is held a tile of TILE_PX pixels at a time (Buffer)
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
takes half a megabyte. The raster, the queries and the halving run on nw workers, numba's thread count, which the
caller passes (a compiled function that reads it is not cached): worker w takes runs w, w + nw, ... of RUN points or
pieces, or of ROW_RUN rows, and each answer is the one a single worker gives.
"""
import math, os
from collections import OrderedDict
from pathlib import Path

os.environ.setdefault('NUMBA_CACHE_DIR', str(Path.home() / '.cache' / 'kit-numba'))

import numpy as np
from numba import get_num_threads, njit, prange

R_PX = 4.0                                             # pixels a point on the page
STEP_PT = 0.25                                         # between a line's samples
HALVINGS = 10                                          # a step halved to under a thousandth of it
CELL_PX = 8                                            # the exact query's cells, doubled while they would hold more
CELL_ITEMS = 200_000_000                               # entries than this
TILE_PX = 4096                                         # the raster's tiles a side, to a whole number of cells
APRON_PX = 2                                           # pixels round a tile held with it, fewer than a cell's
TILE_CACHE = 512 << 20                                 # bytes of tiles kept between queries: an A0 sheet's 514 MB
RUN = 64                                               # points or pieces a run, the runs dealt round the workers
ROW_RUN = 8                                            # the raster's rows a run, dealt the same way
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


@njit(cache=True, parallel=True)
def _raster(P, ts, persp, s, tri, ox, oy, depth, nw):
    """the nearest of the triangles ts of P (m x 3 x 3) at each pixel centre of tri, the frame's pixels from (ox, oy)
    on, s pixels a unit; depth, tri's shape, is written over. Each of nw workers takes every triangle in order over
    its own rows"""
    ny, nx = tri.shape
    depth[:, :] = -np.inf
    for worker in prange(nw):
        for t in ts:
            x0, y0, z0 = P[t, 0, 0] * s, P[t, 0, 1] * s, P[t, 0, 2]
            x1, y1, z1 = P[t, 1, 0] * s, P[t, 1, 1] * s, P[t, 1, 2]
            x2, y2, z2 = P[t, 2, 0] * s, P[t, 2, 1] * s, P[t, 2, 2]
            A = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if A == 0.0:
                continue
            if A < 0.0:                                # wound clockwise as seen: a back face, rasterized reversed
                x1, y1, z1, x2, y2, z2 = x2, y2, z2, x1, y1, z1
                A = -A
            i0 = max(int(math.floor(min(x0, x1, x2) - 0.5)), ox)
            i1 = min(int(math.ceil(max(x0, x1, x2) - 0.5)), ox + nx - 1)
            j0 = max(int(math.floor(min(y0, y1, y2) - 0.5)), oy)
            j1 = min(int(math.ceil(max(y0, y1, y2) - 0.5)), oy + ny - 1)
            if i0 > i1 or j0 > j1:
                continue
            # two triangles sharing an edge run it in opposite directions: a pixel centre exactly on it goes to the one
            # for which it runs down, or right when level
            e0 = (y2 - y1) < 0 or ((y2 - y1) == 0 and (x2 - x1) > 0)
            e1 = (y0 - y2) < 0 or ((y0 - y2) == 0 and (x0 - x2) > 0)
            e2 = (y1 - y0) < 0 or ((y1 - y0) == 0 and (x1 - x0) > 0)
            r0, r1 = (j0 - oy) // ROW_RUN, (j1 - oy) // ROW_RUN
            for r in range(r0 + (worker - r0) % nw, r1 + 1, nw):
                for j in range(max(j0, oy + r * ROW_RUN), min(j1 + 1, oy + (r + 1) * ROW_RUN)):
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
                        if zz > depth[j - oy, i - ox]:
                            depth[j - oy, i - ox] = zz
                            tri[j - oy, i - ox] = t


@njit(cache=True)
def _window(P, ts, s, x0, x1, y0, y1):
    """the pixels of [x0, x1) x [y0, y1) that the boxes of the triangles ts reach as _raster takes them: (i0, i1, j0,
    j1), none where i0 >= i1 or j0 >= j1"""
    i0, i1, j0, j1 = x1, x0, y1, y0
    for t in ts:
        a0 = max(int(math.floor(min(P[t, 0, 0] * s, P[t, 1, 0] * s, P[t, 2, 0] * s) - 0.5)), x0)
        a1 = min(int(math.ceil(max(P[t, 0, 0] * s, P[t, 1, 0] * s, P[t, 2, 0] * s) - 0.5)), x1 - 1)
        b0 = max(int(math.floor(min(P[t, 0, 1] * s, P[t, 1, 1] * s, P[t, 2, 1] * s) - 0.5)), y0)
        b1 = min(int(math.ceil(max(P[t, 0, 1] * s, P[t, 1, 1] * s, P[t, 2, 1] * s) - 0.5)), y1 - 1)
        if a0 <= a1 and b0 <= b1:
            i0, i1, j0, j1 = min(i0, a0), max(i1, a1 + 1), min(j0, b0), max(j1, b1 + 1)
    return i0, i1, j0, j1


@njit(cache=True)
def _px_fill(tri, ox, oy, x0, x1, y0, y1, n, px, p0, q0):
    """px[q - q0, p - p0] = pixel (n // 2 + n p, n // 2 + n q) of tri, the frame's pixels from (ox, oy) on, for those
    in [x0, x1) x [y0, y1)"""
    h, w = tri.shape
    a0, a1, b0, b1 = max(x0, ox), min(x1, ox + w), max(y0, oy), min(y1, oy + h)
    for q in range(max(-(-(b0 - n // 2) // n), q0), min(-(-(b1 - n // 2) // n), q0 + px.shape[0])):
        for p in range(max(-(-(a0 - n // 2) // n), p0), min(-(-(a1 - n // 2) // n), p0 + px.shape[1])):
            px[q - q0, p - p0] = tri[n // 2 + n * q - oy, n // 2 + n * p - ox]


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
def _cell_box(P, t, s, cs):
    """the cells of cs pixels that triangle t's box meets: (i0, i1, j0, j1), inclusive"""
    return (int(math.floor(min(P[t, 0, 0], P[t, 1, 0], P[t, 2, 0]) * s / cs)),
            int(math.floor(max(P[t, 0, 0], P[t, 1, 0], P[t, 2, 0]) * s / cs)),
            int(math.floor(min(P[t, 0, 1], P[t, 1, 1], P[t, 2, 1]) * s / cs)),
            int(math.floor(max(P[t, 0, 1], P[t, 1, 1], P[t, 2, 1]) * s / cs)))


@njit(cache=True)
def _bin_total(P, use, s, cs, cnx, cny):
    """the entries of the frame's cnx x cny cells of cs pixels: each used triangle in every cell its box meets"""
    n = 0
    for t in range(P.shape[0]):
        if not use[t]:
            continue
        i0, i1, j0, j1 = _cell_box(P, t, s, cs)
        if i1 < 0 or j1 < 0 or i0 >= cnx or j0 >= cny:
            continue
        n += (min(i1, cnx - 1) - max(i0, 0) + 1) * (min(j1, cny - 1) - max(j0, 0) + 1)
    return n


@njit(cache=True)
def _bin_count(P, ts, s, cs, cx0, cy0, cbw, cbh, count):
    """each triangle of ts counted in every cell of cs pixels its box meets, of the cbw x cbh cells from (cx0, cy0)"""
    for t in ts:
        i0, i1, j0, j1 = _cell_box(P, t, s, cs)
        for j in range(max(j0, cy0), min(j1, cy0 + cbh - 1) + 1):
            for i in range(max(i0, cx0), min(i1, cx0 + cbw - 1) + 1):
                count[(j - cy0) * cbw + i - cx0] += 1


@njit(cache=True)
def _bin_fill(P, ts, s, cs, cx0, cy0, cbw, cbh, start, items):
    at = start[:-1].copy()
    for t in ts:
        i0, i1, j0, j1 = _cell_box(P, t, s, cs)
        for j in range(max(j0, cy0), min(j1, cy0 + cbh - 1) + 1):
            for i in range(max(i0, cx0), min(i1, cx0 + cbw - 1) + 1):
                c = (j - cy0) * cbw + i - cx0
                items[at[c]] = t
                at[c] += 1


@njit(cache=True)
def _tile_span(P, t, s, cs, nx, ny, cnx, cny, cpt, tpx, ntx, nty):
    """the tiles of tpx pixels, cpt cells, that triangle t can reach: its box's pixels on the frame within APRON_PX of
    a tile, or its cells on the grid within a cell of a tile's own: (a0, a1, b0, b1), inclusive, none where a0 > a1 or
    b0 > b1"""
    a0, a1, b0, b1 = ntx, -1, nty, -1
    i0 = max(int(math.floor(min(P[t, 0, 0] * s, P[t, 1, 0] * s, P[t, 2, 0] * s) - 0.5)), 0)
    i1 = min(int(math.ceil(max(P[t, 0, 0] * s, P[t, 1, 0] * s, P[t, 2, 0] * s) - 0.5)), nx - 1)
    j0 = max(int(math.floor(min(P[t, 0, 1] * s, P[t, 1, 1] * s, P[t, 2, 1] * s) - 0.5)), 0)
    j1 = min(int(math.ceil(max(P[t, 0, 1] * s, P[t, 1, 1] * s, P[t, 2, 1] * s) - 0.5)), ny - 1)
    if i0 <= i1 and j0 <= j1:
        a0, a1 = (i0 - APRON_PX) // tpx, (i1 + APRON_PX) // tpx
        b0, b1 = (j0 - APRON_PX) // tpx, (j1 + APRON_PX) // tpx
    i0, i1, j0, j1 = _cell_box(P, t, s, cs)
    i0, i1, j0, j1 = max(i0, 0), min(i1, cnx - 1), max(j0, 0), min(j1, cny - 1)
    if i0 <= i1 and j0 <= j1:
        a0, a1 = min(a0, (i0 - 1) // cpt), max(a1, (i1 + 1) // cpt)
        b0, b1 = min(b0, (j0 - 1) // cpt), max(b1, (j1 + 1) // cpt)
    return max(a0, 0), min(a1, ntx - 1), max(b0, 0), min(b1, nty - 1)


@njit(cache=True)
def _tile_count(P, use, s, cs, nx, ny, cnx, cny, cpt, tpx, ntx, nty, count):
    """each used triangle counted in every tile it can reach"""
    for t in range(P.shape[0]):
        if not use[t]:
            continue
        a0, a1, b0, b1 = _tile_span(P, t, s, cs, nx, ny, cnx, cny, cpt, tpx, ntx, nty)
        for b in range(b0, b1 + 1):
            for a in range(a0, a1 + 1):
                count[b * ntx + a] += 1


@njit(cache=True)
def _tile_fill(P, use, s, cs, nx, ny, cnx, cny, cpt, tpx, ntx, nty, start, items):
    at = start[:-1].copy()
    for t in range(P.shape[0]):
        if not use[t]:
            continue
        a0, a1, b0, b1 = _tile_span(P, t, s, cs, nx, ny, cnx, cny, cpt, tpx, ntx, nty)
        for b in range(b0, b1 + 1):
            for a in range(a0, a1 + 1):
                items[at[b * ntx + a]] = t
                at[b * ntx + a] += 1


@njit(cache=True)
def _tile_of(x, y, s, nx, ny, cnx, cny, cs, tpx, ntx):
    """the tile a point is queried in, that of the pixel its queries centre on, clamped to the frame (nx x ny pixels,
    cnx x cny cells of cs), and that pixel: (tile, i, j), the tile -1 for a point whose 3 x 3 pixels are off the frame
    and whose cell is off the grid, which reads nothing"""
    i = int(math.floor(x * s))
    j = int(math.floor(y * s))
    if (i < -1 or j < -1 or i > nx or j > ny) and (i < 0 or j < 0 or i >= cnx * cs or j >= cny * cs):
        return -1, i, j
    i, j = min(max(i, 0), nx - 1), min(max(j, 0), ny - 1)
    return j // tpx * ntx + i // tpx, i, j


@njit(cache=True)
def _tile_counts(X, Y, s, nx, ny, cnx, cny, cs, tpx, ntx, count):
    """the points X, Y queried in each tile c, in count[c + 1]; those that read nothing in count[0]"""
    for q in range(X.shape[0]):
        count[_tile_of(X[q], Y[q], s, nx, ny, cnx, cny, cs, tpx, ntx)[0] + 1] += 1


@njit(cache=True)
def _better(zt, fc, bz, bf, tie):
    """is a surface at depth zt facing fc nearer than the best so far: by more than tie, or level within it and turned
    to the camera where the best is not (a capped solid standing on the ground: its back face at the foot of its walls
    would hide the ground's edge there on some samples and not others)"""
    return zt > bz + tie or (zt >= bz - tie and (fc > bf or (fc == bf and zt > bz)))


@njit(cache=True)
def _nearest(P, persp, s, cs, cnx, cny, start, items, cx0, cy0, cbw, x, y, tie):
    """the triangle nearest the camera covering (x, y), of all those in its cell: (t or -1, depth, facing); the cells
    held are a block cbw cells wide from cell (cx0, cy0) of the frame's cnx x cny"""
    ci = int(math.floor(x * s / cs))
    cj = int(math.floor(y * s / cs))
    best, bz, bf = -1, -np.inf, 1
    if ci < 0 or cj < 0 or ci >= cnx or cj >= cny or items.shape[0] == 0:
        return best, bz, bf
    c = (cj - cy0) * cbw + ci - cx0
    for q in range(start[c], start[c + 1]):
        zt, fc = _covers(P, items[q], x, y, persp)
        if zt > -np.inf and (best < 0 or _better(zt, fc, bz, bf, tie)):
            best, bz, bf = items[q], zt, fc
    return best, bz, bf


@njit(cache=True)
def _exact(tri, ox, oy, start, items, cx0, cy0, cbw, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a, tol_b,
           planes, cs, cnx, cny, x, y, z):
    """is the point seen, against the nearest triangle covering it: of those the 3 x 3 pixels round it hold, or, where
    one of them would hide it but does not reach it (an edge of something in front is near: a face folded over
    another, a sliver), of all those in its cell. tri holds the frame's pixels from (ox, oy) on that any triangle
    reaches round the point"""
    tol = tol_a + tol_b * abs(z)
    oc = _on_plane(x, y, z, planes, persp, hx, hy, f, L, sy, tol)
    h, w = tri.shape
    i = int(math.floor(x * s)) - ox
    j = int(math.floor(y * s)) - oy
    best, bz, bf = -1, -np.inf, 1
    edge = False
    for dj in range(-1, 2):
        for di in range(-1, 2):
            ii, jj = i + di, j + dj
            if ii < 0 or jj < 0 or ii >= w or jj >= h:
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
        best, bz, bf = _nearest(P, persp, s, cs, cnx, cny, start, items, cx0, cy0, cbw, x, y, delta)
    if best < 0:
        return True
    return _sees(best, bf, x, y, z, P, tri_o, cap_o, persp, hx, hy, f, L, sy, delta, tol, oc)


@njit(cache=True, parallel=True)
def _exact_all(c, tri, ox, oy, start, items, cx0, cy0, cbw, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s, delta, tol_a,
               tol_b, planes, cs, cnx, cny, nx, ny, tpx, ntx, X, Y, Z, out, nw):
    """_exact for the points queried in tile c"""
    n = X.shape[0]
    nruns = (n + RUN - 1) // RUN
    for worker in prange(nw):
        for r in range(worker, nruns, nw):
            for q in range(r * RUN, min(r * RUN + RUN, n)):
                if _tile_of(X[q], Y[q], s, nx, ny, cnx, cny, cs, tpx, ntx)[0] == c:
                    out[q] = _exact(tri, ox, oy, start, items, cx0, cy0, cbw, P, tri_o, cap_o, persp, hx, hy, f, L, sy,
                                    s, delta, tol_a, tol_b, planes, cs, cnx, cny, X[q], Y[q], Z[q])


@njit(cache=True, parallel=True)
def _front_all(c, tri, ox, oy, start, items, cx0, cy0, cbw, P, persp, s, cs, cnx, cny, nx, ny, tpx, ntx, delta, X, Y,
               out, nw):
    """the triangle nearest the camera covering each point queried in tile c, as _exact finds it, -1 for none"""
    h, w = tri.shape
    n = X.shape[0]
    nruns = (n + RUN - 1) // RUN
    for worker in prange(nw):
        for r in range(worker, nruns, nw):
            for q in range(r * RUN, min(r * RUN + RUN, n)):
                if _tile_of(X[q], Y[q], s, nx, ny, cnx, cny, cs, tpx, ntx)[0] != c:
                    continue
                x, y = X[q], Y[q]
                i = int(math.floor(x * s)) - ox
                j = int(math.floor(y * s)) - oy
                best, bz, bf = -1, -np.inf, 1
                for dj in range(-1, 2):
                    for di in range(-1, 2):
                        ii, jj = i + di, j + dj
                        if ii < 0 or jj < 0 or ii >= w or jj >= h:
                            continue
                        t = tri[jj, ii]
                        if t < 0 or t == best:
                            continue
                        zt, fc = _covers(P, t, x, y, persp)
                        if zt > -np.inf and (best < 0 or _better(zt, fc, bz, bf, delta)):
                            best, bz, bf = t, zt, fc
                if best < 0:
                    best, bz, bf = _nearest(P, persp, s, cs, cnx, cny, start, items, cx0, cy0, cbw, x, y, delta)
                out[q] = best


@njit(cache=True, parallel=True)
def _front_cell_all(c, start, items, cx0, cy0, cbw, P, persp, s, cs, cnx, cny, nx, ny, tpx, ntx, delta, X, Y, out, nw):
    """the triangle nearest the camera covering each point queried in tile c of all those in its cell, the pixels not
    consulted: a triangle narrower than a pixel that wins none of them is found too"""
    n = X.shape[0]
    nruns = (n + RUN - 1) // RUN
    for worker in prange(nw):
        for r in range(worker, nruns, nw):
            for q in range(r * RUN, min(r * RUN + RUN, n)):
                if _tile_of(X[q], Y[q], s, nx, ny, cnx, cny, cs, tpx, ntx)[0] == c:
                    out[q] = _nearest(P, persp, s, cs, cnx, cny, start, items, cx0, cy0, cbw, X[q], Y[q], delta)[0]


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
def _along(A, B, e, m, persp):
    """the point at parameter m on piece e, A -> B (frame x, y, camera z)"""
    x = A[e, 0] + m * (B[e, 0] - A[e, 0])
    y = A[e, 1] + m * (B[e, 1] - A[e, 1])
    if persp:
        z = 1.0 / ((1.0 - m) / A[e, 2] + m / B[e, 2])
    else:
        z = A[e, 2] + m * (B[e, 2] - A[e, 2])
    return x, y, z


@njit(cache=True)
def _halve_counts(A, B, ta, tb, it, persp, s, nx, ny, cnx, cny, cs, tpx, ntx, count):
    """the pieces still halving whose next point is queried in each tile c, in count[c + 1]; those whose next point
    reads nothing in count[0]"""
    for e in range(A.shape[0]):
        if it[e] < HALVINGS:
            x, y, z = _along(A, B, e, 0.5 * (ta[e] + tb[e]), persp)
            count[_tile_of(x, y, s, nx, ny, cnx, cny, cs, tpx, ntx)[0] + 1] += 1


@njit(cache=True, parallel=True)
def _halve(c, q0, q1, r0, r1, tri, ox, oy, start, items, cx0, cy0, cbw, P, tri_o, cap_o, persp, hx, hy, f, L, sy, s,
           delta, tol_a, tol_b, planes, cs, cnx, cny, nx, ny, tpx, ntx, A, B, ta, tb, it, cell, out, nw):
    """for each piece A -> B (frame x, y, camera z) whose next point is queried in tile c, the point between parameters
    ta (seen) and tb (not) where it turns, by halving: the last parameter seen, in out once it[e], the halvings done,
    reaches HALVINGS. The tile goes on with a piece while its point centres on a pixel in q0..q1 x r0..r1 or reads
    nothing, and leaves it at the next point for the tile that holds it; where cell is set, each point is judged against
    every triangle in its cell, as a sample between an outline's crossings was"""
    n = A.shape[0]
    nruns = (n + RUN - 1) // RUN
    for worker in prange(nw):
        for r in range(worker, nruns, nw):
            for e in range(r * RUN, min(r * RUN + RUN, n)):
                if it[e] >= HALVINGS:
                    continue
                a, b = ta[e], tb[e]
                x, y, z = _along(A, B, e, 0.5 * (a + b), persp)
                if _tile_of(x, y, s, nx, ny, cnx, cny, cs, tpx, ntx)[0] != c:
                    continue
                while it[e] < HALVINGS:
                    m = 0.5 * (a + b)
                    x, y, z = _along(A, B, e, m, persp)
                    k, i, j = _tile_of(x, y, s, nx, ny, cnx, cny, cs, tpx, ntx)
                    if k >= 0 and not (q0 <= i <= q1 and r0 <= j <= r1):
                        break
                    if cell[e]:
                        t, zt, fc = _nearest(P, persp, s, cs, cnx, cny, start, items, cx0, cy0, cbw, x, y, delta)
                        tol = tol_a + tol_b * abs(z)
                        ok = t < 0 or _sees(t, fc, x, y, z, P, tri_o, cap_o, persp, hx, hy, f, L, sy, delta, tol,
                                            _on_plane(x, y, z, planes, persp, hx, hy, f, L, sy, tol))
                    else:
                        ok = _exact(tri, ox, oy, start, items, cx0, cy0, cbw, P, tri_o, cap_o, persp, hx, hy, f, L, sy,
                                    s, delta, tol_a, tol_b, planes, cs, cnx, cny, x, y, z)
                    if ok:
                        a = m
                    else:
                        b = m
                    it[e] += 1
                ta[e], tb[e] = a, b
                if it[e] >= HALVINGS:
                    out[e] = a


def _f64(a):
    return np.ascontiguousarray(a, dtype=np.float64)


# a tile with no triangle: (tri, ox, oy, start, items, cx0, cy0, cbw) as Buffer._tile gives them
_NONE = (np.full((0, 0), -1, dtype=np.int32), 0, 0, np.zeros(1, dtype=np.int64), np.zeros(0, dtype=np.int32), 0, 0, 0)


class Buffer:
    """the frame rasterized a tile at a time: at each pixel centre the index into P of the triangle nearest the camera,
    -1 for none, row j the page's y from j / R_PX to (j + 1) / R_PX pt from its foot, column i its x. The tiles are
    squares of the frame's pixels, TILE_PX a side to a whole number of cells; each is rasterized over as much of itself
    and the APRON_PX pixels round it as its triangles reach, with its cells and those round it, so a pixel keeps its
    centre, its edge rule and its depth comparison. A point is queried in the tile of the pixel it centres on, clamped
    to the frame, and a halving goes on in the next tile where its point leaves one, so every query answers as one
    raster of the frame would. Tiles are kept for the next query while they come to TILE_CACHE bytes.
      P       the triangles (m x 3 x 3), frame x and y with z, or 1 / z in a perspective; tri_o each one's object
      use     the triangles that hide
      view    (hx, hy, f, L, sy): the frame's half width and height, the true-length factor, a perspective's focal
              depth and shift (0 in a parallel view)
      k       pt a frame unit; W, H the frame in pt
      delta   depth along the view within which a surface in front still shows what lies on it
      tol_pt  the tolerance square to the surface, on the page; err a length added to it in camera units (the
              meshes' float32 rounding)
      planes  the clip planes in camera space, rows of unit normal and offset
      cap_o   per object: a closed solid whose back faces stand for its missing cut face
    px is the raster at a pixel centre a point, which the depth bands read: pixel (n // 2 + n p, n // 2 + n q), n R_PX
    rounded, at px[q - px_at[1], p - px_at[0]], over the box of the pixels the triangles reach"""

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
        use = np.ascontiguousarray(use, dtype=np.bool_)
        # 16 pixels a square point of page; a tile's raster is 4 bytes a pixel, and 8 more in _raster's depth while it
        # runs, 0.2 GB for a whole tile
        self.nx, self.ny = int(math.ceil(W * R_PX)), int(math.ceil(H * R_PX))
        self.cs = float(CELL_PX)                       # the triangles by cells of cs pixels, for the exact query
        while True:
            self.cnx = int(math.ceil(self.nx / self.cs))
            self.cny = int(math.ceil(self.ny / self.cs))
            if _bin_total(self.P, use, self.s, self.cs, self.cnx, self.cny) <= CELL_ITEMS or self.cs >= 1024:
                break
            self.cs *= 2
        self.cpt = max(1, TILE_PX // int(self.cs))     # cells a tile's side
        self.tpx = self.cpt * int(self.cs)
        self.ntx, self.nty = -(-self.nx // self.tpx), -(-self.ny // self.tpx)
        span = (self.s, self.cs, self.nx, self.ny, self.cnx, self.cny, self.cpt, self.tpx, self.ntx, self.nty)
        count = np.zeros(self.ntx * self.nty, dtype=np.int64)
        _tile_count(self.P, use, *span, count)
        self.tstart = np.zeros(len(count) + 1, dtype=np.int64)
        np.cumsum(count, out=self.tstart[1:])
        self.titems = np.zeros(int(self.tstart[-1]), dtype=np.int32)
        _tile_fill(self.P, use, *span, self.tstart, self.titems)
        self.cache, self.held, self.made = OrderedDict(), 0, 0     # tiles kept, their bytes, tiles rasterized
        self.depth = None                              # _raster's depth, kept while a tile may be rasterized again
        n = max(1, int(round(R_PX)))
        i0, i1, j0, j1 = self.nx, 0, self.ny, 0         # the pixels the triangles reach, each tile's within it
        for c in range(len(count)):
            if count[c]:
                x0, y0 = c % self.ntx * self.tpx, c // self.ntx * self.tpx
                w = _window(self.P, self.titems[self.tstart[c]:self.tstart[c + 1]], self.s, x0,
                            min(x0 + self.tpx, self.nx), y0, min(y0 + self.tpx, self.ny))
                if w[0] < w[1] and w[2] < w[3]:
                    i0, i1, j0, j1 = min(i0, w[0]), max(i1, w[1]), min(j0, w[2]), max(j1, w[3])
        p0, p1 = max(-(-(i0 - n // 2) // n), 0), max(-(-(i1 - n // 2) // n), 0)
        q0, q1 = max(-(-(j0 - n // 2) // n), 0), max(-(-(j1 - n // 2) // n), 0)
        self.px_at = (p0, q0)
        self.px = np.full((q1 - q0, p1 - p0) if p1 > p0 and q1 > q0 else (0, 0), -1, dtype=np.int32)
        for c in range(len(count) if self.px.size else 0):
            if count[c]:
                x0, y0 = c % self.ntx * self.tpx, c // self.ntx * self.tpx
                _px_fill(*self._tile(c)[:3], x0, min(x0 + self.tpx, self.nx), y0, min(y0 + self.tpx, self.ny), n,
                         self.px, p0, q0)
        if len(self.cache) == int((count > 0).sum()):
            self.depth = None

    def tols(self, tol_pt):
        """the tolerance square to the surface, tol_pt on the page, as the exact query takes it: (tol_a, tol_b)"""
        if self.persp:
            return self.err, float(tol_pt) / (self.k * self.L)
        return float(tol_pt) / (self.k * self.f) + self.err, 0.0

    def _tile(self, c):
        """tile c rasterized, with its cells: (tri, ox, oy, start, items, cx0, cy0, cbw), tri the frame's pixels from
        (ox, oy) on that its triangles reach, start and items the triangles of each cell (as _bin_fill fills them) of
        a block cbw cells wide from cell (cx0, cy0)"""
        if c in self.cache:
            self.cache.move_to_end(c)
            return self.cache[c]
        ts = self.titems[self.tstart[c]:self.tstart[c + 1]]
        a, b = c % self.ntx, c // self.ntx
        x0, y0 = a * self.tpx, b * self.tpx
        i0, i1, j0, j1 = _window(self.P, ts, self.s, max(x0 - APRON_PX, 0), min(x0 + self.tpx + APRON_PX, self.nx),
                                 max(y0 - APRON_PX, 0), min(y0 + self.tpx + APRON_PX, self.ny))
        shape = (j1 - j0, i1 - i0) if i1 > i0 and j1 > j0 else (0, 0)
        self._room(4 * shape[0] * shape[1])
        tri = np.full(shape, -1, dtype=np.int32)
        if self.depth is None:                         # for the largest window a tile can have
            self.depth = np.empty(min(self.tpx + 2 * APRON_PX, self.nx) * min(self.tpx + 2 * APRON_PX, self.ny))
        _raster(self.P, ts, self.persp, self.s, tri, i0, j0, self.depth[:tri.size].reshape(shape), get_num_threads())
        cx0, cy0 = max(a * self.cpt - 1, 0), max(b * self.cpt - 1, 0)
        cbw, cbh = min((a + 1) * self.cpt + 1, self.cnx) - cx0, min((b + 1) * self.cpt + 1, self.cny) - cy0
        count = np.zeros(cbw * cbh, dtype=np.int64)
        _bin_count(self.P, ts, self.s, self.cs, cx0, cy0, cbw, cbh, count)
        start = np.zeros(len(count) + 1, dtype=np.int64)
        np.cumsum(count, out=start[1:])
        del count
        items = np.zeros(int(start[-1]), dtype=np.int32)
        _bin_fill(self.P, ts, self.s, self.cs, cx0, cy0, cbw, cbh, start, items)
        tile = (tri, i0, j0, start, items, cx0, cy0, cbw)
        self.made += 1
        self._room(tri.nbytes + start.nbytes + items.nbytes)
        self.cache[c] = tile
        self.held += tri.nbytes + start.nbytes + items.nbytes
        return tile

    def _room(self, nbytes):
        """the tiles kept let go, the longest unused first, till nbytes more come within TILE_CACHE"""
        while self.cache and self.held + nbytes > TILE_CACHE:
            t = self.cache.popitem(last=False)[1]
            self.held -= t[0].nbytes + t[3].nbytes + t[4].nbytes

    def _each(self, count, run):
        """run(c, tile) for each tile c with points to query (count[c + 1]), those kept first, and then for the points
        that read nothing (c -1) with no tile"""
        for c in sorted((c for c in range(len(count) - 1) if count[c + 1]), key=lambda c: c not in self.cache):
            run(c, self._tile(c) if self.tstart[c + 1] > self.tstart[c] else _NONE)
        if count[0]:
            run(-1, _NONE)

    def _grid(self):
        return self.s, self.nx, self.ny, self.cnx, self.cny, self.cs, self.tpx, self.ntx

    def _count(self, X, Y):
        count = np.zeros(self.ntx * self.nty + 1, dtype=np.int64)
        _tile_counts(X, Y, *self._grid(), count)
        return count

    def raster(self):
        """the frame's whole raster (ny x nx) from the tiles"""
        out = np.full((self.ny, self.nx), -1, dtype=np.int32)
        for c in range(self.ntx * self.nty):
            if self.tstart[c + 1] > self.tstart[c]:
                tri, ox, oy = self._tile(c)[:3]
                x0, y0 = c % self.ntx * self.tpx, c // self.ntx * self.tpx
                a0, a1 = max(x0, ox), min(x0 + self.tpx, ox + tri.shape[1])
                b0, b1 = max(y0, oy), min(y0 + self.tpx, oy + tri.shape[0])
                if a1 > a0 and b1 > b0:
                    out[b0:b1, a0:a1] = tri[b0 - oy:b1 - oy, a0 - ox:a1 - ox]
        return out

    def seen(self, X, Y, Z, tol_pt=None):
        """each point seen (_exact), within tol_pt square to the surface where given, else the buffer's"""
        out = np.zeros(len(X), dtype=np.bool_)
        X, Y, Z = _f64(X), _f64(Y), _f64(Z)
        tol = (self.tol_a, self.tol_b) if tol_pt is None else self.tols(tol_pt)
        self._each(self._count(X, Y), lambda c, T: _exact_all(
            c, *T, self.P, self.tri_o, self.cap_o, self.persp, self.hx, self.hy, self.f, self.L, self.sy, self.s,
            self.delta, *tol, self.planes, self.cs, self.cnx, self.cny, self.nx, self.ny, self.tpx, self.ntx, X, Y, Z,
            out, get_num_threads()))
        return out

    def front(self, X, Y):
        """the triangle nearest the camera over each point (an index into P, -1 for none): what hides a point the
        buffer does not see"""
        out = np.full(len(X), -1, dtype=np.int64)
        X, Y = _f64(X), _f64(Y)
        self._each(self._count(X, Y), lambda c, T: _front_all(
            c, *T, self.P, self.persp, self.s, self.cs, self.cnx, self.cny, self.nx, self.ny, self.tpx, self.ntx,
            self.delta, X, Y, out, get_num_threads()))
        return out

    def front_cell(self, X, Y):
        """the triangle nearest the camera over each point of all those in its cell (-1 for none), however narrow"""
        out = np.full(len(X), -1, dtype=np.int64)
        X, Y = _f64(X), _f64(Y)
        self._each(self._count(X, Y), lambda c, T: _front_cell_all(
            c, *T[3:], self.P, self.persp, self.s, self.cs, self.cnx, self.cny, self.nx, self.ny, self.tpx, self.ntx,
            self.delta, X, Y, out, get_num_threads()))
        return out

    def sees(self, T, X, Y, Z):
        """each point seen past the triangle T given for it (-1 for none) by the same rules: a check of the buffer
        against an exact query of the nearest triangle"""
        out = np.zeros(len(X), dtype=np.bool_)
        _sees_given(np.ascontiguousarray(T, dtype=np.int64), self.P, self.tri_o, self.cap_o, self.persp, self.hx,
                    self.hy, self.f, self.L, self.sy, self.s, self.delta, self.tol_a, self.tol_b, self.planes,
                    _f64(X), _f64(Y), _f64(Z), out)
        return out

    def halve(self, A, B, tk, tl, cell=None):
        """the last parameter seen between tk and tl on each piece A -> B (n x 3); where cell is set, against every
        triangle in each point's cell"""
        out = np.zeros(len(A), dtype=np.float64)
        A, B = _f64(A), _f64(B)
        ta, tb = np.array(tk, dtype=np.float64), np.array(tl, dtype=np.float64)   # each piece's halving so far
        it = np.zeros(len(A), dtype=np.int64)
        cell = np.zeros(len(A), dtype=np.bool_) if cell is None else np.ascontiguousarray(cell, dtype=np.bool_)
        m = APRON_PX - 1                               # a point centred this far past a tile's pixels is held in it

        def run(c, T):
            x0, y0 = c % self.ntx * self.tpx, c // self.ntx * self.tpx
            q = (x0 - m, x0 + self.tpx - 1 + m, y0 - m, y0 + self.tpx - 1 + m) if c >= 0 else (0, -1, 0, -1)
            _halve(c, *q, *T, self.P, self.tri_o, self.cap_o, self.persp, self.hx, self.hy, self.f, self.L, self.sy,
                   self.s, self.delta, self.tol_a, self.tol_b, self.planes, self.cs, self.cnx, self.cny, self.nx,
                   self.ny, self.tpx, self.ntx, A, B, ta, tb, it, cell, out, get_num_threads())
        while True:
            count = np.zeros(self.ntx * self.nty + 1, dtype=np.int64)
            _halve_counts(A, B, ta, tb, it, self.persp, *self._grid(), count)
            if not count.any():
                return out
            self._each(count, run)


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
