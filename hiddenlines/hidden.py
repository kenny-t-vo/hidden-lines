"""A model's exact hidden-line drawing, from rhino/hidden_lines.py's export, as a layered SVG and DXF that pass lint.

  kit.py hidden-lines REQUEST.json [--rhino OUT.json] [--explain REDLINE.md] [--check CHECKS.json]
  kit.py hidden-lines --check CHECKS.json

The request (docs/commands.md, hidden-lines) names the scale, the view, the frame on paper and groups of the model's
layers, each with the kit layer its lines go on. rhino/hidden_lines.py, run in Rhino through the connector, writes
scene.json and meshes.bin into the request's out folder; this reads them and writes ID.svg, ID.dxf, ID.ai (Illustrator's
own document: a layer per layer, a sublayer per class, a global swatch per sublayer) and ID-report.json there. --rhino
also writes the drawing for rhino/hidden_lines.py to add to the model (for_rhino), which the HL alias asks for.
--explain also writes ID-fates.svg: the drawing's lines in grey over every line a pass took out, in a colour for each
reason, and the stretches the engine hid in blue; and for each note of a Redline markup of the drawing (its
redline.md) it prints what was taken out under the note and why, what the engine hid there and what is drawn.
--check runs the checks written from review notes (check_notes) on the drawing, writes ID-check.txt and, with
the notes' boxes, ID-notes/note-N.png: each note's mark beside the drawing at the same window (notes_sheet).

A request with clip planes draws a section or a plan cut, and one with view.lens_mm a perspective: the export's
points are then x L / -z and y L / -z on paper's scale, and every depth along a line or across a triangle is
interpolated as 1 / z, which is affine on paper where z is not.

  faces    with the request's "visibility": "faces" (else "engine", the default): what is seen is decided from the
           meshes through an ID buffer (hiddenlines/idbuf.py, faces_of), not from the engine's verdicts. The lines tried are
           every segment the engine found of a group that hides, visible, hidden ('under') or Duplicate ('dup'), but
           the cuts, and the meshes' own boundaries, silhouettes and creases, but a crease turning under 40 degrees on
           an object the export gives edge curves for (a fold of a curved wall's mesh is no edge of the model), where
           no line of the same object that
           is drawn (a stretch of the engine's the faces kept, or a cut) lies along them within near_pt on the page
           and 3 MESH_PT in depth (a silhouette's depth aside); each is kept where the buffer sees it, its ends found by
           halving, a
           stretch under near_pt of a line seen in part left out as a sliver. Where two of the meshes' outline edges
           cross a line under a step apart with no sample between, a sample between them is judged against every
           triangle in its cell, so an object narrower than a step in front of a line hides it. A run of samples hidden at the buffer's
           tolerance but seen within twice it takes its neighbours' where both are seen (flicker held off), and in an
           export the engine judged, a gap in a line it drew as visible, between seen samples, that only the line's own
           object's mesh hides is seen (the engine had the object's own surfaces; a curved wall's crease broken by a
           facet of the same wall). A
           Duplicate segment gives way where a
           seen Visible one lies along it as near: one edge drawn twice, by two objects (a pipe's elbow and the next
           tube)
           The revival of 'under' and the meshes' check below are not run; a group that does not hide, the cuts and
           the dashed classes keep the engine's visible segments
  under    what the engine hid of a drawn line is kept where the surface nearest the camera over it is behind it, or
           within twice the meshes' tolerance of it measured square to that surface: a curve drawn on a twisted roof,
           which the engine's cut face of that roof hid behind nothing (the model's tiles), an edge on another object's
           coplanar face. Where no mesh covers it, the engine is trusted; a stretch kept under near_pt is left out
  graph    every visible segment, clipped to the frame, noded by snap rounding on a grid hidden_lines.grid_pt wide
           on paper: crossings become shared nodes and lines lying on each other one edge that keeps all their sources.
           A line goes only where it would print wrong: a stretch the meshes see hidden (another object's surface in
           front of it, measured square to that surface, by more than 0.27 pt at the export's default tolerance), what
           lies inside a cut face, and doubles (below). Nothing is drawn that the model does not have : a line end left farther than lint's touch and nearer than its near_pt from other linework,
           as drawn, is run on along its own direction to the line it points at only where the export's lines (any,
           hidden and duplicate ones too) lie along the run-on within 1.5 grid steps, and within the grid is noded to
           it; a gap under lint's min_len_pt between it and a free end of the same object, each facing the other
           within 30 degrees, is closed (the only length drawn off the model); an end beside the lines it is near, its own line within 20 degrees of each and each to its
           side, not ahead (a double kept, a line converging on another), stays as the model has it (ends_beside);
           else it is cut back along its own path, as far as its junction or change of class, until it
           is clear of every other line by near_pt as drawn, and a line clear nowhere is taken whole. Its overshoot past a line
           it crosses is cut back, and a hair that leaves a line and stays within reach of it is taken out; each is
           listed with where it is in the model, and an end a line taken out frees is met in the same round. A line's
           own stretch until it first leaves the circle of near_pt round its end is the line itself and nothing to
           meet (a curve's next short edges); a stub under near_pt off a junction is cut back. A line's last stretch in
           another class
           than the line it goes on from is a path of its own to lint: with its end within near_pt of that line, it is
           cut back to it, unless it ends within near_pt of where it leaves and within 20 degrees, which the paths draw
           in that line's class
  doubles  decided by line, a line being a chain of drawn edges of one tier and weight, from the heaviest down: a cut,
           then a solid line, then a dashed one; its weight along its length; exact sources above the meshes' own
           edges; the nearer; the earlier group; the longer. A lesser line beside a heavier one as drawn, within lint's
           5 degrees of parallel, gives way only where its stroke lies inside the heavier one's, so nothing that prints
           apart is taken out. With simplify_doubles (the request's, false by default) it gives
           way under doubles_pt apart (lint's double_pt unless the request sets it; 0 for none), measured, and its
           parallel, between the two lines' sources before snap rounding, since the two print as one heavier line;
           a request's doubles_inside, from before, changes nothing. Either way: converging all along, closing or opening steadily at a degree or more, the two stay, meeting or not.
           Else where the gap closes onto the heavier line the lesser runs on along its own path to where they meet, a
           node of both or the first sample within touch as the model gives them ('in'). Where the gap stays wider, an
           even offset, it gives way under the threshold, each run decided whole, no cut under 2 pt and no kept stretch
           under 2 pt between two cuts, and nothing is joined onto the heavier line : a
           cut ends at the line's corner where the line on from it meets the heavier one, at the line's free end
           where the heavier line runs beside it all the way, or at a junction of the line within it, else it is not
           made and lint warns of a double; a closed line beside a heavier one all round gives way whole. A cut is
           made only where the line's outline stays closed and its junctions joined: a line left ending inside it
           meets the heavier line as drawn, inside its stroke, crossing it, or running into it along its own
           direction where the model's lines run on there (lands_on), else both lines stay. A sample with no heavier
           line beside it is never cut; a break under 1 pt in the heavier line between two cuts is bridged along it.
           A tile's line (a TEXTURE group's) ranks under any other line of its weight, and where one lies on another
           object's line the edge is that line's.
           A face between lines thinner than doubles_pt all but a speck (kept, one the strokes round it cover) keeps
           only its heaviest line, lines ranked whole, unless every line round it is one object's or a line left ending
           there would not meet the heaviest; kept, a line round it goes only where it lies inside the heaviest's stroke.
           The report counts both and the mode (doubles)
  classes  what lies either side of each edge, read from the meshes eps_pt off its middle, and its depth there, for the
           body its owner belongs to (a group, or the groups naming one body: a building's homes, cores and galleries):
             profile  the body against the paper or a surface behind it
             base     the body against the ground or another body, meeting it with no gap
             overlap  inside the body, a part in front of a part more than gap_m behind it; a step if less
             seam     inside the body, two of its objects meeting flush: two homes' shared wall
             crease   a fold or a line on one object
             line     a curve object (curbs, lot lines), and an object without a mesh (trees seen through)
             hidden   behind a surface, for a group marked hidden: dashed on HIDDEN
             above    in the half a clip plane takes away, seen from the plane, for a group marked above: dashed on
                      ABOVE (a plan's roof edges and beams). A dashed line gives way to a solid one, is not checked
                      against the meshes, bounds no fill, and a hidden one stays inside a cut
           Where two surfaces lie level, within three times the export's bias, the earlier group's is the one seen: a
           terrace on a roof, a gallery on a wall. With faces, an edge along the rim of an opening (idbuf.openings: a
           hole through a smooth patch of a mesh, or a pocket cut from its edge, a door, its rim convex) is the
           outline of the plane it is cut out of: a profile where the patch is turned to the camera, and where it is
           turned away (the reveal's far rim seen through) an overlap at most. A pocket that stops at a back face of
           the object within the reveal's depth is a recess, no opening, and its rim keeps its class by depth
             cut      on a clip plane. A closed solid's cut, of a group that hides and is drawn, is the export's
                      rings (from the model, exact and closed; where its clipped mesh's section runs over 0.1 pt off
                      them, more than the mesh's own error carried along the plane at the angle its face meets it
                      explains, the cut follows the mesh there and it is reported, kind 'ring-mismatch'), kept whole
                      past the frame and noded with the rest: its
                      edges polygonized, its region the faces inside an odd number of them, a body's regions merged
                      where they touch (as the survey merges walls and the posts that touch them), each region one
                      closed path on CUT in a sublayer for its body, at its first group's cut weight: as its weights
                      set it, heavy for a group on a cut layer and for the ground, a rung under heavy for a group on a
                      light layer (detail, furniture), else its profile weight. A lighter group in a heavier body (its
                      windows and doors, a roof's frame) is not massing: its cut is its own, closed, at its own cut
                      weight, in a sublayer for the group. A body's surfaces (walls, floors and roofs modelled as
                      surfaces, not closed solids) are cut where the cells of their section lines, as the graph holds
                      them (the engine's cut segments, Duplicate ones too, and the meshes' edges on the plane where it
                      left one out), are solid: where the surfaces round a cell face away from it, as the meshes'
                      normals at the plane say, or where the sides are mixed or not read and it is thinner than
                      hidden_lines.cut_surface_m all through; a line ending under near_pt short of another is run on
                      to it, and two skins whose free ends face away from each other are capped across within
                      cut_surface_m (solid_cells). A closed solid's outline counts as facing into the cell beside
                      it. A skin facing the way the skin beside it within cut_surface_m faces, toward it, is turned,
                      as is a thin wall's outer skin facing in; it is read the other way and reported (kind
                      'turned'). A cell the sides leave mixed and thicker than that is reported, not filled. A gap between parts of one body's cut narrower than twice its weight is closed, the white
                      between two outlines being thinner than either (a stair landing just off its wall), its new edge
                      noded into the graph and what lies in it taken out, so lines meet the cut as drawn; a wedge, the
                      gap closed by one new edge and tapering to a point from it, stays open (a valley's two skins). The massing,
                      the bodies cut heavy, runs on as one poché where their cuts touch or come within that gap (the
                      walls into a foundation block of the ground's), drawn as the earliest body's. In a parallel view
                      cut square to it, a region thinner than thin_cut.times_weight that weight all through is drawn
                      at thin_cut.share of it ('building cuts thin'), and one with a thick part keeps its weight whole,
                      the poché continuous. Where two cuts overlap, the earlier's is whole and the later's clipped and
                      reported. A group marked joints keeps its parts' outlines inside the merged cut, as lines on
                      OUTLINE in a sublayer of their own ('building joints'), the cut still one closed shape. A ring
                      that does not close is reported; a cut line that closes no region is drawn at the cut weight on
                      OUTLINE ('building open cuts'), since CUT holds closed paths, unless its group is neither on a
                      cut layer, the ground nor given a cut weight, when it is a line of its own group at its profile
                      weight
             earth    the ground's open sheets (a terrain, the top and bottom faces of a slab of ground) are cut as one
                      line, their top: on a vertical plane what lies under their section lines is earth (earth_under),
                      less the cut regions and what they enclose (a basement), and a cut line of theirs with earth
                      either side, and a line lying past the plane behind the earth, are taken out. A ground modelled
                      as a closed solid keeps its own cut
  weights  a class steps down the band's four weights, heavy to fine, from its group's profile weight by
           hidden_lines.steps; the profile weight is the role weight of the group's profile_layer, or of its layer, unless
           it sets profile_weight; a group's weights {class: band or pt} set a class outright. Each group's classes are
           sublayers of its layer, one weight each (data-weight on the sublayer, which lint checks), and its profiles
           and bases can go on another layer (profile_layer: the subject's OUTLINE). A group whose layer is a cut
           layer (CUT) is what the clip planes cut: its own lines are seen beyond the plane and go on BEYOND, as
           rhino/make2d_roles.py sends a cut source layer's visible curves there. With depth_bands_m (metres beyond the
           first clip plane, else beyond the subject's nearest drawn line) or depth_bands_share (those shares of how far
           the subject runs beyond it, context left out: with faces, the 95th percentile of its seen area's depth,
           else of its drawn edges'), a line within the first band is a weight heavier than
           its class, never heavier than its group's profile weight, one in the next keeps its class's weight, and one
           past each further edge is a weight lighter, each band on a distance leaf ('building overlaps::middle (3–10 m)').
           With crease_turns_deg, a crease
           whose faces turn by less than an angle listed is a weight lighter for each ('building creases under 20
           deg'). A group's weights are keyed by class, singular or plural ({"cuts": "heavy"})
  paths    a sublayer's edges chained through their nodes, straight on where three or more meet, closed where they
           close; a piece shorter than lint's min_len_pt standing free at both ends (a sliver seen between two things)
           is a stray, left out and counted. Decided on the grid, drawn from the model: each node is drawn where the
           export's lines through it meet, the least-squares point of its edges' own sources (a cut edge's section
           line, any other its owner's), a free end at its line's own end, held within 1.5 grid steps of the node; a
           cut region's corners likewise. Curves and poché run along the model's lines, not the grid's steps. An
           edge whose node is drawn further than that off its own source, where drawn straight to it the edge would
           leave the model's lines, runs along its source to the point nearest the node first
  model    the drawing held to the model, in the report's model (held_to_model): the drawn length further than 1.5 grid
           steps from every line of the export (off_pt: the gaps closed, else 0), and further
           than 0.01 pt (off_grid_pt: mostly lines the model gives twice a few hundredths of a point apart, drawn
           between them); each stretch of a line Rhino drew as visible that is not drawn, by reason (behind a face,
           under poché, a stray, a sliver, or what a pass took it out for), each reason by the object in front or the
           line given way to (named); and the length with no reason (unexplained_pt)
  fills    the faces between all visible lines, those of groups that hide but are not drawn among them, each filled as
           the surface seen in it says: its group's fill, or its fills by source layer pattern, on fill_layer (GROUND
           unless the group names another); a face whose middle sees another fill than its own point does is listed,
           a boundary between two fills that no line marks. A cut region is not filled
  verify   the drawing as drawn, against its own cut regions shrunk by 0.01 pt: the length of line inside them, but
           the joints and the dashed hidden lines, which lie there on purpose, and where its longest piece is in the
           model (verify.inside_cut, printed with the cuts); 0 unless a pass after the cuts' put a line back inside one
"""
import fnmatch, json, math, re, time
from collections import defaultdict
from pathlib import Path
from archkit.project import load, PT_PER_MM

LADDER = ('heavy', 'medium', 'light', 'fine')
MESH_PT = 0.05                                         # rhino/hidden_lines.py's mesh tolerance, on paper
CHUNK = 1 << 18                                        # vertices, triangles or points taken at a time, not all at once
PLURAL = {'profile': 'profiles', 'base': 'bases', 'overlap': 'overlaps', 'step': 'steps', 'seam': 'seams',
          'crease': 'creases', 'line': 'lines', 'cut': 'cuts', 'hidden': 'hidden', 'above': 'above'}
DASHED = {'hidden': 'HIDDEN', 'above': 'ABOVE'}     # a dashed class: the layer its lines go on
RING = ('CUT', None, None)                             # an edge of a cut that closes: drawn with its body's cut regions
UNITS = {1.0: 'mm', 10.0: 'cm', 1000.0: 'm', 25.4: 'in', 304.8: 'ft'}
# a fault the export reports on an object, as its issue begins: its kind, the key rhino/hl.py's FAULTS says it by in
# plain words; the issue text is read, so an export older than the kinds gets them too
FAULT_KINDS = (('invalid', r'invalid (brep|mesh)'), ('open', r'open (polysurface|mesh)'),
               ('self-crossing-face', r'\d+ faces cross their own'), ('non-manifold', r'\d+ non-manifold|non-manifold mesh'),
               ('inside-out', r'inside out'), ('runs-into', r'runs into'), ('lies-on', r'lies on'),
               ('unjoined-edge', r'shares an edge with'), ('union-failed', r'union with'), ('cut-open', r'the cut by clip plane'),
               ('nearly-planar', r'\d+ faces nearly planar'), ('creased', r'(\d+ faces )?creased inside'),
               ('short-edges', r'\d+ edges under'), ('duplicate', r'duplicate of'), ('curve-in-solids', r'a curve among'),
               ('both-ways', r'mesh faces point both ways'), ('far', r'more than .* km from the origin'), ('no-mesh', r'no mesh'),
               ('turned', r'faces the same way as'), ('ring-mismatch', r'its ring and its clipped mesh disagree'))
# the kinds of fault that can leave each kind of artifact the drawing meets: a line end short of or past its line, a
# cut that does not close, a cell of a body's surfaces whose sides cannot be read, a stray
CAUSES = {'near miss': {'invalid', 'open', 'self-crossing-face', 'non-manifold', 'runs-into', 'lies-on', 'unjoined-edge',
                        'union-failed', 'nearly-planar', 'creased', 'short-edges', 'duplicate'},
          'open cut': {'invalid', 'open', 'cut-open', 'unjoined-edge', 'non-manifold', 'self-crossing-face', 'union-failed',
                       'ring-mismatch'},
          'unresolved cell': {'open', 'unjoined-edge', 'non-manifold', 'inside-out', 'both-ways', 'turned'},
          'stray': {'short-edges', 'self-crossing-face', 'nearly-planar', 'creased', 'duplicate', 'lies-on'}}


def fault_kind(issue):
    """the FAULT_KINDS key of an issue's text, or None"""
    return next((k for k, rx in FAULT_KINDS if re.match(rx, issue)), None)


def draw_hidden(d, candidates, cuts, doubles_pt):
    """hidden stretches after the visible drawing is fixed; candidates are (group, line, legacy) in drawing units"""
    import numpy as np
    import shapely
    from shapely.geometry import LineString, box
    visible = []
    for lid, ents in d.ents.items():
        if lid == 'HIDDEN':
            continue
        for e in ents:
            if e.get('stroke') == 'none':
                continue
            paths = e['rings'] if e['k'] == 'pg' else [e['pts']] if e['k'] == 'pl' else []
            for P in paths:
                if e['k'] == 'pg' or e['closed']:
                    P = P + P[:1]
                visible += [[a, b] for a, b in zip(P, P[1:]) if a != b]
    vt = shapely.STRtree(shapely.linestrings(np.asarray(visible).reshape(-1, 2, 2)))
    drawn_cuts = [shapely.make_valid(shapely.Polygon(e['rings'][0], e['rings'][1:])) for e in d.ents['CUT'] if e['k'] == 'pg']
    poche = shapely.union_all(cuts + drawn_cuts)
    window = box(*d.clip)
    pieces, gids = [], []
    for gid, line, legacy in candidates:
        line = shapely.intersection(line, window)
        if not legacy:
            line = shapely.difference(line, poche)
        for part in shapely.get_parts(line):
            if part.geom_type == 'LineString':
                P = list(part.coords)
                for a, b in zip(P, P[1:]):
                    if a != b:
                        pieces.append([a, b])
                        gids.append(gid)
    if not pieces:
        return [], dict(count=0, length_pt=0.0)
    lines = shapely.linestrings(pieces)
    ht = shapely.STRtree(lines)
    eps = 1e-7 / d.k
    tolerance = max(doubles_pt / d.k, eps)
    subtract = defaultdict(list)
    for tree, distance, previous in ((vt, tolerance, False), (ht, eps, True)):
        qi, ti = tree.query(lines, predicate='dwithin', distance=distance)
        if previous:
            keep = ti < qi
            qi, ti = qi[keep], ti[keep]
        if not len(qi):
            continue
        AB = np.asarray(pieces)
        CD = shapely.get_coordinates(tree.geometries).reshape(-1, 2, 2)
        u, v = AB[qi, 1] - AB[qi, 0], CD[ti, 1] - CD[ti, 0]
        along = np.abs(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]) <= \
            math.sin(math.radians(5)) * np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1)
        qi, ti, u, v = qi[along], ti[along], u[along], v[along]
        lv = np.linalg.norm(v, axis=1)
        offset = AB[qi, 0] - CD[ti, 0]
        along0, along1 = (offset * v).sum(1) / lv, (u * v).sum(1) / lv
        across0 = (v[:, 0] * offset[:, 1] - v[:, 1] * offset[:, 0]) / lv
        across1 = (v[:, 0] * u[:, 1] - v[:, 1] * u[:, 0]) / lv
        lo, hi = np.zeros(len(qi)), np.ones(len(qi))
        for origin, slope, low, high in ((along0, along1, 0.0, lv), (across0, across1, -distance, distance)):
            flat = np.abs(slope) < 1e-20
            ta = np.divide(low - origin, slope, out=np.full(len(qi), -np.inf), where=~flat)
            tb = np.divide(high - origin, slope, out=np.full(len(qi), np.inf), where=~flat)
            lo, hi = np.maximum(lo, np.minimum(ta, tb)), np.minimum(hi, np.maximum(ta, tb))
            hi[flat & ((origin < low) | (origin > high))] = -1.0
        keep = hi > lo
        for i, a, b in zip(qi[keep].tolist(), lo[keep].tolist(), hi[keep].tolist()):
            subtract[i].append((a, b))
    by_group = defaultdict(list)
    for i, (a, b) in enumerate(np.asarray(pieces)):
        start = 0.0
        for lo, hi in sorted(subtract[i]) + [(1.0, 1.0)]:
            if (lo - start) * np.linalg.norm(b - a) > eps:
                by_group[gids[i]].append(LineString([a + start * (b - a), a + lo * (b - a)]))
            start = max(start, hi)
    d.ents['HIDDEN'] = []
    d.subs = {st: w for st, w in d.subs.items() if st[0] != 'HIDDEN'}
    layer = d.t.layer('drawing', 'HIDDEN')
    weight = layer.get('weight') or d.t['roles'][layer['role']].get('weight') or 'fine'
    paths = []
    for gid, parts in by_group.items():
        sub = f'{gid} hidden'
        for line in shapely.get_parts(shapely.line_merge(shapely.union_all(parts))):
            if line.length * d.k < float(d.t['lint']['min_len_pt']):
                continue
            P = list(line.coords)
            d.polyline('HIDDEN', P[:-1] if line.is_closed else P, closed=line.is_closed, sub=sub)
            paths.append((sub, P))
        if any(s == sub for s, _ in paths):
            d.sublayer('HIDDEN', sub, weight)
    return paths, dict(count=len(paths), length_pt=round(sum(LineString(P).length for _, P in paths) * d.k, 1))


def held_to_model(report, drawn, src, scene, draw_g, o_group, hidden, taken, strays, cuts, f, hx, hy, k, grid, slivers=()):
    """the drawing held to the model, in report['model'] (drawn: each drawn path's points; src: an STRtree of the model's
    lines as pieces, every line of the export, hidden and duplicate ones too, and the cuts, drawing units):
      off_pt       drawn length further than 1.5 grid steps from every piece: a join, a bend or a bridge, drawn but
                   not modelled; off_grid_pt the length further than 0.01 pt, which takes in the grid's own steps;
                   places, the five largest by the 2 pt cell they lie in
      dropped      every stretch of a line Rhino drew as visible (the engine's Visible segments, cuts aside) inside the
                   frame that is not drawn, by reason: under poche, behind a face (hidden: (the object in front, its
                   points)), a stray, a sliver seen for under near_pt where the rest is hidden (slivers, frame units),
                   or what a pass took it out for (taken: (a, b, why, the line it gave way to));
                   named, each reason's length by the object in front or the line given way to, the eight largest;
                   unexplained_pt, the length with no reason, and its five largest places"""
    import numpy as np
    import shapely

    def samples(lines):
        """points every 0.25 pt along polylines (drawing units), each with the length it stands for"""
        A, B = [], []
        for P in lines:
            for a, b in zip(P, P[1:]):
                if a != b:
                    A.append(a[:2])
                    B.append(b[:2])
        if not A:
            return np.zeros((0, 2)), np.zeros(0)
        A, B = np.array(A, dtype=float), np.array(B, dtype=float)
        L = np.hypot(*(B - A).T)
        n = np.maximum(1, np.ceil(L * k / 0.25)).astype(np.int64)
        j = np.repeat(np.arange(len(A)), n)
        t = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n) + 0.5) / n[j]
        return A[j] + (B[j] - A[j]) * t[:, None], (L / n)[j]

    def places(P, w):
        cell = defaultdict(float)
        for (x, y), w_ in zip(P.tolist(), w.tolist()):
            cell[(round(x * k / 2) * 2, round((2 * hy - y) * k / 2) * 2)] += w_ * k
        return [dict(at_pt=[float(x), float(y)], length_pt=round(v, 2)) for (x, y), v in sorted(cell.items(), key=lambda kv: -kv[1])[:5]]
    Q, w = samples(drawn)
    out = {}
    for key, tol in (('off_pt', 1.5 * grid), ('off_grid_pt', 0.01 / k)):
        hit = np.zeros(len(Q), dtype=bool)
        if len(Q):
            hit[src.query(shapely.points(Q), predicate='dwithin', distance=tol)[0]] = True
        out[key] = round(float(w[~hit].sum()) * k, 1)
        if key == 'off_pt':
            out['places'] = places(Q[~hit], w[~hit])
    # what Rhino drew as visible and is not drawn
    vis = [[(p_[0] * f + hx, p_[1] * f + hy) for p_ in s_['pts']] for s_ in scene['segments']
           if s_.get('vis') is None and s_.get('cut') is None and s_.get('src') not in ('mesh', 'ring') and draw_g[o_group[s_['o']]]]
    V, wv = samples(vis)
    inside = (V[:, 0] > 0) & (V[:, 0] < 2 * hx) & (V[:, 1] > 0) & (V[:, 1] < 2 * hy) if len(V) else np.zeros(0, dtype=bool)
    V, wv = V[inside], wv[inside]
    d_segs = [[a, b] for P in drawn for a, b in zip(P, P[1:]) if a != b] + \
        [[a, b] for q in cuts for r in [q.exterior, *q.interiors] for a, b in zip(r.coords, list(r.coords)[1:])]
    left = np.ones(len(V), dtype=bool)
    if len(V) and d_segs:                              # nothing drawn: a lone sliver left out as a stray
        left[shapely.STRtree(shapely.linestrings(d_segs)).query(shapely.points(V), predicate='dwithin', distance=1.5 * grid)[0]] = False
    why_ = np.full(len(V), '', dtype=object)
    who_ = np.full(len(V), '', dtype=object)
    if cuts and left.any():
        under = shapely.contains_xy(shapely.union_all(cuts).buffer(1.5 * grid), V[:, 0], V[:, 1])
        why_[left & under] = 'under poche'

    def pieces(lines, to_frame):
        """the pieces of polylines [(name, points)] with a length on paper, in order (n x 2 x 2), and each one's name;
        with to_frame, the points (x, y,...) are first taken to the frame, (x f + hx, y f + hy)"""
        lines = [(nm, P) for nm, P in lines if len(P) > 1]
        if not lines:
            return np.zeros((0, 2, 2)), []
        P_ = np.concatenate([np.asarray(P, dtype=float).reshape(len(P), -1)[:, :2] for _, P in lines])
        if to_frame:
            P_ = P_ * f + [hx, hy]
        n_ = [len(P) for _, P in lines]
        on_ = np.ones(len(P_), dtype=bool)
        on_[np.cumsum(n_) - 1] = False                 # a line's last point begins no piece
        j = np.nonzero(on_[:-1] & (P_[1:] != P_[:-1]).any(1))[0]
        return np.stack([P_[j], P_[j + 1]], 1), np.repeat(np.array([nm for nm, _ in lines], dtype=object), n_)[j].tolist()
    tries = [('behind a face', hidden, True), ('a stray', [('', P) for _, _, P in strays], False),
             ('a sliver: seen for under near_pt', [('', P) for P in slivers], False)]
    by_why = defaultdict(list)
    for a, b, why, front in taken:
        by_why[why].append((front, [a, b]))
    tries += [(why, lines, False) for why, lines in sorted(by_why.items())]
    for why, lines, to_frame in tries:
        todo = np.nonzero(left & (why_ == ''))[0]
        if not len(todo) or not lines:
            continue
        segs_, nm_ = pieces(lines, to_frame)
        if not len(segs_):
            continue
        tr = shapely.STRtree(shapely.linestrings(segs_))
        qi, si = tr.query(shapely.points(V[todo]), predicate='dwithin', distance=1.5 * grid)
        why_[todo[qi]] = why
        who_[todo[qi]] = np.array(nm_, dtype=object)[si]
    lost = left & (why_ == '')
    out['dropped'] = {w_: round(float(wv[left & (why_ == w_)].sum()) * k, 1) for w_ in sorted(set(why_[left].tolist()) - {''})}
    named = {}
    for w_ in out['dropped']:
        by_n = defaultdict(float)
        for nm, ln in zip(who_[left & (why_ == w_)].tolist(), wv[left & (why_ == w_)].tolist()):
            if nm:
                by_n[nm] += ln * k
        if by_n:
            named[w_] = {nm: round(v, 1) for nm, v in sorted(by_n.items(), key=lambda kv: -kv[1])[:8]}
    out['named'] = named
    out['unexplained_pt'] = round(float(wv[lost].sum()) * k, 1)
    out['unexplained'] = places(V[lost], wv[lost])
    out['unexplained_at'] = [paper(q, hx, hy, k) for q in V[lost][:4000].tolist()]   # each a sample for 0.25 pt, 1000 pt at most
    report['model'] = out


def read_scene(folder):
    """scene.json, and meshes.bin as (vertices n x 3, triangles m x 3 of global vertex indices, each triangle's object).
    From version 4 the export writes the vertices less meshes.origin, which float32 would round 0.2 pt off at the model's
    depth (78,740 in from the camera); it is added back here, and an older export has none"""
    import numpy as np
    s = json.loads((folder / 'scene.json').read_text(encoding='utf-8'))
    raw = (folder / 'meshes.bin').read_bytes()
    nv, nt = s['meshes']['vertices'], s['meshes']['triangles']
    if len(raw) < 12 * (nv + nt):                      # float32 x 3 a vertex, int32 x 3 a triangle
        raise SystemExit(f'hidden-lines: {folder / "meshes.bin"} holds {len(raw)} bytes, short of the {12 * (nv + nt)} '
                         f'its scene.json says ({nv} vertices, {nt} triangles); export again')
    V = np.frombuffer(raw, dtype='<f4', count=nv * 3).reshape(-1, 3).astype(float)
    if s['meshes'].get('origin'):
        V += np.array(s['meshes']['origin'], dtype=float)
    F = np.frombuffer(raw, dtype='<i4', count=nt * 3, offset=nv * 12).reshape(-1, 3).astype(np.int64)
    tri_o = np.full(nt, -1, dtype=np.int64)
    for it in s['meshes']['items']:
        F[it['f0']:it['f0'] + it['nf']] += it['v0']
        tri_o[it['f0']:it['f0'] + it['nf']] = it['o']
    return s, V, F, tri_o


class Tris:
    """projected triangles, for the nearest surface at a point: a grid of the points asked, each triangle tested
    against the points under its box; nearer is larger z, the camera looking down -z. In a perspective the depth is
    kept as 1 / z, which is affine on paper, and given back as z"""

    def __init__(self, V, F, tri_o, f, shift, rank, tie, persp=False):
        import numpy as np
        P = V[F] * np.array([f, f, 1.0]) + np.array([shift[0], shift[1], 0.0])
        if persp:
            P[:, :, 2] = 1.0 / P[:, :, 2]
        self.persp = persp
        a = (P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1])
        good = np.abs(a) > 1e-12                       # seen edge-on, a triangle covers nothing
        self.P, self.o, self.area = P[good], tri_o[good], a[good]
        self.rank = rank[self.o]                        # surfaces level within tie: the earlier group's is in front
        self.tie = tie
        self.lo = self.P[:, :, :2].min(1)
        self.hi = self.P[:, :, :2].max(1)
        self.size = float(np.median((self.hi - self.lo).max(1))) if len(self.P) else 0.0   # a triangle's usual extent

    def plane_z(self, t, q):
        """depth of triangle t's plane at points q (n x 2)"""
        import numpy as np
        P = self.P[t]
        x, y = q[:, 0], q[:, 1]
        l1 = ((x - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (y - P[:, 0, 1])) / self.area[t]
        l2 = ((P[:, 1, 0] - P[:, 0, 0]) * (y - P[:, 0, 1]) - (x - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1])) / self.area[t]
        z = P[:, 0, 2] + l1 * (P[:, 1, 2] - P[:, 0, 2]) + l2 * (P[:, 2, 2] - P[:, 0, 2])
        return 1.0 / z if self.persp else z

    def nearest(self, Q, allow=None):
        """for points Q (n x 2), the triangle nearest the camera covering each, or -1; allow, a boolean per triangle"""
        import numpy as np
        from .idbuf import _nearest_points
        n = len(Q)
        best = np.full(n, -1, dtype=np.int64)
        bz = np.full(n, -np.inf)
        br = np.full(n, 1 << 30)
        if n == 0 or len(self.P) == 0:
            return best
        lo, hi = Q.min(0), Q.max(0)
        side = max(hi[0] - lo[0], hi[1] - lo[1], 1e-9)
        # about four points a cell, but no wider than a triangle: with few points most triangles then cover none
        cell = min(side / max(1.0, math.sqrt(n) / 2), max(self.size, side / 1000))
        nx = int((hi[0] - lo[0]) / cell) + 1
        ny = int((hi[1] - lo[1]) / cell) + 1
        ix = ((Q[:, 0] - lo[0]) / cell).astype(np.int64)
        iy = ((Q[:, 1] - lo[1]) / cell).astype(np.int64)
        key = iy * nx + ix
        order = np.argsort(key, kind='stable')
        starts = np.searchsorted(key[order], np.arange(nx * ny + 1))
        sat = np.zeros((ny + 1, nx + 1), dtype=np.int64)  # points per cell summed over each corner's rectangle: a
        sat[1:, 1:] = np.bincount(key, minlength=nx * ny).reshape(ny, nx).cumsum(0).cumsum(1)   # triangle over none is skipped
        for t0 in range(0, len(self.P), CHUNK):
            tl = np.floor((self.lo[t0:t0 + CHUNK] - lo) / cell).astype(np.int64)
            th = np.floor((self.hi[t0:t0 + CHUNK] - lo) / cell).astype(np.int64)
            live = (th[:, 0] >= 0) & (th[:, 1] >= 0) & (tl[:, 0] < nx) & (tl[:, 1] < ny)
            if allow is not None:
                live &= allow[t0:t0 + CHUNK]
            cx0, cx1 = np.clip(tl[:, 0], 0, nx - 1), np.clip(th[:, 0], 0, nx - 1)
            cy0, cy1 = np.clip(tl[:, 1], 0, ny - 1), np.clip(th[:, 1], 0, ny - 1)
            live &= (sat[cy1 + 1, cx1 + 1] - sat[cy0, cx1 + 1] - sat[cy1 + 1, cx0] + sat[cy0, cx0]) > 0
            _nearest_points(self.P, self.area, self.rank, self.tie, self.persp, Q, np.nonzero(live)[0] + t0, tl, th, t0,
                            nx, ny, order, starts, best, bz, br)
        return best


def clip(a, b, box):
    """the parameters (t0, t1) of segment ab inside box (x0, y0, x1, y1), or None"""
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - box[0]), (dx, box[2] - a[0]), (-dy, a[1] - box[1]), (dy, box[3] - a[1])):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
        if t0 >= t1:
            return None
    return t0, t1


def group_fill(g, layer):
    """the colour a group fills its regions with, for an object from layer: its fills by layer pattern, then its fill"""
    for pat, col in (g.get('fills') or {}).items():
        if fnmatch.fnmatchcase(layer, pat):
            return col
    return g.get('fill')


def free_ends(lines, others, grid):
    """the ends of polylines (each [(x, y),...]) that touch no other line of lines or others within grid:
    [(polyline, 0 for its start or -1 for its end)]"""
    import shapely
    geoms = [shapely.LineString(P) for P in lines] + [shapely.LineString(P) for P in others]
    tree = shapely.STRtree(geoms)
    out = []
    for i, P in enumerate(lines):
        for end in (0, -1):
            hits = tree.query(shapely.Point(P[end]), predicate='dwithin', distance=grid).tolist()
            if all(j == i for j in hits):
                out.append((i, end))
    return out


def solid_cells(lines, sides, rings, cmax, near, grid, step, tol):
    """which cells of one body's section on a clip plane are solid, from the model's own section curves, whatever the
    drawing keeps of them (drawing units throughout):
      lines  [[(x, y),...]] the section lines of its surfaces, its objects that are not closed (walls and slabs
             modelled as surfaces)
      sides  n x 6, the meshes' section edges of those surfaces (ax, ay, bx, by), each with the unit normal on paper of
             the surface it lies on (nx, ny): the side the surface faces
      rings  [Polygon] its closed solids' cut regions, solid by containment
    The lines are noded with the rings' outlines. A free end under near of another line is run on to it (a slab's line
    0.1 pt short of its wall's); else one whose surface faces away from a line within cmax straight behind it, that
    line's surface facing away too, is capped across to it (a roof's two skins, their ends not joined). A cell its
    surfaces face away from, over 0.7 of the length along it whose side is read, is solid; one they face into, 0.7 of
    it, is air (a room, a cavity); else, the sides mixed or none read, it is solid where it is thinner than cmax all
    through, and unresolved where not. A cell no surface's line bounds (a gap between closed solids) is left out.
    A side is read every step along a cell's outline, from a section edge within tol and 20 degrees of it; along a
    closed solid's outline the side faces into the cell, as a solid's faces face out of it. Loose surfaces promise no
    side: an edge facing the way the nearest near-parallel edge in front of it within cmax faces, of an object whose
    edges run beside its own for 2 cmax in all, is turned (a wall's two skins face away from each other, so of two
    facing one way the one facing the other is turned) and read the other way. Column 7 of sides, where given, is each
    edge's object.
    Returns (solid cells, unresolved cells, the run-ons and caps added as [(a, b)], the turned edges as
    [(object, the object it pairs with, the gap)])"""
    import numpy as np
    import shapely
    lines = [[tuple(map(float, p)) for p in P] for P in lines if len(P) > 1]
    if not lines:
        return [], [], [], []
    rr = [q for r in rings for q in shapely.get_parts(r) if q.geom_type == 'Polygon' and q.area > 0]
    outl = [list(rg.coords) for q in rr for rg in [q.exterior, *q.interiors]]
    S = np.asarray(sides, dtype=float)
    S = S.reshape(len(S), -1) if len(S) else np.zeros((0, 7))
    if S.shape[1] < 7:
        S = np.column_stack([S, np.arange(len(S), dtype=float) - len(S)])   # each edge its own object
    s_tree = shapely.STRtree(shapely.linestrings(S[:, :4].reshape(-1, 2, 2))) if len(S) else None
    sin20 = math.sin(math.radians(20))
    turned = {}                                        # edge: (object, the object it pairs with, gap)
    pairs = []                                         # (i, j, gap): j the nearest edge beside i, in front of it
    if len(S):
        dS = S[:, 2:4] - S[:, :2]
        lS = np.maximum(np.hypot(dS[:, 0], dS[:, 1]), 1e-300)
        mS = (S[:, :2] + S[:, 2:4]) / 2
        qi, qj = s_tree.query(shapely.linestrings(S[:, :4].reshape(-1, 2, 2)), predicate='dwithin', distance=cmax)
        best_ = {}                                     # i: (gap, j, overlap), the nearest edge beside it in front
        for i, j in zip(qi.tolist(), qj.tolist()):
            gap = float((mS[j] - mS[i]) @ S[i, 4:6]) if i != j else 0.0
            ov = min(lS[i], lS[j], (lS[i] + lS[j]) / 2 - abs(float((mS[j] - mS[i]) @ dS[i])) / lS[i])
            if grid < gap <= cmax and ov > 0 and abs(dS[i, 0] * dS[j, 1] - dS[i, 1] * dS[j, 0]) <= sin20 * lS[i] * lS[j] \
                    and gap < best_.get(i, (math.inf,))[0]:
                best_[i] = (gap, j, ov)
        run_ = defaultdict(float)                      # two objects' edges beside each other, in all: a wall's skins
        for i, (gap, j, ov) in best_.items():
            run_[(S[i, 6], S[j, 6])] += ov
        pairs = [(i, j, gap) for i, (gap, j, ov) in best_.items() if run_[(S[i, 6], S[j, 6])] >= 2 * cmax]

    def same_way():
        """turn each edge facing toward an edge in front of it that faces the same way"""
        for i, j, gap in pairs:
            if i not in turned and float(S[i, 4:6] @ S[j, 4:6]) > 0.5:
                turned[i] = (int(S[i, 6]), int(S[j, 6]), gap)
                S[i, 4:6] = -S[i, 4:6]
    same_way()
    ring_t = shapely.STRtree([shapely.LineString(c) for c in outl]) if outl else None

    def side(P, D):
        """for points P (n x 2) on lines running along D (unit, n x 2): the normal of the nearest section edge within
        tol and 20 degrees of D, n x 2, nan where there is none"""
        out = np.full((len(P), 2), np.nan)
        if s_tree is None or not len(P):
            return out
        pi, si = s_tree.query(shapely.points(P), predicate='dwithin', distance=tol)
        A, B = S[si, :2], S[si, 2:4]
        ab = B - A
        L2 = np.maximum((ab * ab).sum(1), 1e-300)
        along = np.abs(D[pi, 0] * ab[:, 1] - D[pi, 1] * ab[:, 0]) <= sin20 * np.sqrt(L2)
        t_ = np.clip(((P[pi] - A) * ab).sum(1) / L2, 0, 1)
        dist = np.hypot(*(A + ab * t_[:, None] - P[pi]).T)
        order = np.lexsort((dist, pi))
        best = {}
        for j in order[along[order]].tolist():
            best.setdefault(int(pi[j]), j)
        for p_, j in best.items():
            out[p_] = S[si[j], 4:6]
        return out

    geoms = [shapely.LineString(P) for P in lines] + [shapely.LineString(c) for c in outl]
    tree = shapely.STRtree(geoms)
    links = []
    for i, end in free_ends(lines, outl, grid):
        P = np.array(lines[i])
        p, q0 = P[end], P[end - 1 if end == -1 else 1]           # the end, and the point before it on its line
        pt = shapely.Point(p)
        hit = [j for j in tree.query(pt, predicate='dwithin', distance=near).tolist() if j != i]
        if hit:
            j = min(hit, key=lambda j: geoms[j].distance(pt))
            c = shapely.get_coordinates(shapely.shortest_line(geoms[j], pt))[0]
            if math.dist(c, p) > grid / 2 and not any(math.dist(c, a_) <= grid and math.dist(p, b_) <= grid for a_, b_ in links):
                links.append((tuple(p), tuple(c)))
            continue
        d = (p - q0) / max(math.dist(p, q0), 1e-300)
        n = side(((p + q0) / 2)[None], d[None])[0]
        if np.isnan(n).any():
            continue
        ray = shapely.LineString([p, p - n * cmax])
        best = None
        for j in tree.query(ray, predicate='intersects').tolist():
            if j == i:
                continue
            for c in shapely.get_parts(shapely.intersection(ray, geoms[j])):
                for x, y in shapely.get_coordinates(c).tolist():
                    dd = math.dist(p, (x, y))
                    if dd > grid and (best is None or dd < best[0]):
                        best = (dd, (x, y), j)
        if best is None:
            continue
        g = geoms[best[2]]
        s_ = g.project(shapely.Point(best[1]))
        a_, b_ = g.interpolate(max(s_ - tol, 0)), g.interpolate(min(s_ + tol, g.length))
        dg = np.array([b_.x - a_.x, b_.y - a_.y])
        if not np.hypot(*dg):
            continue
        m = side(np.array([best[1]]), (dg / np.hypot(*dg))[None])[0]
        if not np.isnan(m).any() and float(m @ n) < -0.5 and \
                not any(math.dist(best[1], a_) <= grid and math.dist(p, b_) <= grid for a_, b_ in links):
            links.append((tuple(p), best[1]))
    try:                                              # on the lines' own points, a graph's already noded
        noded = shapely.union_all(geoms + [shapely.LineString(ab) for ab in links])
    except shapely.errors.GEOSException:
        noded = shapely.union_all(geoms + [shapely.LineString(ab) for ab in links], grid_size=grid)
    cells = [q for q in shapely.get_parts(shapely.polygonize(shapely.get_parts(noded))) if q.area > 0]
    have = shapely.union_all(rr) if rr else None
    # an edge with the section's outside behind it and an edge in front of it within cmax is a thin wall's outer face,
    # which faces out: facing in, it is turned too (a wall's two skins both facing into it), and of what remains two
    # facing one way are read again
    if pairs and cells:
        whole = shapely.union_all(cells + rr)
        for i, j, gap in pairs:
            if i in turned:
                continue
            n_ = S[i, 4:6] * tol / 3
            if shapely.contains_xy(whole, *(mS[i] + n_)) and not shapely.contains_xy(whole, *(mS[i] - n_)):
                turned[i] = (int(S[i, 6]), int(S[j, 6]), gap)
                S[i, 4:6] = -S[i, 4:6]
        same_way()
    open_t = shapely.STRtree(geoms[:len(lines)])
    solid, unresolved = [], []
    for q in cells:
        if have is not None and shapely.difference(q, have).area < 0.5 * q.area:
            continue
        pts, dirs = [], []
        for rg in [q.exterior, *q.interiors]:
            n_ = max(1, int(rg.length / step))
            at = (np.arange(n_) + 0.5) * rg.length / n_
            a_ = shapely.line_interpolate_point(rg, np.maximum(at - step / 4, 0))
            b_ = shapely.line_interpolate_point(rg, np.minimum(at + step / 4, rg.length))
            dv = shapely.get_coordinates(b_) - shapely.get_coordinates(a_)
            pts.append(shapely.get_coordinates(shapely.line_interpolate_point(rg, at)))
            dirs.append(dv / np.maximum(np.hypot(dv[:, 0], dv[:, 1]), 1e-300)[:, None])
        P, D = np.concatenate(pts), np.concatenate(dirs)
        if not len(open_t.query(shapely.points(P), predicate='dwithin', distance=tol)[0]):
            continue                                   # bounded by closed solids alone: a gap between them
        N = side(P, D)
        ok_ = ~np.isnan(N[:, 0])
        inside = shapely.contains_xy(q, *(P[ok_] + N[ok_] * tol / 3).T) if ok_.any() else np.zeros(0, dtype=bool)
        out_, in_ = float((~inside).sum()), float(inside.sum())
        if ring_t is not None and (~ok_).any():        # along a closed solid's outline: facing into the cell
            in_ += float(len(np.unique(ring_t.query(shapely.points(P[~ok_]), predicate='dwithin', distance=tol)[0])))
        if out_ + in_ and out_ >= 0.7 * (out_ + in_):
            solid.append(q)
        elif out_ + in_ and in_ >= 0.7 * (out_ + in_):
            continue
        elif 2 * shapely.maximum_inscribed_circle(q, cmax / 50).length <= cmax:
            solid.append(q)
        else:
            unresolved.append(q)
    return solid, unresolved, links, list(turned.values())


def earth_under(lines, up, box):
    """the earth under a ground's open sheets on a vertical section plane (drawing units): what lies below any of their
    section lines (each [(x, y),...]), each segment's shadow along -up, within the box (x0, y0, x1, y1). A ground
    closed in section, its top and bottom faces and its ends, and a pit between its parts are read the same way: the
    earth runs on under the bottom face, and the pit, with no line over it, stays open. An overhang's underside would
    take what lies under it as earth"""
    import numpy as np
    import shapely
    u = np.array(up, dtype=float) / math.hypot(*up)
    far = 2 * math.hypot(box[2] - box[0], box[3] - box[1])
    quads = [shapely.Polygon([a, b, tuple(np.array(b) - u * far), tuple(np.array(a) - u * far)])
             for P in lines for a, b in zip(P, P[1:])]
    quads = [q for q in quads if q.area > 0]
    if not quads:
        return shapely.Polygon()
    return shapely.intersection(shapely.union_all(quads), shapely.box(*box))


def faces_of(scene, V, F, tris, use, objects, k, W, H):
    """for visibility "faces" and the fuzz checker: the ID buffer (hiddenlines/idbuf.py) over the frame, W x H pt at k pt a
    frame unit, of the triangles of tris that use marks, with the clip planes in camera space and a closed solid's
    back faces standing for its cut face, and the tolerance square to a surface 2 MESH_PT, to which the meshes'
    float32 rounding of depth is added (an export with no origin rounds 0.2 pt at the model's depth); and the meshes' own
    edges of objects (idbuf.mesh_edges), those on a clip plane, within 2 mm as the mesh cuts take one, left out:
    (Buffer, edges)"""
    import numpy as np
    from . import idbuf
    v = scene['view']
    f = float(v['true_factor'])
    persp = v.get('projection') == 'perspective'
    L, sy = float(v.get('focal') or 0.0), float(v.get('shift') or 0.0)
    M = np.array(v['xform'], dtype=float)
    planes = []                                        # unit normal and offset, in camera space
    for cl in scene.get('clip') or []:
        n = np.linalg.inv(M[:3, :3]).T @ np.array(cl['normal'], dtype=float)
        n /= np.linalg.norm(n)
        planes.append([*n, float(n @ (M @ np.r_[np.array(cl['origin'], dtype=float), 1.0])[:3])])
    planes = np.array(planes, dtype=float).reshape(-1, 4)
    cap_o = np.array([bool(len(planes)) and bool(o.get('solid')) for o in scene['objects']] + [False])
    org = np.array(scene['meshes'].get('origin') or [0.0, 0.0, 0.0], dtype=float)
    err = float(np.abs(V[:, 2] - org[2]).max()) * 2 ** -24 if len(V) else 0.0
    buf = idbuf.Buffer(tris.P, tris.o, use, persp, (W / 2 / k, H / 2 / k, f, L, sy), k, W, H, 3 * float(scene['bias']),
                       2 * MESH_PT, err, planes, cap_o)
    if persp:
        camf = lambda X: np.stack([X[:, 0] * -X[:, 2] / L, (X[:, 1] + sy) * -X[:, 2] / L, X[:, 2]], 1)
    else:
        camf = lambda X: X
    tol_c = 2.0 / float(scene['unit_mm']) + err
    on_clip = (lambda C: (np.abs(C @ planes[:, :3].T - planes[:, 3]) <= tol_c).any(1)) if len(planes) else None
    E = idbuf.mesh_edges(V, F, scene['meshes']['items'], objects, camf, persp,
                         near=float(v['near']) if persp else None, on_clip=on_clip)
    return buf, E


def build(req_path, req=None, t=None):
    """the drawing and its report: (Drawing, report dict)"""
    import numpy as np
    import shapely
    from shapely.geometry import LineString, box as sbox
    from archkit.draw import Drawing
    T0 = time.time()
    req_path = Path(req_path).absolute()
    req = req or json.loads(req_path.read_text(encoding='utf-8'))
    t = t or load(req_path)
    if req.get('visibility', 'engine') not in ('engine', 'faces'):
        raise SystemExit(f'hidden-lines: visibility is "engine" or "faces", not {req["visibility"]!r}')
    for key in ('groups', 'scale', 'frame'):
        if key not in req:
            raise SystemExit(f'hidden-lines: {req_path.name} has no "{key}"')
    try:
        if float(req['scale']) <= 0 or float(req['frame']['w_pt']) <= 0 or float(req['frame']['h_pt']) <= 0:
            raise ValueError
    except (TypeError, ValueError, KeyError):
        raise SystemExit(f'hidden-lines: in {req_path.name}, scale is a number over 0 and frame holds w_pt and h_pt, '
                         f'points over 0; not {req["scale"]!r} and {req["frame"]!r}')
    if not isinstance(req.get('simplify_doubles', False), bool):
        raise SystemExit(f'hidden-lines: in {req_path.name}, simplify_doubles is true or false; not {req["simplify_doubles"]!r}')
    if not isinstance(req.get('show_hidden', False), bool):
        raise SystemExit(f'hidden-lines: in {req_path.name}, show_hidden is true or false; not {req["show_hidden"]!r}')
    show_hidden = req.get('show_hidden', False)
    hidden_candidates = []
    hidden_sources = []
    by_faces = req.get('visibility') == 'faces'
    folder = req_path.parent / req.get('out', 'hidden-lines')
    scene, V, F, tri_o = read_scene(folder)
    hl = t['hidden_lines']
    lint_t = t['lint']
    objs = scene['objects']
    groups = {g['id']: g for g in req['groups']}
    prio = {g['id']: n for n, g in enumerate(req['groups'])}
    units = UNITS.get(round(float(scene['unit_mm']), 6))
    if units is None:
        raise SystemExit(f'hidden-lines: the model is in {scene["units"]}; draw from millimetres, centimetres, metres, inches or feet')
    f = float(scene['view']['true_factor'])
    persp = scene['view'].get('projection') == 'perspective'
    L_ = float(scene['view'].get('focal') or 0.0)      # a perspective's depth drawn at the request's scale
    sy_ = float(scene['view'].get('shift') or 0.0)
    if persp:                                          # depth along a line drawn straight: its reciprocal is affine on paper
        zl = lambda z0, z1, t: 1.0 / ((1 - t) / z0 + t / z1)
    else:
        zl = lambda z0, z1, t: z0 + t * (z1 - z0)
    d = Drawing(float(req['scale']), units=units, tokens=t, title=req.get('title', req.get('id', '')),
                meta=dict(made_by='kit.py hidden-lines', request=req_path.name))
    k = d.k                                            # pt per drawing unit
    W, H = float(req['frame']['w_pt']), float(req['frame']['h_pt'])
    hx, hy = W / 2 / k, H / 2 / k
    frame = (0.0, 0.0, 2 * hx, 2 * hy)                 # the frame's corner at the origin puts its edges on the grid
    d.clip = frame
    g_ = float(hl['grid_pt']) / k                       # the noding grid, drawing units
    eps = float(hl['eps_pt']) / k
    near = float(lint_t['near_pt']) / k
    touch = max(float(lint_t['touch_mm']) * PT_PER_MM / d.scale, 0.005) / k
    minlen = float(lint_t['min_len_pt']) / k
    delta = 3 * float(scene['bias'])                   # depth within which two surfaces meet: three times the bias
    gap = float(hl['gap_m']) * 1000.0 / float(scene['unit_mm'])
    draw_g = {gid: g.get('draw', True) for gid, g in groups.items()}
    hides_g = {gid: g.get('hides', True) for gid, g in groups.items()}
    o_group = [o['group'] for o in objs]
    report = dict(request=str(req_path), scene=str(folder / 'scene.json'), fixes=[], strays=dict(count=0, length_pt=0.0),
                  issues=[dict(object=o['i'], ids=o['ids'], layer=o['layer'], issue=i) for o in objs for i in o['issues']],
                  rhino=scene.get('log', []), seconds={})
    solid_g = {o['group'] for o in objs if o.get('solid')}
    report['issues'] += [dict(object=o['i'], ids=o['ids'], layer=o['layer'], issue='a curve among its group\'s solids, drawn as '
                              'a line') for o in objs if o['kind'] == 'curve' and o['group'] in solid_g]
    M = np.array(scene['view']['xform'])
    Minv = np.linalg.inv(M)

    def named_o(o):
        """an object as the report names it: its layer and the start of its id; '' for none"""
        return '' if o is None else f"{objs[o]['layer']} {objs[o]['ids'][0][:8] if objs[o]['ids'] else ''}".strip()

    def model_at(x, y, z):
        """a drawing point with its camera depth, in model coordinates"""
        if persp:
            q = [(x - hx) * -z / L_, (y - hy + sy_) * -z / L_, z, 1.0]
        else:
            q = [(x - hx) / f, (y - hy) / f, z, 1.0]
        p = Minv @ np.array(q)
        return [round(float(v), 3) for v in p[:3]]

    meshed_o = set(int(x) for x in set(tri_o.tolist()))
    rank_o = np.array([prio[g] for g in o_group] + [len(prio)])
    tris = Tris(V, F, tri_o, f, (hx, hy), rank_o, delta, persp)
    del tri_o                                          # tris.o holds what is read of it
    hide_kept = np.array([hides_g[o_group[o]] for o in tris.o.tolist()], dtype=bool)

    # ---- what the engine hid of a line lying on the surface in front of it: a curve drawn on a ruled roof seen at a
    # grazing angle, which dips under the engine's facets, or an edge on another object's coplanar face. The export
    # gives the hidden stretches as vis 'under'; a stretch is kept where the surface nearest the camera over it lies
    # within on_ of it, measured square to that surface in camera space, so a glass pane's back edges stay hidden
    on_ = 2 * MESH_PT / k
    under = [s for s in scene['segments'] if s.get('vis') == 'under']
    report['under'] = dict(segments=len(under), kept=0, length_pt=0.0)

    def cam(x, y, z):
        """drawing coordinates (n,) with camera depth, in camera space"""
        if not persp:
            return np.stack([x, y, z], 1)
        return np.stack([x * -z / L_, (y + sy_) * -z / L_, z], 1)
    tight = scene.get('version', 0) >= 3              # meshes within MESH_PT of twisted faces too (rhino/hidden_lines.py)
    tri_cam = nrm_c = None                            # each triangle's first corner in camera space, and its unit normal
    if (under or tight or req.get('crease_turns_deg')) and len(tris.P):
        def corner(j):
            z = 1.0 / tris.P[:, j, 2] if persp else tris.P[:, j, 2]
            return cam((tris.P[:, j, 0] - hx) / f, (tris.P[:, j, 1] - hy) / f, z)
        tri_cam = corner(0)
        e1 = corner(1) - tri_cam
        nrm_c = np.cross(e1, corner(2) - tri_cam)
        del e1
        nrm_c /= np.maximum(np.linalg.norm(nrm_c, axis=1), 1e-300)[:, None]

    def on_front(Q, z):
        """for points Q (n x 2, drawing coordinates) at camera depths z: True where the surface nearest the camera there
        is behind them, or lies within on_ of them. Where no mesh covers them, what the engine hid them behind is not
        known, and they stay hidden"""
        Qf = Q * f + np.array([hx, hy])
        t_ = tris.nearest(Qf, hide_kept)
        out = np.zeros(len(Q), dtype=bool)
        hit = t_ >= 0
        if hit.any():
            p_ = cam(Q[hit, 0], Q[hit, 1], z[hit])
            behind = tris.plane_z(t_[hit], Qf[hit]) <= z[hit] + delta     # the engine's cut face over a twisted roof
            out[hit] = behind | (np.abs(((p_ - tri_cam[t_[hit]]) * nrm_c[t_[hit]]).sum(1)) <= on_)
        return out
    revived, samples = [], []
    revived_seen = defaultdict(list)
    for s in ([] if by_faces else under):              # every segment's samples, then one query of the meshes for all
        P = np.array(s['pts'], dtype=float)
        n_ = np.maximum(2, np.ceil(np.hypot(*(P[1:, :2] - P[:-1, :2]).T) * k * f / 0.25).astype(np.int64))   # every 1/4 pt
        samples.append((s, P, np.repeat(np.arange(len(n_)), n_), np.concatenate([np.linspace(0, 1, m) for m in n_])))

    def at(P_, pc, w):
        """points on pieces pc of polylines P_ (one or one a point) at parameters t: (drawing xy, camera depth)"""
        A_, B_ = P_[pc] if P_.ndim == 2 else P_[np.arange(len(pc)), pc], P_[pc + 1] if P_.ndim == 2 else P_[np.arange(len(pc)), pc + 1]
        z = 1.0 / ((1 - w) / A_[:, 2] + w / B_[:, 2]) if persp else A_[:, 2] + w * (B_[:, 2] - A_[:, 2])
        return A_[:, :2] + (B_[:, :2] - A_[:, :2]) * w[:, None], z
    if samples:
        pts_ = [at(P, pc, u_) for _, P, pc, u_ in samples]
        ok_all = on_front(np.concatenate([q for q, _ in pts_]), np.concatenate([z for _, z in pts_]))
        off_ = np.cumsum([0] + [len(u_) for *_, u_ in samples])
    runs, ends = [], []                                # (segment, first, last sample); (run, start or end, piece, t kept, t not)
    for i, (s, P, pc, u_) in enumerate(samples):
        ok_ = ok_all[off_[i]:off_[i + 1]]
        d_ = np.diff(np.concatenate([[0], ok_.astype(np.int8), [0]]))
        for j, j2 in zip(np.nonzero(d_ == 1)[0], np.nonzero(d_ == -1)[0] - 1):
            if j2 == j:
                continue
            r = len(runs)
            runs.append((i, j, j2))
            if j > 0 and pc[j - 1] == pc[j]:           # where it turns visible, between two samples on one piece
                ends.append((r, 0, pc[j], u_[j], u_[j - 1]))
            if j2 < len(u_) - 1 and pc[j2 + 1] == pc[j2]:
                ends.append((r, 1, pc[j2], u_[j2], u_[j2 + 1]))
    if ends:                                           # each end found by halving to a thousandth of a point
        E_ = np.array([e[:3] for e in ends], dtype=np.int64)
        kept_t, lost_t = np.array([e[3] for e in ends]), np.array([e[4] for e in ends])
        Pm = [samples[runs[r][0]][1] for r in E_[:, 0]]
        width = max(len(P) for P in Pm)
        Pp = np.array([np.vstack([P, np.repeat(P[-1:], width - len(P), 0)]) for P in Pm])
        for _ in range(8):
            mid_ = (kept_t + lost_t) / 2
            q_, z_ = at(Pp, E_[:, 2], mid_)
            ok_ = on_front(q_, z_)
            kept_t, lost_t = np.where(ok_, mid_, kept_t), np.where(ok_, lost_t, mid_)
        end_at = {(r, side): (int(p_), float(t_)) for (r, side, p_), t_ in zip(E_.tolist(), kept_t.tolist())}
    else:
        end_at = {}
    for r, (i, j, j2) in enumerate(runs):
        s, P, pc, u_ = samples[i]
        (p0, t0), (p1, t1) = end_at.get((r, 0), (pc[j], u_[j])), end_at.get((r, 1), (pc[j2], u_[j2]))
        (q0, z0), (q1, z1) = at(P, np.array([p0]), np.array([t0])), at(P, np.array([p1]), np.array([t1]))
        run = [[*q0[0], z0[0]]] + [list(P[v]) for v in range(p0 + 1, p1 + 1)] + [[*q1[0], z1[0]]]
        length = float(np.hypot(*np.diff(np.array(run)[:, :2], axis=0).T).sum() * k * f)
        if show_hidden:
            revived_seen[id(s)].append(((p0, t0), (p1, t1)))
        if length < float(lint_t['near_pt']):         # a sliver at a junction; a gap that short is met below
            continue
        revived.append(dict((k_, v) for k_, v in s.items() if k_ != 'vis') | dict(pts=[[float(x) for x in q] for q in run]))
        report['under']['kept'] += 1
        report['under']['length_pt'] += length
    report['under']['length_pt'] = round(report['under']['length_pt'], 1)

    # ---- faces (visibility "faces"): what is seen decided from the meshes' faces through an ID buffer
    # (hiddenlines/idbuf.py), not from the engine's verdicts. The lines that may be drawn are every segment the engine
    # found of a group that hides, visible, hidden ('under') or Duplicate ('dup'), but the cuts, each kept where the
    # buffer sees it; then the meshes' own edges, kept where the buffer sees them and no line of the same object that
    # is drawn lies along them. Lines lying on each other merge in the graph below. The cuts, the dashed classes and a
    # group that does not hide keep the engine's visible segments
    faced, faced_hid, slivers = [], [], []              # slivers: stretches seen for under near_pt, frame units

    def probed(s):
        return s.get('cut') is None and s.get('vis') in (None, 'under', 'dup') and hides_g[o_group[s['o']]]
    if by_faces:
        from . import idbuf
        T_f = time.time()
        tex_o = np.array([groups[g].get('layer') == 'TEXTURE' for g in o_group] + [False])   # tiles hide nothing
        mo = {o for o in range(len(objs)) if hides_g[o_group[o]] and draw_g[o_group[o]] and not tex_o[o]}
        buf, E = faces_of(scene, V, F, tris, hide_kept & ~tex_o[tris.o], mo, k, W, H)

        def kept(lines, S, ok, seen, left=None):
            """the stretches of ok samples along lines, each (line, its points in frame units with depth, its length
            in pt); a stretch under near_pt of a line seen only in part is left out, a sliver at a junction, as the
            revival of 'under' leaves out, and listed in left where given"""
            out = []
            for li_, a_, b_ in idbuf.stretches(S, buf, ok, seen):
                P_ = idbuf.stretch_points(S, persp, li_, lines[li_], a_, b_)
                ln = sum(math.dist(p_[:2], q_[:2]) for p_, q_ in zip(P_, P_[1:])) * k
                if ln >= float(lint_t['near_pt']) or ln >= float(np.hypot(*np.diff(lines[li_][:, :2], axis=0).T).sum()) * k * 0.999:
                    out.append((li_, P_, ln))
                elif left is not None:
                    left.append([tuple(q_[:2]) for q_ in P_])
            return out
        steadied = [0]

        def steady(S_, X, Y, Z, seen_):
            """flicker taken out: a run of samples hidden at the buffer's tolerance but seen within twice it takes its
            neighbours' along its line where the samples either side of it are both seen, so a line lying about the
            tolerance off a surface in front is drawn whole, not in dashes; where they differ it stays hidden"""
            j_ = np.nonzero(~seen_ & ~S_.get('extra', np.zeros(len(seen_), dtype=bool)))[0]   # not one judged in its cell
            amb = j_[buf.seen(X[j_], Y[j_], Z[j_], tol_pt=4 * MESH_PT)] if len(j_) else j_
            if not len(amb):
                return seen_
            li_, out = S_['line'], seen_.copy()
            cut_ = np.nonzero((np.diff(amb) > 1) | (li_[amb[1:]] != li_[amb[:-1]]))[0]
            for a0, a1 in zip(np.r_[amb[0], amb[cut_ + 1]].tolist(), np.r_[amb[cut_], amb[-1]].tolist()):
                if a0 > 0 and a1 < len(seen_) - 1 and li_[a0 - 1] == li_[a0] == li_[a1 + 1] and seen_[a0 - 1] and seen_[a1 + 1]:
                    out[a0:a1 + 1] = True
                    steadied[0] += a1 + 1 - a0
            return out
        cand = [s for s in scene['segments'] if probed(s)]
        lines_ = [np.array(s['pts'], dtype=float)[:, :3] * [f, f, 1.0] + [hx, hy, 0.0] for s in cand]
        S = idbuf.samples(lines_, k, W, H)
        S = idbuf.between(S, E['a'][:, :2] * f + [hx, hy], E['b'][:, :2] * f + [hx, hy], k)
        X_, Y_, Z_ = idbuf.at(S, persp)
        seen = buf.seen(X_, Y_, Z_)
        ex_ = np.nonzero(S.get('extra', np.zeros(len(seen), dtype=bool)))[0]
        if len(ex_):                                   # what lies between two crossings, against every triangle there
            seen[ex_] = buf.sees(buf.front_cell(X_[ex_], Y_[ex_]), X_[ex_], Y_[ex_], Z_[ex_])
        seen = steady(S, X_, Y_, Z_, seen)
        # what hides each sample the buffer does not see (the report's model.named, --explain). A gap in a line the
        # engine drew as visible, a run of samples between seen ones that only the line's own object's mesh hides, is
        # seen: the engine had the object's own surfaces, the mesh stands a tolerance off them (a curved wall's crease
        # broken where a facet of the same wall stood in front); a stretch
        # that reaches the line's end stays the faces' to judge (drawn, it broke the model's electronics ring, two rims 0.18 pt
        # apart)
        hid_j = np.nonzero(~seen)[0]
        front_o = np.full(len(seen), -1, dtype=np.int64)
        if len(hid_j):
            t_f = buf.front(X_[hid_j], Y_[hid_j])
            front_o[hid_j] = np.where(t_f >= 0, tris.o[np.maximum(t_f, 0)], -1)
            judged = any(s_.get('vis') == 'under' for s_ in scene['segments'])   # an export the engine judged
            own_l = np.array([judged and s_.get('vis') is None and s_['o'] for s_ in cand], dtype=object)
            mine_ = np.zeros(len(seen), dtype=bool)
            mine_[hid_j] = [own_l[S['line'][j]] is not False and front_o[j] == own_l[S['line'][j]] for j in hid_j.tolist()]
            li_s, filled = S['line'], 0
            cut_ = np.nonzero((np.diff(hid_j) > 1) | (li_s[hid_j[1:]] != li_s[hid_j[:-1]]))[0]
            for a0, a1 in zip(np.r_[hid_j[0], hid_j[cut_ + 1]].tolist(), np.r_[hid_j[cut_], hid_j[-1]].tolist()):
                if a0 > 0 and a1 < len(seen) - 1 and li_s[a0 - 1] == li_s[a0] == li_s[a1 + 1] and seen[a0 - 1] and seen[a1 + 1] \
                        and mine_[a0:a1 + 1].all():
                    seen[a0:a1 + 1] = True
                    front_o[a0:a1 + 1] = -1
                    filled += a1 + 1 - a0
            report['faces_own'] = round(filled * idbuf.STEP_PT, 1)
            del t_f, own_l, mine_
        # one edge drawn twice: a Duplicate segment (the engine's copy, from another object, of a line it drew) gives way
        # where a Visible segment that is seen lies along it within 3 MESH_PT on the page and in depth, so the two are
        # not noded into one staircase that the doubles and the line ends then take apart (the model's pipe frames, an
        # elbow's silhouette and the next tube's 0.05 to 0.3 pt apart)
        ok_e = seen.copy()
        vis_l = np.array([s.get('vis') is None for s in cand], dtype=bool)
        dup_l = np.array([s.get('vis') == 'dup' for s in cand], dtype=bool)
        if len(cand) and vis_l.any() and dup_l.any():
            st_v = [P_ for _, P_, _ in kept(lines_, S, seen & vis_l[S['line']], seen)]
            jd = np.nonzero(seen & dup_l[S['line']])[0]
            if st_v and len(jd):
                VA = np.concatenate([np.array(P_[:-1], dtype=float) for P_ in st_v])
                VB = np.concatenate([np.array(P_[1:], dtype=float) for P_ in st_v])
                qi, gi = shapely.STRtree(shapely.linestrings(np.stack([VA[:, :2], VB[:, :2]], 1))).query(
                    shapely.points(np.column_stack([X_[jd], Y_[jd]])), predicate='dwithin', distance=3 * MESH_PT / k)
                du = S['B'][S['pc'][jd[qi]], :2] - S['A'][S['pc'][jd[qi]], :2]
                vu = VB[gi, :2] - VA[gi, :2]
                lv = np.hypot(vu[:, 0], vu[:, 1])
                along = np.abs(du[:, 0] * vu[:, 1] - du[:, 1] * vu[:, 0]) <= \
                    math.sin(math.radians(20)) * np.hypot(du[:, 0], du[:, 1]) * lv
                tq = np.clip(((np.column_stack([X_[jd[qi]], Y_[jd[qi]]]) - VA[gi, :2]) * vu).sum(1) / np.maximum(lv ** 2, 1e-300), 0, 1)
                zq = zl(VA[gi, 2], VB[gi, 2], tq)
                near_z = np.abs(zq - Z_[jd[qi]]) <= 3 * MESH_PT / (k * f) * (np.abs(Z_[jd[qi]]) / L_ if persp else 1.0)
                ok_e[jd[qi[along & near_z]]] = False
                report.setdefault('faces_dup', 0)
                report['faces_dup'] = int((~ok_e & seen).sum())
                del VA, VB, qi, gi, du, vu, lv, along, tq, zq, near_z
            del st_v, jd
        st_e = kept(lines_, S, ok_e, seen, slivers)
        m_h = (~seen).astype(np.int8)
        brk_h = np.concatenate([[True], S['line'][1:] != S['line'][:-1]])
        st_h = np.nonzero((m_h == 1) & (brk_h | np.concatenate([[True], m_h[:-1] == 0])))[0]
        en_h = np.nonzero((m_h == 1) & (np.concatenate([brk_h[1:], [True]]) | np.concatenate([m_h[1:] == 0, [True]])))[0]
        for (li_, a_, b_), j0, j1 in zip(idbuf.stretches(S, None, ~seen, np.ones(len(seen), dtype=bool)), st_h, en_h):
            fo_ = front_o[j0:j1 + 1]
            fo_ = fo_[fo_ >= 0]
            faced_hid.append(dict(o=cand[li_]['o'], by=int(np.bincount(fo_).argmax()) if len(fo_) else None,
                                  pts=np.array([[(x - hx) / f, (y - hy) / f, z] for x, y, z in
                                                idbuf.stretch_points(S, persp, li_, lines_[li_], a_, b_)])))
        if show_hidden:
            seen_runs = defaultdict(list)
            for li_, a_, b_ in idbuf.stretches(S, buf, seen, seen):
                seen_runs[li_].append((a_, b_))
            for li_, s_ in enumerate(cand):
                if not draw_g[o_group[s_['o']]]:
                    continue
                pc0 = int(S['pc0'][li_])
                start = (pc0, 0.0)
                end = (pc0 + len(lines_[li_]) - 2, 1.0)
                for a_, b_ in seen_runs[li_] + [(end, end)]:
                    if start[0] + start[1] < a_[0] + a_[1]:
                        P_ = idbuf.stretch_points(S, persp, li_, lines_[li_], start, a_)
                        hidden_candidates.append((o_group[s_['o']], LineString(np.asarray(P_)[:, :2]), False))
                        hidden_sources.append((o_group[s_['o']], hidden_candidates[-1][1], s_['o']))
                    start = b_
        # a mesh's own edge gives way to a line of its object lying along it as drawn: a stretch of the engine's the
        # faces kept, or a cut. A segment the buffer hides does not stand for an edge it sees (fuzz seeds 73, 146 and
        # 159: a curved solid's silhouette, the engine's hidden and the mesh's seen 0.1 pt from it)
        eo = [(cand[li_]['o'], np.array(P_, dtype=float)) for li_, P_, _ in st_e] + \
            [(s['o'], np.array(s['pts'], dtype=float)[:, :3] * [f, f, 1.0] + [hx, hy, 0.0]) for s in scene['segments']
             if s['o'] in mo and s.get('cut') is not None and s.get('vis') not in ('under', 'dup')]
        own_t = None
        if eo:
            PO = np.concatenate([np.full(len(P_) - 1, o) for o, P_ in eo])
            PA_, PB_ = np.concatenate([P_[:-1] for _, P_ in eo]), np.concatenate([P_[1:] for _, P_ in eo])
            own_t = shapely.STRtree(shapely.linestrings(np.stack([PA_[:, :2], PB_[:, :2]], 1)))
        ztol = 3 * MESH_PT / (k * f)                   # in camera units; at depth z in a perspective, times |z| / L
        sin20 = math.sin(math.radians(20))

        def own_near(Q, D, o_q, any_z):
            """points Q (n x 3, frame x, y and depth) of edges running along D (n x 2, unit) with a line of their own
            object o_q within near_pt on the page lying along them, within 20 degrees (not one meeting them at a
            corner), and within 3 MESH_PT of their depth unless any_z (a silhouette, whose mesh's edge and the
            surface's own lie apart in depth, however near on the page). Within near_pt, not the mesh's tolerance: a
            facet's fold on a curved wall's mesh, 0.17 pt off the wall's own crease, was drawn beside it as a second
            line crossing it ; the model's line stands for the mesh's"""
            hit = np.zeros(len(Q), dtype=bool)
            if own_t is None or not len(Q):
                return hit
            for c in range(0, len(Q), CHUNK):
                qi, pi = own_t.query(shapely.points(Q[c:c + CHUNK, :2]), predicate='dwithin',
                                     distance=float(lint_t['near_pt']) / k)
                qi = qi + c
                mine = PO[pi] == o_q[qi]
                qi, pi = qi[mine], pi[mine]
                ab = PB_[pi, :2] - PA_[pi, :2]
                along = np.abs(D[qi, 0] * ab[:, 1] - D[qi, 1] * ab[:, 0]) <= sin20 * np.hypot(ab[:, 0], ab[:, 1])
                tq = np.clip(((Q[qi, :2] - PA_[pi, :2]) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-300), 0, 1)
                zq = zl(PA_[pi, 2], PB_[pi, 2], tq)
                near_z = np.abs(zq - Q[qi, 2]) <= ztol * (np.abs(Q[qi, 2]) / L_ if persp else 1.0)
                hit[qi[along & (near_z | any_z[qi])]] = True
            return hit
        EA2, EB2 = E['a'][:, :2] * f + [hx, hy], E['b'][:, :2] * f + [hx, hy]
        # a mesh's crease turning under 40 degrees on an object the export gives edge curves for is a facet's fold,
        # not an edge of the model, whose creases are those curves (the folds of a curved wall's mesh crossing its own
        # crease); a box's edge the engine got wrong turns 90 (fuzz seed 119), and a
        # pure mesh's creases are its own
        curved_o = np.zeros(len(objs) + 1, dtype=bool)
        curved_o[[s_['o'] for s_ in scene['segments'] if s_.get('src') == 'geom']] = True
        me = np.nonzero(~(((EA2[:, 0] < 0) & (EB2[:, 0] < 0)) | ((EA2[:, 0] > 2 * hx) & (EB2[:, 0] > 2 * hx)) |
                          ((EA2[:, 1] < 0) & (EB2[:, 1] < 0)) | ((EA2[:, 1] > 2 * hy) & (EB2[:, 1] > 2 * hy)) |
                          ((E['kind'] == 1) & curved_o[E['obj']] & (E['turn'] < 40.0))))[0]
        EA3, EB3 = E['a'][me] * [f, f, 1.0] + [hx, hy, 0.0], E['b'][me] * [f, f, 1.0] + [hx, hy, 0.0]
        D3 = EB3[:, :2] - EA3[:, :2]
        D3 = D3 / np.maximum(np.hypot(D3[:, 0], D3[:, 1]), 1e-300)[:, None]
        Q3 = np.concatenate([np.column_stack([EA3[:, :2] + (EB3[:, :2] - EA3[:, :2]) * u, zl(EA3[:, 2], EB3[:, 2], u)])
                             for u in (0.25, 0.5, 0.75)])
        # an edge with such a line along it a quarter, a half and three quarters of its way goes whole, untried
        sil_ = E['kind'][me] == 2
        me = me[~own_near(Q3, np.tile(D3, (3, 1)), np.tile(E['obj'][me], 3), np.tile(sil_, 3)).reshape(3, -1).all(0)]
        LM = list(np.stack([E['a'][me], E['b'][me]], 1) * [f, f, 1.0] + [hx, hy, 0.0])
        S2 = idbuf.samples(LM, k, W, H)
        X2, Y2, Z2 = idbuf.at(S2, persp)
        seen2 = steady(S2, X2, Y2, Z2, buf.seen(X2, Y2, Z2))
        ok2 = seen2.copy()
        j_ = np.nonzero(seen2)[0]
        jm = S2['line'][j_]
        DM = np.array([(P_[1, :2] - P_[0, :2]) / max(math.dist(P_[1, :2], P_[0, :2]), 1e-300) for P_ in LM]).reshape(-1, 2)
        ok2[j_[own_near(np.stack([X2[j_], Y2[j_], Z2[j_]], 1), DM[jm], E['obj'][me][jm], E['kind'][me][jm] == 2)]] = False
        st_m = kept(LM, S2, ok2, seen2)
        kinds = ('Boundary', 'Crease', 'Silhouette', 'NonManifold')
        back = lambda P_: [[(x - hx) / f, (y - hy) / f, z] for x, y, z in P_]   # to the export's coordinates
        faced += [{k_: v for k_, v in cand[li_].items() if k_ != 'vis'} | dict(pts=back(P_)) for li_, P_, _ in st_e]
        faced += [dict(o=int(E['obj'][me[li_]]), src='mesh', sil=kinds[int(E['kind'][me[li_]])], pts=back(P_))
                  for li_, P_, _ in st_m]
        report['faces'] = dict(px_per_pt=idbuf.R_PX, tolerance_pt=2 * MESH_PT, lines=len(cand),
                               samples=int(len(seen) + len(seen2)),
                               mesh_edges=dict(found=int(len(E['obj'])), tried=int(len(me)), drawn=len(st_m)),
                               stretches=len(faced), seen_pt=round(sum(x[2] for x in st_e + st_m), 1),
                               steadied_pt=round(steadied[0] * idbuf.STEP_PT, 1),
                               seconds=round(time.time() - T_f, 2))
        tri_px, s_px = buf.tri, buf.s                  # what the depth bands read of the buffer
        del buf, cand, lines_, S, X_, Y_, Z_, seen, hid_j, front_o, ok_e, st_e, m_h, brk_h, st_h, en_h, eo, own_t, EA2, \
            EB2, me, EA3, EB3, D3, Q3, sil_, LM, S2, X2, Y2, Z2, seen2, ok2, j_, jm, DM, st_m

    # ---- source pieces: every consecutive pair of a visible segment's points, clipped to the frame
    pieces = []                                        # (x0, y0, z0, x1, y1, z1, segment)
    # a closed solid's cut by a plane facing the camera comes from the model, exact and closed (rings), not from the
    # engine's cut segments, which can leave out an edge two objects share; each ring is a segment of source 'ring'
    ring_o = set(r['o'] for r in scene.get('rings', []))
    # where two objects' cuts lie on each other the engine keeps one (the other is Duplicate, which the export leaves
    # out): the model's wall against a box, the model's floor under a nightstand. The export clips the meshes by the planes, so an
    # object's cut is its mesh's edges on a plane that one triangle alone holds; what of that lies over 0.1 pt off the
    # object's own cut segments is added as a cut segment of its own (source 'mesh'). A closed solid's mesh is held to
    # its rings the same way: where its section runs over 0.1 pt off them, more than the mesh's own error explains, the
    # two disagree, the cut follows the mesh there too, and the disagreement is reported as the model's (a ring
    # narrower than the solid's clipped mesh, the adversarial scenes' min-cap-mismatch1, would otherwise drop the cut's
    # edge and cap what is not cut)
    mesh_cut = []
    report['mesh_cuts'] = dict(pieces=0, length_pt=0.0)
    ring_xy = defaultdict(list)                        # (object, plane): its rings' edges, drawing units
    for r in scene.get('rings', []):
        P_ = [(q_[0] * f + hx, q_[1] * f + hy) for q_ in r['pts']]
        ring_xy[(r['o'], r['cut'])] += list(zip(P_, P_[1:] + P_[:1]))
    off_ring = defaultdict(lambda: [0.0, 0.0])         # object: [length of its mesh's section off its rings, farthest]
    # and the side each surface (an object not closed) faces along its cut: its triangle's normal on the plane, on
    # paper, for the cells of a body's section that are solid (solid_cells); in a parallel view, where the plane's
    # width on paper is its true width
    sides_o = defaultdict(list)                        # object: [(ax, ay, bx, by, nx, ny)], drawing units
    if scene.get('clip') and len(F):
        def cam_v(ix):
            """vertices ix (indices or a slice) in camera space"""
            if persp:
                return np.stack([V[ix, 0] * f * -V[ix, 2] / L_, (V[ix, 1] * f + sy_) * -V[ix, 2] / L_, V[ix, 2]], 1)
            return V[ix]
        tol_m = 2.0 / float(scene['unit_mm'])          # 2 mm, over float32's error on a vertex the export put on a plane
        own = defaultdict(list)
        for s in scene['segments']:
            if s.get('cut') is not None and s.get('vis') not in ('under', 'dup'):
                own[s['o']] += [((a[0] * f + hx, a[1] * f + hy), (b[0] * f + hx, b[1] * f + hy)) for a, b in zip(s['pts'], s['pts'][1:])]
        for i, cl in enumerate(scene['clip']):
            nv = np.array(cl['normal'], dtype=float)
            on = np.zeros(len(V), dtype=bool)          # each vertex within tol_m of the plane, CHUNK at a time
            for c in range(0, len(V), CHUNK):
                C_ = cam_v(slice(c, c + CHUNK))
                Vm = (Minv @ np.column_stack([C_, np.ones(len(C_))]).T).T[:, :3]
                on[c:c + CHUNK] = np.abs((Vm - np.array(cl['origin'], dtype=float)) @ nv / np.linalg.norm(nv)) < tol_m
            pc = np.linalg.inv(M[:3, :3]).T @ (nv / np.linalg.norm(nv))   # the plane's normal in camera space
            pc /= np.linalg.norm(pc)
            for it in scene['meshes']['items']:
                o = it['o']
                if not draw_g[o_group[o]] or (o in ring_o and not ring_xy.get((o, i))):
                    continue
                Fo = F[it['f0']:it['f0'] + it['nf']]
                Ea = np.concatenate([Fo[:, 0], Fo[:, 1], Fo[:, 2]])
                Eb = np.concatenate([Fo[:, 1], Fo[:, 2], Fo[:, 0]])
                ti = np.tile(np.arange(len(Fo)), 3)
                pick = on[Ea] & on[Eb]
                if not pick.any():
                    continue
                Ea, Eb, ti = Ea[pick], Eb[pick], ti[pick]
                ka = np.round(V[Ea, :2] * f * k / 1e-3).astype(np.int64)   # in thousandths of a point
                kb = np.round(V[Eb, :2] * f * k / 1e-3).astype(np.int64)
                swap = (ka[:, 0] > kb[:, 0]) | ((ka[:, 0] == kb[:, 0]) & (ka[:, 1] > kb[:, 1]))
                key = np.where(swap[:, None], np.concatenate([kb, ka], 1), np.concatenate([ka, kb], 1))
                _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
                one = cnt[inv.ravel()] == 1
                Ea, Eb, ti = Ea[one], Eb[one], ti[one]
                if not len(Ea):
                    continue
                A2 = V[Ea, :2] * f + np.array([hx, hy])
                B2 = V[Eb, :2] * f + np.array([hx, hy])
                if not persp and o not in ring_o:
                    nt = np.cross(cam_v(Fo[ti, 1]) - cam_v(Fo[ti, 0]), cam_v(Fo[ti, 2]) - cam_v(Fo[ti, 0]))
                    n_in = nt - (nt @ pc)[:, None] * pc
                    nn = np.hypot(n_in[:, 0], n_in[:, 1])
                    good = nn > 0.2 * np.linalg.norm(nt, axis=1)   # not a face lying in the plane
                    sides_o[o] += np.column_stack([A2, B2, n_in[:, :2] / np.maximum(nn, 1e-300)[:, None]])[good].tolist()
                lines_ = shapely.linestrings(np.stack([A2, B2], 1))
                if o in ring_o:                        # inside the frame, where a perspective's rings are cut by the view
                    lines_ = shapely.intersection(lines_, sbox(near, near, 2 * hx - near, 2 * hy - near))
                    # the sine of the angle each edge's face meets the plane at
                    nt = np.cross(cam_v(Fo[ti, 1]) - cam_v(Fo[ti, 0]), cam_v(Fo[ti, 2]) - cam_v(Fo[ti, 0]))
                    sin_f = np.linalg.norm(np.cross(nt / np.maximum(np.linalg.norm(nt, axis=1), 1e-300)[:, None], pc), axis=1)
                ref_ = ring_xy[(o, i)] if o in ring_o else own.get(o)
                if ref_:
                    ref_g = shapely.multilinestrings([list(s) for s in ref_])
                    lines_ = shapely.difference(lines_, shapely.buffer(ref_g, 0.1 / k, cap_style='flat'))
                # the ring is the model's exact cut. The mesh lies off its surface by up to its tolerance, MESH_PT on
                # paper, which Rhino keeps only roughly (the model's base profile: a vertex 3.1 times it off), and a face
                # meeting the plane at a glancing angle carries that along the plane divided by the angle's sine (0.48
                # pt there). A piece's offset is taken square to the ring's edge beside it and parallel, so an edge
                # running on along the ring's own line to meet a moved one is none. Where four tolerances so carried
                # explain every piece off an object's ring, the ring stands; else the cut follows the mesh there, and
                # the disagreement is reported
                parts_o = []                           # (edge, piece, explained)
                for j, g_l in enumerate(lines_.tolist()):
                    for part in shapely.get_parts(g_l).tolist():
                        if part.length * k < 0.3 or part.geom_type != 'LineString':
                            continue
                        far_j = 0.0
                        if o in ring_o:
                            pc_ = np.array(part.coords)
                            far_j = float(shapely.distance(shapely.points(pc_), ref_g).max())
                            u_ = pc_[-1] - pc_[0]
                            u_ = u_ / max(float(np.hypot(*u_)), 1e-300)
                            reach_ = max(near, 4 * MESH_PT / (k * max(float(sin_f[j]), 0.05)))
                            sq_ = [far_j]
                            for ra_, rb_ in ref_:
                                rd_ = np.subtract(rb_, ra_)
                                rl_ = float(np.hypot(*rd_))
                                if rl_ > 0 and abs(u_[0] * rd_[1] - u_[1] * rd_[0]) <= math.sin(math.radians(20)) * rl_ and \
                                        shapely.distance(part, shapely.LineString([ra_, rb_])) <= reach_:
                                    sq_.append(float((np.abs((pc_[:, 0] - ra_[0]) * rd_[1] - (pc_[:, 1] - ra_[1]) * rd_[0]) / rl_).max()))
                            far_j = min(sq_)
                        parts_o.append((j, part, far_j, o in ring_o and far_j * sin_f[j] * k <= 4 * MESH_PT))
                if o in ring_o and parts_o and all(x_[3] for x_ in parts_o):
                    report['mesh_cuts']['ring_kept_pt'] = round(report['mesh_cuts'].get('ring_kept_pt', 0.0) +
                                                                sum(x_[1].length for x_ in parts_o) * k, 1)
                    parts_o = []
                for j, part, far_j, _ in parts_o:
                    AB = B2[j] - A2[j]
                    ts = [float(np.clip(((np.array(c_) - A2[j]) @ AB) / max(AB @ AB, 1e-300), 0, 1)) for c_ in part.coords]
                    mesh_cut.append(dict(o=o, src='mesh', sil='SectionCut', cut=i, pts=[
                        [(c_[0] - hx) / f, (c_[1] - hy) / f, zl(V[Ea[j], 2], V[Eb[j], 2], t_)] for c_, t_ in zip(part.coords, ts)]))
                    report['mesh_cuts']['pieces'] += 1
                    report['mesh_cuts']['length_pt'] += part.length * k
                    if o in ring_o:
                        off_ring[o][0] += part.length * k
                        off_ring[o][1] = max(off_ring[o][1], far_j * k)
        del on, C_, Vm
    report['mesh_cuts']['length_pt'] = round(report['mesh_cuts']['length_pt'], 1)
    for o, (ln_, far_) in sorted(off_ring.items()):
        report['issues'].append(dict(object=o, ids=objs[o]['ids'], layer=objs[o]['layer'],
                                     issue=f'its ring and its clipped mesh disagree: {ln_:.1f} pt of the mesh\'s section '
                                           f'lies up to {far_:.2f} pt off the ring; the cut follows the mesh there'))
    centre = {}                                        # each meshed object's centre in the model, for the faults below
    if len(F):
        for it in scene['meshes']['items']:
            Vo = V[np.unique(F[it['f0']:it['f0'] + it['nf']].ravel())]
            if len(Vo):
                c_ = Vo.mean(0)
                centre[it['o']] = model_at(c_[0] * f + hx, c_[1] * f + hy, c_[2])
    del V, F
    # a cut the engine left out as Duplicate of another is one more source of that line, so the graph holds the body's
    # section whole when its faces are closed (the model's roof skins where its two roofs cross)
    segs = [s for s in scene['segments'] if (s.get('vis') not in ('under', 'dup') or s.get('vis') == 'dup' and s.get('cut') is not None)
            and not (by_faces and probed(s))] + \
        revived + faced + mesh_cut + \
        [dict(o=r['o'], src='ring', sil='SectionCut', cut=r['cut'], pts=r['pts'] + r['pts'][:1]) for r in scene.get('rings', [])]
    seg_ring = [s['src'] == 'ring' for s in segs]
    for si, s in enumerate(segs):
        if s.get('cut') is not None and not seg_ring[si] and (s['cut'] < 0 or s['o'] in ring_o and s['src'] != 'mesh'):
            continue                                   # a perspective's view edge, or what the rings draw
        P = s['pts']
        for a, b in zip(P, P[1:]):
            A, B = (a[0] * f + hx, a[1] * f + hy), (b[0] * f + hx, b[1] * f + hy)
            if A == B:
                continue
            c = (0.0, 1.0) if seg_ring[si] else clip(A, B, frame)
            if c is None:
                continue
            t0, t1 = c
            pieces.append((A[0] + t0 * (B[0] - A[0]), A[1] + t0 * (B[1] - A[1]), zl(a[2], b[2], t0),
                        A[0] + t1 * (B[0] - A[0]), A[1] + t1 * (B[1] - A[1]), zl(a[2], b[2], t1), si))
    if not pieces:
        raise SystemExit('hidden-lines: no visible line falls inside the frame')
    PC = np.array(pieces)
    # the model's lines on paper (x0, y0, x1, y1): the graph's pieces and every line of the export besides, hidden and
    # duplicate ones too, which a run-on must lie on and the drawing is held to (report['model'])
    MP = np.concatenate([PC[:, [0, 1, 3, 4]], np.array([
        [a[0] * f + hx, a[1] * f + hy, b[0] * f + hx, b[1] * f + hy] for s in scene['segments']
        for a, b in zip(s['pts'], s['pts'][1:]) if a[:2] != b[:2]], dtype=float).reshape(-1, 4)])
    m_tree = shapely.STRtree(shapely.linestrings(MP.reshape(-1, 2, 2)))
    del MP

    def on_model(a, b, r=None):
        """the stretch from a to b, on the grid, within a grid step (or r) of the model's lines all along, sampled every
        grid step (at 0.25 pt a run-on stepped over a 0.22 pt gap between two tile pieces), so drawn where the model has
        it, half a step off at most, it lies within the 1.5 steps report['model'] holds the drawing to"""
        n = max(2, int(math.ceil(math.dist(a, b) / g_)) + 1)
        S = np.asarray(a, dtype=float) + (np.asarray(b, dtype=float) - np.asarray(a, dtype=float)) * np.linspace(0, 1, n)[:, None]
        return len(np.unique(m_tree.query(shapely.points(S), predicate='dwithin', distance=r or g_)[0])) == n
    seg_drawn = np.array([draw_g[o_group[s['o']]] for s in segs])
    seg_dash = [s.get('vis') if s.get('vis') in DASHED else None for s in segs]   # a group's hidden or above lines
    report['seconds']['read'] = round(time.time() - T0, 2)

    # ---- the graph: snap rounding nodes crossings and merges lines lying on each other
    T1 = time.time()
    src_lines = shapely.linestrings(PC[:, [0, 1, 3, 4]].reshape(-1, 2, 2))
    noded = shapely.union_all(src_lines, grid_size=g_)
    xy, ix = shapely.get_coordinates(shapely.get_parts(noded), return_index=True)
    E0 = []
    for i in range(len(xy) - 1):
        if ix[i] == ix[i + 1] and (xy[i, 0] != xy[i + 1, 0] or xy[i, 1] != xy[i + 1, 1]):
            E0.append((xy[i, 0], xy[i, 1], xy[i + 1, 0], xy[i + 1, 1]))
    E0 = np.array(E0)
    node_of = {}
    nodes = []

    def node(x, y):
        key = (round(x / g_), round(y / g_))
        n = node_of.get(key)
        if n is None:
            n = node_of[key] = len(nodes)
            nodes.append((key[0] * g_, key[1] * g_))
        return n
    edges = [[node(a, b), node(c, e)] for a, b, c, e in E0]
    edges = [e for e in edges if e[0] != e[1]]
    nodes = np.array(nodes)
    EA = nodes[[e[0] for e in edges]]
    EB = nodes[[e[1] for e in edges]]
    # each edge's sources: pieces it lies along, both its ends within 1.2 grid of the piece
    tree = shapely.STRtree(src_lines)
    e_lines = shapely.linestrings(np.stack([EA, EB], 1))
    qi, si_ = tree.query(e_lines, predicate='dwithin', distance=1.2 * g_)

    def seg_dist(p, a, b):
        ab = b - a
        L2 = (ab ** 2).sum(1)
        tt = np.clip(((p - a) * ab).sum(1) / np.where(L2 > 0, L2, 1), 0, 1)
        return np.hypot(*(a + ab * tt[:, None] - p).T), tt
    pa, pb = PC[si_][:, [0, 1]], PC[si_][:, [3, 4]]
    da, _ = seg_dist(EA[qi], pa, pb)
    db, _ = seg_dist(EB[qi], pa, pb)
    _, tm = seg_dist((EA[qi] + EB[qi]) / 2, pa, pb)
    along = (da <= 1.2 * g_) & (db <= 1.2 * g_)
    qi, si_, tm = qi[along], si_[along], tm[along]
    zmid = zl(PC[si_, 2], PC[si_, 5], tm)
    srcs = defaultdict(list)                           # edge: [(piece, depth at its middle)]
    for e, p, z in zip(qi.tolist(), si_.tolist(), zmid.tolist()):
        srcs[e].append((p, z))
    lost = [e for e in range(len(edges)) if e not in srcs]
    if lost:                                           # snapping's own short links: the nearest piece
        nn = tree.query_nearest(e_lines[lost], all_matches=False)
        for j, p in zip(nn[0].tolist(), nn[1].tolist()):
            srcs[lost[j]].append((p, PC[p, 2]))
    report['seconds']['graph'] = round(time.time() - T1, 2)

    # ---- each edge's owner: the nearest of its sources, the earliest group among those level with it
    T2 = time.time()
    n_e = len(edges)
    owner = np.zeros(n_e, dtype=np.int64)
    e_seg = np.zeros(n_e, dtype=np.int64)
    e_piece = np.zeros(n_e, dtype=np.int64)            # the source piece it is owned by, for its true direction
    e_z = np.zeros(n_e)
    e_drawn = np.zeros(n_e, dtype=bool)
    l_drawn = np.zeros(n_e, dtype=bool)                # drawn as a line, should it close no ring
    e_dash = [None] * n_e                              # hidden or above, where only such lines lie along it
    ring_of = [set(segs[int(PC[p, 6])]['o'] for p, _ in srcs[e] if seg_ring[int(PC[p, 6])]) for e in range(n_e)]
    has_nr = [any(not seg_ring[int(PC[p, 6])] for p, _ in srcs[e]) for e in range(n_e)]
    for e in range(n_e):
        ss = srcs[e]
        if ring_of[e] and has_nr[e]:
            ss = [(p, z) for p, z in ss if not seg_ring[int(PC[p, 6])]]
        drawn = [(p, z) for p, z in ss if seg_drawn[int(PC[p, 6])]]
        solid_ = [(p, z) for p, z in drawn if not seg_dash[int(PC[p, 6])]]
        pool = solid_ or drawn or ss
        # a tile's line lying on another object's is that line: tiles hide nothing, and an outline the tiles owned took
        # their weight and place stretch by stretch (the model's roof)
        pool = [pz for pz in pool if groups[o_group[segs[int(PC[pz[0], 6])]['o']]].get('layer') != 'TEXTURE'] or pool
        zt = max(z for _, z in pool)
        level = [(p, z) for p, z in pool if z >= zt - delta]
        p, z = min(level, key=lambda pz: (prio[o_group[segs[int(PC[pz[0], 6])]['o']]], segs[int(PC[pz[0], 6])]['o']))
        e_seg[e] = int(PC[p, 6])
        e_piece[e] = p
        owner[e] = segs[e_seg[e]]['o']
        e_z[e] = zt
        e_dash[e] = None if solid_ else seg_dash[e_seg[e]]
        l_drawn[e] = bool(drawn)
        e_drawn[e] = bool(drawn) or bool(ring_of[e])
    e_cut = [any(segs[int(PC[p, 6])].get('cut') is not None for p, _ in srcs[e]) for e in range(n_e)]   # a cut among its sources

    # ---- classes: the surfaces a hair either side of each edge's middle, and their depth at it
    mid = (EA + EB) / 2
    dv = EB - EA
    L = np.hypot(dv[:, 0], dv[:, 1])
    nrm = np.stack([-dv[:, 1], dv[:, 0]], 1) / L[:, None]
    QL, QR = mid + nrm * eps, mid - nrm * eps
    see_through = np.array([not hides_g[o_group[o]] for o in owner.tolist()])
    hitL = np.full(n_e, -1, dtype=np.int64)
    hitR = np.full(n_e, -1, dtype=np.int64)
    main_e = np.nonzero(~see_through)[0]
    if len(main_e):
        hitL[main_e] = tris.nearest(QL[main_e], hide_kept)
        hitR[main_e] = tris.nearest(QR[main_e], hide_kept)
    for gid in sorted(set(o_group[o] for o in owner[see_through].tolist())):
        es = np.nonzero(see_through & np.array([o_group[o] == gid for o in owner.tolist()]))[0]
        allow = hide_kept | np.array([o_group[o] == gid for o in tris.o.tolist()], dtype=bool)
        hitL[es] = tris.nearest(QL[es], allow)
        hitR[es] = tris.nearest(QR[es], allow)

    def o_at(h):
        """the object of each triangle h, -1 for none (every triangle seen edge-on leaves none at all)"""
        return np.where(h >= 0, tris.o[np.maximum(h, 0)], -1) if len(tris.o) else np.full(len(h), -1, dtype=np.int64)

    def side(h, e_idx):
        ob = o_at(h)
        z = np.full(len(h), -np.inf)
        ok_ = h >= 0
        if ok_.any():
            z[ok_] = tris.plane_z(h[ok_], mid[e_idx][ok_])
        return ob, z
    idx = np.arange(n_e)
    oL, zL = side(hitL, idx)
    oR, zR = side(hitR, idx)
    body = [groups[g].get('body', g) for g in o_group]
    cls = np.empty(n_e, dtype=object)
    for e in range(n_e):
        s = segs[e_seg[e]]
        o = int(owner[e])
        if e_dash[e]:
            cls[e] = e_dash[e]
            continue
        if s.get('cut') is not None:
            cls[e] = 'cut'
            continue
        if s['src'] == 'curve' or o not in meshed_o:
            cls[e] = 'line'
            continue
        a, b = int(oL[e]), int(oR[e])
        inL = a >= 0 and body[a] == body[o]
        inR = b >= 0 and body[b] == body[o]
        back = e_z[e] - min(zL[e], zR[e])
        if not (inL and inR):                          # the body against the paper, a surface behind it or another body
            far = a < 0 or b < 0 or back > delta
            cls[e] = 'profile' if far or not (inL or inR) else 'base'
        elif back > delta:
            cls[e] = 'overlap' if back >= gap else 'step'
        else:
            cls[e] = 'crease' if a == b else 'seam'
    # openings, with faces: an edge along the rim of a hole through a face turned to the camera (a window, a door;
    # idbuf.openings) is the outline of the nearer plane it is cut out of and takes that plane's outline weight, a
    # profile's; one along the rim of such a hole through a face turned away, the reveal's far edge seen through it, is
    # drawn lighter, an overlap at most; a blind
    # recess is none (idbuf.openings) and keeps its class by depth. A rim is matched to the edge's own object, along it
    # within 20 degrees, within 3 MESH_PT on the page and in depth
    report['openings'] = dict(rims=0, reveals=0)
    if by_faces and (E['hole'] != 0).any():
        hj = np.nonzero(E['hole'] != 0)[0]
        HA, HB = E['a'][hj] * [f, f, 1.0] + [hx, hy, 0.0], E['b'][hj] * [f, f, 1.0] + [hx, hy, 0.0]
        hab = HB[:, :2] - HA[:, :2]
        ce = np.array([e for e in range(n_e) if cls[e] in ('profile', 'base', 'overlap', 'step', 'seam', 'crease')],
                      dtype=np.int64)
        qi, pi = shapely.STRtree(shapely.linestrings(np.stack([HA[:, :2], HB[:, :2]], 1))).query(
            shapely.points(mid[ce]), predicate='dwithin', distance=3 * MESH_PT / k) if len(ce) else (np.zeros(0, int),) * 2
        keep = E['obj'][hj[pi]] == owner[ce[qi]]
        keep &= np.abs(dv[ce[qi], 0] * hab[pi, 1] - dv[ce[qi], 1] * hab[pi, 0]) <= \
            math.sin(math.radians(20)) * L[ce[qi]] * np.hypot(hab[pi, 0], hab[pi, 1])
        tq = np.clip(((mid[ce[qi]] - HA[pi, :2]) * hab[pi]).sum(1) / np.maximum((hab[pi] ** 2).sum(1), 1e-300), 0, 1)
        dz = np.abs(zl(HA[pi, 2], HB[pi, 2], tq) - e_z[ce[qi]])
        keep &= dz <= 3 * MESH_PT / (k * f) * (np.abs(e_z[ce[qi]]) / L_ if persp else 1.0)
        best = {}
        for e, j, z_ in zip(ce[qi[keep]].tolist(), pi[keep].tolist(), dz[keep].tolist()):
            if e not in best or z_ < best[e][1]:
                best[e] = (j, z_)
        for e, (j, _) in best.items():
            if E['hole'][hj[j]] > 0:
                cls[e] = 'profile'
                report['openings']['rims'] += 1
            elif cls[e] in ('profile', 'base'):
                cls[e] = 'overlap'
                report['openings']['reveals'] += 1
    report['seconds']['classes'] = round(time.time() - T2, 2)

    # ---- weights: each class a sublayer of its group's layer
    def role_weight(lid):
        L = t.layer('drawing', lid)
        return L.get('weight') or t['roles'][L['role']].get('weight')
    style_of = {}                                      # (group, class): (layer, sublayer, weight name or pt)

    def set_weight(g, c):
        """the weight a group's weights set for class c, keyed by the class or its plural ({"cuts": "heavy"}), or None"""
        ws = g.get('weights') or {}
        return ws.get(c, ws.get(PLURAL.get(c)))

    def cut_weight(gid):
        """a group's cut: as its weights set it; heavy for a group on a cut layer and for the ground; a rung under heavy for a detail or furniture group; else its
        profile's weight, so context cut by the plane stays as light as its outline"""
        g = groups[gid]
        role = t.layer('drawing', g.get('layer', 'CONTEXT'))['role']
        if set_weight(g, 'cut') is not None:
            return set_weight(g, 'cut')
        if role == 'cut' or g.get('ground'):
            return 'heavy'
        if role == 'light':
            return LADDER[1]
        return style(gid, 'profile')[2]

    def style(gid, c):
        key = (gid, c)
        if key in style_of:
            return style_of[key]
        g = groups[gid]
        if c in DASHED:                                # dashed on its own layer, at its role's weight
            style_of[key] = (DASHED[c], f'{gid} {PLURAL[c]}', set_weight(g, c) or role_weight(DASHED[c]))
            return style_of[key]
        lid = g.get('layer', 'CONTEXT')
        if c == 'cut' and (t.layer('drawing', lid)['role'] == 'cut' or g.get('ground') or set_weight(g, c)):
            # a cut that closes no region (a wall, floor or roof modelled as surfaces) is still the cut: on OUTLINE, since
            # CUT holds closed paths, at the body's cut weight (the model's slabs and roofs drew theirs as medium lines)
            style_of[key] = ('OUTLINE', f'{gid} open cuts', cut_weight(gid))
            return style_of[key]
        if t.layer('drawing', lid)['role'] == 'cut':   # what the clip planes cut: its lines are seen beyond them
            lid = 'BEYOND'
        own = lid
        if c in ('profile', 'base', 'cut') and g.get('profile_layer'):
            lid = g['profile_layer']
        band = role_weight(g.get('profile_layer') or own)
        pw = g.get('profile_weight') or band            # in points it sets the outline; the rest step from the band
        start = pw if isinstance(pw, str) else band
        step = int(hl['steps'].get(c, 0))
        set_ = set_weight(g, c)
        if set_ is not None:
            w = set_
        elif c == 'line':
            w = role_weight(lid)
        elif not isinstance(pw, str) and step == 0:
            w = pw
        elif start in LADDER:
            w = LADDER[min(LADDER.index(start) + step, len(LADDER) - 1)]
        else:
            w = start
        sub = f'{gid} {PLURAL[c]}'
        style_of[key] = (lid, sub, w)
        return style_of[key]
    line_style = [style(o_group[int(owner[e])], cls[e]) if l_drawn[e] or (ring_of[e] and not has_nr[e]) else None
                  for e in range(n_e)]
    # crease turns: with crease_turns_deg, a crease whose faces turn by less than an angle listed is a weight lighter for
    # each, on a sublayer of its own ('building creases under 30 deg'): a fold or an obtuse corner reads lighter than a
    # square one, as in a pen drawing. The turn is read from the two triangles either side of the edge's middle
    turns = sorted(float(x) for x in req.get('crease_turns_deg') or [])
    if turns:
        report['crease_turns'] = dict(turns_deg=turns, edges=[0] * (len(turns) + 1))
        for e in range(n_e):
            st_ = line_style[e]
            if st_ is None or cls[e] != 'crease' or hitL[e] < 0 or hitR[e] < 0:
                continue
            c_ = abs(float((nrm_c[hitL[e]] * nrm_c[hitR[e]]).sum()))
            b = sum(math.degrees(math.acos(min(1.0, c_))) < x for x in turns)
            report['crease_turns']['edges'][b] += 1
            if b:
                lid, sub, w = st_
                w2 = LADDER[min(LADDER.index(w) + b, len(LADDER) - 1)] if w in LADDER else w
                line_style[e] = (lid, f'{sub} under {turns[len(turns) - b]:g} deg', w2)
    # depth bands: with depth_bands_m, a line within the first band, in metres beyond the first clip plane (without one,
    # beyond the subject's nearest drawn line, context left out), is a weight heavier than its class, never heavier than
    # its group's profile weight, one in the next keeps its class's weight, and one past each further edge a weight
    # lighter, each band on a sublayer of its own ('building overlaps 3-10 m'), as Revit's view depth and Archicad's
    # distant area grade what lies beyond a cut; all K100, a grey line under 0.5 pt printing as dots
    # With depth_bands_share instead, the bands are those shares of how far the subject runs beyond the plane (its
    # lines' 95th percentile, context left out), since fixed metres fit one drawing: the model's lines run 0 to 6.3 m past
    # its plane, and bands at 3 and 8 m put 26,515 of 36,422 edges in the first and 58 past the last
    bands_m = sorted(float(x) for x in req.get('depth_bands_m') or [])
    share_ = [] if bands_m else sorted(float(x) for x in req.get('depth_bands_share') or [])
    if bands_m or share_:
        um = float(scene['unit_mm']) / 1000.0
        cl = (scene.get('clip') or [None])[0]
        drawn_ = [e for e in range(n_e) if line_style[e] is not None]
        subj_ = [e for e in drawn_
                 if t.layer('drawing', groups[o_group[int(owner[e])]].get('layer', 'CONTEXT'))['role'] != 'context']
        z_front = max((e_z[e] for e in (subj_ or drawn_)), default=0.0)   # the subject's nearest line, not a ground's edge
        deps = {}
        for e in range(n_e):
            if line_style[e] is None or cls[e] == 'cut' or e_dash[e]:
                continue
            if cl:
                pm = model_at(float(mid[e][0]), float(mid[e][1]), float(e_z[e]))
                nn = math.sqrt(sum(v * v for v in cl['normal']))
                deps[e] = sum((pm[i] - cl['origin'][i]) * cl['normal'][i] for i in range(3)) / nn * um
            else:
                deps[e] = (z_front - e_z[e]) * um
        if share_ and deps:
            subj = [d_ for e, d_ in deps.items()
                    if t.layer('drawing', groups[o_group[int(owner[e])]].get('layer', 'CONTEXT'))['role'] != 'context']
            span = float(np.percentile(subj or list(deps.values()), 95))
            if by_faces:
                # with faces, by area: the subject's surfaces as the buffer sees them, a pixel centre a point, each at its
                # depth past the plane. Counted by drawn edge, a long segment weighed as much as a mesh's short edge
                # (the model's span fell from 5.13 to 4.75 m when segments took the place of the meshes' edges)
                ctx_ = np.array([t.layer('drawing', groups[g_id].get('layer', 'CONTEXT'))['role'] == 'context'
                                 for g_id in o_group] + [True])
                n_px = max(1, int(round(idbuf.R_PX)))
                T_px = tri_px[n_px // 2::n_px, n_px // 2::n_px]
                jj, ii = np.nonzero(T_px >= 0)
                tt_ = T_px[jj, ii].astype(np.int64)
                del T_px
                sel = ~ctx_[tris.o[tt_]]
                if sel.any():
                    X_ = (ii[sel] * n_px + n_px // 2 + 0.5) / s_px
                    Y_ = (jj[sel] * n_px + n_px // 2 + 0.5) / s_px
                    Z_ = tris.plane_z(tt_[sel], np.stack([X_, Y_], 1))
                    if cl:
                        Cq = (np.stack([(X_ - hx) * -Z_ / L_, (Y_ - hy + sy_) * -Z_ / L_, Z_], 1) if persp
                              else np.stack([(X_ - hx) / f, (Y_ - hy) / f, Z_], 1))
                        Pm = (Minv @ np.column_stack([Cq, np.ones(len(Cq))]).T).T[:, :3]
                        nv_ = np.array(cl['normal'], dtype=float)
                        dep_px = (Pm - np.array(cl['origin'], dtype=float)) @ nv_ / np.linalg.norm(nv_) * um
                    else:
                        dep_px = (z_front - Z_) * um
                    span = float(np.percentile(dep_px, 95))
            bands_m = [float(f'{x * span:.3g}') for x in share_] if span > 0 else []   # 3 figures: models in inches too
    if by_faces:
        del tri_px, s_px
    if bands_m:
        report['depth_bands'] = dict(bands_m=bands_m, edges=[0] * (len(bands_m) + 1), from_span=bool(share_))
        for e, dep in deps.items():
            st_ = line_style[e]
            b = sum(dep > x for x in bands_m)
            report['depth_bands']['edges'][b] += 1
            lid, sub, w = st_
            if w in LADDER:                            # the first band a weight heavier, never past the group's outline
                top = style(o_group[int(owner[e])], 'profile')[2]
                i_ = min(max(LADDER.index(w) - 1 + b, LADDER.index(top) if top in LADDER else 0), len(LADDER) - 1)
                tail = (f'under {bands_m[0]:g} m' if not b else f'{bands_m[b - 1]:g}-{bands_m[b]:g} m' if b < len(bands_m)
                        else f'past {bands_m[-1]:g} m')
                line_style[e] = (lid, f'{sub} {tail}', LADDER[i_])
    # a line's style along it: a run of edges under 2 pt in one style between two of another, along a chain of one
    # object's edges straight on through nodes where it goes on alone (under 20 degrees), takes theirs, so a class or a
    # depth band does not flicker where what lies behind or the depth is near a threshold (a book's side between
    # profile and step; a roof's base between two bands)
    report['styles_smoothed'] = 0
    by_o = defaultdict(list)
    for e in range(n_e):
        if line_style[e] is not None and not ring_of[e] and not e_dash[e] and cls[e] not in ('cut', 'line'):
            by_o[int(owner[e])].append(e)
    two_s = 2.0 / k
    for o, es in by_o.items():
        inc = defaultdict(list)
        for e in es:
            inc[edges[e][0]].append(e)
            inc[edges[e][1]].append(e)

        def on_from(e, v):
            """the edge the chain goes on along from edge e at node v, or None"""
            nx = [y for y in inc[v] if y != e]
            if len(nx) != 1:
                return None
            y = nx[0]
            d1 = nodes[edges[e][1] if edges[e][0] == v else edges[e][0]] - nodes[v]
            d2 = nodes[edges[y][1] if edges[y][0] == v else edges[y][0]] - nodes[v]
            c_ = -float(d1 @ d2) / max(float(np.hypot(*d1) * np.hypot(*d2)), 1e-300)
            return y if c_ >= math.cos(math.radians(20)) else None
        seen = set()
        for e0 in es:
            if e0 in seen:
                continue
            seen.add(e0)
            chain_e = [e0]
            for end_ in (0, 1):
                e, v = e0, edges[e0][end_]
                while True:
                    y = on_from(e, v)
                    if y is None or y in seen:
                        break
                    seen.add(y)
                    (chain_e.append if end_ == 1 else lambda z: chain_e.insert(0, z))(y)
                    v = edges[y][1] if edges[y][0] == v else edges[y][0]
                    e = y
            if len(chain_e) < 3:
                continue
            runs_s = []                                # [style, length, edges]
            for e in chain_e:
                if runs_s and runs_s[-1][0] == line_style[e]:
                    runs_s[-1][1] += L[e]
                    runs_s[-1][2].append(e)
                else:
                    runs_s.append([line_style[e], L[e], [e]])
            for n_r in range(1, len(runs_s) - 1):
                st_, ln_r, es_r = runs_s[n_r]
                if ln_r < two_s and runs_s[n_r - 1][0] == runs_s[n_r + 1][0] and runs_s[n_r - 1][0][0] == st_[0]:
                    for e in es_r:
                        line_style[e] = runs_s[n_r - 1][0]
                    runs_s[n_r][0] = runs_s[n_r - 1][0]
                    report['styles_smoothed'] += 1
    e_style = [RING if ring_of[e] else line_style[e] for e in range(n_e)]

    # ---- the engine checked against the meshes: a point of an edge with another object's surface in front of it, more
    # than lim from it measured square to that surface, should have been hidden. The engine drew such points in
    # perspective (a box's corner through the box in front of it, fuzz seeds 4 and 13, which ray casting in Rhino
    # confirms), threaded (a driveway's edge through a home 28 m in front of it), and behind the model's outer roof skin
    # (contact curves 4 to 11 cm behind a twisted face, which it hid behind that face alone and not once the face was
    # joined to the twisted hips beside it, seen edge on). An object's own mesh is left out, since at a curved
    # silhouette its facets stand in front of the true curve; measured square to the surface, a line on a face seen at
    # a grazing angle stays. An export before version 3 meshed a twisted face up to 200 mm off it, so there only an
    # object more than gap_m in front along the view counts
    lim = delta + 3 * MESH_PT / k if tight else max(gap, delta + 3 * MESH_PT / k)

    def covered(Q, zs, ow, by=False):
        """for points Q (n x 2) at depths zs on owners ow: True where another object's surface stands more than lim in
        front; with by, also the object of the surface nearest the camera at each"""
        h = tris.nearest(Q, hide_kept)
        hit = h >= 0
        far = np.full(len(Q), -np.inf)
        if hit.any():
            far[hit] = tris.plane_z(h[hit], Q[hit]) - zs[hit]
            if tight:
                p_ = cam((Q[hit, 0] - hx) / f, (Q[hit, 1] - hy) / f, zs[hit])
                far[hit] = np.sign(far[hit]) * np.abs(((p_ - tri_cam[h[hit]]) * nrm_c[h[hit]]).sum(1))
        out = (far > lim) & (o_at(h) != ow)
        return (out, o_at(h)) if by else out

    # ---- the graph as lists that the passes below edit: a stretch the meshes see hidden, cuts, doubles, line ends
    T3 = time.time()
    alive = [e_drawn[e] for e in range(n_e)]
    edges = [list(x) for x in edges]
    nodes = [tuple(p) for p in nodes]
    adj = defaultdict(set)
    for e in range(n_e):
        if alive[e]:
            adj[edges[e][0]].add(e)
            adj[edges[e][1]].add(e)

    def add_node(p):
        nodes.append((float(p[0]), float(p[1])))
        return len(nodes) - 1

    def add_edge(a, b, like):
        edges.append([a, b])
        alive.append(True)
        e_style.append(e_style[like])
        e_extra.append(like)
        adj[a].add(len(edges) - 1)
        adj[b].add(len(edges) - 1)
        return len(edges) - 1

    fate = {}                                          # an edge taken out by a pass: why, for --explain
    fate_by = {}                                       # the object in front of it, or the line it gave way to

    killed_log = []                                    # every edge taken out, in order

    def kill(e, why=None):
        alive[e] = False
        killed_log.append(e)
        if why:
            fate[e] = why
        adj[edges[e][0]].discard(e)
        adj[edges[e][1]].discard(e)

    halves = {}                                        # an edge split in two: its two halves

    def split(e, p):
        """edge e split at point p on it; the new node"""
        a, b = edges[e]
        v = add_node(p)
        kill(e)
        halves[e] = (add_edge(a, v, e), add_edge(v, b, e))
        return v

    def live_of(e):
        """e while it is alive, else the live edges it was split into"""
        out, todo = [], [e]
        while todo:
            x = todo.pop()
            if alive[x]:
                out.append(x)
            else:
                todo += halves.get(x, ())
        return out

    def first(e):
        """the graph's own edge an added edge was made from"""
        while e >= n_e:
            e = e_extra[e]
        return e
    e_extra = [None] * n_e

    def heading(e, v):
        a, b = edges[e]
        u = b if a == v else a
        return math.atan2(nodes[u][1] - nodes[v][1], nodes[u][0] - nodes[v][0])

    own_dir = {}                                       # an added edge along no source (a closed gap's cut): its direction

    def slope(e):                                      # its source's direction: snapping a short piece can turn it 45 degrees
        while e >= n_e and e not in own_dir:
            e = e_extra[e]
        if e in own_dir:
            return own_dir[e]
        q = PC[e_piece[e]]
        return math.atan2(q[4] - q[1], q[3] - q[0]) % math.pi

    def bend(e, x):
        t_ = abs(slope(e) - slope(x))
        return min(t_, math.pi - t_)

    def elen(e):
        return math.dist(nodes[edges[e][0]], nodes[edges[e][1]])

    def chain(es):
        """a style's edges chained, straight on through nodes where three or more meet: [(nodes, closed, edges)]"""
        inc = defaultdict(list)
        for e in es:
            inc[edges[e][0]].append(e)
            inc[edges[e][1]].append(e)
        pair = {}                                      # (node, edge): the edge the path goes on along
        for v, es_v in inc.items():
            if len(es_v) == 2:
                pair[(v, es_v[0])], pair[(v, es_v[1])] = es_v[1], es_v[0]
            elif len(es_v) > 2:
                cand = []
                for i in range(len(es_v)):
                    for j in range(i + 1, len(es_v)):
                        turn = abs(abs(heading(es_v[i], v) - heading(es_v[j], v)) - math.pi)
                        turn = min(turn, abs(turn - 2 * math.pi))
                        short = min(elen(es_v[i]), elen(es_v[j])) < minlen
                        cand.append((not short, turn, es_v[i], es_v[j]))
                used = set()
                for a in es_v:                         # a loop out of the node and back through nodes of two lines alone
                    if a in used:                      # closes on itself, so a line meeting it there ends on it
                        continue                       # (a door knob's ring with its stem)
                    w, x = v, a
                    while True:
                        u = edges[x][1] if edges[x][0] == w else edges[x][0]
                        if u == v or len(inc[u]) != 2:
                            break
                        x = inc[u][0] if inc[u][1] == x else inc[u][1]
                        w = u
                    if u == v and x != a and x in es_v and x not in used:
                        used |= {a, x}
                        pair[(v, a)], pair[(v, x)] = x, a
                for straight, turn, a, b in sorted(cand):     # an edge under min_len_pt goes on whatever the turn
                    if straight and turn > math.radians(20):
                        continue
                    if a in used or b in used:
                        continue
                    used |= {a, b}
                    pair[(v, a)], pair[(v, b)] = b, a
        seen = set()

        def walk(e, v):
            out, run = [v], []
            e0 = e
            while True:
                seen.add(e)
                run.append(e)
                a, b = edges[e]
                u = b if a == v else a
                out.append(u)
                nxt = pair.get((u, e))
                if nxt is None:
                    return out, False, run
                if nxt == e0:
                    return out, True, run
                if nxt in seen:
                    return out, False, run
                e, v = nxt, u
        chains = []
        for v, es_v in inc.items():                     # open chains start where no pairing goes on
            for e in es_v:
                if e not in seen and (v, e) not in pair:
                    chains.append(walk(e, v))
        for e in es:                                    # what is left goes round in rings
            if e not in seen:
                chains.append(walk(e, edges[e][0]))
        return chains

    # the meshes' check, every half point along each line, its depth there read from its source: a hidden stretch is
    # cut out at the points where it starts and ends, found by halving to a hundredth of a point, and the ends left
    # are met below like any other
    def depth_on(e, Q):
        """the depth of edge e's source at points Q (n x 2) on it; e one edge, or one for each point"""
        q = PC[e_piece[np.broadcast_to(e, (len(Q),))]]
        pa, pb = q[:, [0, 1]], q[:, [3, 4]]
        ab = pb - pa
        tq = np.clip(((Q - pa) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-300), 0, 1)
        return zl(q[:, 2], q[:, 5], tq)
    report['hidden_by_meshes'] = dict(count=0, length_pt=0.0, examples=[], lim_pt=round(lim * k, 3))
    step = 0.5 / k
    chk_e = np.array([e for e in range(n_e) if alive[e] and not ring_of[e] and not e_dash[e] and not by_faces], dtype=np.int64)
    if len(chk_e):                                     # every line's points in one query of the meshes
        A_m = np.array([nodes[edges[e][0]] for e in chk_e])
        B_m = np.array([nodes[edges[e][1]] for e in chk_e])
        L_m = np.hypot(*(B_m - A_m).T)
        n_m = np.maximum(3, np.ceil(L_m / step).astype(np.int64))
        off = np.concatenate([[0], np.cumsum(n_m)])
        ts_m = np.concatenate([(np.arange(n) + 0.5) / n for n in n_m])
        ei = np.repeat(np.arange(len(chk_e)), n_m)
        Q_m = A_m[ei] + (B_m - A_m)[ei] * ts_m[:, None]
        hid_m, by_m = covered(Q_m, depth_on(chk_e[ei], Q_m), owner[chk_e[ei]], by=True)
        cov_j = {}                                     # line: the object in front over most of its hidden points
        trans = []                                     # (line, sample) where visibility changes
        for j, e in enumerate(chk_e.tolist()):
            hid = hid_m[off[j]:off[j + 1]]
            if not hid.any():
                continue
            cov_j[j] = int(np.bincount(by_m[off[j]:off[j + 1]][hid]).argmax())
            report['hidden_by_meshes']['count'] += 1
            report['hidden_by_meshes']['length_pt'] += float(hid.mean() * L_m[j] * k)
            if len(report['hidden_by_meshes']['examples']) < 20:
                m = Q_m[off[j] + int(np.argmax(hid))]
                report['hidden_by_meshes']['examples'].append(dict(layer=objs[int(owner[e])]['layer'], at_pt=paper(m, hx, hy, k),
                                                                   model=model_at(m[0], m[1], float(depth_on(e, m[None])[0]))))
            if hid.all():
                kill(e, 'the meshes see it hidden')
                fate_by[e] = cov_j[j]
                continue
            trans += [(j, int(i)) for i in np.nonzero(hid[:-1] != hid[1:])[0]]
        if trans:                                      # each change found by halving to a hundredth of a point, all together
            tj = np.array([j for j, _ in trans])
            ti = off[tj] + np.array([i for _, i in trans])
            lo, hi, before = ts_m[ti], ts_m[ti + 1], hid_m[ti]
            for _ in range(12):
                mid_ = (lo + hi) / 2
                pts = A_m[tj] + (B_m - A_m)[tj] * mid_[:, None]
                same = covered(pts, depth_on(chk_e[tj], pts), owner[chk_e[tj]]) == before
                lo, hi = np.where(same, mid_, lo), np.where(same, hi, mid_)
            by = defaultdict(list)                     # line: [(fraction along it where visibility changes, hidden before it)]
            for j, t_, b_h in zip(tj.tolist(), ((lo + hi) / 2).tolist(), before.tolist()):
                by[j].append((t_, b_h))
            for j, cuts_t in by.items():
                a_, b_ = A_m[j], B_m[j]
                rest = int(chk_e[j])                   # split in order along it: (a, v) is always the earlier piece
                for t_, before_ in sorted(cuts_t):
                    split(rest, a_ + (b_ - a_) * t_)
                    earlier, rest = len(edges) - 2, len(edges) - 1
                    if before_:
                        kill(earlier, 'the meshes see it hidden')
                        fate_by[earlier] = cov_j[j]
                if not sorted(cuts_t)[-1][1]:
                    kill(rest, 'the meshes see it hidden')
                    fate_by[rest] = cov_j[j]
    report['hidden_by_meshes']['length_pt'] = round(report['hidden_by_meshes']['length_pt'], 2)
    report['seconds']['meshes'] = round(time.time() - T3, 2)

    # ---- cuts: each object's cut edges polygonized, its region the faces inside an odd number of its rings. An edge
    # that bounds no face (a sliver beside a corner that snapping put within a grid step of the cut; an engine line
    # lying a hair off the cut) is drawn as what its other sources make it, before doubles and line ends see it; one
    # with no other source is a cut that does not close, reported and drawn as a line
    def exact(op, *a):
        """a shapely overlay on the graph's own coordinates: on the grid it would move a node the line ends added off it,
        and a line ending there would end off the cut drawn; on the grid only where the exact overlay fails"""
        try:
            return op(*a)
        except shapely.errors.GEOSException:
            return op(*a, grid_size=g_)
    # a body's cut is one poché where its parts touch, but a lighter group in a heavier body (its windows and doors, a
    # roof's frame) is not massing: its cut is its own, a rung lighter and closed, under the massing's (furniture lighter but continuous, as windows and doors and other elements that are not massing). rkey is the key an object's cut region goes under: its body, or such a group
    first_g = {}
    for gid in sorted(groups, key=lambda x: prio[x]):
        first_g.setdefault(groups[gid].get('body', gid), gid)
    gkey = {}
    for gid in sorted(groups, key=lambda x: prio[x]):
        b_ = groups[gid].get('body', gid)
        gkey[gid] = b_ if t.weight(cut_weight(gid), d.scale) >= t.weight(cut_weight(first_g[b_]), d.scale) - 1e-9 else gid
        first_g.setdefault(gkey[gid], gid)
    rkey = [gkey[g] for g in o_group]
    ring_e = defaultdict(list)                         # object: the live edges of its cut
    for e in range(len(edges)):
        if alive[e] and e_style[e] is RING:
            for o in ring_of[first(e)]:
                ring_e[o].append(e)
    used, regions, opened = set(), defaultdict(list), defaultdict(list)
    obj_regs = defaultdict(list)                       # body: [(group order, object, its region)]
    for o, es in sorted(ring_e.items()):
        faces = [q for q in shapely.get_parts(shapely.polygonize(
            [LineString([nodes[edges[e][0]], nodes[edges[e][1]]]) for e in es])) if q.area > 0]
        bound, reg = set(), None
        for q in faces:
            for r in [q.exterior] + list(q.interiors):
                c = list(r.coords)
                bound.update(zip(c, c[1:]))
                bound.update(zip(c[1:], c))
            q = shapely.Polygon(q.exterior)
            reg = q if reg is None else exact(shapely.symmetric_difference, reg, q)
        used.update(e for e in es if (nodes[edges[e][0]], nodes[edges[e][1]]) in bound)
        if reg is not None and not reg.is_empty:
            regions[rkey[o]].append(reg)
            obj_regs[rkey[o]].append((prio[o_group[o]], o, reg))
    for e in range(len(edges)):
        if alive[e] and e_style[e] is RING and e not in used:
            f0 = first(e)
            e_style[e] = line_style[f0]
            if not has_nr[f0]:
                for o in ring_of[f0]:
                    opened[o].append(e)
            if e_style[e] is None:
                kill(e, 'a cut edge in no closed region, with no line of its own')

    # ---- cuts: walls, floors and roofs modelled as surfaces (open polysurfaces, unjoined skins) have no closed ring.
    # What of a body's section is solid is read from the model's section curves as the graph holds them, all of them
    # before any pass has taken one out: its surfaces' cut segments (the engine's, Duplicate ones too, and those drawn
    # again from the meshes), with its closed solids' regions, each cell solid where the surfaces round it face away
    # from it, as the meshes' normals at the plane say, and else where it is thinner than hidden_lines.cut_surface_m
    # (solid_cells); a cell the sides leave mixed and thicker than that is reported, not filled. the model's right wall, an
    # open polysurface 1 m thick, closes by its sides, and the model's roof skins, 5 cm apart, by theirs. A line ending a
    # hair short of another is run on to it, and two skins' free ends facing away from each other are capped across;
    # those join the graph. The cells are the graph's own faces, its lines snap-rounded, so their outlines are its
    # edges: drawn off them, an outline would leave slivers in the poché  and line ends off the cut.
    # The lines round a solid cell are its outline, not lines of their own (158 of the model's 173 wall and floor objects
    # were surfaces)
    hair_ = g_ / 100

    def node_at(p):
        """the graph's node at point p, the line it lies on split there; a node of its own on none"""
        live = [e for e in range(len(edges)) if alive[e]]
        dd, _ = seg_dist(np.repeat(np.array([p]), len(live), 0), np.array([nodes[edges[e][0]] for e in live]),
                         np.array([nodes[edges[e][1]] for e in live]))
        j = int(np.argmin(dd))
        if dd[j] > hair_:
            return add_node(p)
        x = live[j]
        v = next((v for v in edges[x] if math.dist(nodes[v], p) <= hair_), None)
        return split(x, p) if v is None else v

    surf_n = 0
    surf_round = set()                                 # edges round a face of surfaces made a region
    unresolved = []                                    # a cell of surfaces its sides leave mixed, thicker than cmax
    cmax = float(hl.get('cut_surface_m') or 0) * 1000.0 / float(scene['unit_mm']) * f    # in drawing units
    snap_ = 0.75 * g_                                  # how far snap rounding can move a line: half a grid step's diagonal

    def cut_lines(near_):
        """the live edges with a cut among their sources (no dashed one) whose lines come within snap_ of geometry near_"""
        es_ = [e for e in range(len(edges)) if alive[e] and e_cut[first(e)] and not e_dash[first(e)]]
        if not es_:
            return []
        tr_ = shapely.STRtree(shapely.linestrings([[nodes[edges[e][0]], nodes[edges[e][1]]] for e in es_]))
        return [es_[i] for i in tr_.query(near_, predicate='dwithin', distance=snap_).tolist()]

    def attach(p, es_):
        """the graph's node for point p of a new outline: a node of a cut edge of es_ within snap_, or one split into the
        nearest such edge, else node_at"""
        best = None
        for e in es_:
            if not alive[e]:
                continue
            A_, B_ = np.array(nodes[edges[e][0]]), np.array(nodes[edges[e][1]])
            dd, tt = seg_dist(np.array([p]), A_[None], B_[None])
            if dd[0] <= snap_ and (best is None or dd[0] < best[0]):
                best = (float(dd[0]), e, A_ + (B_ - A_) * float(tt[0]))
        if best is None:
            return node_at(p)
        _, e, q = best
        v = min(edges[e], key=lambda v_: math.dist(nodes[v_], q))
        return v if math.dist(nodes[v], q) <= snap_ else split(e, tuple(q))
    if cmax > 0 and not persp:
        open_o = {o for o in range(len(objs)) if o not in ring_o and draw_g[o_group[o]]
                  and t.layer('drawing', groups[o_group[o]].get('layer', 'CONTEXT'))['role'] == 'cut'}
        lines_k = defaultdict(list)                    # rkey: the live edges with a cut of its surfaces among their sources
        for e in range(len(edges)):
            if alive[e] and e_cut[first(e)] and not e_dash[first(e)]:
                for b_ in {rkey[segs[int(PC[p_, 6])]['o']] for p_, _ in srcs[first(e)]
                           if segs[int(PC[p_, 6])].get('cut') is not None and segs[int(PC[p_, 6])]['o'] in open_o}:
                    lines_k[b_].append(e)
        for b_, es_b in sorted(lines_k.items()):
            sides_b = [list(x) + [o] for o in range(len(objs)) if rkey[o] == b_ for x in sides_o.get(o, ())]
            sol, unres, links, turned = solid_cells([[nodes[edges[e][0]], nodes[edges[e][1]]] for e in es_b], sides_b,
                                                    regions[b_], cmax, near, g_, 0.5 / k, 3 * MESH_PT / k)
            for o, o2 in sorted({(o, o2) for o, o2, _ in turned if o >= 0}):   # a fault of the model, on the turned one
                gap_m = max(g for a_, b2_, g in turned if (a_, b2_) == (o, o2)) / f * float(scene['unit_mm']) / 1000.0
                report['issues'].append(dict(object=o, ids=objs[o]['ids'], layer=objs[o]['layer'],
                                             issue=f"faces the same way as {objs[o2]['layer']} "
                                             f"{objs[o2]['ids'][0] if objs[o2]['ids'] else ''} beside it, {gap_m:.2f} m "
                                             f"apart, so one of the two is turned; read as facing out of the wall between"))
            for q in unres:
                unresolved.append(dict(body=b_, at_pt=paper(q.representative_point().coords[0], hx, hy, k),
                                       area_pt2=round(q.area * k * k, 1)))
            if not sol:
                continue
            like = es_b[0]
            mask = shapely.union_all(sol)
            for a_, c_ in links:                       # a run-on or cap round a solid cell joins the graph
                if mask.boundary.distance(shapely.Point((a_[0] + c_[0]) / 2, (a_[1] + c_[1]) / 2)) <= snap_:
                    v0, v1 = attach(a_, es_b), attach(c_, es_b)
                    if v0 != v1:
                        e_new = add_edge(v0, v1, like)
                        e_style[e_new] = RING
                        surf_round.add(first(e_new))
                        own_dir[e_new] = math.atan2(nodes[v1][1] - nodes[v0][1], nodes[v1][0] - nodes[v0][0]) % math.pi
            at_e = {}
            for e in cut_lines(mask):
                at_e[(nodes[edges[e][0]], nodes[edges[e][1]])] = at_e[(nodes[edges[e][1]], nodes[edges[e][0]])] = e
            for q in sol:
                round_ = set()
                for r in [q.exterior] + list(q.interiors):
                    c = list(r.coords)
                    round_.update(at_e[x] for x in zip(c, c[1:]) if x in at_e)
                for e in round_:
                    e_style[e] = RING
                    surf_round.add(first(e))
                o = int(owner[first(min(round_))]) if round_ else int(owner[first(like)])
                regions[b_].append(q)
                obj_regs[b_].append((prio[o_group[o]], o, q))
                surf_n += 1

    # ---- cuts: a body's regions merged where they touch, as the survey merges walls with the posts that touch them,
    # each region one closed path on CUT; what did not close is reported where it is
    report['cuts'] = dict(objects=len(ring_e), regions=0, open=[], from_surfaces=surf_n, unresolved=unresolved)
    cut_polys = []
    for o, es in sorted(opened.items()):
        merged = shapely.line_merge(shapely.MultiLineString([[nodes[edges[e][0]], nodes[edges[e][1]]] for e in es]))
        for part in shapely.get_parts(merged):
            P = list(part.coords)
            report['cuts']['open'].append(dict(object=o, ids=objs[o]['ids'], layer=objs[o]['layer'],
                                               length_pt=round(part.length * k, 2),
                                               ends_pt=[paper(q, hx, hy, k) for q in (P[0], P[-1])],
                                               model=model_at(P[0][0], P[0][1], float(e_z[first(opened[o][0])]))))
    # a body's cut at its first group's cut_weight; where two bodies' cuts overlap (the model has them interpenetrate) the
    # earlier group's is whole and the later's is clipped by it, and the overlap reported
    taken = None
    report['cuts']['overlaps'] = []
    report['cuts']['gaps_closed'] = []
    report['cuts']['wedges'] = []
    report['cuts']['merged'] = []
    clipped = []
    gaps = []                                          # (body, a gap closed, its cut before)

    def wedge(q, u):
        """does a piece the closing would fill come to a point: one edge of it new (the closing's), its area under 0.7
        of that edge's length times its depth from it, the white tapering to nothing between two edges of the outline
        that meet, where a gap between parts, or a slot, keeps its width"""
        new = [c for c in shapely.get_parts(shapely.line_merge(shapely.difference(q.boundary, u.boundary.buffer(g_ / 10))))
               if c.length > g_ / 10]
        if len(new) != 1:
            return False
        depth = max(new[0].distance(shapely.Point(c)) for c in q.exterior.coords)
        return q.area < 0.7 * new[0].length * depth

    def close_gaps(b, u):
        """u with the gaps between its parts narrower than twice body b's cut weight closed, each listed in gaps: a gap
        that narrow prints as one dark line, the white between the two outlines thinner than either (the model's stair
        landings 0.7 pt off the wall at 1:96). A wedge, the white narrowing to nothing where two edges of the outline
        meet at a sharp angle, is the outline's own corner and stays open, listed in wedges (the model's valley, note 1 of
        where the closing cut the two roofs' outer skins short of their point)"""
        w_ = t.weight(cut_weight(first_g[b]), d.scale) / k
        shut = u.buffer(w_, join_style='mitre', mitre_limit=2.0).buffer(-w_, join_style='mitre', mitre_limit=2.0)
        filled = [q for q in shapely.get_parts(exact(shapely.difference, shut, u)) if q.area * k * k > 0.05]
        open_ = [q for q in filled if wedge(q, u)]
        for q in open_:                                # a merged lead's cut is closed again: each wedge listed once
            w_at = dict(body=b, at_pt=paper(q.centroid.coords[0], hx, hy, k), area_pt2=round(q.area * k * k, 2))
            if w_at not in report['cuts']['wedges']:
                report['cuts']['wedges'].append(w_at)
        filled = [q for q in filled if not any(q is x for x in open_)]
        if not filled:
            return u
        gaps.extend((b, q, u) for q in filled)
        report['cuts']['gaps_closed'] += [dict(body=b, at_pt=paper(q.centroid.coords[0], hx, hy, k),
                                               area_pt2=round(q.area * k * k, 2)) for q in filled]
        return exact(shapely.union_all, [u] + filled)
    by_prio = sorted(regions, key=lambda b: prio[first_g[b]])
    U = {b: close_gaps(b, exact(shapely.union_all, regions[b])) for b in by_prio}
    # the massing: bodies cut heavy whose cuts touch, or come within the gap closed, are one poché, drawn as the
    # earliest's (the model's walls running on into the foundation block, notes 1, 3 and 4); a lighter body's cut (furniture,
    # detail) stays its own, clipped by what came before
    heavy_pt = t.weight('heavy', d.scale)
    lead = {}                                          # body: the body whose cut draws it
    for b in by_prio:
        if t.weight(cut_weight(first_g[b]), d.scale) < heavy_pt - 1e-9 or U[b].is_empty:
            continue
        w_ = heavy_pt / k
        near_ = [a for a in dict.fromkeys(lead.values()) if U[a].distance(U[b]) <= w_]
        if not near_:
            lead[b] = b
            continue
        a = near_[0]
        U[a] = close_gaps(a, exact(shapely.union_all, [U[x] for x in near_] + [U[b]]))
        for x in [b] + near_[1:]:
            U[x] = shapely.Polygon()
            for y in [y for y, l_ in lead.items() if l_ == x] + [x]:
                lead[y] = a
        report['cuts']['merged'].append(dict(body=b, into=a))
    members = defaultdict(list)                        # a lead body: the bodies its cut draws
    for b, a in lead.items():
        members[a].append(b)
    for b in by_prio:
        u = U[b]
        if u.is_empty:
            continue
        if taken is not None:
            over = exact(shapely.intersection, u, taken).area
            if over > 0:
                report['cuts']['overlaps'].append(dict(body=b, area_pt2=round(over * k * k, 1)))
                u = exact(shapely.difference, u, taken)
        taken = u if taken is None else exact(shapely.union, taken, u)
        clipped.append((b, u))
    # joints: a group marked joints keeps its parts' outlines inside its body's merged cut, drawn as lines on OUTLINE in
    # a sublayer of their own ('building joints', at the cut's weight unless its weights set joints), so the cut stays
    # one closed shape and hiding the sublayer gives the merged cut back. Parts are taken in group order: an earlier one
    # whole, a later one less what came before, so parts running into each other show one line where they meet
    joint_g = {gid for gid, g in groups.items() if g.get('joints')}
    joint_lines = []                                   # (body, [paths], weight)
    for b, u in clipped:
        parts = sorted([x for m in members.get(b, [b]) for x in obj_regs.get(m, [])], key=lambda x: (x[0], x[1]))
        if not any(o_group[o] in joint_g for _, o, _ in parts):
            continue
        before, outs = None, []
        for _, o, reg in parts:
            own = reg if before is None else exact(shapely.difference, reg, before)
            before = reg if before is None else exact(shapely.union, before, reg)
            if o_group[o] in joint_g and not own.is_empty:
                outs.append(own.boundary)
        J = exact(shapely.difference, exact(shapely.intersection, exact(shapely.union_all, outs), u), u.boundary) if outs else None
        if J is None or J.is_empty:
            continue
        J = shapely.line_merge(J) if J.geom_type == 'MultiLineString' else J
        paths = [list(q.coords) for q in shapely.get_parts(J) if q.geom_type == 'LineString' and q.length > g_ / 10]
        jg = sorted((gid for gid in joint_g if gkey[gid] in members.get(b, [b])), key=lambda x: prio[x])
        w = next((groups[gid]['weights']['joints'] for gid in jg if (groups[gid].get('weights') or {}).get('joints')),
                 cut_weight(first_g[b]))
        if paths:
            joint_lines.append((b, paths, w))
    # a closed gap's new outline joins the graph as cut edges, noded with the lines crossing it, so doubles and line ends
    # meet the cut as drawn (fuzz seed 32: a line seen in a gap 0.2 pt wide was run on to the old outline, 0.2 pt inside
    # the new one). The old outline stays in the graph, undrawn, so a line beside it still gives way to it
    def add_outline(b, a_, c_):
        """the piece a_ c_ of body b's cut outline as cut edges of the graph, noded with the lines crossing it"""
        bs_ = set(members.get(lead.get(b, b), [b]))
        like = next((e for e in range(len(edges)) if alive[e] and e_style[e] is RING
                     and ({rkey[o] for o in ring_of[first(e)]} | {rkey[int(owner[first(e)])]}) & bs_),
                    next(e for e in range(len(edges)) if alive[e] and e_style[e] is RING))
        ends_ = (node_at(a_), node_at(c_))
        A_, D_ = np.array(a_), np.array(c_) - np.array(a_)
        live = [e for e in range(len(edges)) if alive[e] and not set(edges[e]) & set(ends_)]
        P0 = np.array([nodes[edges[e][0]] for e in live])
        V_ = np.array([nodes[edges[e][1]] for e in live]) - P0
        den = D_[0] * V_[:, 1] - D_[1] * V_[:, 0]
        den_ = np.where(den == 0, 1.0, den)
        tq = ((P0[:, 0] - A_[0]) * V_[:, 1] - (P0[:, 1] - A_[1]) * V_[:, 0]) / den_   # along the new piece
        sq = ((P0[:, 0] - A_[0]) * D_[1] - (P0[:, 1] - A_[1]) * D_[0]) / den_          # along the line it meets
        on = [(0.0, ends_[0]), (1.0, ends_[1])]
        for i in np.nonzero((den != 0) & (tq > 0) & (tq < 1) & (sq >= 0) & (sq <= 1))[0].tolist():
            on.append((float(tq[i]), node_at(tuple(A_ + D_ * tq[i]))))
        on.sort()
        for (_, v0), (_, v1) in zip(on, on[1:]):
            if v0 != v1:
                e_new = add_edge(v0, v1, like)
                own_dir[e_new] = math.atan2(nodes[v1][1] - nodes[v0][1], nodes[v1][0] - nodes[v0][0]) % math.pi
    for b, q, u0 in gaps:
        for r in [q.exterior] + list(q.interiors):
            c = list(r.coords)
            for a_, c_ in zip(c, c[1:]):
                if u0.boundary.distance(shapely.Point((a_[0] + c_[0]) / 2, (a_[1] + c_[1]) / 2)) <= hair_:
                    continue                           # the old outline
                add_outline(b, a_, c_)

    # a cut face is opaque: a line inside a body's cut region is behind it, whatever the engine made of it (two solids
    # running into each other left the engine a crease inside their merged cut, fuzz seed 97), and is taken out before
    # doubles and line ends, so a line that ended on it is met (fuzz seed 62); in a gap closed, so is a line on its edge
    report['cuts']['inside'] = 0
    if clipped:
        zone = shapely.union_all([u for _, u in clipped])
        shut_ = shapely.union_all([q for _, q, _ in gaps])
        zone_w = {}                                    # a heavier body's open cut stays inside a lighter body's region:
        for e in range(len(edges)):                    # the floor under a nightstand set into it
            if alive[e] and e_style[e] not in (None, RING) and e_dash[first(e)] != 'hidden':
                m = ((nodes[edges[e][0]][0] + nodes[edges[e][1]][0]) / 2, (nodes[edges[e][0]][1] + nodes[edges[e][1]][1]) / 2)
                z_ = zone
                if e_style[e][1].endswith(' open cuts'):
                    w_e = t.weight(e_style[e][2], d.scale)
                    if w_e not in zone_w:
                        zone_w[w_e] = shapely.union_all([u for b, u in clipped
                                                         if t.weight(cut_weight(first_g[b]), d.scale) >= w_e])
                    z_ = zone_w[w_e]
                if (shapely.contains_xy(z_, *m) and z_.boundary.distance(shapely.Point(m)) > g_
                        or shapely.contains_xy(shut_, *m)):
                    kill(e, 'inside a cut')
                    report['cuts']['inside'] += 1
        # a cut's own edge inside its body's merged cut (a wall's foot, where its slab now runs on under it) is drawn by
        # no outline, and a line ending on it would end 0.05 pt off the outline drawn (the model, after its slabs closed);
        # taken out, such ends are met to the outline as drawn
        reg_b = defaultdict(list)
        for b, u in clipped:
            for m in members.get(b, [b]):
                reg_b[m].append(u)
        reg_b = {b: shapely.union_all(us) for b, us in reg_b.items()}
        for e in range(len(edges)):
            if alive[e] and e_style[e] is RING:
                m = shapely.Point((nodes[edges[e][0]][0] + nodes[edges[e][1]][0]) / 2,
                                  (nodes[edges[e][0]][1] + nodes[edges[e][1]][1]) / 2)
                bs_ = {rkey[o] for o in ring_of[first(e)]} | {rkey[int(owner[first(e)])]}
                if all(b in reg_b and shapely.contains(reg_b[b], m) and reg_b[b].boundary.distance(m) > g_ for b in bs_):
                    kill(e)

    # ---- the earth: a ground modelled as open sheets (a terrain surface, the top and bottom faces of a slab of ground)
    # is cut as one line, its top, and below that line on a vertical plane lies earth (earth_under), which hides what
    # lies behind it beyond the plane. A ground modelled as a
    # closed solid keeps its own cut. The earth stops at the cut regions and at what they enclose (a basement), and
    # hides a line only where it lies beyond the plane there, so nothing on the plane or in front of it goes
    report['earth'] = dict(area_pt2=0.0, cut_lines_pt=0.0, behind_pt=0.0)
    cl0_ = (scene.get('clip') or [None])[0]
    up_c = M[:3, :3] @ np.array([0.0, 0.0, 1.0])          # the model's up in camera space
    nz_ = abs(cl0_['normal'][2]) / max(math.hypot(*cl0_['normal']), 1e-300) if cl0_ else 1.0
    ground_o = {o for o in range(len(objs)) if groups[o_group[o]].get('ground') and o not in ring_o and draw_g[o_group[o]]}
    if ground_o and nz_ < 0.1 and math.hypot(up_c[0], up_c[1]) > 0.7 and (not persp or abs(up_c[2]) < 0.05):
        sheet_ = [[(p[0] * f + hx, p[1] * f + hy) for p in s['pts']] for s in scene['segments'] + mesh_cut
                  if s['o'] in ground_o and s.get('cut') is not None and s['cut'] >= 0 and s.get('vis') != 'under']
        earth = earth_under(sheet_, up_c[:2], frame) if sheet_ else shapely.Polygon()
        if clipped and not earth.is_empty:
            heavy_ = [q for b, u in clipped if t.weight(cut_weight(first_g[b]), d.scale) >= heavy_pt - 1e-9
                      for q in shapely.get_parts(u) if q.geom_type == 'Polygon']
            earth = exact(shapely.difference, earth, shapely.union_all([zone] + [shapely.Polygon(q.exterior) for q in heavy_]))
        report['earth']['area_pt2'] = round(earth.area * k * k, 1)
        if not earth.is_empty:
            n_c = np.linalg.inv(M[:3, :3]).T @ np.array(cl0_['normal'], dtype=float)
            n_c /= np.linalg.norm(n_c)
            d_c = float(n_c @ (M @ np.r_[np.array(cl0_['origin'], dtype=float), 1.0])[:3])

            def beyond(e, q):
                """edge e's point q (drawing units) lies past the plane, on the side its normal keeps, by more than delta"""
                z = float(depth_on(first(e), np.array([q]))[0])
                X = np.array([(q[0] - hx) * -z / L_, (q[1] - hy + sy_) * -z / L_, z] if persp else [(q[0] - hx) / f, (q[1] - hy) / f, z])
                return float(n_c @ X) - d_c > delta
            bd_ = earth.boundary
            for e in [e for e in range(len(edges)) if alive[e] and e_style[e] not in (None, RING) and cls[first(e)] != 'cut'
                      and e_dash[first(e)] != 'hidden']:   # split where the earth's edge crosses them
                ln_ = LineString([nodes[edges[e][0]], nodes[edges[e][1]]])
                if not ln_.intersects(bd_):
                    continue
                ts = sorted({round(ln_.project(p_), 12) for p_ in shapely.get_parts(shapely.intersection(ln_, bd_))
                             if p_.geom_type == 'Point'} - {0.0})
                rest, done = e, 0.0
                for s_ in ts:
                    if g_ < s_ - done and s_ < ln_.length - g_:
                        split(rest, ln_.interpolate(s_).coords[0])
                        rest, done = len(edges) - 1, s_
            for e in range(len(edges)):
                if not alive[e] or e_style[e] in (None, RING) or e_dash[first(e)] == 'hidden':
                    continue
                A_, B_ = np.array(nodes[edges[e][0]]), np.array(nodes[edges[e][1]])
                m = (A_ + B_) / 2
                if cls[first(e)] == 'cut':             # a sheet's cut with earth either side: a slab's bottom face
                    if int(owner[first(e)]) in ground_o:
                        nrm_ = np.array([A_[1] - B_[1], B_[0] - A_[0]]) / max(math.dist(A_, B_), 1e-300) * 2 * g_
                        if shapely.contains_xy(earth, *(m + nrm_)) and shapely.contains_xy(earth, *(m - nrm_)):
                            kill(e, 'a ground sheet\'s cut inside the earth')
                            report['earth']['cut_lines_pt'] += elen(e) * k
                elif shapely.contains_xy(earth, *m) and bd_.distance(shapely.Point(m)) > g_ and beyond(e, tuple(m)):
                    kill(e, 'behind the earth')
                    report['earth']['behind_pt'] += elen(e) * k
        report['earth'] = {k_: round(v, 1) for k_, v in report['earth'].items()}

    report['seconds']['cuts'] = round(time.time() - T3 - report['seconds']['meshes'], 2)
    T3d = time.time()

    # ---- doubles: a line beside a heavier one, within lint's DOUBLE_DEG of parallel and under doubles_pt apart, prints
    # as one heavier line, and gives way over the stretch that runs beside; the ends left are met below like any other.
    # Beside means across from the heavier line: a line going on past its end in line with it is not beside it. Along a
    # stretch, the points where the line meets or crosses the heavier one divide it: a part from such a point to where
    # the line leaves, dbl off, stays (two lines meeting at a small angle), and every other part goes (a roof edge lying
    # along the model's cut, 0.09 pt off it for 2.7 pt; a facade line on the cut for 0.24 pt before it turns away; two
    # party walls 2 mm apart). doubles_pt is lint's double_pt unless the request sets it, at most near_pt so the ends
    # left can be met; 0 for none
    from archkit.lint import DOUBLE_DEG
    dbl = min(float(req.get('doubles_pt', lint_t['double_pt'])) / k, near)
    # a lesser line gives way only where its stroke lies inside the heavier one's, under half the difference of their
    # weights off it, so nothing that prints apart is taken out; with simplify_doubles it gives way under doubles_pt
    #.
    # A request's doubles_inside, from before, is the default now and changes nothing
    inside = not req.get('simplify_doubles', False)
    report['doubles'] = dict(mode='simplified' if not inside else 'kept', count=0, length_pt=0.0, examples=[])
    d.meta['doubles'] = report['doubles']['mode']      # for lint, in the SVG's <desc> and the DXF's KIT_DOUBLES

    def ring_w(e):                                     # the weight a ring's edge is drawn at: its heaviest body's cut
        return max((t.weight(cut_weight(first_g[rkey[o]]), d.scale) for o in ring_of[first(e)]),
                   default=math.inf)

    def mark(e):
        """a tile's line: a mark on its host, which gives way to an outline of its weight (a roof's tiling)"""
        return e_style[e] is not RING and groups[o_group[int(owner[first(e)])]].get('layer') == 'TEXTURE'

    def rank(e):                                       # a cut, then a solid line, then the heavier, not a tile's, the
        if e_style[e] is RING:                         # earlier group, the longer. A ring at its body's cut weight, over
            return (2, ring_w(e), 1, 1, 0.0, 0)        # an open cut as heavy: a wall's cut gives way to no lighter
        tier = 2 if e_style[e][1].endswith(' open cuts') else 0 if e_dash[first(e)] else 1   # furniture's
        return (tier, t.weight(e_style[e][2], d.scale), int(not mark(e)), -prio[o_group[int(owner[first(e)])]], elen(first(e)), -first(e))

    # of two lines of one weight round a thin face, the longer chain ranks higher, not each edge by its own length:
    # the model's skylight frame zigzagged between two edges 0.4 pt apart, crease and seam (one weight) alternating along
    # each. Measured once, before the doubles, and kept by the pieces an edge is split into
    clen = {}
    for _, _, run_ in chain([e for e in range(len(edges)) if alive[e] and e_style[e] not in (None, RING)]):
        len_ = sum(elen(e) for e in run_)
        for e in run_:
            clen[first(e)] = max(clen.get(first(e), 0.0), len_)
    # the pass works on lines, the chains of drawn edges, decided one at a time from the heaviest down, so a line beside
    # one that gave way is measured against what is drawn. A line is ranked once: a cut, then a solid line, then a dashed
    # one; its weight along its length; exact sources (the engine's lines, curves, contacts) above the meshes' own
    # edges; the nearer; the earlier group; the longer. It is sampled every 0.25 pt, a sample beside a heavier line where
    # that line's drawn part passes within 1.5 dbl of it, square to it and within DOUBLE_DEG of parallel, and a run is a
    # stretch of such samples, breaks under 0.5 pt bridged. A run is decided whole :
    #   converging  the gap closes to under a tenth of dbl at one end and opens past three quarters of it at the other,
    #               or at both ends from a touch between, the line not lying along the heavier one for most of the
    #               way: both stay (the model's mounds' shell lines; the model's roof edges running into the valleys)
    #   else        the lesser gives way where the gap is under dbl (not on to 1.15 dbl, the council's hysteresis: that
    #               took it out where the heavier line was past double_pt, a line the fuzz checker found missing on
    #               seed 119); a cut under 2 pt is not made, and a kept stretch under 2 pt between two cuts goes with
    #               them, which keeps a run from flickering. Where
    #               the line goes on past a cut, it is drawn onto the heavier line by a join at 20 degrees to it, in place
    #               of its own stretch that far, so no end is left a hair off the heavier line for the line ends below to
    #               hook back with a square link (the notches)
    step_d = 0.25 / k
    tan20 = math.tan(math.radians(20))
    sin_d = math.sin(math.radians(DOUBLE_DEG))
    exact_e = lambda e: segs[e_seg[first(e)]]['src'] != 'mesh'
    lines_ = []
    by_w = defaultdict(list)                           # a line is of one tier and weight: a chain through a change of class
    for e in range(len(edges)):                        # would let a light edge ride on a heavy line beside it
        if alive[e] and e_style[e] is not None:
            by_w[('ring', 0) if e_style[e] is RING else (rank(e)[0], t.weight(e_style[e][2], d.scale))].append(e)
    for pts_n, closed, run in [c_ for es_w in by_w.values() for c_ in chain(es_w)]:
        P = np.array([nodes[v] for v in pts_n], dtype=float)
        ln_ = np.hypot(*np.diff(P, axis=0).T)
        if not len(ln_) or ln_.sum() <= 0:
            continue
        ring_ = all(e_style[e] is RING for e in run)
        if ring_:
            rk = (2, max(ring_w(e) for e in run), 1, 1, math.inf, 0, math.inf)
        else:
            w_ = np.array([t.weight(e_style[e][2], d.scale) if e_style[e] is not RING else ring_w(e) for e in run])
            tier = max(rank(e)[0] for e in run)
            z_m = float((np.array([e_z[first(e)] for e in run]) * ln_).sum() / ln_.sum())
            rk = (tier, round(float((w_ * ln_).sum() / ln_.sum()), 4), int(not all(mark(e) for e in run)),
                  int(sum(l_ for e, l_ in zip(run, ln_) if exact_e(e)) >= 0.5 * ln_.sum()),
                  round(z_m / (3 * MESH_PT / (k * f) * (abs(z_m) / L_ if persp else 1.0))),   # the nearer, to 3 MESH_PT
                  -min(prio[o_group[int(owner[first(e)])]] for e in run), float(ln_.sum()))
        lines_.append(dict(nodes=pts_n, edges=list(run), closed=closed, P=P, pos=np.concatenate([[0.0], np.cumsum(ln_)]),
                           ring=ring_, rank=rk + (-len(lines_),)))
    def walk_dir(v, x, far):
        """the direction a line comes into node v along its edge x, from far back along it through nodes where
        it goes on alone"""
        w_, y_, run_ = v, x, 0.0
        while True:
            u_ = edges[y_][1] if edges[y_][0] == w_ else edges[y_][0]
            run_ += math.dist(nodes[w_], nodes[u_])
            if run_ >= far or len(adj[u_]) != 2:
                break
            (y2_,) = adj[u_] - {y_}
            w_, y_ = u_, y2_
        d_ = np.array(nodes[v]) - np.array(nodes[u_])
        return d_ / max(float(np.hypot(*d_)), 1e-300)

    def short_stub(v, x):
        """the line leaving node v by its edge x ends free within near_pt: a stub the line ends below take out"""
        w_, y_, run_ = v, x, 0.0
        while True:
            u_ = edges[y_][1] if edges[y_][0] == w_ else edges[y_][0]
            run_ += math.dist(nodes[w_], nodes[u_])
            if run_ >= near:
                return False
            if len(adj[u_]) == 1:
                return True
            if len(adj[u_]) != 2:
                return False
            (y2_,) = adj[u_] - {y_}
            w_, y_ = u_, y2_

    def lands_on(v, x, A_, B_, t_in):
        """a line ending at node v by its edge x, once a line there gives way, meets the heavier line A_ B_ (its
        segments) as drawn: it ends within t_in of it (inside its stroke), crosses it within near_pt back from its end
        (an overshoot the line ends below cut back), or runs into it at 30 degrees or more within twice near_pt where
        the model's lines run on there, as the line ends then run it on (not a cubby's side 0.4 pt short of the shelf
        above, whose rim then stays closed)"""
        p_ = np.array(nodes[v])
        if not len(A_):
            return False
        if float(seg_dist(np.repeat(p_[None], len(A_), 0), A_, B_)[0].min()) <= t_in:
            return True
        back_, w_, y_, run_ = [nodes[v]], v, x, 0.0
        while run_ < near:
            u_ = edges[y_][1] if edges[y_][0] == w_ else edges[y_][0]
            run_ += math.dist(nodes[w_], nodes[u_])
            back_.append(nodes[u_])
            if len(adj[u_]) != 2:
                break
            (y2_,) = adj[u_] - {y_}
            w_, y_ = u_, y2_
        if shapely.linestrings(back_).intersects(shapely.multilinestrings(np.stack([A_, B_], 1))):
            return True
        d_ = walk_dir(v, x, 0.5 / k)
        e_ = B_ - A_
        den = d_[0] * e_[:, 1] - d_[1] * e_[:, 0]
        safe = np.where(np.abs(den) > 1e-12, den, np.inf)
        w_ = A_ - p_
        t_ = (w_[:, 0] * e_[:, 1] - w_[:, 1] * e_[:, 0]) / safe
        u_ = (w_[:, 0] * d_[1] - w_[:, 1] * d_[0]) / safe
        sin_ = np.abs(den) / np.maximum(np.hypot(e_[:, 0], e_[:, 1]), 1e-300)
        hit_ = np.nonzero((t_ > 0) & (t_ <= 2 * near) & (u_ >= 0) & (u_ <= 1) & (sin_ >= 0.5))[0]
        return any(on_model(p_, p_ + d_ * float(t_[j])) for j in hit_[np.argsort(t_[hit_])][:3])

    if dbl > 0 and lines_:
        # every line's segments, for the search
        SA = np.concatenate([Ld['P'][:-1] for Ld in lines_])
        SB = np.concatenate([Ld['P'][1:] for Ld in lines_])
        s_line = np.concatenate([np.full(len(Ld['P']) - 1, i) for i, Ld in enumerate(lines_)])
        s_edge = np.concatenate([np.array(Ld['edges'], dtype=np.int64) for Ld in lines_])
        s_pos = np.concatenate([Ld['pos'][:-1] for Ld in lines_])
        s_tree = shapely.STRtree(shapely.linestrings(np.stack([SA, SB], 1)))
        s_off = np.cumsum([0] + [len(Ld['P']) - 1 for Ld in lines_])
        # each segment's source as the model gave it, before snap rounding moved it up to a grid step: whether two
        # lines lie under doubles_pt apart is decided on their sources, so it does not turn on how the grid fell (two
        # chords 0.61 pt apart read 0.56 pt apart once noded, the adversarial scenes' min-arc-1-chords); how a gap
        # closes along a line is read on the graph as before
        def src_of(e):
            ss_ = srcs[first(e)]
            o_ = int(owner[first(e)])
            p_ = next((p_ for p_, _ in ss_ if segs[int(PC[p_, 6])]['o'] == o_), ss_[0][0] if ss_ else None)
            return PC[p_, [0, 1, 3, 4]] if p_ is not None else None
        SR = np.array([src_of(e) if src_of(e) is not None else np.r_[SA[j_], SB[j_]] for j_, e in enumerate(s_edge.tolist())],
                      dtype=float).reshape(-1, 4)
        rank_l = [Ld['rank'] for Ld in lines_]
        q_dist = 1.5 * dbl
        removed = defaultdict(list)                    # line: [(from, to)] along it, gone
        for i in sorted(range(len(lines_)), key=lambda i: rank_l[i], reverse=True):
            Ld = lines_[i]
            if Ld['ring']:
                continue
            total = float(Ld['pos'][-1])
            n_s = max(1, int(math.ceil(total / step_d)))
            s_at = (np.arange(n_s) + 0.5) * total / n_s
            seg_i = np.clip(np.searchsorted(Ld['pos'], s_at, side='right') - 1, 0, len(Ld['P']) - 2)
            dv_ = Ld['P'][seg_i + 1] - Ld['P'][seg_i]
            dl_ = np.maximum(np.hypot(dv_[:, 0], dv_[:, 1]), 1e-300)
            Q = Ld['P'][seg_i] + dv_ * ((s_at - Ld['pos'][seg_i]) / dl_)[:, None]
            U = dv_ / dl_[:, None]
            qi, gi = s_tree.query(shapely.points(Q), predicate='dwithin', distance=q_dist)
            ab = SB[gi] - SA[gi]
            lab = np.maximum(np.hypot(ab[:, 0], ab[:, 1]), 1e-300)
            par = np.abs(U[qi, 0] * ab[:, 1] - U[qi, 1] * ab[:, 0]) <= sin_d * lab
            tq = ((Q[qi] - SA[gi]) * ab).sum(1) / lab ** 2
            foot = SA[gi] + ab * tq[:, None]
            gap_ = np.hypot(*(Q[qi] - foot).T)
            sq_ = s_off[i] + seg_i[qi]                 # each sample on its own source, its gap to the heavier one's
            ra_, rd_ = SR[sq_, :2], SR[sq_, 2:] - SR[sq_, :2]
            rl_ = (rd_ ** 2).sum(1)
            Qt = ra_ + rd_ * (((Q[qi] - ra_) * rd_).sum(1) / np.maximum(rl_, 1e-300))[:, None]
            ha_, hd_ = SR[gi, :2], SR[gi, 2:] - SR[gi, :2]
            hl_ = np.hypot(hd_[:, 0], hd_[:, 1])
            gap_t = np.abs(hd_[:, 0] * (Qt[:, 1] - ha_[:, 1]) - hd_[:, 1] * (Qt[:, 0] - ha_[:, 0])) / np.maximum(hl_, 1e-300)
            gap_t = np.where((rl_ > 0) & (hl_ > 0) & (np.abs(gap_t - gap_) <= 1.5 * g_), gap_t, gap_)   # off by more, a source of another line
            arc_ = s_pos[gi] + tq * lab
            # a heavier line, or the line's own earlier part well apart from the sample along it (the two long sides of
            # a thin outline: the later gives way)
            sep_ = np.abs(arc_ - s_at[qi])
            if Ld['closed']:
                sep_ = np.minimum(sep_, total - sep_)
            ok_ = par & (tq >= 0) & (tq <= 1) & np.where(
                s_line[gi] == i, (arc_ < s_at[qi]) & (sep_ > 4 * dbl),
                np.array([rank_l[j] > rank_l[i] for j in s_line[gi].tolist()], dtype=bool))
            g = np.full(n_s, np.inf)
            g_src = np.full(n_s, np.inf)               # the same gap between the two lines' sources
            who = [None] * n_s                         # (line, its arc, foot point)
            for q, j, a_, gp, gt_, fx, fy, o_ in zip(qi.tolist(), s_line[gi].tolist(), arc_.tolist(), gap_.tolist(),
                                                     gap_t.tolist(), foot[:, 0].tolist(), foot[:, 1].tolist(), ok_.tolist()):
                if not o_ or gp >= g[q] or any(r0 <= a_ <= r1 for r0, r1 in removed[j]):
                    continue
                g[q], g_src[q], who[q] = gp, gt_, (j, a_, (fx, fy))
            beside = np.isfinite(g)
            if not beside.any():
                continue
            # runs, breaks of up to 2 samples bridged; a closed line's run across its start unrolled
            idx = np.nonzero(beside)[0]
            runs_ = [[idx[0], idx[0]]]
            for q in idx[1:].tolist():
                if q - runs_[-1][1] <= 3:
                    runs_[-1][1] = q
                else:
                    runs_.append([q, q])
            if Ld['closed'] and len(runs_) > 1 and runs_[0][0] <= 2 and runs_[-1][1] >= n_s - 3:
                last = runs_.pop()
                runs_[0] = [last[0] - n_s, runs_[0][1]]
            # each run's stretches beside the heavier line under thr, and how each end of a stretch is met. Going in from
            # an end, where the gap closes steadily onto the heavier line (to the noding grid), the lines converge: the
            # cut starts there, so the lesser line runs on along its own path into the heavier one's stroke and ends on
            # it ('in'); a stretch converging all along that never meets it stays whole, its end met below along its own
            # path. Where the gap stays wider, the lines run side by side at an even offset and the cut keeps to where the
            # gap is under thr, the lesser drawn onto the heavier there by a join at 20 degrees ('join'). A sample with no
            # heavier line beside it is never cut, so a lesser line is drawn across a break in the heavier one (the model's
            # arch,). A 20 degree join read as a kink on
            # converging lines)
            thr_in = lambda j: max(rank_l[j][1] - Ld['rank'][1], 0.0) / (2 * k) + touch
            two_ = 2.0 / k
            cuts_ = []                                 # [from, to, heavier line, end kind at from, at to], unrolled for a ring
            for k0, k1 in runs_:
                ks = [q % n_s for q in range(k0, k1 + 1)]
                G = np.array([g[q] for q in ks])
                Gt = np.array([g_src[q] for q in ks])
                js = [who[q][0] for q in ks if who[q]]
                jm = max(set(js), key=js.count)
                thr = thr_in(jm) if inside else dbl
                t_in = g_ + touch                     # on the heavier line, to the noding grid
                on = np.isfinite(G) & (Gt < thr)        # under the threshold as the model gives the lines
                Gf = np.where(np.isfinite(G), G, thr)
                Gs = np.convolve(np.pad(Gf, 2, mode='edge'), np.ones(5) / 5, mode='valid')   # over 1.25 pt: the grid's noise

                t_touch = (rank_l[jm][1] + Ld['rank'][1]) / (2 * k)   # the two strokes touching: no white between

                def in_from(seq):
                    """going in from a stretch's end along samples seq: the first sample on the heavier line, where the
                    gap closes to it steadily (while the strokes are apart, not rising past its least by the grid nor
                    closing by under 0.01 pt in 2 pt: a fin's top edges, 0.5 degrees apart); else None"""
                    best, since = math.inf, 0.0
                    for m in seq:
                        if G[m] <= t_in:
                            return m
                        if Gs[m] <= t_touch:
                            continue
                        if Gs[m] > best + g_:
                            return None
                        if Gs[m] < best - 0.01 / k:
                            best, since = Gs[m], 0.0
                        else:
                            since += step_d
                        if since > two_:
                            return None
                    return None
                n_ = 0
                while n_ < len(G):
                    if not on[n_]:
                        n_ += 1
                        continue
                    a = n_
                    while n_ < len(G) and on[n_]:
                        n_ += 1
                    b = n_ - 1
                    # a meeting at the stretch's own first or last sample is no convergence to cut: the line
                    # starts or ends on the heavier one
                    ends_ = ['join', 'join']
                    m = in_from(range(a, b + 1))
                    if m is not None and a < m < b:
                        a, ends_[0] = m, 'in'
                    m = in_from(range(b, a - 1, -1))
                    if m is not None and a < m < b:
                        b, ends_[1] = m, 'in'
                    # converging all along, never inside (the gap's slope at 1 degree or more and its range past the
                    # grid's noise, closing or opening steadily): both stay, an end met below along its own path
                    d_g = np.diff(Gs[a:b + 1])
                    if ends_ == ['join', 'join'] and len(d_g) > 1 and ((d_g <= g_ / 5).all() or (d_g >= -g_ / 5).all()) \
                            and np.ptp(Gs[a:b + 1]) >= 2 * g_ \
                            and abs(np.polyfit(np.arange(a, b + 1) * total / n_s, Gs[a:b + 1], 1)[0]) >= math.tan(math.radians(1)):
                        continue
                    cuts_.append([(k0 + a) * total / n_s, (k0 + b + 1) * total / n_s, jm] + ends_)
            if not cuts_:
                continue
            two = 2.0 / k
            s_of = lambda x: int(np.clip(math.floor(x / total * n_s), 0, n_s - 1))   # the sample at an arc, unrolled
            # a cut reaching the line's end runs to it; one round a closed line takes the loop whole
            for c_ in cuts_:
                if not Ld['closed']:
                    if c_[0] <= 3 * step_d:
                        c_[0], c_[3] = 0.0, 'end'
                    if c_[1] >= total - 3 * step_d:
                        c_[1], c_[4] = total, 'end'
                elif c_[1] - c_[0] >= total - 3 * step_d:
                    c_[0], c_[1], c_[3], c_[4] = 0.0, total, 'end', 'end'
            cuts_.sort()
            # two cuts merge across a stretch under 2 pt that has a heavier line beside it all along (the gap hovering
            # about thr, or one heavier line taking over from another), so a run does not flicker; never across a break
            # in the heavier lines, where the lesser one is drawn
            merged_ = []
            for c_ in cuts_:
                if merged_ and c_[0] - merged_[-1][1] < two:
                    qs = list(range(int(math.floor(merged_[-1][1] / total * n_s)), int(math.ceil(c_[0] / total * n_s))))
                    gap_q = [q for q in qs if not who[q % n_s]]
                    if not gap_q:
                        if c_[1] > merged_[-1][1]:
                            merged_[-1][1], merged_[-1][4] = c_[1], c_[4]
                        continue
                merged_.append(list(c_))
            # no cut under 2 pt but one reaching the line's end, and not even that where the line runs into the heavier
            # one there, ending on it, unless the line is short
            merged_ = [c_ for c_ in merged_ if c_[1] - c_[0] >= two or ('end' in c_[3:5] and ('in' not in c_[3:5] or total < 2 * two))]
            # the line as drawn now: its live edges in order, each with its arcs and its nodes at them (an edge of it
            # another line's join split is there as its halves)
            pieces_l = []                              # [edge, arc from, arc to, node at from, node at to]
            for n_e_, e in enumerate(Ld['edges']):
                a0_, a1_ = float(Ld['pos'][n_e_]), float(Ld['pos'][n_e_ + 1])
                P0_ = np.array(nodes[Ld['nodes'][n_e_]])
                du_ = np.array(nodes[Ld['nodes'][n_e_ + 1]]) - P0_
                L2_ = max(float(du_ @ du_), 1e-300)
                for x in live_of(e):
                    w0_, w1_ = edges[x]
                    t0_, t1_ = (float((np.array(nodes[w]) - P0_) @ du_) / L2_ for w in (w0_, w1_))
                    if t1_ < t0_:
                        t0_, t1_, w0_, w1_ = t1_, t0_, w1_, w0_
                    pieces_l.append([x, a0_ + t0_ * (a1_ - a0_), a0_ + t1_ * (a1_ - a0_), w0_, w1_])
            pieces_l.sort(key=lambda t_: t_[1])
            l_live = {t_[0] for t_ in pieces_l}
            junc = []                                  # (arc, node): other lines meeting the line at its nodes
            for x, a0_, a1_, w0_, w1_ in pieces_l:
                for a_, w in ((a0_, w0_), (a1_, w1_)):
                    if any(y not in l_live for y in adj[w]) and (a_, w) not in junc:
                        junc.append((a_, w))
            junc.sort()
            free0 = not Ld['closed'] and bool(pieces_l) and len(adj[pieces_l[0][3]]) <= 1
            free1 = not Ld['closed'] and bool(pieces_l) and len(adj[pieces_l[-1][4]]) <= 1
            # each 'in' end, the lesser line converging onto the heavier one, runs on along its own path to where they
            # meet: a node of both within the cut (a crossing, or where the noding grid made them touch), so the end
            # lies on the heavier line as drawn; with no such node, the first sample whose gap as the model gives it is
            # within touch. Lines that never meet so are planned as a 'join' end below (the model's tiles, tangent to the
            # roof's outline 7 pt past where the grid's gap first fell under it)
            unroll = (0.0, -total, total) if Ld['closed'] else (0.0,)
            for c_ in merged_:
                for side in (0, 1):
                    if c_[3 + side] != 'in':
                        continue
                    on_j = set(lines_[c_[2]]['nodes'])
                    meet = [a_ + o_ for a_, w in junc if w in on_j for o_ in unroll if c_[0] - g_ <= a_ + o_ <= c_[1] + g_]
                    if meet:
                        c_[side] = min(meet) if side == 0 else max(meet)
                        continue
                    qs = range(int(math.floor(c_[0] / total * n_s)), int(math.ceil(c_[1] / total * n_s)))
                    qs = [q for q in (qs if side == 0 else qs[::-1]) if (Ld['closed'] or 0 <= q < n_s) and g_src[q % n_s] <= touch]
                    if qs:
                        c_[side] = (qs[0] + 0.5) * total / n_s
                    else:
                        c_[3 + side] = 'join'
            # each 'join' end, the lesser line leaving the heavier one at an even offset: nothing is drawn that the
            # model does not have, so no join.
            # The cut ends at the line's corner where the line on from it runs into the heavier one; else, with no room
            # before the line's free end, the stub goes with the cut where the heavier line runs beside it all along;
            # else it ends at a junction of the line within it, pulled back so it keeps 2 pt, the line going on from a
            # node other lines meet; else it is not made, and lint warns of the double
            for n_, c_ in enumerate(merged_):
                for side in (1, 0):
                    if c_[3 + side] != 'join':
                        continue
                    sgn = 1 if side == 1 else -1
                    at_ = c_[side]
                    q = s_of(at_ % total if Ld['closed'] else at_)
                    near_q = [x for x in range(q - 3, q + 4) if (Ld['closed'] or 0 <= x < n_s) and who[x % n_s]]
                    if not near_q:
                        c_[3 + side] = 'drop'
                        continue
                    q = min(near_q, key=lambda x: abs(x - q)) % n_s
                    j = who[q][0]
                    jx = max(g[q], 0.0) / tan20         # how far on the line turning a corner is the cut's own
                    if side == 1:                      # the room past the cut's end: to the next cut, junction or line end
                        nxt = merged_[n_ + 1][0] if n_ + 1 < len(merged_) else (merged_[0][0] + total if Ld['closed'] else total)
                        jn_ = [a_ for a_, _ in junc if at_ < a_ < nxt] + \
                            ([a_ + total for a_, _ in junc if at_ < a_ + total < nxt] if Ld['closed'] else [])
                        stop = min(jn_ + [nxt])
                    else:
                        prv = merged_[n_ - 1][1] if n_ > 0 else (merged_[-1][1] - total if Ld['closed'] else 0.0)
                        jn_ = [a_ for a_, _ in junc if prv < a_ < at_] + \
                            ([a_ - total for a_, _ in junc if prv < a_ - total < at_] if Ld['closed'] else [])
                        stop = max(jn_ + [prv])
                    # the line turning a corner within reach of the cut's end: the cut ends at the corner, where the
                    # line on from it runs into the heavier one (a box's edge beside another's, its side then run on to
                    # it below: the model's shelves)
                    far_ = at_ + sgn * (jx + two / 2)
                    u0_ = None                         # the line's direction at the cut's end, coming out of the cut
                    for t_ in (pieces_l if side == 1 else pieces_l[::-1]):
                        x, a0_, a1_, w0_, w1_ = t_
                        lo_, hi_ = (a0_, a1_) if side == 1 else (-a1_, -a0_)
                        if lo_ < sgn * at_ - g_ and hi_ >= sgn * at_ - two / 2:
                            d_ = np.array(nodes[w1_ if side == 1 else w0_]) - np.array(nodes[w0_ if side == 1 else w1_])
                            if float(np.hypot(*d_)) > 0:
                                u0_ = d_ / float(np.hypot(*d_))
                    corner = None
                    for t_ in (pieces_l if side == 1 else pieces_l[::-1]):
                        x, a0_, a1_, w0_, w1_ = t_
                        lo_, hi_ = (a0_, a1_) if side == 1 else (-a1_, -a0_)
                        if hi_ <= sgn * at_ - g_ or lo_ >= sgn * far_ or lo_ < sgn * at_ - g_:
                            continue
                        d_ = np.array(nodes[w1_ if side == 1 else w0_]) - np.array(nodes[w0_ if side == 1 else w1_])
                        ld_ = float(np.hypot(*d_))
                        if ld_ <= 0:
                            continue
                        d_ /= ld_
                        if u0_ is None:
                            u0_ = d_
                            continue
                        if float(d_ @ u0_) < math.cos(math.radians(30)):
                            corner = (a0_ if side == 1 else a1_, w0_ if side == 1 else w1_, x)
                            break
                    if corner is not None and (j != i or Ld['closed']) and sgn * (corner[0] - c_[1 - side]) >= two:
                        A_c, B_c = lines_[j]['P'][:-1], lines_[j]['P'][1:]
                        if j == i:                     # a closed line's own earlier part, a thin outline's other side: less
                            ex0, ex1 = ((c_[0], corner[0] + elen(corner[2])) if side == 1   # the cut and the edge on
                                        else (corner[0] - elen(corner[2]), c_[1]))           # from the corner
                            pos_ = Ld['pos']
                            keep_ = [n for n in range(len(Ld['P']) - 1) if not any(   # overlapping it by over a grid step
                                min(pos_[n + 1] + o_, ex1) - max(pos_[n] + o_, ex0) > g_ for o_ in ((0.0, -total, total) if Ld['closed'] else (0.0,)))]
                            A_c, B_c = A_c[keep_], B_c[keep_]
                        if lands_on(corner[1], corner[2], A_c, B_c, max(thr_in(j), g_ + touch)):
                            c_[side], c_[3 + side] = corner[0], 'corner'
                            continue
                    at_end = not jn_ and not Ld['closed'] and stop in (0.0, total)
                    if at_end and (free1 if side == 1 else free0):
                        if all(who[x] for x in range(min(q, s_of(stop)), max(q, s_of(stop)) + 1)):
                            c_[side], c_[3 + side] = stop, 'end'   # a stub along the heavier line to the line's free end
                            continue
                    inner = [a_ for a_, _ in junc if (c_[0] + two <= a_ <= at_ + g_ if side == 1 else at_ - g_ <= a_ <= c_[1] - two)]
                    if inner:
                        c_[side], c_[3 + side] = (max(inner) if side == 1 else min(inner)), 'corner'
                        continue
                    c_[3 + side] = 'drop'

            def segs_of(j, c_):
                """the heavier line's segments for the landing tests: for the line's own earlier part (the long sides of
                a thin outline), less the stretch round the cut, which a node on it would land on trivially"""
                Pj = lines_[j]['P']
                if j != i:
                    return Pj[:-1], Pj[1:]
                pos_ = lines_[j]['pos']
                lo_, hi_ = c_[0] - 4 * dbl, c_[1] + 4 * dbl
                keep_ = [n for n in range(len(Pj) - 1) if not (lo_ <= pos_[n + 1] and pos_[n] <= hi_)
                         and not (Ld['closed'] and (lo_ <= pos_[n + 1] - total and pos_[n] - total <= hi_
                                                    or lo_ <= pos_[n + 1] + total and pos_[n] + total <= hi_))]
                return (Pj[:-1][keep_], Pj[1:][keep_]) if keep_ else (Pj[:0], Pj[:0])

            def spans(c_):
                """a cut's stretches along the line, within its length"""
                c0, c1 = c_[0], c_[1]
                if 0 <= c0 and c1 <= total:
                    return [(c0, c1)]
                if Ld['closed']:
                    return [(c0 % total, total), (0.0, c1 % total if c1 % total else total)]
                return [(max(c0, 0.0), min(c1, total))]
            # a cut is made only where no outline is left open: a line meeting the lesser one inside the cut and left
            # ending there must meet the heavier line as drawn, or be a stub the line ends take out; else both stay
            # and lint reports the double (books, a kettle, a joist's end opened by the
            # doubles). A join landing on a junction keeps it; tile marks (TEXTURE) close no outline
            mark_l = all(e_style[e] is not RING and e_style[e][0] == 'TEXTURE' for e in Ld['edges'])
            for n_, c_ in enumerate(merged_):
                if 'drop' in c_[3:5] or mark_l:   # tiles are marks on a surface, not an outline
                    continue
                lands_ = [c_[sd] % total if Ld['closed'] else c_[sd] for sd in (0, 1) if c_[3 + sd] == 'corner']
                for a_, v in junc:
                    if not any(q0 - g_ <= a_ <= q1 + g_ for q0, q1 in spans(c_)) or any(abs(a_ - l_) <= g_ for l_ in lands_):
                        continue
                    others = [x for x in adj[v] if x not in l_live]
                    # the heavier lines beside the line about the junction, the one it gave way to there first
                    q_v = s_of(a_ % total if Ld['closed'] else a_)
                    js_v = [who[x % n_s][0] for x in sorted(range(q_v - 4, q_v + 5), key=lambda x: abs(x - q_v))
                            if (Ld['closed'] or 0 <= x < n_s) and who[x % n_s]] + [c_[2]]
                    js_v = list(dict.fromkeys(js_v))
                    if len(others) == 1 and e_style[others[0]] not in (None, RING) and e_style[others[0]][0] != 'TEXTURE' \
                            and not short_stub(v, others[0]) and \
                            not any(lands_on(v, others[0], *segs_of(j_v, c_), max(thr_in(j_v), g_ + touch)) for j_v in js_v):
                        c_[3] = 'drop'
                        report['doubles']['kept'] = report['doubles'].get('kept', 0) + 1
                        break
            keep_c = [n_ for n_, c_ in enumerate(merged_) if 'drop' not in c_[3:5]]
            if not keep_c:
                continue
            # the cuts applied along the line, each end on a node of it: an existing one within the noding grid, else a
            # new one, so no piece under the grid is left and every join finds the node it lands at
            node_arcs = sorted({(a_, w) for _, a0_, a1_, w0_, w1_ in pieces_l for a_, w in ((a0_, w0_), (a1_, w1_))})
            ends_at = {}                               # (cut, side): the node there
            for n_ in keep_c:
                c_ = merged_[n_]
                sp_ = spans(c_)
                for si_, (q0, q1) in enumerate(sp_):
                    bn = {}
                    for b_, qq in ((0, q0), (1, q1)):
                        a_n, w_n = min(node_arcs, key=lambda t_: abs(t_[0] - qq))
                        if abs(a_n - qq) <= g_:
                            bn[b_] = (a_n, w_n)
                    q0, q1 = bn[0][0] if 0 in bn else q0, bn[1][0] if 1 in bn else q1
                    if q1 - q0 <= 0:
                        continue
                    removed[i].append((q0, q1))
                    for t_ in list(pieces_l):
                        x, a0_, a1_, w0_, w1_ = t_
                        if not alive[x] or a1_ <= q0 or a0_ >= q1:
                            continue
                        kill(x, 'a double: gave way to a heavier line beside it')
                        fate_by[x] = int(owner[first(lines_[c_[2]]['edges'][0])])
                        pieces_l.remove(t_)
                        P0_, P1_ = np.array(nodes[w0_]), np.array(nodes[w1_])
                        at_q = lambda qq: add_node(P0_ + (P1_ - P0_) * ((qq - a0_) / max(a1_ - a0_, 1e-300)))
                        if q0 - a0_ > g_ / 2:
                            w_ = bn[0][1] if 0 in bn else at_q(q0)
                            bn[0] = (q0, w_)
                            if w_ != w0_:
                                pieces_l.append([add_edge(w0_, w_, x), a0_, q0, w0_, w_])
                        elif 0 not in bn and abs(a0_ - q0) <= g_ / 2:
                            bn[0] = (a0_, w0_)
                        if a1_ - q1 > g_ / 2:
                            w_ = bn[1][1] if 1 in bn else at_q(q1)
                            bn[1] = (q1, w_)
                            if w_ != w1_:
                                pieces_l.append([add_edge(w_, w1_, x), q1, a1_, w_, w1_])
                        elif 1 not in bn and abs(a1_ - q1) <= g_ / 2:
                            bn[1] = (a1_, w1_)
                    pieces_l.sort(key=lambda t_: t_[1])
                    node_arcs = sorted({(a_, w) for _, a0_, a1_, w0_, w1_ in pieces_l for a_, w in ((a0_, w0_), (a1_, w1_))})
                    if si_ == 0 and 0 in bn:
                        ends_at[(n_, 0)] = bn[0][1]
                    if si_ == len(sp_) - 1 and 1 in bn:
                        ends_at[(n_, 1)] = bn[1][1]
                report['doubles']['count'] += 1
                report['doubles']['length_pt'] += (c_[1] - c_[0]) * k
                report['doubles']['in'] = report['doubles'].get('in', 0) + c_[3:5].count('in')
                if len(report['doubles']['examples']) < 20:
                    mpt = Ld['P'][int(np.clip(np.searchsorted(Ld['pos'], ((c_[0] + c_[1]) / 2) % total) - 1, 0, len(Ld['P']) - 1))]
                    named = lambda L2: next(('/'.join(e_style[e][:2]) for e in L2['edges'] if e_style[e] not in (None, RING)), 'CUT')
                    report['doubles']['examples'].append(dict(
                        layer=named(Ld), beside=named(lines_[c_[2]]),
                        length_pt=round((c_[1] - c_[0]) * k, 2), at_pt=paper(mpt, hx, hy, k)))
    # thin faces: a face between drawn lines and cuts thinner than dbl all but a speck (shrunk by dbl / 2, less than
    # (dbl / 2)^2 of it is left) prints as a heavier line, and keeps only the heaviest line round it; the cut's edges
    # stay (a beyond edge bowing out 0.607 pt from the model's cut and back to it). A line is ranked whole, by its chain's
    # length as the doubles are: ranked edge by edge, all but the longest of its pieces round a face went (the model's
    # discs, their back edges broken in dashes where a context building's lines ran 0.4 pt behind them). The heaviest
    # is one of the lines running along the face, at least half as long round it as the longest: a short end of a long
    # line crossing it took both of a fin's top lines . A face round which every line
    # is one object's, no cut among them, is that object's own thin part (a book's spine, a fin's top) and keeps its
    # lines; and the face keeps them all where a line left ending there would not meet the heaviest (lands_on), so no
    # outline is opened
    report['doubles']['thin_faces'] = 0
    if dbl > 0:
        live = [e for e in range(len(edges)) if alive[e] and e_style[e] is not None]
        at_e = {}
        for e in live:
            at_e[(nodes[edges[e][0]], nodes[edges[e][1]])] = at_e[(nodes[edges[e][1]], nodes[edges[e][0]])] = e
        faces = shapely.get_parts(shapely.polygonize([LineString([nodes[edges[e][0]], nodes[edges[e][1]]]) for e in live]))
        faces = faces[shapely.area(faces) > 0]
        for fc in faces[shapely.area(shapely.buffer(faces, -dbl / 2)) < (dbl / 2) ** 2]:
            round_ = set()
            for r in [fc.exterior] + list(fc.interiors):
                c = list(r.coords)
                round_.update(at_e[q] for q in zip(c, c[1:]) if q in at_e)
            round_ = [e for e in round_ if alive[e]]
            if not round_:
                continue
            if inside:                                 # kept: thin only where the strokes round it cover it
                w_r = [w for w in (ring_w(e) if e_style[e] is RING else t.weight(e_style[e][2], d.scale) for e in round_)
                       if math.isfinite(w)]
                if not w_r:
                    continue
                t_f = (max(w_r) + min(w_r)) / (2 * k)
                if shapely.area(shapely.buffer(fc, -t_f / 2)) >= (t_f / 2) ** 2:
                    continue
            if not any(e_style[e] is RING for e in round_) and len({int(owner[first(e)]) for e in round_}) == 1:
                continue
            line_rank = lambda e: rank(e)[:4] + (0.0 if e_style[e] is RING else clen.get(first(e), 0.0),)
            by_l = defaultdict(float)                  # a line round the face, by style and object: its length round it
            for e in round_:
                by_l[(e_style[e], int(owner[first(e)]))] += elen(e)
            long_ = max(by_l.values())
            top = max(line_rank(e) for e in round_ if by_l[(e_style[e], int(owner[first(e)]))] >= 0.5 * long_)
            gone = [e for e in round_ if e_style[e] is not RING and line_rank(e) < top]
            carrier = [e for e in round_ if line_rank(e) >= top]
            if gone and carrier:
                A_c = np.array([nodes[edges[e][0]] for e in carrier])
                B_c = np.array([nodes[edges[e][1]] for e in carrier])
                w_c = max(ring_w(e) if e_style[e] is RING else t.weight(e_style[e][2], d.scale) for e in carrier)
                if inside:                             # kept, a line goes only where it lies inside the heaviest's stroke
                    def in_stroke(e):                  # (a beyond edge 0.04 pt inside a wall's 0.8 pt cut, the model)
                        P3 = np.array([nodes[edges[e][0]], nodes[edges[e][1]],
                                       [(nodes[edges[e][0]][0] + nodes[edges[e][1]][0]) / 2, (nodes[edges[e][0]][1] + nodes[edges[e][1]][1]) / 2]])
                        lim = max(min(w_c, 1e9) - t.weight(e_style[e][2], d.scale), 0.0) / (2 * k) + touch + g_
                        return all(float(seg_dist(np.repeat(q[None], len(A_c), 0), A_c, B_c)[0].min()) <= lim for q in P3)
                    gone = [e for e in gone if in_stroke(e)]
                gone_s = set(gone)
                ends_ = {v for e in gone for v in edges[e]}
                if any(len(left) == 1 and not lands_on(v, left[0], A_c, B_c, max(w_c - t.weight(e_style[left[0]][2], d.scale) if e_style[left[0]] not in (None, RING) else 0.0, 0.0) / (2 * k) + touch)
                       for v in ends_ for left in [[x for x in adj[v] if x not in gone_s]]):
                    continue
            if not gone:
                continue
            for e in gone:
                kill(e, 'a thin face: only its heaviest line kept')
                fate_by[e] = int(owner[first(carrier[0])])
            report['doubles']['thin_faces'] += 1
            report['doubles']['length_pt'] += sum(elen(e) for e in gone) * k
            if len(report['doubles']['examples']) < 20:
                x0 = max(round_, key=line_rank)
                report['doubles']['examples'].append(dict(
                    layer='/'.join(e_style[gone[0]][:2]), beside='CUT' if e_style[x0] is RING else '/'.join(e_style[x0][:2]),
                    length_pt=round(sum(elen(e) for e in gone) * k, 2), at_pt=paper((fc.centroid.x, fc.centroid.y), hx, hy, k),
                    thin_face=True))
    report['doubles']['length_pt'] = round(report['doubles']['length_pt'], 2)
    report['seconds']['doubles'] = round(time.time() - T3d, 2)

    # ---- line ends: met where they stop a hair short of other linework or run a hair past it
    T3e = time.time()
    on_frame = lambda p: min(abs(p[0]), abs(2 * hx - p[0]), abs(p[1]), abs(2 * hy - p[1])) < g_ / 100   # clipped ends lie on it
    ran_on = set()                                     # edges the line ends added, under reach each
    # decided on the grid, drawn from the model: a node is drawn where the export's lines through it meet, the point
    # nearest in least squares to the source pieces of its live edges, pulled lightly to the node and kept within 1.5
    # grid steps of it, so a curve runs along its source, not the grid's steps , and every path through a node takes the same point. Lines meeting at a slant too fine for that point to lie
    # within 1.5 grid steps (a tile line touching a roof's outline where the grid made them meet) are held to square to
    # their mean direction and left where the grid put the node along them
    nrm_pc = np.stack([-(PC[:, 4] - PC[:, 1]), PC[:, 3] - PC[:, 0]], 1)
    nrm_pc /= np.maximum(np.hypot(nrm_pc[:, 0], nrm_pc[:, 1]), 1e-300)[:, None]
    def solve_at(q0, ps_):
        if not ps_:
            return tuple(q0.tolist())
        ps_ = np.array(sorted(ps_))
        N_ = nrm_pc[ps_]
        c_ = (N_ * PC[ps_][:, [0, 1]]).sum(1)
        q = np.linalg.solve(N_.T @ N_ + 1e-6 * np.eye(2), (N_ * c_[:, None]).sum(0) + 1e-6 * q0)
        if math.dist(q, q0) > 1.5 * g_:
            u_ = np.linalg.eigh(N_.T @ N_)[1][:, 1]
            nu_ = N_ @ u_
            q = q0 - u_ * float(((N_ @ q0 - c_) * nu_).sum() / max(float((nu_ ** 2).sum()), 1e-300))
        return tuple((q if math.dist(q, q0) <= 1.5 * g_ else q0).tolist())

    def own_src(x):
        """the source pieces edge x is drawn from: a cut edge's section lines, any other its owner's; all of them where
        none is (a ring's edge merged with a stair's line 0.05 pt beside it, drawn halfway between, the model)"""
        ss_ = [p_ for p_, _ in srcs[first(x)]]
        if e_style[x] is RING:
            own_ = [p_ for p_ in ss_ if segs[int(PC[p_, 6])].get('cut') is not None]
        else:
            own_ = [p_ for p_ in ss_ if segs[int(PC[p_, 6])]['o'] == int(owner[first(x)])]
        return own_ or ss_

    def true_pt(n):
        """node n where the paths will draw it, from the lines at it now"""
        q0 = np.array(nodes[n], dtype=float)
        ps_ = {p_ for x in adj[n] if alive[x] and e_style[x] is not None for p_ in own_src(x)}
        ends_ = [PC[p_, c_] for p_ in ps_ for c_ in ([0, 1], [3, 4])] if len(adj[n]) == 1 else []
        end_ = min(ends_, key=lambda c_: math.dist(c_, q0)) if ends_ else None
        # a free end at its line's own end where the model's is within the grid (a light well's crease ending
        # 0.003 pt off the roof's corner, the grid's steps falling between them: the model)
        return tuple(end_.tolist()) if end_ is not None and math.dist(end_, q0) <= 1.5 * g_ else solve_at(q0, ps_)

    reach = near * 1.02                                # past lint's near_pt, which an end measured a hair under it would fail
    cos30, cos20 = math.cos(math.radians(30)), math.cos(math.radians(20))

    def src_dir(x):
        """the direction of edge x's longest own source piece"""
        ps_ = own_src(x)
        if not ps_:
            return None
        d_ = max((PC[p_, [3, 4]] - PC[p_, [0, 1]] for p_ in ps_), key=lambda v_: float(np.hypot(*v_)))
        ln_ = float(np.hypot(*d_))
        return d_ / ln_ if ln_ > 0 else None

    def ray_on(v, p, walk, walked):
        """the run on of free end v (at p, its line's walk back from it) along its own direction to the first line it
        meets within 3 pt, 6 pt where it meets it under 10 degrees, one within reach of the end, where it meets it at 1
        degree or more, and only where the model's lines run on there: (length, the edge met, the point), or None"""
        back_n = next((y for x, at, y in walk if at + elen(x) >= 0.5 / k), walk[-1][2])
        u_r = p - np.array(nodes[back_n])
        lu_r = float(np.hypot(*u_r))
        if lu_r <= 0:
            return None
        u_r /= lu_r
        hit = None
        for jr in tr.query(shapely.linestrings([p, p + u_r * 6.0 / k]), predicate='intersects').tolist():
            for x in live_of(live_e[jr]):
                if x in adj[v] or x in walked or not alive[x]:
                    continue
                qa_, qb_ = np.array(nodes[edges[x][0]]), np.array(nodes[edges[x][1]])
                d2_ = qb_ - qa_
                den_ = u_r[0] * d2_[1] - u_r[1] * d2_[0]
                l2_ = float(np.hypot(*d2_))
                if l2_ <= 0 or abs(den_) < math.sin(math.radians(1)) * l2_:
                    continue
                w0_ = qa_ - p
                t_r = (w0_[0] * d2_[1] - w0_[1] * d2_[0]) / den_
                s_r = (w0_[0] * u_r[1] - w0_[1] * u_r[0]) / den_
                lim_r = (6.0 if abs(den_) < math.sin(math.radians(10)) * l2_ else 3.0) / k   # further nearly along it
                if 0 < t_r <= lim_r and 0.0 <= s_r <= 1.0 and (hit is None or t_r < hit[0]) and \
                        float(seg_dist(p[None], qa_[None], qb_[None])[0][0]) < reach:   # a line the end is near
                    hit = (t_r, x, p + u_r * t_r)
        return hit if hit is not None and on_model(p, hit[2]) else None

    def end_dir(n, x):
        """the way a line points out of its free end n along edge x, as drawn, over about 0.3 pt back along it"""
        w, prev, run = n, x, 0.0
        while True:
            a, b = edges[prev]
            u = b if a == w else a
            run += math.dist(true_pt(w), true_pt(u))
            if run >= 0.3 / k or len(adj[u]) != 2:
                break
            (nxt,) = adj[u] - {prev}
            w, prev = u, nxt
        d = np.array(true_pt(n)) - np.array(true_pt(u))
        ln = float(np.hypot(*d))
        return d / ln if ln > 0 else None
    reach_t = near + 0.002 / k                         # as drawn, where only the SVG's rounding parts this from lint's

    # a line's last stretch in its own class, back across one edge or within near of its end to a node of two lines
    # where it goes on in another class, is a path of its own: its end, within near of the other line, is a near miss of
    # that line's path. Under min_len_pt, or ending within near of that node and going on within 20 degrees, the paths
    # draw it in that line's class; else, with nothing else met, it is cut back to the node, as a stub or hair off a
    # junction is, and the end left there is met next round (a contact curve's corner 0.2 pt before it turns hidden,
    # fuzz seed 73; one leaving a step line at 7 degrees, its end 0.13 pt off it, fuzz seed 180)
    def cut_tail(v, own):
        p, tail, w, y = np.array(nodes[v]), [own], v, own
        while True:
            a, b = edges[y]
            c = b if a == w else a
            if len(adj[c]) != 2:
                return False
            (y,) = adj[c] - {y}
            if e_style[y] != e_style[own]:
                break
            if math.dist(nodes[v], nodes[c]) >= near:
                return False
            tail.append(y)
            w = c
        ln = sum(elen(x) for x in tail)
        if e_style[y] in (None, RING) or ln < minlen or \
                float(seg_dist(p[None], np.array([nodes[edges[y][0]]]), np.array([nodes[edges[y][1]]]))[0][0]) >= near:
            return False
        stub = math.dist(p, nodes[c]) < near
        if stub and bend(tail[-1], y) <= math.radians(20):
            return False
        for x in tail:
            kill(x, 'a hair: a line end within reach of a line, taken out')
        report['fixes'].append(dict(o=int(owner[first(own)]), kind='overshoot cut back' if stub else 'hair taken out', length_pt=round(ln * k, 3),
                                    at_pt=paper(nodes[v], hx, hy, k),
                                    model=model_at(nodes[v][0], nodes[v][1], float(e_z[first(own)]))))
        return True
    for rnd in range(8):                               # a line taken whole frees the ends that met it, met next round
        live_e = [e for e in range(len(edges)) if alive[e]]
        if not live_e:                                 # every line taken out before the ends are met
            break
        A_ = np.array([nodes[edges[e][0]] for e in live_e])
        B_ = np.array([nodes[edges[e][1]] for e in live_e])
        tr = shapely.STRtree(shapely.linestrings(np.stack([A_, B_], 1)))
        free = [v for v in list(adj) if len(adj[v]) == 1 and not on_frame(nodes[v])]
        if not free:
            break
        changed = 0
        queued, n_log, at_v = set(free), len(killed_log), 0
        while at_v < len(free):
            # an end that a line taken out this round left free is met in the same round (a book's line taken whole,
            # then the chair's line that ended on it)
            for e_k in killed_log[n_log:]:
                for n_k in edges[e_k]:
                    if len(adj[n_k]) == 1 and n_k not in queued and not on_frame(nodes[n_k]):
                        free.append(n_k)
                        queued.add(n_k)
            n_log = len(killed_log)
            v = free[at_v]
            at_v += 1
            if len(adj[v]) != 1:
                continue
            p = np.array(nodes[v])
            (own,) = adj[v]
            # the line back from its end through nodes where it goes on alone, to 2 reach; its stretch until it first
            # leaves the circle of near round the end (a curve in grid steps, bending, came back 0.58 pt off its end
            # 0.9 pt along it, fuzz seed 146), followed straight on through junctions, is the line itself, not linework
            # to meet (the next short edges of a curve; a curb's next piece past a node on the P2 section's ground line)
            walk, w, prev, run = [], v, own, 0.0
            while True:
                a, b = edges[prev]
                u = b if a == w else a
                walk.append((prev, run, u))
                run += math.dist(nodes[w], nodes[u])
                if run >= 2 * reach or len(adj[u]) != 2:
                    break
                (nxt,) = adj[u] - {prev}
                w, prev = u, nxt
            itself, w_, x_ = set(), v, own                # until it first leaves the circle of near round the end, as
            while x_ not in itself:                       # lint counts a path's own stretch, straight on through junctions
                itself.add(x_)
                a, b = edges[x_]
                u_ = b if a == w_ else a
                if math.dist(nodes[v], nodes[u_]) >= near:
                    break
                on_ = [(abs(abs(heading(y, u_) - heading(x_, u_)) - math.pi), y) for y in adj[u_] if y != x_]
                on_ = [(min(tn, abs(tn - 2 * math.pi)), y) for tn, y in on_]
                if not on_ or len(on_) > 1 and min(on_)[0] > math.radians(20):
                    break                              # alone it goes on whatever the turn; at a junction, straight on
                w_, x_ = u_, min(on_)[1]
            # a line split by an end met earlier in the round is in the tree as it was: its halves stand for it (a beam's
            # edge that the first of the model's joists to reach it split, which the joists after it then missed)
            cand = [x for j in tr.query(shapely.points(p).buffer(near * 1.05)) for x in live_of(live_e[j])
                    if x not in adj[v] and x not in itself]
            sides = [p[0], 2 * hx - p[0], p[1], 2 * hy - p[1]]   # the frame is linework too: lines crossing it end on it
            df = min(sides)
            # a near miss is decided as drawn, the end and the lines by it where the model has them: the grid put a
            # stub's end 0.65 pt off a line the model has it 0.588 pt off (the model's tiles), and two chords 0.61 pt apart
            # are no near miss however the grid falls
            tp_ = {}

            def tpt(n):
                if n not in tp_:
                    tp_[n] = np.array(true_pt(n))
                return tp_[n]
            if cand:
                ca = np.array([nodes[edges[e][0]] for e in cand])
                cb = np.array([nodes[edges[e][1]] for e in cand])
                dd, tt = seg_dist(np.repeat(p[None], len(cand), 0), ca, cb)
                j = int(np.argmin(dd))
                dd_t = seg_dist(np.repeat(tpt(v)[None], len(cand), 0), np.array([tpt(edges[e][0]) for e in cand]),
                                np.array([tpt(edges[e][1]) for e in cand]))[0]
            q_f = p.copy()
            if df < reach:
                i_ = sides.index(df)
                q_f[i_ // 2] = (0.0, 2 * hx, 0.0, 2 * hy)[i_]
            if df < reach and (not cand or df < float(dd[j])) and on_model(p, q_f):   # the model's line runs on past it
                q = q_f
                ran_on.add(add_edge(v, add_node(q), own))
                report['fixes'].append(dict(o=int(owner[first(own)]), kind='run on to the frame', length_pt=round(df * k, 3), at_pt=paper(nodes[v], hx, hy, k),
                                            model=model_at(nodes[v][0], nodes[v][1], float(e_z[first(own)]))))
                changed += 1
                continue
            # a gap under min_len_pt in one object's lines, between this end and a free end of the same object, each
            # facing the other within 30 degrees, is closed: too short to read as a gap, and cut back clear of each
            # other the two ends would open it to near_pt (the model's pillows, two tangent edges 0.19 pt apart at each
            # corner where the export has nothing between)
            o_v, d_v, gap_w = int(owner[first(own)]), False, None
            for x in cand:
                if e_style[x] in (None, RING) or int(owner[first(x)]) != o_v:
                    continue
                for w in edges[x]:
                    if w == v or len(adj[w]) != 1 or on_frame(nodes[w]):
                        continue
                    gv = tpt(w) - tpt(v)
                    gl = float(np.hypot(*gv))
                    if not 0 < gl < minlen or gap_w is not None and gl >= gap_w[0]:
                        continue
                    d_v = end_dir(v, own) if d_v is False else d_v
                    d_w = end_dir(w, next(iter(adj[w])))
                    if d_v is not None and d_w is not None and float(d_v @ gv) >= cos30 * gl and float(d_w @ -gv) >= cos30 * gl:
                        gap_w = (gl, w)
            if gap_w is not None:
                ran_on.add(add_edge(v, gap_w[1], own))
                report['fixes'].append(dict(o=o_v, kind='gap closed', length_pt=round(gap_w[0] * k, 3), at_pt=paper(nodes[v], hx, hy, k),
                                            model=model_at(nodes[v][0], nodes[v][1], float(e_z[first(own)]))))
                changed += 1
                continue
            if not cand or float(dd_t.min()) >= reach_t:
                changed += cut_tail(v, own)
                continue
            # an end beside the lines it is near, its own line within 20 degrees of each and each to its side, not
            # ahead, its stroke clear of theirs (a double the doubles kept, or a line converging on another), is the
            # model's and stays as it is:
            # the line ends take out no line the doubles kept beside another (the adversarial tests doubles-min-hair and
            # doubles-min-convergence: a 2 pt line 0.42 pt beside a 4 pt one taken whole, a line converging at 8 degrees
            # cut back 1.6 pt)
            d_e = end_dir(v, own)
            run_b, w_b = 0.0, v                        # as drawn, back to where the line meets others: a stub off a
            for _, _, y_b in walk:                     # junction under near is no line beside another, and goes below
                run_b += float(np.hypot(*(tpt(y_b) - tpt(w_b))))
                w_b = y_b
            if d_e is not None and not (run_b < near and len(adj[walk[-1][2]]) >= 3) and ray_on(v, p, walk, {x for x, _, _ in walk}) is None:
                near_i = np.nonzero(dd_t < reach_t)[0].tolist()
                ta_ = np.array([tpt(edges[cand[i_]][0]) for i_ in near_i])
                tb_ = np.array([tpt(edges[cand[i_]][1]) for i_ in near_i])
                dn_, tn_ = seg_dist(np.repeat(tpt(v)[None], len(near_i), 0), ta_, tb_)
                beside_ = True
                w_v = t.weight(e_style[own][2], d.scale) if e_style[own] not in (None, RING) else 0.0
                for i_, (qa_, qb_, t_n, g_n) in enumerate(zip(ta_, tb_, tn_.tolist(), dn_.tolist())):
                    x_n = cand[near_i[i_]]
                    u_x = src_dir(x_n)
                    o_x = qa_ + (qb_ - qa_) * t_n - tpt(v)
                    w_x = ring_w(x_n) if e_style[x_n] is RING else t.weight(e_style[x_n][2], d.scale) if e_style[x_n] else 0.0
                    if u_x is None or abs(float(d_e @ u_x)) < cos20 or abs(float(o_x @ d_e)) > 0.5 * float(np.hypot(*o_x)) \
                            or g_n <= max(min(w_x, 1e9) - w_v, 0.0) / (2 * k) + touch:   # inside its stroke: it may go
                        beside_ = False
                        break
                if beside_:
                    report['ends_beside'] = report.get('ends_beside', 0) + 1
                    continue
            # a stub: the line hangs off a node where three or more meet, under near back along it, and is cut back
            # there (an overshoot past the line it crosses; a remnant a double left at a junction, the long section's
            # tile lines); a hair: it leaves the line it is nearest at such a node and stays within reach of other
            # linework to its end (a tile line from a cut's corner that ended on a double that gave way), and is taken out
            walked = {x for x, _, _ in walk}
            run_t, w_t = 0.0, v                        # the walk's length as drawn: a stub 0.6 pt on the grid is 0.59
            for x, _, y in walk:
                run_t += float(np.hypot(*(tpt(y) - tpt(w_t))))
                w_t = y
            # a line pointing at another within reach along its own direction, square to it at 30 degrees or more or at
            # its end, runs on to it there and is not cut back as a stub: a corner the meshes hid a hair of (the model's
            # joist end under its beam)
            back_s = next((y for x, at, y in walk if at + elen(x) >= 0.5 / k), walk[-1][2])
            u_s = p - np.array(nodes[back_s])
            if float(np.hypot(*u_s)) > 0:
                u_s = u_s / float(np.hypot(*u_s))
                hit_s = None
                for jr in tr.query(shapely.linestrings([p, p + u_s * reach]), predicate='intersects').tolist():
                    for x in live_of(live_e[jr]):
                        if x in adj[v] or x in walked or not alive[x]:
                            continue
                        qa_, qb_ = np.array(nodes[edges[x][0]]), np.array(nodes[edges[x][1]])
                        d2_ = qb_ - qa_
                        l2_ = float(np.hypot(*d2_))
                        den_ = u_s[0] * d2_[1] - u_s[1] * d2_[0]
                        if l2_ <= 0 or abs(den_) < math.sin(math.radians(1)) * l2_:
                            continue
                        w0_ = qa_ - p
                        t_r = (w0_[0] * d2_[1] - w0_[1] * d2_[0]) / den_
                        s_r = (w0_[0] * u_s[1] - w0_[1] * u_s[0]) / den_
                        if 0 < t_r <= reach and -g_ / l2_ <= s_r <= 1 + g_ / l2_ and (abs(den_) >= 0.5 * l2_ or min(s_r, 1 - s_r) * l2_ <= g_) \
                                and (hit_s is None or t_r < hit_s[0]):
                            hit_s = (t_r, x, p + u_s * t_r)
                if hit_s is not None and run_t < near and len(adj[u]) >= 3 and on_model(p, hit_s[2]):
                    e_h = hit_s[1]
                    q_h = hit_s[2]
                    ea_, eb_ = edges[e_h]
                    w2 = ea_ if math.dist(q_h, nodes[ea_]) <= g_ else eb_ if math.dist(q_h, nodes[eb_]) <= g_ else split(e_h, q_h)
                    if w2 != v:
                        ran_on.add(add_edge(v, w2, own))
                    report['fixes'].append(dict(o=int(owner[first(own)]), kind='run on to meet', length_pt=round(hit_s[0] * k, 3),
                                                at_pt=paper(nodes[v], hx, hy, k),
                                                model=model_at(nodes[v][0], nodes[v][1], float(e_z[first(own)]))))
                    changed += 1
                    continue
            at_u = len(adj[u]) >= 3 and any(x in adj[u] for x, dx in zip(cand, dd.tolist()) if dx <= float(dd[j]) + g_)
            oth = [i for i, x in enumerate(cand) if x not in walked]
            if run_t < near and len(adj[u]) >= 3 or at_u and oth and all(
                    float(seg_dist(np.repeat(np.array(nodes[y])[None], len(oth), 0), ca[oth], cb[oth])[0].min()) < reach
                    for _, _, y in walk):
                for x, _, _ in walk:
                    kill(x, 'a stub at a junction, cut back')
                report['fixes'].append(dict(o=int(owner[first(own)]), kind='overshoot cut back' if run_t < near else 'hair taken out', length_pt=round(run_t * k, 3),
                                            at_pt=paper(nodes[v], hx, hy, k),
                                            model=model_at(nodes[v][0], nodes[v][1], float(e_z[first(own)]))))
                changed += 1
                continue
            mine = adj[edges[own][0]] | adj[edges[own][1]]
            # else run on to the nearest line that is not the one its own edge runs on from, unless the run on would go
            # back over the line itself, within 30 degrees of its chord over near and lying on it (a curb piece on the
            # P2 section's ground line, run back 0.3 pt over itself to the next piece past a hidden gap), or, for a
            # line under near free at both ends, within 30 degrees of it at all (a tile course's 0.2 pt left between
            # two tile lines that gave way as doubles, run back 0.6 pt past its own far end on the model's roof); a hook
            # closing on the line further back is met
            far_ = next((y for x, at, y in walk if at + elen(x) >= near), walk[-1][2])
            back_ = np.array(nodes[far_]) - p
            back_ /= max(float(np.hypot(*back_)), 1e-300)
            to_ = ca + (cb - ca) * tt[:, None] - p
            wa = np.array([nodes[edges[x][0]] for x, _, _ in walk])
            wb = np.array([nodes[edges[x][1]] for x, _, _ in walk])
            sliver = run_t < near and len(adj[u]) == 1
            over = np.array([(q_ @ back_) > 0.866 * float(np.hypot(*q_)) and (sliver or
                             float(seg_dist(np.repeat((p + q_ / 2)[None], len(walk), 0), wa, wb)[0].min()) < g_) for q_ in to_])
            dd = np.where(np.array([e in mine for e in cand]) | over, np.inf, dd)
            dd_t = np.where(np.array([e in mine for e in cand]) | over, np.inf, dd_t)
            j = int(np.argmin(dd))
            dist = float(dd[j])
            if float(dd_t.min()) >= reach_t:
                changed += cut_tail(v, own)
                continue
            e = cand[j]
            q = ca[j] + (cb[j] - ca[j]) * tt[j]
            # run on along the line's own direction to the first line it meets within 3 pt, 6 pt where it meets it under
            # 10 degrees, one within reach of the end, where it meets it at 1 degree or more, and only where the model's
            # lines run on there (the line's own, hidden past its end, or one lying along it): a line converging on
            # another ends on it along its own path, not by a link square to it, and
            # nothing is drawn the model does not have (a door's mullion ending at a knob's
            # edge that the thin faces took, the model)
            hit = ray_on(v, p, walk, walked)
            if hit is not None:
                dist, e, q = hit
                hit = 'ray'
            if hit != 'ray' and dist > 1.5 * g_ and float(dd_t.min()) > touch:   # within the grid or on it as drawn, met
                # met only along its own direction: an end the ray does not take to the line beside it is cut back
                # along its own path, the line as far as its junction or change of class, until it is clear of every
                # other line by reach and a grid step, which drawing the nodes where the model has them can take back;
                # a line clear nowhere is taken whole (a link square to the line, or eased onto it, read as a hook:
                # a counter's mesh crease 0.4 pt off its edge, ending 0.26 pt short of
                # the sink, the model's plan)
                line_, w_c, x = [], v, own
                while True:
                    a_, b_ = edges[x]
                    u_c = b_ if a_ == w_c else a_
                    line_.append((x, w_c, u_c))
                    if len(adj[u_c]) != 2 or len(line_) > 4096:
                        break
                    (y,) = adj[u_c] - {x}
                    if any(y == x_ for x_, _, _ in line_) or e_style[y] != e_style[own]:
                        break
                    x, w_c = y, u_c
                excl_ = itself | adj[v]

                def clear_(i_, t_):
                    """the point t_ along the line's edge i_ clear of every other line by reach as drawn: the line itself
                    up to there, and on from there until it first leaves the circle of near round it, is not other
                    linework; the line coming back later is, as lint counts a hook"""
                    _, w_i, u_i = line_[i_]
                    q_ = np.array(nodes[w_i]) + (np.array(nodes[u_i]) - np.array(nodes[w_i])) * t_
                    q_t = tpt(w_i) + (tpt(u_i) - tpt(w_i)) * t_
                    own_ = {x_ for x_, _, _ in line_[:i_ + 1]}
                    for x_, _, u_ in line_[i_ + 1:]:
                        own_.add(x_)
                        if math.dist(q_, nodes[u_]) >= near:
                            break
                    for jr in tr.query(shapely.points(q_), predicate='dwithin', distance=reach + 3 * g_).tolist():
                        for x in live_of(live_e[jr]):
                            if x not in excl_ and x not in own_ and alive[x] and float(seg_dist(
                                    q_t[None], tpt(edges[x][0])[None], tpt(edges[x][1])[None])[0][0]) < reach:
                                return False
                    return True
                cut_, whole = [], True
                for i_c, (x, w_c, u_c) in enumerate(line_):
                    # the first point along the edge, every 0.25 pt, clear (an edge's far node may be a corner where it
                    # is not, its middle clear: a box's edge 42 pt long ending 0.3 pt short of its corner)
                    ts_ = np.linspace(0.0, 1.0, max(2, int(math.ceil(elen(x) * k / 0.25)) + 1))[1:]
                    t_ok = next((t_ for t_ in ts_ if clear_(i_c, float(t_))), None)
                    if t_ok is not None:
                        lo_, hi_ = float(t_ok) - 1.0 / (len(ts_)), float(t_ok)   # where along the edge it clears: halved
                        lo_ = max(lo_, 0.0)
                        for _ in range(20):
                            mid_ = (lo_ + hi_) / 2
                            lo_, hi_ = (mid_, hi_) if not clear_(i_c, mid_) else (lo_, mid_)
                        P0_, P1_ = np.array(nodes[w_c]), np.array(nodes[u_c])
                        q_c = P0_ + (P1_ - P0_) * hi_
                        if math.dist(q_c, P1_) > g_ / 2:
                            v_c = split(x, tuple(q_c))
                            x = next(y for y in adj[v_c] if w_c in edges[y])
                        cut_.append(x)
                        whole = False
                        break
                    cut_.append(x)
                why_c = 'a hair: within reach of other linework to its junction, taken whole' if whole else \
                    'an end cut back clear of a line beside it'
                for x in cut_:
                    kill(x, why_c)
                    fate_by[x] = int(owner[first(e)])
                report['fixes'].append(dict(o=int(owner[first(own)]), kind='hair taken whole' if whole else 'end cut back clear',
                                            length_pt=round(sum(elen(x) for x in cut_) * k, 3), at_pt=paper(nodes[v], hx, hy, k),
                                            model=model_at(nodes[v][0], nodes[v][1], float(e_z[first(own)]))))
                changed += 1
                continue
            ea, eb = edges[e]
            if math.dist(q, nodes[ea]) <= g_:
                w2 = ea
            elif math.dist(q, nodes[eb]) <= g_:
                w2 = eb
            else:
                w2 = split(e, q)
            if dist > touch:
                report['fixes'].append(dict(o=int(owner[first(own)]), kind='run on to meet', length_pt=round(dist * k, 3), at_pt=paper(nodes[v], hx, hy, k),
                                            model=model_at(nodes[v][0], nodes[v][1], float(e_z[first(own)]))))
            if w2 != v:
                ran_on.add(add_edge(v, w2, own))
            changed += 1
        if not changed:
            break
    report['seconds']['ends'] = round(time.time() - T3e, 2)

    # ---- paths: each sublayer's edges chained, straight on through nodes where three or more meet
    T4 = time.time()
    def styled(v):
        return [x for x in adj[v] if alive[x] and e_style[x] not in (None, RING)]

    # a path shorter than lint's min_len_pt that does not stand free (a class flickering along a curve where the depth
    # behind it is near gap_m, a sliver by a cut's corner) takes the style of a line that ends where it ends, the
    # straightest, so it is part of that path; with none, it goes if every node it touches keeps two lines, so nothing
    # comes apart; else it stays. So does a line's last stretch to a free end, ending within near_pt of it, in another
    # class than the line it goes on from within 20 degrees: drawn apart, its free end would be a near miss of that line
    for rnd in range(4):
        by_style = defaultdict(list)
        for e in range(len(edges)):
            if alive[e] and e_style[e] not in (None, RING):
                by_style[e_style[e]].append(e)
        changed = 0
        for st, es in by_style.items():
            for pts_n, closed, run in chain(es):
                ends = ((pts_n[0], run[0]), (pts_n[-1], run[-1]))
                free_ = sum(len([x for x in adj[v] if alive[x]]) <= 1 for v, _ in ends)
                if closed or (math.dist(true_pt(pts_n[0]), true_pt(pts_n[-1])) >= reach_t if free_ == 1 else   # as drawn: 0.6
                              sum(elen(e) for e in run) >= minlen):                                    # on the grid is 0.583
                    continue
                if free_ == 2:
                    continue                           # free at both ends: a stray, left out below
                cand = [(bend(e, x), x) for v, e in ends for x in styled(v) if x not in run and e_style[x] != st
                        and sum(1 for y in styled(v) if e_style[y] == e_style[x]) == 1]
                if free_ and sum(elen(e) for e in run) >= minlen and not (cand and min(cand)[0] <= math.radians(20)):
                    continue
                if cand:
                    to = e_style[min(cand)[1]]
                    for e in run:
                        e_style[e] = to
                    changed += 1
                elif all(len([x for x in adj[v] if alive[x] and x not in run]) >= 2 for v, _ in ends) and \
                        all(len([x for x in adj[v] if alive[x] and x not in run]) != 1 for v in pts_n[1:-1]):
                    for e in run:
                        kill(e, 'a short run between lines, tucked')
                    report['strays']['tucked'] = report['strays'].get('tucked', 0) + 1
                    changed += 1
        if not changed:
            break
    by_style = defaultdict(list)
    overdrawn = set()
    outline_w = {}                                     # a weight: the outlines of the cut regions at least that heavy
    for e in range(len(edges)):
        if alive[e] and e_style[e] is not None and e_style[e] is not RING:
            by_style[e_style[e]].append(e)
        elif alive[e] and e_style[e] is RING and has_nr[first(e)] and first(e) not in surf_round:
            st = line_style[first(e)]                  # a ring's edge that is also a heavier body's open cut (a box
            if st and st[1].endswith(' open cuts') and t.weight(st[2], d.scale) > ring_w(e):   # against a wall,
                w_st = t.weight(st[2], d.scale)        # a wall's open cut) is drawn as that cut too, over the ring;
                if w_st not in outline_w:              # a cut closed into a region draws its own outline there
                    outline_w[w_st] = shapely.union_all([u.boundary for b_, u in clipped
                                                         if t.weight(cut_weight(first_g[b_]), d.scale) >= w_st - 1e-9])
                m_ = shapely.Point((nodes[edges[e][0]][0] + nodes[edges[e][1]][0]) / 2, (nodes[edges[e][0]][1] + nodes[edges[e][1]][1]) / 2)
                if outline_w[w_st].is_empty or outline_w[w_st].distance(m_) > g_:
                    by_style[st].append(e)
                    overdrawn.add(e)
    by_style = dict(sorted(by_style.items(), key=lambda kv: (t.weight(kv[0][2], d.scale), kv[0][1])))   # lightest first
    deg_all = {v: len(es) for v, es in adj.items()}
    lengths = defaultdict(float)
    stray_P = []
    drawn_paths = []                                   # every drawn path's points, drawing units
    true_at = {}                                       # each node where it is drawn, once the graph is final

    def at_model(n):
        if n not in true_at:
            true_at[n] = true_pt(n)
        return true_at[n]
    # the cuts are drawn from the model too: each corner of a region that is a node of the graph where its node is drawn,
    # or, a node the passes left no line at (inside a merged poché, under a gap closed), where its rings meet
    xy_node, ring_at = {}, defaultdict(set)
    for e in range(len(edges)):
        if alive[e]:
            for n in edges[e]:
                xy_node.setdefault((round(nodes[n][0], 9), round(nodes[n][1], 9)), n)
    for e in range(len(edges)):
        if e_style[e] is RING:
            for n in edges[e]:
                xy_node.setdefault((round(nodes[n][0], 9), round(nodes[n][1], 9)), n)
                ring_at[n] |= set(own_src(e))

    def true_ring(coords):
        out = []
        for c in coords:
            n = xy_node.get((round(c[0], 9), round(c[1], 9)))
            out.append(tuple(c) if n is None else at_model(n) if any(alive[x] and e_style[x] is not None for x in adj[n])
                       else solve_at(np.array(nodes[n], dtype=float), ring_at[n]))
        return out
    cut_true = [(b, [shapely.Polygon(true_ring(q.exterior.coords), [true_ring(r.coords) for r in q.interiors])
                     for q in shapely.get_parts(u) if q.geom_type == 'Polygon' and q.area > 0]) for b, u in clipped]
    # a line ending on a ring's edge ends on the cut as drawn, within 3 MESH_PT: the regions are merged and closed from
    # the rings, so their outline can lie a grid step or so off the ring's edges in the graph (an open cut that gave way
    # to the model's roof ring ended 0.055 pt off the roof's cut, a near miss)
    cut_parts = [r for _, qs in cut_true for q in qs for r in [q.exterior] + list(q.interiors)]
    true_of = {id(u): qs for (_, u), (_, qs) in zip(clipped, cut_true)}
    cut_tree = shapely.STRtree(cut_parts) if cut_parts else None

    def on_cut(n):
        p = at_model(n)
        if cut_tree is None or not any(alive[x] and e_style[x] is RING for x in adj[n]):
            return p
        near_ = cut_tree.query_nearest(shapely.Point(p), max_distance=3 * MESH_PT / k)
        if not len(near_):
            return p
        return tuple(shapely.shortest_line(cut_parts[int(near_[0])], shapely.Point(p)).coords[0])
    def loops_apart(pts_n, closed):
        """a path that comes back through its own end, as a loop and the rest: drawn as one, its end would touch only
        itself, a near miss of the line beside it (the model's contact curves, a loop of four edges 0.1 pt across at a
        junction, its end 0.05 pt off the next line)"""
        if closed:
            return [(pts_n, True)]
        if pts_n[0] in pts_n[1:-1]:
            i = pts_n.index(pts_n[0], 1)
            if len(set(pts_n[:i])) >= 3:
                return [(pts_n[:i + 1], True)] + loops_apart(pts_n[i:], False)
        if pts_n[-1] in pts_n[1:-1]:
            j = len(pts_n) - 1 - pts_n[::-1].index(pts_n[-1], 1)
            if len(set(pts_n[j:])) >= 3:
                return loops_apart(pts_n[:j + 1], False) + [(pts_n[j:], True)]
        return [(pts_n, False)]
    def src_near(x, p):
        """the point of edge x's own source pieces nearest p"""
        best, p = None, np.asarray(p, dtype=float)
        for p_ in own_src(x):
            a_, ab = PC[p_, [0, 1]], PC[p_, [3, 4]] - PC[p_, [0, 1]]
            q_ = a_ + ab * min(1.0, max(0.0, float((p - a_) @ ab) / max(float(ab @ ab), 1e-300)))
            if best is None or math.dist(q_, p) < math.dist(best, p):
                best = q_
        return best

    def along_own(pts_n, P, es_at):
        """P with, beside each node drawn further than 1.5 grid steps off an edge's own source where the edge drawn
        straight to it would leave the model's lines, that source's point nearest it: the edge runs along its source to
        there (two lines the grid noded together that the model has 0.08 pt apart, the node drawn on one, dragged 2 pt of
        the other off the model: the model under B and C)"""
        out, sources = [P[0]], []
        for i_ in range(len(pts_n) - 1):
            x_ = es_at.get(frozenset((pts_n[i_], pts_n[i_ + 1])))
            o_ = int(owner[first(x_)])
            if x_ is not None and x_ not in ran_on:
                qa, qb = src_near(x_, P[i_]), src_near(x_, P[i_ + 1])
                if qa is not None and math.dist(qa, P[i_]) > 1.5 * g_ and not on_model(P[i_], P[i_ + 1], 1.5 * g_):
                    out.append(tuple(qa.tolist()))
                    sources.append(o_)
                    report['paths_to_node'] += 1
                if qb is not None and math.dist(qb, P[i_ + 1]) > 1.5 * g_ and not on_model(out[-1], P[i_ + 1], 1.5 * g_):
                    out.append(tuple(qb.tolist()))
                    sources.append(o_)
                    report['paths_to_node'] += 1
            out.append(P[i_ + 1])
            sources.append(o_)
        return out, sources
    report['paths_to_node'] = 0
    d.rhino_lines = {}
    for st, es in by_style.items():
        lid, sub, w = st
        es_at = {frozenset(edges[e]): e for e in es}
        chains = [c_ for pts_n, closed, _ in chain(es) for c_ in loops_apart(pts_n, closed)]
        for pts_n, closed in chains:
            P = [at_model(n) for n in pts_n]
            if not closed:
                P[0], P[-1] = on_cut(pts_n[0]), on_cut(pts_n[-1])
            P, sources = along_own(pts_n, P, es_at)
            ln = sum(math.dist(a, b) for a, b in zip(P, P[1:]))
            if not closed and ln < minlen and deg_all.get(pts_n[0], 0) <= 1 and deg_all.get(pts_n[-1], 0) <= 1:
                report['strays']['count'] += 1
                report['strays']['length_pt'] += ln * k
                stray_P.append((lid, sub, P))
                continue
            if closed:
                P = P[:-1]
            d.polyline(lid, P, closed=closed, sub=sub)
            d.rhino_lines[id(d.ents[lid][-1])] = sources
            drawn_paths.append((P + [P[0]]) if closed else P)
            lengths[(lid, sub)] += ln * k
        d.sublayer(lid, sub, w)
    report['strays']['length_pt'] = round(report['strays']['length_pt'], 3)
    # lightest first, so where two bodies' cuts share an edge the heavier is drawn over it
    # a cut region thinner than thin_cut.times_weight its line's weight all through (glazing, a mullion, a thin slab) is
    # drawn at thin_cut.share of that weight, since two heavy lines that close read as one thick line; a region with a
    # thick part keeps its weight whole, so the poché runs on unbroken between thick and thin . Only where a cut's width on paper is its true width: a parallel view, its
    # first plane within 5 degrees of square to it (a perspective plan's wall thins with distance, which is no thin part)
    cl0 = (scene.get('clip') or [None])[0]
    true_w = not persp and cl0 is not None and abs(sum(a_ * b_ for a_, b_ in zip(cl0['normal'], scene['view']['direction']))) \
        >= math.cos(math.radians(5)) * math.sqrt(sum(a_ * a_ for a_ in cl0['normal']))
    tc = (hl.get('thin_cut') or {}) if true_w else {}
    report['cuts']['thin'] = 0
    for b, u in sorted(clipped, key=lambda bu: t.weight(cut_weight(first_g[bu[0]]), d.scale)):
        w_b = cut_weight(first_g[b])
        wb_pt = t.weight(w_b, d.scale)
        lim_w = float(tc.get('times_weight', 0)) * wb_pt / k          # a region thinner than this all through is thin
        w_thin = round(wb_pt * float(tc.get('share', 1)), 2)
        used_ = set()
        for poly, poly_t in zip([q for q in shapely.get_parts(u) if q.geom_type == 'Polygon' and q.area > 0], true_of[id(u)]):
            thin_ = lim_w > 0 and w_thin < wb_pt and 2 * shapely.maximum_inscribed_circle(poly, lim_w / 20).length < lim_w
            sub = f'{b} cuts thin' if thin_ else f'{b} cuts'
            rings = [list(poly_t.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly_t.interiors]
            d.polygon('CUT', rings, sub=sub)
            lengths[('CUT', sub)] += poly_t.length * k
            cut_polys.append(poly)                     # as decided: drawn where the model has it, a ring may cross itself
            report['cuts']['regions'] += 1
            report['cuts']['thin'] += thin_
            used_.add((sub, w_thin if thin_ else w_b))
        for sub, w_ in sorted(used_, key=lambda sw: (t.weight(sw[1], d.scale), sw[0])):   # lightest first, as the regions
            d.sublayer('CUT', sub, w_)
    report['cuts']['joints_pt'] = 0.0
    for b, paths, w in joint_lines:
        sub = f'{b} joints'
        for P in paths:
            P = true_ring(P)
            d.polyline('OUTLINE', P, sub=sub)
            ln = sum(math.dist(a_, b_) for a_, b_ in zip(P, P[1:])) * k
            lengths[('OUTLINE', sub)] += ln
            report['cuts']['joints_pt'] += ln
        d.sublayer('OUTLINE', sub, w)
    report['cuts']['joints_pt'] = round(report['cuts']['joints_pt'], 1)

    hidden_paths = []
    if show_hidden:
        if not by_faces:
            for s_ in under:
                if draw_g[o_group[s_['o']]] and s_.get('cut') is None:
                    P_ = np.asarray(s_['pts'], dtype=float)
                    start, end = (0, 0.0), (len(P_) - 2, 1.0)
                    for a_, b_ in revived_seen[id(s_)] + [(end, end)]:
                        if start[0] + start[1] < a_[0] + a_[1]:
                            Q_, _ = at(P_, np.array([start[0], a_[0]]), np.array([start[1], a_[1]]))
                            pts_ = [tuple(Q_[0])] + [tuple(p[:2]) for p in P_[start[0] + 1:a_[0] + 1]] + [tuple(Q_[1])]
                            hidden_candidates.append((o_group[s_['o']], LineString(np.asarray(pts_) * f + [hx, hy]), False))
                            hidden_sources.append((o_group[s_['o']], hidden_candidates[-1][1], s_['o']))
                        start = b_
            for e, why in fate.items():
                if why == 'the meshes see it hidden' and draw_g[o_group[int(owner[first(e)])]]:
                    hidden_candidates.append((o_group[int(owner[first(e)])],
                                              LineString([nodes[edges[e][0]], nodes[edges[e][1]]]), False))
                    hidden_sources.append((o_group[int(owner[first(e)])], hidden_candidates[-1][1], int(owner[first(e)])))
        for e_ in d.ents['HIDDEN']:
            P_ = e_['pts'] + e_['pts'][:1] if e_['closed'] else e_['pts']
            hidden_candidates.append((e_['sub'].removesuffix(' hidden'), LineString(P_), True))
            for a, b, o in zip(P_, P_[1:], d.rhino_lines[id(e_)]):
                if a != b:
                    hidden_sources.append((hidden_candidates[-1][0], LineString([a, b]), o))
            d.rhino_lines.pop(id(e_))
        hidden_paths, report['hidden_drawn'] = draw_hidden(d, hidden_candidates, cut_polys,
                                                         float(req.get('doubles_pt', lint_t['double_pt'])))
        for st_ in list(lengths):
            if st_[0] == 'HIDDEN':
                del lengths[st_]
        for sub, P in hidden_paths:
            lengths[('HIDDEN', sub)] += LineString(P).length * k
        drawn_paths += [P for _, P in hidden_paths]
    report['seconds']['paths'] = round(time.time() - T4, 2)
    held_to_model(report, drawn_paths, m_tree, scene, draw_g, o_group,
                  [(named_o(h.get('by')), h['pts']) for h in faced_hid] if by_faces else [],
                  [(nodes[edges[e][0]], nodes[edges[e][1]], why, named_o(fate_by.get(e))) for e, why in fate.items()],
                  stray_P, cut_polys, f, hx, hy, k, g_, slivers)

    # ---- fills: the faces between every visible line, each the colour of the surface seen in it
    T5 = time.time()
    fill_of = {}
    for gid, g in groups.items():
        if g.get('fill') or g.get('fills'):
            fill_of[gid] = g
    report['fills'] = dict(faces=0, filled=0, mixed=0)
    if fill_of:
        allE = [e for e in range(len(edges)) if (alive[e] or (e < n_e and not e_drawn[e])) and not e_dash[first(e)]]
        lines_ = [LineString([nodes[edges[e][0]], nodes[edges[e][1]]]) for e in allE]
        lines_.append(sbox(*frame).exterior)
        net = shapely.union_all(lines_, grid_size=g_)
        faces = [p for p in shapely.get_parts(shapely.polygonize(shapely.get_parts(net))) if p.area > 0]
        report['fills']['faces'] = len(faces)
        if faces:
            fa = np.array(faces, dtype=object)
            pts = np.array([[q.x, q.y] for q in shapely.point_on_surface(fa)])
            mids = np.array([[q.x, q.y] for q in shapely.centroid(fa)])
            hit = tris.nearest(pts, hide_kept)
            hit2 = tris.nearest(mids, hide_kept)
            inside = shapely.contains_xy(fa, mids[:, 0], mids[:, 1])
            skip = (pts[:, 0] <= 0) | (pts[:, 0] >= 2 * hx) | (pts[:, 1] <= 0) | (pts[:, 1] >= 2 * hy)
            if cut_polys:
                skip |= shapely.contains_xy(shapely.union_all(cut_polys), pts[:, 0], pts[:, 1])

            def fill_at(h):
                if h < 0:
                    return None
                o = int(tris.o[h])
                g = fill_of.get(o_group[o])
                return (g.get('fill_layer', 'GROUND'), group_fill(g, objs[o]['layer'])) if g else None
            by_fill = defaultdict(list)
            for face, h, h2, ins, sk in zip(faces, hit.tolist(), hit2.tolist(), inside.tolist(), skip.tolist()):
                if sk:
                    continue
                fl = fill_at(h)
                if ins and fill_at(h2) != fl:                # a boundary between two fills with no line on it
                    report['fills']['mixed'] += 1
                    report['fills'].setdefault('mixed_at_pt', []).append(paper((face.centroid.x, face.centroid.y), hx, hy, k))
                if fl and fl[1]:
                    by_fill[fl].append(face)
            for (lid, col), fs in sorted(by_fill.items()):
                u = shapely.union_all(fs, grid_size=g_)
                for poly in shapely.get_parts(u):
                    if poly.geom_type != 'Polygon' or poly.area <= 0:
                        continue
                    rings = [list(poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly.interiors]
                    d.polygon(lid, rings, fill=col, stroke='none')
                    report['fills']['filled'] += 1
    report['seconds']['fills'] = round(time.time() - T5, 2)

    # ---- the same check on what is drawn, after the line ends were met: none should remain. A line end run on under
    # reach closes a gap lint needs closed, whatever is behind it (a base line run on 0.4 pt across a solid's side face
    # to its cut, after the profile it ended on gave way to the cut, fuzz seed 2), and is left out
    T6 = time.time()
    chk = [e for e in range(len(edges)) if alive[e] and e_style[e] not in (None, RING) and e not in ran_on and not e_dash[first(e)]]
    occl, n_bad = [], 0
    if chk:                                            # a quarter, half and three quarters along each, in one query
        f_v = np.array([first(e) for e in chk], dtype=np.int64)
        A_v = np.array([nodes[edges[e][0]] for e in chk])
        B_v = np.array([nodes[edges[e][1]] for e in chk])
        Q_v = (A_v[:, None, :] + (B_v - A_v)[:, None, :] * np.array([0.25, 0.5, 0.75])[None, :, None]).reshape(-1, 2)
        f3 = np.repeat(f_v, 3)
        bad_v = covered(Q_v, depth_on(f3, Q_v), owner[f3]).reshape(-1, 3).all(1)
        n_bad = int(bad_v.sum())
        for j in np.nonzero(bad_v)[0][:20].tolist():
            sg = segs[e_seg[f_v[j]]]
            m = Q_v[3 * j + 1]
            occl.append(dict(layer=objs[int(owner[f_v[j]])]['layer'], source=sg['src'] + (' with %d' % sg['with'] if 'with' in sg else ''),
                             at_pt=paper(m, hx, hy, k), model=model_at(m[0], m[1], float(depth_on(int(f_v[j]), m[None])[0]))))
    report['verify'] = dict(edges=len(chk), occluded=n_bad, examples=occl)
    # the finished drawing against its own cut regions: a pass after the cuts' can put a line back inside one (a line
    # end run on into a closed gap, fuzz seed 32; three BEYOND lines across a part of the model's cut 0.35 pt wide). The
    # joints and the dashed hidden lines lie there on purpose
    skip = {('OUTLINE', f'{b} joints') for b, _, _ in joint_lines} | {st_[:2] for (_, c), st_ in style_of.items() if c == 'hidden'}
    pcs = inside_cut(d, skip)
    ic = dict(length_pt=round(sum((p[2] for p in pcs), 0.0), 3), pieces=len(pcs), longest=None)
    if pcs:                                            # the longest piece's depth from the line drawn there
        lid, sub, ln, m = pcs[0]
        ic['longest'] = dict(layer=f'{lid}/{sub}', length_pt=round(ln, 3), at_pt=paper(m, hx, hy, k))
        es = [e for e in range(len(edges)) if alive[e] and (e_style[e] not in (None, RING) and e_style[e][:2] == (lid, sub)
                                                             or e in overdrawn and line_style[first(e)][:2] == (lid, sub))]
        if es:
            dd, _ = seg_dist(np.repeat(np.array([m]), len(es), 0), np.array([nodes[edges[e][0]] for e in es]),
                             np.array([nodes[edges[e][1]] for e in es]))
            ic['longest']['model'] = model_at(m[0], m[1], float(depth_on(first(es[int(np.argmin(dd))]), np.array([m]))[0]))
    report['verify']['inside_cut'] = ic
    report['seconds']['verify'] = round(time.time() - T6, 2)

    # ---- the report
    clen = defaultdict(float)
    for e in range(n_e):
        if e_drawn[e] and alive[e]:
            clen[str(cls[e])] += float(L[e]) * k
    report['classes_pt'] = {c: round(v, 1) for c, v in sorted(clen.items())}
    report['sublayers'] = [dict(layer=lid, sublayer=sub, weight=d.subs[(lid, sub)], length_pt=round(lengths[(lid, sub)], 1))
                           for (lid, sub) in sorted(d.subs)]
    report['counts'] = dict(segments=len(segs), pieces=len(pieces), edges=n_e, nodes=len(node_of),
                            fixes=len(report['fixes']), issues=len(report['issues']))
    # ---- the model's faults: each issue's kind and the object's centre in the model, and the suspects, the places the
    # drawing met a line end short of or past its line, a cut that does not close, a cell it could not settle or a
    # stray, traced to a fault the export found on that place's own object ('traced') or on one within near_pt of it
    # ('near'); a place with neither is not listed
    seg_n = [len(s_['pts']) for s_ in scene['segments']]
    seg_o = np.repeat(np.array([s_['o'] for s_ in scene['segments']], dtype=np.int64), seg_n)
    seg_p = np.concatenate([np.zeros((0, 3))] + [np.asarray(s_['pts'], dtype=float).reshape(n_, -1)[:, :3]
                                                 for s_, n_ in zip(scene['segments'], seg_n) if n_])
    page_x, page_y = (seg_p[:, 0] * f + hx) * k, (2 * hy - (seg_p[:, 1] * f + hy)) * k
    box_o = {}
    for o in np.unique(seg_o).tolist():
        m_ = seg_o == o
        box_o[o] = (page_x[m_].min(), page_y[m_].min(), page_x[m_].max(), page_y[m_].max())
        if o not in centre:
            c_ = seg_p[m_].mean(0)
            centre[o] = model_at(c_[0] * f + hx, c_[1] * f + hy, c_[2])
    del seg_n, seg_o, seg_p, page_x, page_y
    faults = defaultdict(list)                         # object: [(kind, issue)]
    for i in report['issues']:
        i['kind'] = fault_kind(i['issue'])
        i['model'] = centre.get(i['object'])
        g_i = groups[o_group[i['object']]]
        if i['kind'] == 'open' and (g_i.get('ground') or g_i.get('layer') == 'TEXTURE'):
            continue                                   # a ground's sheets and a roof's tiles are open by design
        if i['kind']:
            faults[i['object']].append((i['kind'], i['issue']))
    npt = float(lint_t['near_pt'])

    def suspect(at, o, what, measure, action, model=None):
        causal = CAUSES[what]
        own_ = [(k_, x) for k_, x in faults.get(o, []) if k_ in causal] if o is not None else []
        if own_:
            who, conf = [(o, own_)], 'traced'
        else:
            who = [(o_, [(k_, x) for k_, x in fs if k_ in causal]) for o_, fs in faults.items()
                   if o_ in box_o and box_o[o_][0] - npt <= at[0] <= box_o[o_][2] + npt
                   and box_o[o_][1] - npt <= at[1] <= box_o[o_][3] + npt]
            who = [(o_, x) for o_, x in who if x][:3]
            conf = 'near'
        if not who:
            return
        report['suspects'].append(dict(
            at_pt=at, model=model or (centre.get(o) if o is not None else None), what=what,
            why='; '.join(f"{objs[o_]['layer']} {objs[o_]['ids'][0][:8] if objs[o_]['ids'] else ''}: {x[0][1]}"
                          + (' (a suspicion: alike by box and counts, the geometry not compared)' if x[0][0] == 'duplicate' else '')
                          for o_, x in who),
            ids=[g for o_, _ in who for g in objs[o_]['ids']], kinds=sorted({k_ for _, x in who for k_, _ in x}),
            confidence=conf, measure=measure, action=action))
    report['suspects'] = []
    for fx in report['fixes']:
        if fx['kind'] != 'run on to the frame':
            suspect(fx['at_pt'], fx.get('o'), 'near miss', fx['length_pt'], 'repaired', fx.get('model'))
    for oc in report['cuts']['open']:
        suspect(oc['ends_pt'][0], oc['object'], 'open cut', oc['length_pt'], 'left', oc.get('model'))
    for uc in report['cuts']['unresolved']:
        suspect(uc['at_pt'], None, 'unresolved cell', uc['area_pt2'], 'left')
    for lid, sub, P in stray_P:
        suspect(paper(P[len(P) // 2], hx, hy, k), None, 'stray', round(sum(math.dist(a_, b_) for a_, b_ in zip(P, P[1:])) * k, 3), 'removed')

    # ---- for --explain, on paper: every line a pass took out and why, the strays, the stretches the engine hid, and
    # what is drawn
    def on_paper(P):
        return [paper(p, hx, hy, k) for p in P]
    taken = []
    for e, why in fate.items():
        o = objs[int(owner[first(e)])]
        taken.append(dict(why=why, layer=o['layer'], id=o['ids'][0][:8] if o['ids'] else '', behind=named_o(fate_by.get(e)),
                          pts=on_paper([nodes[edges[e][0]], nodes[edges[e][1]]])))
    for lid, sub, P in stray_P:
        taken.append(dict(why='a stray: under min_len_pt and free at both ends', layer=f'{lid} {sub}', id='', pts=on_paper(P)))
    hid_ = [dict(layer=objs[s['o']]['layer'], behind=named_o(s.get('by')),
                 pts=on_paper([(x * f + hx, y * f + hy) for x, y, *_ in s['pts']]))
            for s in (faced_hid if by_faces else under)]
    drawn_ = [dict(sub=f'{e_style[e][0]} {e_style[e][1]}', layer=objs[int(owner[first(e)])]['layer'],
                   id=objs[int(owner[first(e)])]['ids'][0][:8] if objs[int(owner[first(e)])]['ids'] else '',
                   pts=on_paper([nodes[edges[e][0]], nodes[edges[e][1]]]))
              for e in range(len(edges)) if alive[e] and e_style[e] not in (None, RING)
              and (not show_hidden or e_style[e][0] != 'HIDDEN')]
    drawn_ += [dict(sub=f'HIDDEN {sub}', layer=sub.removesuffix(' hidden'), id='', pts=on_paper(P)) for sub, P in hidden_paths]
    report['_fates'] = dict(taken=taken, hidden=hid_, drawn=drawn_, suspects=report['suspects'])
    name_sublayers(d, bands_m, float(scene['unit_mm']))
    d.rhino_objects = [dict(ids=o['ids'], layer=o['layer']) for o in objs]
    d.rhino_classes = {}
    styles = sorted([(st[0], st[1], PLURAL[c]) for (_, c), st in style_of.items()], key=lambda x: -len(x[1]))
    for lid, sub in d.subs:
        d.rhino_classes[lid, sub] = ('cuts' if lid == 'CUT' else 'hidden' if lid == 'HIDDEN' else 'above' if lid == 'ABOVE' else
                                   'seams' if sub.endswith(' joints') else
                                   next((c for l, s, c in styles if l == lid and (sub == s or sub.startswith(s + ' '))), 'lines'))
    d.rhino_spans = defaultdict(list)
    for pc in PC:
        s = segs[int(pc[6])]
        if s.get('cut') is not None:
            body = gkey[o_group[s['o']]]
            d.rhino_spans['cut', lead.get(body, body)].append((tuple(pc[:2]), tuple(pc[3:5]), s['o']))
    if show_hidden:
        for gid, line, o in hidden_sources:
            P = list(line.coords)
            d.rhino_spans['hidden', gid].extend((a, b, o) for a, b in zip(P, P[1:]) if a != b)
    d.rhino_tolerance = 3 * g_
    for sub in report['sublayers']:
        sub['sublayer'] = '::'.join(p[0] for p in d.subpaths[sub['layer'], sub['sublayer']])
    report['seconds']['total'] = round(time.time() - T0, 2)
    return d, report


def inside_cut(d, skip=(), inset=0.01):
    """a drawing's stroked lines inside its CUT regions shrunk by inset pt, as its clip window shows them, but CUT's own
    and those on the (layer, sublayer)s in skip: [(layer, sublayer, length in pt, its middle in drawing units)] a piece
    each, longest first"""
    import shapely
    # a ring drawn where the model has it may cross itself by a grid step
    regs = [shapely.make_valid(shapely.Polygon(e['rings'][0], e['rings'][1:])) for e in d.ents['CUT'] if e['k'] == 'pg']
    if not regs:
        return []
    zone = shapely.union_all(regs).buffer(-inset / d.k)
    if d.clip:
        zone = shapely.intersection(zone, shapely.box(*d.clip))
    shapely.prepare(zone)
    out = []
    for lid, ents in d.ents.items():
        for e in ents:
            if lid == 'CUT' or e['k'] not in ('pl', 'pg') or e.get('stroke') == 'none' or (lid, e.get('sub')) in skip:
                continue
            for r in e['rings'] if e['k'] == 'pg' else [e['pts']]:
                line = shapely.LineString(list(r) + list(r[:1]) if e['k'] == 'pg' or e['closed'] else r)
                if not shapely.intersects(line, zone):
                    continue
                ins = [q for q in shapely.get_parts(shapely.intersection(line, zone)) if q.length > 0]
                for q in shapely.get_parts(shapely.line_merge(shapely.MultiLineString(ins))) if ins else []:
                    m = q.interpolate(0.5, normalized=True)
                    out.append((lid, e.get('sub'), q.length * d.k, (m.x, m.y)))
    return sorted(out, key=lambda x: -x[2])


def paper(p, hx, hy, k):
    """a drawing point as page points from the frame's top-left corner, y down, as lint reports and Redline marks"""
    return [round(float(p[0]) * k, 2), round((2 * hy - float(p[1])) * k, 2)]


FATE_INKS = ['#e6194b', '#f58231', '#3cb44b', '#911eb4', '#f032e6', '#9a6324', '#800000', '#808000', '#000075', '#46f0f0']


def write_fates(fates, path, W, H):
    """ID-fates.svg: what the engine hid in blue, each line a pass took out in its reason's colour, and the drawing's
    lines in grey over them, on the drawing's page, with a key"""
    from archkit.project import place
    why = sorted({g['why'] for g in fates['taken']})
    ink = {w: FATE_INKS[i % len(FATE_INKS)] for i, w in enumerate(why)}

    def pl(P, attrs):
        return f'<polyline points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in P)}" {attrs}/>'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}pt" height="{H:.2f}pt" viewBox="0 0 {W:.2f} {H:.2f}">',
           '<g id="hidden" fill="none" stroke="#3b8beb" stroke-width="0.5" stroke-opacity="0.6">']
    out += [pl(h['pts'], '') for h in fates['hidden']]
    out.append('</g>')
    for w in why:
        out.append(f'<g id="{w}" fill="none" stroke="{ink[w]}" stroke-width="0.6">')
        out += [pl(g['pts'], '') for g in fates['taken'] if g['why'] == w]
        out.append('</g>')
    out.append('<g id="drawn" fill="none" stroke="#9a9a9a" stroke-width="0.2">')
    out += [pl(x['pts'], '') for x in fates['drawn']]
    out.append('</g><g id="key" font-family="Helvetica" font-size="7">')
    for i, (w, c) in enumerate([('the engine hid it', '#3b8beb')] + [(w, ink[w]) for w in why]):
        out.append(f'<text x="8" y="{12 + 9 * i}" fill="{c}">{w}</text>')
    out.append('</g></svg>')
    place('\n'.join(out) + '\n', path)


def note_boxes(md):
    """the notes of a Redline markup (its redline.md): [dict(n, text, page, box)], box [x0, y0, x1, y1] round the
    note's marks on paper"""
    notes = []
    for line in md.splitlines():
        m = re.match(r'^(\d+)\. (.*)', line)
        if m:
            notes.append(dict(n=int(m.group(1)), text=m.group(2)))
            continue
        m = re.match(r'^\s+Where: (?:page (\d+), )?x (-?\d+(?:\.\d+)?)\u2013(-?\d+(?:\.\d+)?), '
                     r'y (-?\d+(?:\.\d+)?)\u2013(-?\d+(?:\.\d+)?)', line)
        if m and notes and 'box' not in notes[-1]:
            notes[-1]['page'] = int(m.group(1) or 1)
            notes[-1]['box'] = [float(v) for v in m.group(2, 4, 3, 5)]
    return notes


def notches(paths, touch=0.05):
    """the notch signature in a drawing's paths (lint.read_svg's): a path's last segment, 0.3 to 0.62 pt long, turning
    more than 45 degrees from the segment before it onto another line that runs beside that segment, within 6 degrees
    of it and 0.7 pt of its middle (a line giving way beside another and its end hooked back onto it): [page point of
    each]"""
    import shapely
    segs = [(a, b, i) for i, p in enumerate(paths) if p.stroke not in (None, 'none') for a, b in p.segs if a != b]
    if not segs:
        return []
    tree = shapely.STRtree([shapely.LineString([a, b]) for a, b, _ in segs])
    sin6 = math.sin(math.radians(6))
    out = []
    for i, p in enumerate(paths):
        if p.closed or p.stroke in (None, 'none') or len(p.segs) < 2:
            continue
        for end in (0, -1):
            (a, b), (c, d) = (p.segs[-1], p.segs[-2]) if end == -1 else ((p.segs[0][1], p.segs[0][0]), (p.segs[1][1], p.segs[1][0]))
            ln = math.dist(a, b)
            if not 0.3 <= ln <= 0.62:
                continue
            u = (d[0] - c[0], d[1] - c[1])            # the segment before, toward a
            v = (b[0] - a[0], b[1] - a[1])
            nu, nv = math.hypot(*u), math.hypot(*v)
            if not nu or (u[0] * v[0] + u[1] * v[1]) / (nu * nv) > math.cos(math.radians(45)):
                continue
            mid = shapely.Point((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
            par = lambda j: abs(u[0] * (segs[j][1][1] - segs[j][0][1]) - u[1] * (segs[j][1][0] - segs[j][0][0])) <= \
                sin6 * nu * math.dist(segs[j][0], segs[j][1])
            hit = {segs[j][2] for j in tree.query(shapely.Point(b), predicate='dwithin', distance=touch).tolist() if par(j)} - {i}
            for j in tree.query(mid, predicate='dwithin', distance=0.7).tolist():
                (e, f_, k_) = segs[j]
                w = (f_[0] - e[0], f_[1] - e[1])
                nw = math.hypot(*w)
                if k_ in hit and nw and abs(u[0] * w[1] - u[1] * w[0]) <= sin6 * nu * nw:
                    out.append(b)
                    break
    return out


def kinks(paths, touch=0.05):
    """the join signature in a drawing's paths (lint.read_svg's): a path's last segment, 0.1 to 3 pt long, turning 8 to
    45 degrees from the segment before it, at least 0.2 pt long, and ending on another line within 6 degrees of that
    segment (a lesser line run onto a heavier one beside it by a straight join, which reads as a kink): [page point of
    each]"""
    import shapely
    segs = [(a, b, i) for i, p in enumerate(paths) if p.stroke not in (None, 'none') for a, b in p.segs if a != b]
    if not segs:
        return []
    tree = shapely.STRtree([shapely.LineString([a, b]) for a, b, _ in segs])
    sin6 = math.sin(math.radians(6))
    out = []
    for i, p in enumerate(paths):
        if p.closed or p.stroke in (None, 'none') or len(p.segs) < 2:
            continue
        for end in (0, -1):
            (a, b), (c, d) = (p.segs[-1], p.segs[-2]) if end == -1 else ((p.segs[0][1], p.segs[0][0]), (p.segs[1][1], p.segs[1][0]))
            u = (d[0] - c[0], d[1] - c[1])            # the segment before, toward a
            v = (b[0] - a[0], b[1] - a[1])
            nu, nv = math.hypot(*u), math.hypot(*v)
            if not 0.1 <= nv <= 3.0 or nu < 0.2:
                continue
            turn = math.degrees(math.acos(max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (nu * nv)))))
            if not 8.0 <= turn <= 45.0:
                continue
            if any(abs(u[0] * (segs[j][1][1] - segs[j][0][1]) - u[1] * (segs[j][1][0] - segs[j][0][0]))
                   <= sin6 * nu * math.dist(segs[j][0], segs[j][1]) and segs[j][2] != i
                   for j in tree.query(shapely.Point(b), predicate='dwithin', distance=touch).tolist()):
                out.append(b)
    return out


def open_ends(paths, touch=0.05, frame=None):
    """a drawing's line ends that meet nothing (lint.read_svg's paths): an open path's end farther than touch from every
    other stroked path, from its own but the segments next to it and from the frame (w, h) if given, an outline left
    open: [page point of each]"""
    import shapely
    segs = [(a, b, i, n) for i, p in enumerate(paths) if p.stroke not in (None, 'none') for n, (a, b) in enumerate(p.segs)]
    if not segs:
        return []
    tree = shapely.STRtree([shapely.LineString([a, b]) if a != b else shapely.Point(a) for a, b, _, _ in segs])
    out = []
    for i, p in enumerate(paths):
        if p.closed or p.stroke in (None, 'none') or not p.segs:
            continue
        last = len(p.segs) - 1
        for q, n_end in ((p.segs[0][0], 0), (p.segs[-1][1], last)):
            if frame and min(q[0], q[1], frame[0] - q[0], frame[1] - q[1]) <= touch:
                continue
            if not any(segs[j][2] != i or abs(segs[j][3] - n_end) > 2
                       for j in tree.query(shapely.Point(q), predicate='dwithin', distance=touch).tolist()):
                out.append(q)
    return out


def check_notes(svg, checks):
    """a drawing against checks written from review notes, each with its note and its geometry on paper (pt,
    y down), as [(check, passed, measure, detail)]:
      line    a line drawn along path, within tol_pt (1) of it and 20 degrees of its direction, over cover (0.8) of
              its length; min_w and max_w (pt) bound the width of what counts, layers the layers
      clear   at most max_pt (0.5) of line inside area (a polygon) or box: on the layers in layers, else on any but
              those in allow; min_w and max_w (pt) bound the width of what counts
      drawn   at least min_pt of line inside area or box, counted as clear counts it: lines a note says are missing
      single  one line, no more, across path within tol_pt (2) either side, at cover (0.9) of its points
      lines   n lines across path likewise, at cover (0.7) of its points: two lines converging, both drawn
      gap     along path, the longest stretch with no line within tol_pt (0.5) and 20 degrees of it, at most max_pt
              (0.5): an outline that runs on unbroken; min_w, max_w and layers as for line
      regions n cut regions, at most, meeting area or box: CUT's closed paths at least min_w wide, a hole in one not
              counted (a poché that runs on, not parts of it), and at least one
      notches at most n (0) notch signatures (notches) inside area or box
      kinks   at most n (0) join signatures (kinks) inside area or box
      ends    at most n (0) line ends that meet nothing (open_ends) inside area or box: outlines left open
      model   at most max_pt (0.05) of line inside area or box further than tol_pt (0.075, 1.5 grid steps) from every
              line of the export (its scene.json and request beside the drawing): a join or bend the model does not
              have; at tol_pt 0.01, a curve drawn in the grid's steps
      kept    at most max_pt (0.3) of the export's visible lines inside area or box dropped with no reason
              (the report's model.unexplained_at, beside the drawing): a piece dropped where the model has it
      look    none: the note is looked at, on the sheet notes_sheet makes
    A check with mode (kept or simplified) is about how doubles are drawn and applies only to a drawing whose report
    says its doubles are so (an older report, without it, counts as simplified); else it is not tested"""
    import shapely
    from archkit.lint import read_svg
    paths_ = read_svg(svg)['paths']
    vb_ = re.search(r'<svg\b[^>]*\bviewBox="([^"]+)"', Path(svg).read_text(encoding='utf-8'))
    frame = tuple(float(v) for v in vb_.group(1).split()[2:4]) if vb_ else None
    segs = [(a, b, p.width or 0.0, p.layer or '') for p in paths_
            if p.stroke not in (None, 'none') and (p.width or 0.0) > 0 for a, b in p.segs]
    tree = shapely.STRtree([shapely.LineString([a, b]) for a, b, _, _ in segs])
    sin20 = math.sin(math.radians(20))

    def along(path, step):
        """points every step along path, each with the path's unit direction there"""
        out = []
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            L = math.dist((x0, y0), (x1, y1))
            if L == 0:
                continue
            u = ((x1 - x0) / L, (y1 - y0) / L)
            n = max(1, int(L / step))
            out += [((x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (i + 0.5) / n), u) for i in range(n)]
        return out

    def parallel(i, u):
        (ax, ay), (bx, by) = segs[i][0], segs[i][1]
        L = math.dist((ax, ay), (bx, by))
        return L > 0 and abs(u[0] * (by - ay) - u[1] * (bx - ax)) / L <= sin20

    rp_ = Path(svg).with_name(Path(svg).stem + '-report.json')
    mode_ = json.loads(rp_.read_text(encoding='utf-8')).get('doubles', {}).get('mode', 'simplified') if rp_.exists() else None
    out = []
    for c in checks:
        kind = c['kind']
        if c.get('mode') and mode_ and c['mode'] != mode_:
            out.append((c, None, None, f'for a drawing with its doubles {c["mode"]} only'))
            continue
        if kind == 'line':
            tol, lo, hi = float(c.get('tol_pt', 1.0)), float(c.get('min_w', 0.0)), float(c.get('max_w', math.inf))
            pts = along(c['path'], 0.1)
            hit, widths = 0, []
            for q, u in pts:
                P = shapely.Point(q)
                ok = [i for i in tree.query(P, predicate='dwithin', distance=tol).tolist() if parallel(i, u)
                      and (not c.get('layers') or segs[i][3] in c['layers'])]
                good = [i for i in ok if lo <= segs[i][2] <= hi]
                hit += bool(good)
                widths += [segs[i][2] for i in ok]
            share = hit / max(len(pts), 1)
            w_ = f', widths {min(widths):.2f} to {max(widths):.2f} pt' if widths else ''
            out.append((c, share >= float(c.get('cover', 0.8)), round(share, 2), f'{share:.0%} covered{w_}'))
        elif kind in ('clear', 'drawn'):
            area = shapely.box(*c['box']) if 'box' in c else shapely.Polygon(c['area'])
            lo, hi = float(c.get('min_w', 0.0)), float(c.get('max_w', math.inf))
            inside = defaultdict(float)
            for i in tree.query(area, predicate='intersects').tolist():
                if not lo <= segs[i][2] <= hi:
                    continue
                if segs[i][3] in c['layers'] if c.get('layers') else segs[i][3] not in c.get('allow', []):
                    inside[segs[i][3]] += shapely.LineString(segs[i][:2]).intersection(area).length
            tot = sum(inside.values())
            top = ', '.join(f'{k_} {v:.1f}' for k_, v in sorted(inside.items(), key=lambda kv: -kv[1])[:3])
            ok_ = tot >= float(c['min_pt']) if kind == 'drawn' else tot <= float(c.get('max_pt', 0.5))
            out.append((c, ok_, round(tot, 2), f'{tot:.1f} pt inside' + (f' ({top})' if top else '')))
        elif kind in ('single', 'lines'):
            tol, want = float(c.get('tol_pt', 2.0)), 1 if kind == 'single' else int(c['n'])
            pts = along(c['path'], 0.5)
            one, counts = 0, []
            for (x, y), u in pts:
                probe = shapely.LineString([(x + u[1] * tol, y - u[0] * tol), (x - u[1] * tol, y + u[0] * tol)])
                at = sorted(round(float(shapely.line_locate_point(probe, shapely.centroid(
                    probe.intersection(shapely.LineString(segs[i][:2]))))), 2)
                    for i in tree.query(probe, predicate='intersects').tolist() if parallel(i, u))
                n = len([a for j, a in enumerate(at) if j == 0 or a - at[j - 1] > 0.05])
                one += n == want
                counts.append(n)
            share = one / max(len(pts), 1)
            out.append((c, share >= float(c.get('cover', 0.9 if kind == 'single' else 0.7)), round(share, 2),
                        f'{want} line{"s" if want > 1 else ""} at {share:.0%} of points, '
                        f'{min(counts, default=0)} to {max(counts, default=0)}'))
        elif kind == 'gap':
            tol, lo, hi = float(c.get('tol_pt', 0.5)), float(c.get('min_w', 0.0)), float(c.get('max_w', math.inf))
            run, worst = 0.0, 0.0
            for q, u in along(c['path'], 0.1):
                P = shapely.Point(q)
                hit = any(parallel(i, u) and lo <= segs[i][2] <= hi and (not c.get('layers') or segs[i][3] in c['layers'])
                          for i in tree.query(P, predicate='dwithin', distance=tol).tolist())
                run = 0.0 if hit else run + 0.1
                worst = max(worst, run)
            out.append((c, worst <= float(c.get('max_pt', 0.5)), round(worst, 2), f'longest gap {worst:.1f} pt'))
        elif kind == 'regions':
            area = shapely.box(*c['box']) if 'box' in c else shapely.Polygon(c['area'])
            rings_ = [shapely.Polygon([p.segs[0][0]] + [b for _, b in p.segs]) for p in paths_
                      if p.layer == 'CUT' and p.closed and len(p.segs) > 2 and (p.width or 0.0) >= float(c.get('min_w', 0.0))]
            rings_ = [r if r.is_valid else r.buffer(0) for r in rings_]
            n_ = sum(1 for r in rings_ if r.intersects(area)   # a ring inside an odd number of others is a hole
                     and sum(1 for x in rings_ if x.area > r.area and x.contains(r.representative_point())) % 2 == 0)
            out.append((c, 1 <= n_ <= int(c.get('n', 1)), n_, f'{n_} cut region{"s" if n_ != 1 else ""} there'))
        elif kind in ('notches', 'kinks', 'ends'):
            area = shapely.box(*c['box']) if 'box' in c else shapely.Polygon(c['area'])
            found = notches(paths_) if kind == 'notches' else kinks(paths_) if kind == 'kinks' else open_ends(paths_, frame=frame)
            n_ = sum(1 for q in found if area.contains(shapely.Point(q)))
            what = {'notches': ('notch', 'notches'), 'kinks': ('kink', 'kinks'), 'ends': ('open end', 'open ends')}[kind]
            out.append((c, n_ <= int(c.get('n', 0)), n_, f'{n_} {what[n_ != 1]} there'))
        elif kind == 'kept':
            area = shapely.box(*c['box']) if 'box' in c else shapely.Polygon(c['area'])
            rp = Path(svg).with_name(Path(svg).stem + '-report.json')
            at = json.loads(rp.read_text(encoding='utf-8'))['model'].get('unexplained_at', []) if rp.exists() else []
            off = 0.25 * sum(1 for q in at if area.contains(shapely.Point(q)))
            out.append((c, off <= float(c.get('max_pt', 0.3)), round(off, 2), f'{off:.2f} pt of the model\'s visible lines dropped with no reason'))
        elif kind == 'model':
            area = shapely.box(*c['box']) if 'box' in c else shapely.Polygon(c['area'])
            ex = model_lines(svg)
            tol = float(c.get('tol_pt', 0.075))
            pool, against, what = [(a, b) for a, b, _, _ in segs], ex['all'], 'drawn off the model'
            off = 0.0
            if pool and against:
                tr_ = shapely.STRtree([shapely.LineString(x) for x in against])
                for a, b in pool:
                    ls = shapely.LineString([a, b]).intersection(area)
                    if ls.is_empty or ls.length == 0:
                        continue
                    for part in shapely.get_parts(ls):
                        n = max(1, int(math.ceil(part.length / 0.05)))
                        Q = [part.interpolate((i + 0.5) / n, normalized=True) for i in range(n)]
                        hit = set(tr_.query(Q, predicate='dwithin', distance=tol)[0].tolist())
                        off += part.length * (n - len(hit)) / n
            elif pool:
                off = sum(shapely.LineString([a, b]).intersection(area).length for a, b in pool)
            out.append((c, off <= float(c.get('max_pt', 0.05)), round(off, 2), f'{off:.2f} pt {what}'))
        elif kind == 'look':
            out.append((c, None, None, 'to look at'))
        else:
            raise SystemExit(f'hidden-lines: a check of kind {kind!r}; the kinds are line, clear, drawn, single, lines, gap, regions, notches, '
                             f'kinks, ends, model, kept and look')
    return out


def model_lines(svg):
    """the export beside a drawing (its folder's scene.json, and request.json or the first request*.json there) on
    paper, pt from the top-left, y down: every line and ring piece ('all') and the pieces of Rhino's visible lines, cuts
    aside ('visible'), as ((x, y), (x, y)) pairs"""
    from archkit.draw import Drawing
    folder = Path(svg).parent
    req_p = folder / 'request.json'
    if not req_p.exists():
        req_p = next(iter(sorted(q for q in folder.glob('request*.json') if not q.name.startswith('.'))), None)
    if req_p is None or not (folder / 'scene.json').exists():
        raise SystemExit(f'hidden-lines: a check of kind model or kept reads the export beside {Path(svg).name}: no scene.json '
                         f'and request there')
    scene = json.loads((folder / 'scene.json').read_text(encoding='utf-8'))
    req = json.loads(req_p.read_text(encoding='utf-8'))
    units = UNITS.get(round(float(scene['unit_mm']), 6))
    k = Drawing(float(req['scale']), units=units).k
    hx, hy = float(req['frame']['w_pt']) / 2 / k, float(req['frame']['h_pt']) / 2 / k
    f = float(scene['view']['true_factor'])
    pp = lambda q: ((q[0] * f + hx) * k, (hy - q[1] * f) * k)
    every, vis = [], []
    for sg in scene['segments']:
        for a, b in zip(sg['pts'], sg['pts'][1:]):
            if a[:2] != b[:2]:
                every.append((pp(a), pp(b)))
                if sg.get('vis') is None and sg.get('cut') is None and sg.get('src') not in ('mesh', 'ring'):
                    vis.append((pp(a), pp(b)))
    for r in scene.get('rings', []):
        every += [(pp(a), pp(b)) for a, b in zip(r['pts'], r['pts'][1:] + r['pts'][:1]) if a[:2] != b[:2]]
    return dict(all=every, visible=vis)


def notes_sheet(svg, notes, results, marks, folder, long=1200):
    """for each note with a box: its mark (marks/note-N.png, Redline's crop) beside the drawing at the same window
    (Redline's: the box padded by 0.35 of its longer side, or 0.04 of the page's), and its checks' results under them,
    as folder/note-N.png"""
    import io, tempfile
    from PIL import Image, ImageDraw
    from archkit.project import place
    from archkit.render import render
    text = Path(svg).read_text(encoding='utf-8')
    root = re.search(r'<svg\b[^>]*>', text)
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', root.group(0)).group(1).split()]
    made = []
    with tempfile.TemporaryDirectory() as td:
        for nt in notes:
            if 'box' not in nt:
                continue
            x0, y0, x1, y1 = nt['box']
            pad = max(0.35 * max(x1 - x0, y1 - y0), 0.04 * max(vb[2], vb[3]))
            x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
            s = min(long / max(x1 - x0, y1 - y0), 8)
            tag = re.sub(r'\s(width|height|viewBox)="[^"]*"', '', root.group(0))
            tag = tag[:-1] + f' width="{x1 - x0:.3f}pt" height="{y1 - y0:.3f}pt" viewBox="{x0:.3f} {y0:.3f} {x1 - x0:.3f} {y1 - y0:.3f}">'
            crop = Path(td) / f'note-{nt["n"]}.svg'
            crop.write_text(text[:root.start()] + tag + text[root.end():], encoding='utf-8')
            png, _ = render(crop, Path(td) / f'note-{nt["n"]}.png', dpi=72 * s)
            rgba = Image.open(png).convert('RGBA')
            right = Image.new('RGB', rgba.size, 'white')
            right.paste(rgba, mask=rgba.getchannel('A'))
            mk = Path(marks) / f'note-{nt["n"]}.png'
            left = Image.open(mk).convert('RGB') if mk.is_file() else Image.new('RGB', right.size, 'white')
            lines_ = [f'note {nt["n"]}: {nt["text"][:110]}'] + [
                f'  {c["kind"]}: {"look" if ok is None else "pass" if ok else "FAIL"}, {why}'
                for c, ok, _, why in results if c.get('note') == nt['n']]
            h = max(left.height, right.height)
            sheet = Image.new('RGB', (left.width + right.width + 12, h + 16 * len(lines_) + 12), 'white')
            sheet.paste(left, (0, 0))
            sheet.paste(right, (left.width + 12, 0))
            dr = ImageDraw.Draw(sheet)
            dr.line([(left.width + 6, 0), (left.width + 6, h)], fill='grey', width=1)
            for j, ln in enumerate(lines_):
                dr.text((6, h + 6 + 16 * j), ln, fill='black')
            buf = io.BytesIO()
            sheet.save(buf, 'PNG')
            made.append(place(buf.getvalue(), Path(folder) / f'note-{nt["n"]}.png'))
    return made


def explain_notes(fates, md, margin=3.0):
    """for each note of a Redline markup (redline.md): under its marks, widened by margin pt, the length of what each
    pass took out and why (with the layers), of what the engine hid, and of what is drawn, by sublayer; and each suspect
    there, a place the drawing met that a fault of the model's likely caused"""
    import shapely
    notes, out = note_boxes(md), []

    def lines(items):
        return [(x, shapely.LineString(x['pts'])) for x in items if len(x['pts']) > 1]
    taken, hidden, drawn = lines(fates['taken']), lines(fates['hidden']), lines(fates['drawn'])
    for nt in notes:
        if 'box' not in nt:
            continue
        x0, y0, x1, y1 = nt['box']
        b = shapely.box(x0 - margin, y0 - margin, x1 + margin, y1 + margin)

        def inside(items, key):
            tot = defaultdict(float)
            who = defaultdict(set)
            for x, ls in items:
                ln = ls.intersection(b).length
                if ln > 0:
                    tot[x[key]] += ln
                    if 'layer' in x:
                        who[x[key]].add(x['layer'] + (' ' + x['id'] if x.get('id') else '')
                                        + (' behind ' + x['behind'] if x.get('behind') else ''))
            return sorted(tot.items(), key=lambda kv: -kv[1]), who
        t_, tw = inside(taken, 'why')
        h_, hw = inside([(dict(x, k='hid'), ls) for x, ls in hidden], 'k')
        d_, dw = inside(drawn, 'sub')
        page = f'page {nt["page"]}, ' if nt['page'] != 1 else ''
        out.append(f'note {nt["n"]} ({page}x {x0:g}-{x1:g}, y {y0:g}-{y1:g}): {nt["text"][:90]}')
        out.append('  taken out: ' + ('; '.join(f'{w} {v:.1f} pt ({", ".join(sorted(tw[w])[:3])})' for w, v in t_) or 'nothing'))
        out.append('  the engine hid: ' + ('; '.join(f'{v:.1f} pt ({", ".join(sorted(hw[w])[:3])})' for w, v in h_) or 'nothing'))
        out.append('  drawn: ' + ('; '.join(f'{w} {v:.1f} pt' + (f' ({", ".join(sorted(dw[w])[:3])})' if dw[w] else '')
                                           for w, v in d_[:6]) or 'nothing'))
        for su in fates.get('suspects', []):
            if b.distance(shapely.Point(su['at_pt'])) == 0:
                out.append(f'  the model ({su["confidence"]}): {su["what"]} {su["measure"]}, {su["action"]}: {su["why"]}')
    return '\n'.join(out)


def name_sublayers(d, bands_m, unit_mm):
    """display paths and range-free ids, assigned after every geometry and weight decision"""
    names, identities = {}, {}
    labels = ['near'] + ([('middle' if len(bands_m) == 2 else f'middle {i}')
                         for i in range(1, len(bands_m))]) + ['far']
    for lid, sub in d.subs:
        base, distance = sub, None
        for i in range(len(bands_m) + 1) if bands_m else []:
            tail = (f'under {bands_m[0]:g} m' if i == 0 else f'past {bands_m[-1]:g} m' if i == len(bands_m)
                    else f'{bands_m[i - 1]:g}-{bands_m[i]:g} m')
            if sub.endswith(' ' + tail):
                base = sub[:-len(tail) - 1]
                fmt = lambda v: f'{v * 1000 / unit_mm:.3g}'
                span = (f'under {fmt(bands_m[0])}' if i == 0 else f'past {fmt(bands_m[-1])}' if i == len(bands_m)
                        else f'{fmt(bands_m[i - 1])}–{fmt(bands_m[i])}')
                distance = (f'{labels[i]} ({span} {d.units})', labels[i])
                break
        identities[lid, sub] = (base, distance[1] if distance else '')
        for singular, plural in PLURAL.items():
            if base == singular + ' ' + plural or base == plural + ' ' + plural:
                base = base.split()[0]
                break
        names[lid, sub] = [(base, base)] + ([distance] if distance else [])
    used = set()
    for key, path in names.items():
        raw = key[0] + '-' + '-'.join(part[1] for part in path)
        sid = ''.join(c if c.isalnum() or c in '_-' else '-' for c in raw)
        if sid in used:
            import hashlib
            sid += '-' + hashlib.sha256(repr(identities[key]).encode()).hexdigest()[:10]
            while sid in used:
                sid += '-leaf'
        used.add(sid)
        d.subids[key] = sid
    d.subpaths = names


def source_runs(points, closed, sources):
    """one path per consecutive source, preserving a closed path only when it has one source"""
    pts = list(points) + (list(points[:1]) if closed else [])
    runs = []
    for a, b, o in zip(pts, pts[1:], sources):
        if runs and runs[-1]['source'] == o:
            runs[-1]['pts'].append(b)
        else:
            runs.append(dict(pts=[a, b], closed=False, source=o))
    if closed and len(runs) > 1 and runs[0]['source'] == runs[-1]['source']:
        runs[0]['pts'] = runs.pop()['pts'][:-1] + runs[0]['pts']
    if closed and len(runs) == 1:
        runs[0]['closed'] = True
        runs[0]['pts'].pop()
    return runs


def source_parts(points, closed, spans, tree, tolerance):
    """cut or hidden paths split at their source spans; repaired gaps take the nearest span's owner"""
    import numpy as np
    import shapely
    pts = list(points) + (list(points[:1]) if closed else [])
    out, sources = [pts[0]], []
    for a, b in zip(pts, pts[1:]):
        a, b = np.asarray(a), np.asarray(b)
        ab = b - a
        length2 = float(ab @ ab)
        if not length2:
            continue
        line = shapely.LineString([a, b])
        candidates = []
        for j in tree.query(line, predicate='dwithin', distance=tolerance).tolist():
            c, e, o = spans[j]
            cd = np.subtract(e, c)
            if abs(float(ab[0] * cd[1] - ab[1] * cd[0])) > 0.35 * math.sqrt(length2 * float(cd @ cd)):
                continue
            lo, hi = sorted((float((np.asarray(c) - a) @ ab / length2), float((np.asarray(e) - a) @ ab / length2)))
            lo, hi = max(0., lo), min(1., hi)
            if hi > lo and max(tree.geometries[j].distance(shapely.Point(a + t * ab)) for t in (lo, hi)) <= tolerance:
                candidates.append((lo, hi, j, o))
        stops = sorted({0., 1.} | {t for lo, hi, _, _ in candidates for t in (lo, hi)})
        for lo, hi in zip(stops, stops[1:]):
            mid = (lo + hi) / 2
            p = shapely.Point(a + mid * ab)
            pool = [(j, o) for l, h, j, o in candidates if l <= mid <= h]
            if pool:
                j, o = min(pool, key=lambda jo: (round(tree.geometries[jo[0]].distance(p), 9), jo[1], jo[0]))
            else:
                js = tree.query_nearest(p).tolist()
                j = min(js, key=lambda j: (spans[j][2], j))
                o = spans[j][2]
            out.append(tuple(a + hi * ab))
            sources.append(o)
    return source_runs(out[:-1] if closed else out, closed, sources)


def for_rhino(d):
    """the drawing as rhino/hidden_lines.py adds it to the model: each layer that holds anything, with its ink, its dash
    (its name, and its lengths in model units) and its sublayers, each with its print width in mm and its lines and fills
    in model units, the frame's lower left corner at the origin; a sublayer named '' is the layer itself. objects holds
    each scene object's ids and full layer path; each line's source indexes it. Only this payload splits paths by source."""
    import shapely
    xy = lambda r: [[round(float(x), 6), round(float(y), 6)] for x, y in r]
    layers = []
    trees = {}
    split_paths = 0
    for L in d.layers:
        lid = L['id']
        if not d.ents[lid]:
            continue
        s = d.look(lid)
        subs = {}
        for e in d.ents[lid]:
            sub = e.get('sub') if (lid, e.get('sub')) in d.subs else None
            if (sub or '') not in subs:
                w = d.t.weight(d.subs[(lid, sub)], d.scale) if sub else s['weight']
                name = '::'.join(p[0] for p in d.subpaths.get((lid, sub), [(sub or '', '')]))
                subs[sub or ''] = dict(name=name, weight_mm=round(w / PT_PER_MM, 3) if w else None,
                                      kind=d.rhino_classes.get((lid, sub), 'lines'), lines=[], fills=[])
            out = subs[sub or '']
            rings = e['rings'] if e['k'] == 'pg' else [e['pts']]
            if e.get('stroke') == 'none':
                out['fills'].append(dict(rings=[xy(r) for r in rings], ink=d.t.hex(e.get('fill'))))
            else:
                for r in rings:
                    closed = e['k'] == 'pg' or e['closed']
                    if id(e) in d.rhino_lines:
                        lines = source_runs(r, closed, d.rhino_lines[id(e)])
                    else:
                        tail = ' cuts thin' if sub.endswith(' cuts thin') else ' cuts' if lid == 'CUT' else ' joints' if sub.endswith(' joints') else ' hidden'
                        key = ('hidden' if lid == 'HIDDEN' else 'cut', sub.removesuffix(tail))
                        spans = d.rhino_spans[key]
                        if key not in trees:
                            trees[key] = shapely.STRtree([shapely.LineString([a, b]) for a, b, _ in spans])
                        lines = source_parts(r, closed, spans, trees[key], d.rhino_tolerance)
                    split_paths += len(lines) > 1
                    out['lines'].extend(dict(ln, pts=xy(ln['pts'])) for ln in lines)
        layers.append(dict(id=lid, ink=d.t.hex(s['stroke'] or s['fill'] or 'K100'), print=s['print'], dash=s['dash_name'],
                           dash_model=[round(d.pt(v), 6) for v in s['dash']] if s['dash'] else None,
                           subs=list(subs.values())))
    return dict(units=d.units, scale=d.scale, layers=layers, objects=d.rhino_objects, split_paths=split_paths)


def run_checks(chk, svg=None):
    """the checks of a checks file (docs/commands.md, hidden-lines --check) against svg, or the drawing it names:
    prints and writes ID-check.txt, and with its notes' boxes ID-notes/note-N.png"""
    from archkit.project import place
    spec = json.loads(chk.read_text(encoding='utf-8'))
    svg = Path(svg) if svg else (chk.parent / spec['svg']).resolve()
    res = check_notes(svg, spec['checks'])
    tested = [ok for _, ok, _, _ in res if ok is not None]
    out = [f'{svg.name}: {sum(tested)} of {len(tested)} checks pass, {len(res) - len(tested)} notes to look at']
    out += [f'  note {c.get("note", "-")} {c["kind"]}: {"look" if ok is None else "pass" if ok else "FAIL"}, {why}'
            + (f' ({c["why"]})' if c.get('why') else '') for c, ok, _, why in res]
    place('\n'.join(out) + '\n', svg.with_name(svg.stem + '-check.txt'))
    print('\n'.join(out))
    if spec.get('notes'):
        made = notes_sheet(svg, spec['notes'], res, (chk.parent / spec.get('marks', '.')).resolve(),
                           svg.with_name(svg.stem + '-notes'))
        print(f'  wrote {svg.stem}-check.txt and {len(made)} notes, each its mark beside the drawing, in {svg.stem}-notes/')
    return 0 if all(tested) else 1


def main(argv):
    if argv and argv[0] == '--check' and len(argv) > 1:
        return run_checks(Path(argv[1]).absolute())
    if not argv or argv[0].startswith('-'):
        print(__doc__)
        return 2
    from archkit.project import place
    req_path = Path(argv[0]).absolute()
    check = None
    if '--check' in argv:
        i = argv.index('--check')
        if i + 1 >= len(argv) or not Path(argv[i + 1]).is_file():
            raise SystemExit('hidden-lines: --check needs the path of a checks file')
        check = Path(argv[i + 1]).absolute()
    rhino = None
    if '--rhino' in argv:
        i = argv.index('--rhino')
        if i + 1 >= len(argv):
            raise SystemExit('hidden-lines: --rhino needs the path to write the drawing to')
        rhino = Path(argv[i + 1]).absolute()
    explain = None
    if '--explain' in argv:
        i = argv.index('--explain')
        if i + 1 >= len(argv) or not Path(argv[i + 1]).is_file():
            raise SystemExit('hidden-lines: --explain needs the path of a Redline markup\'s redline.md')
        explain = Path(argv[i + 1]).absolute()
    req = json.loads(req_path.read_text(encoding='utf-8'))
    d, report = build(req_path, req)
    fates = report.pop('_fates')
    folder = req_path.parent / req.get('out', 'hidden-lines')
    name = req.get('id') or req_path.stem
    W, H = float(req['frame']['w_pt']), float(req['frame']['h_pt'])
    d.to_svg(folder / f'{name}.svg', canvas=(W, H), origin=(0.0, H))
    d.to_dxf(folder / f'{name}.dxf')
    d.to_ai(folder / f'{name}.ai', canvas=(W, H), origin=(0.0, H))
    place(json.dumps(report, indent=1, ensure_ascii=False) + '\n', folder / f'{name}-report.json')
    if rhino:
        place(json.dumps(for_rhino(d), ensure_ascii=False), rhino)
    c = report['counts']
    print(f'{name}: {c["segments"]} segments, {c["edges"]} edges; ' +
          ', '.join(f'{k_} {v:.0f} pt' for k_, v in report['classes_pt'].items()))
    print(f'  {c["fixes"]} line ends met ({", ".join(sorted(set(x["kind"] for x in report["fixes"]))) or "none"}), '
          f'{report["strays"]["count"]} strays left out ({report["strays"]["length_pt"]} pt), '
          f'{report["fills"]["filled"]} fills from {report["fills"]["faces"]} faces ({report["fills"]["mixed"]} seeing two fills); '
          f'{c["issues"]} model issues')
    db = report.get('doubles')
    if db and db['count']:
        print(f'  {db["count"]} doubles gave way to a heavier line beside them ({db["length_pt"]} pt), first at '
              f'{db["examples"][0]["at_pt"]} pt ({db["examples"][0]["layer"]} beside {db["examples"][0]["beside"]})')
    un = report.get('under')
    if un and un['kept']:
        print(f'  {un["length_pt"]} pt in {un["kept"]} stretches the engine hid kept: nothing but the surface they lie on is in '
              f'front of them')
    hm = report.get('hidden_by_meshes')
    if hm and hm['count']:
        print(f'  {hm["length_pt"]} pt of {hm["count"]} lines the engine drew taken out: another object stands over '
              f'{hm["lim_pt"]} pt in front of them, first at {hm["examples"][0]["at_pt"]} pt ({hm["examples"][0]["layer"]})')
    v = report.get('verify')
    if v and v['occluded']:
        print(f'  engine check: {v["occluded"]} of {v["edges"]} edges drawn with another object over {hm["lim_pt"]} pt in front '
              f'of them, first at {v["examples"][0]["at_pt"]} pt ({v["examples"][0]["layer"]})')
    cu = report['cuts']
    ic = report['verify']['inside_cut']
    if cu['objects']:
        print(f'  cuts: {cu["regions"]} closed regions from {cu["objects"]} objects; {len(cu["open"])} that do not close; '
              f'{ic["length_pt"]:g} pt of line drawn inside them'
              + ''.join(f'; {o["body"]} overlaps an earlier group\'s cut by {o["area_pt2"]} pt², clipped' for o in cu['overlaps']))
        if ic['longest']:
            lg = ic['longest']
            print(f'  cut check: {ic["length_pt"]:g} pt of line drawn inside the cuts in {ic["pieces"]} pieces, the longest '
                  f'{lg["length_pt"]:g} pt on {lg["layer"]} at {lg["at_pt"]} pt, in the model at {lg.get("model")}')
        if cu.get('gaps_closed'):
            print(f'  {len(cu["gaps_closed"])} gaps in a body\'s cut narrower than twice its weight closed, first at '
                  f'{cu["gaps_closed"][0]["at_pt"]} pt')
        for o in cu['open'][:12]:
            print(f'  open cut: {o["layer"]} {o["ids"][0][:8]}: {o["length_pt"]} pt from {o["ends_pt"][0]} to {o["ends_pt"][1]}')
        for u_ in cu['unresolved'][:12]:
            print(f'  a cell of {u_["body"]}\'s surfaces their sides leave unsettled, not filled: {u_["area_pt2"]} pt² at {u_["at_pt"]} pt')
        if cu.get('merged'):
            print('  massing: ' + '; '.join(f'{m_["body"]} runs on into {m_["into"]}\'s cut' for m_ in cu['merged']))
    ea = report.get('earth') or {}
    if ea.get('area_pt2'):
        print(f'  earth under the ground\'s open sheets: {ea["area_pt2"]:g} pt²; {ea["cut_lines_pt"]:g} pt of their cut inside it '
              f'and {ea["behind_pt"]:g} pt of line behind it taken out')
    kinds = defaultdict(list)                          # the model's issues by kind, ids left out of the kind
    for i in report['issues']:
        k = re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27}', 'another', i['issue']).split(':')[0].split(' (')[0].split(' by ')[0]
        kinds[' '.join(w for w in k.split() if not re.match(r'^[\d.]+$', w))].append(i)
    for k, items in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
        print(f'  model: {k}, {len(items)}: ' + '; '.join(f'{i["layer"]} {i["ids"][0][:8]}' for i in items[:3])
              + (' ...' if len(items) > 3 else ''))
    print(f'  wrote {folder / (name + ".svg")}, .dxf, .ai and -report.json in {report["seconds"]["total"]} s')
    if explain:
        write_fates(fates, folder / f'{name}-fates.svg', W, H)
        text = explain_notes(fates, explain.read_text(encoding='utf-8'))
        place(text + '\n', folder / f'{name}-explain.txt')
        print(text)
        print(f'  wrote {folder / (name + "-fates.svg")} and -explain.txt')
    if check:
        run_checks(check, folder / f'{name}.svg')
    return 0
