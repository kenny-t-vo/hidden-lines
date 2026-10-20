#! python3
# venv: hl
# r: numpy==2.0.2
"""The exact hidden-line drawing of the open model, written for kit.py hidden-lines to draw.

Run inside Rhino 8 with the model open, through the connector's run_python, in calls the router's timeout allows:
  ns = {'HIDDEN': REQUEST, '__rhino_doc__': __rhino_doc__, '__name__': 'hidden_lines'}
  exec(open(SCRIPT).read, ns); print(ns['main'])
and again while it prints a line starting 'more'. A call works for BUDGET seconds (40 unless ns sets it) and keeps
its progress in scriptcontext.sticky, so no call nears the router's 60 s; ns['RESET'] = True starts over, as does a
change to the request. Nothing in the model changes.

Run as a script (the HL command: the alias _-RunPythonScript with this file's path, or the plug-in rhino/plugin/
builds), it shows a dialog in the manner of Make2D's (alias): what is selected, or everything shown in the viewport;
the view, from the viewport, Rhino's standard views, named views or a section from a clipping plane; the scale and name;
each layer's role, kept on the layer or guessed from its name (rhino/hl.py); whether to add the drawing to the model;
and, as an advanced choice, a request file instead of the layers. It writes the request it drew from, as request.json,
and the export into a folder of the drawing's name, runs kit.py hidden-lines and lint there, adds the drawing under the
layer HL, which no request reads, and leaves a window listing the model's faults. Its last choices are kept in the
document's strings (rhino/RHINO.md, HL).

REQUEST is the drawing's request (docs/commands.md, hidden-lines). This script reads its scale, view, frame, clip,
objects, groups and out, and writes into out:
  scene.json  the view (the world-to-camera transform, the frame in drawing units, the projection, and for a perspective
              the camera, the depth drawn at the request's scale and the frame's shift); the clip planes and each
              closed solid's cut by them (rings: closed polylines in drawing coordinates); every object
              drawn or hiding, with its group, layer, the parts a union joined and what validation found; every visible
              segment in drawing coordinates, depth kept as camera z (nearer larger): its object, its source (geom,
              curve, naked, contact), the engine's silhouette type, the side fills (S its own surface, O another surface,
              V nothing, U unset), whether it is a scene silhouette, and for a cut the plane it lies on (-1 for the
              frame's edge in a perspective); vis 'hidden' on a hidden segment of a group marked hidden, 'above' on
              the segments of the above pass, 'under' on any other hidden segment of what is drawn, for kit.py
              hidden-lines to keep where only a surface it lies on, or nothing, is in front of it, and 'dup' on a
              segment the engine left out as Duplicate of another, which is not always drawn (a rafter's edge seen
              edge-on, an edge on a coplanar face), for kit.py hidden-lines to decide from the faces
  meshes.bin  each surface object's mesh in the same coordinates, clipped as the drawing is: float32 vertices less
              meshes.origin in scene.json (the view's target in camera space, so a depth of 78,740 in, half the view's
              default 4 km, keeps its precision), then int32 triangles, indexed in scene.json (scene version 4)

A parallel view's drawing coordinates are camera x and y. A perspective (view.lens_mm) puts a camera point at
L x / -z, L y / -z less the frame's shift, where L is the depth drawn at the request's scale: the frame spans 36 mm of
a 35 mm camera's film at that lens.

In order:
  collect   objects by layer pattern, each into the first group that names its layer, the group's exclusions
            applied, those outside the frame left out (nothing outside the view can hide anything inside it), and those
            the clip planes take away whole
  union     a group's closed solids that touch and share the user text of its union key, or keys (a house's walls,
            roof, chimney and porch by id; a home's rooms by home and floor), joined into one solid, coplanar faces
            merged; union true joins all that touch; open parts stay apart; a union that fails or does not close is
            reported and its parts kept
  cut       a group's parts inside its cut polygons (plan) removed: surfaces split, solids differenced, curves split
  validate  each object against rhino/MODELLING.md: invalid breps (with Rhino's reason), open polysurfaces and their
            naked edges, non-manifold edges, solids turned inside out, faces crossing their own boundary (tested in
            the face's parameters, since a closed surface's loop runs along its seam twice), faces flat within ten
            tolerances but not one, faces creased inside, edges under ten tolerances, a place over 10 km from the
            origin; open, non-manifold or two-way meshes; duplicates. A creased face is split and an inside-out solid
            turned on the copy (collect), and both reported
  checks    for each pair whose boxes touch, but two objects of groups on CONTEXT outside a check: a surface lying on
            another or on a solid's face that is not turned down
            onto it, solids of groups that hide running into each other (their common volume), and touching faces in
            a group without a union key; open surfaces of one group (not the ground's) sharing an edge unjoined. With
            CHECK in ns the script stops here and writes check.json, every object the groups name checked, frame or
            no frame
  contacts  for each pair of objects whose boxes touch, at least one of them hiding, the curves where their surfaces
            meet or overlap (Intersection.BrepBrep): a box on the ground, a trunk in it, two homes sharing a wall, a
            terrace on a roof. The engine draws no line between separate objects
  hld       HiddenLineDrawing.Compute, on one thread: on the P2 site model, four threaded runs gave 5,257 to 5,303
            visible segments, one of them a driveway's edge through a home 28 m in front of it, where one thread gave
            5,178 every time, in 3.4 s against 1.7. One pass with every object that hides, and one for each group that
            does not (trees, hidden by buildings and hiding none of them). The clip planes go to the engine, which
            takes away the half each faces away from; a closed solid of a group that hides is added so its cut face
            hides what lies behind it, as it does not by default; its cut segments are kept for open surfaces (the
            ground), and a closed solid's cut is taken from the model (rings). Hidden curves are computed and their
            segments left out but for groups marked hidden (drawn dashed on HIDDEN): with IncludeHiddenCurves off, the
            engine called a contact curve wholly visible where a sphere bulging out of a box hides 40 percent of it
            (fuzz seed 33), and split it as ray casting does with it on. With clip planes and a group marked above, one
            more pass of that group alone, mirrored through the first plane into the half it keeps, so what the plane
            takes away is seen from the plane (a plan's roof edges and beams as seen looking up), its cut left out
            (drawn dashed on ABOVE). Contact curves, curve objects and open surfaces' naked edges go in moved toward the camera, so a
            surface they lie on cannot hide them, as the ground hid the base of a trunk standing on it , and their depth is put back after:
            in a parallel view by BIAS tolerances along it, in a perspective by a scaling about the camera, which keeps
            their projection where it is. The engine computes a perspective in a projective space whose depth unit is
            half the scene's farthest depth (c), measured on Rhino 8; its tolerance and the scaling are set from c
  rings     with clip planes, each closed solid's cut by each plane facing the camera, from the model
            (Intersection.BrepPlane, MeshPlane), exact and closed, clipped by the other planes and in a perspective by
            the view: the engine's cut segments left one home's bottom edge out on the P2 site model, where the home
            below shared it, and came back whole for the two homes alone
  meshes    each surface object's mesh, for kit.py hidden-lines to tell what lies either side of a line and to fill
            the visible regions: those of groups that hide, and of a group that does not where it sets mesh; clipped
            by the clip planes and, in a perspective, by the camera's near plane. A twisted face straight in one
            direction is meshed on its own, its edges no longer than its twist allows (twist_cap), so each mesh lies
            within about MESH_PT of its surface (scene version 3); its vertices are written less the origin (version 4)
"""
import array, fnmatch, hashlib, json, math, os, platform, re, sys, tempfile, time
try:
    import numpy as np
except ImportError:
    np = None
import Rhino
import Rhino.Geometry as G
from Rhino.Geometry.Intersect import Intersection
import scriptcontext as sc

PT_PER_MM = 72.0 / 25.4
FAR_M = 10000.0           # a model this far from the origin, in metres, loses precision
COS_FLAT = math.cos(math.radians(0.5))   # faces within half a degree of each other are coplanar
KEY = 'kit.hidden_lines'
BIAS = 4                  # tolerances toward the camera for lines that lie on surfaces
TOL_PT = 0.01             # the engine's tolerance, on paper, unless the request gives tolerance_pt
MESH_PT = 0.05            # a mesh's largest distance from its surface, on paper
SIDE = {'SideUnset': 'U', 'SideVoid': 'V', 'SideSurface': 'S', 'OtherSurface': 'O'}
STAGES = ('collect', 'union', 'cut', 'validate', 'pairs', 'checks', 'contacts', 'hld', 'rings', 'meshes', 'write')
CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'hidden-lines', 'export-cache')
CACHE_BYTES = 2 * 1024 ** 3      # the store's bound: past it the least recently used entries go
CACHE_VERSION = 1                # raised whenever what is cached, or how, changes


def cache_key(*parts):
    """an entry's name: the SHA-256 of the parts (strings, numbers and lists of them) as compact JSON"""
    return hashlib.sha256(json.dumps(list(parts), separators=(',', ':')).encode('utf-8')).hexdigest()


def cache_get(root, key):
    """entry key's payload, or None: root/key[:2]/key holds b'HLC1', the payload's SHA-256, then the payload; one that
    does not check out is removed. A hit marks the entry used now, for cache_trim"""
    path = os.path.join(root, key[:2], key)
    try:
        with open(path, 'rb') as fh:
            header, digest, payload = fh.read(4), fh.read(32), fh.read()
    except OSError:
        return None
    if header != b'HLC1' or digest != hashlib.sha256(payload).digest():
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    try:
        os.utime(path, None)
    except OSError:
        pass
    return payload


def cache_put(root, key, payload):
    """payload kept as entry key, written whole under a temporary name and renamed into place, so a reader sees all of
    it or none; two writers of a key write the same bytes. A store that cannot be written is a miss next time"""
    folder = os.path.join(root, key[:2])
    temp = None
    try:
        os.makedirs(folder, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, prefix='.%d-' % os.getpid(), suffix='.tmp', delete=False) as fh:
            temp = fh.name
            fh.write(b'HLC1')
            fh.write(hashlib.sha256(payload).digest())
            fh.write(payload)
        os.replace(temp, os.path.join(folder, key))
        temp = None
    except OSError:
        pass
    finally:
        if temp is not None:
            try:
                os.remove(temp)
            except OSError:
                pass


def cache_trim(root, limit=CACHE_BYTES, now=None):
    """the store kept under limit bytes, under a lock only one process holds at a time: temporary files an hour old
    and entries unused for 90 days removed, then the least recently used down to three quarters of limit. (removed,
    bytes kept), or (0, None) while another process trims"""
    try:
        os.makedirs(root, exist_ok=True)
        lock = open(os.path.join(root, '.lock'), 'a+b')
    except OSError:
        return 0, None
    with lock:
        try:
            if os.name == 'nt':
                import msvcrt
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return 0, None
        if now is None:
            now = time.time()
        removed, kept_bytes = 0, 0
        entries = []
        for folder, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if not name.startswith('.')]
            for name in files:
                temp = name.startswith('.') and name.endswith('.tmp')
                if name.startswith('.') and not temp:
                    continue
                path = os.path.join(folder, name)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                if now - stat.st_mtime > (3600 if temp else 90 * 24 * 3600):
                    try:
                        os.remove(path)
                        removed += 1
                        continue
                    except OSError:
                        pass
                if not temp:
                    entries.append((stat.st_mtime, name, path, stat.st_size))
                    kept_bytes += stat.st_size
        if kept_bytes > limit:
            for _, _, path, size in sorted(entries):
                try:
                    os.remove(path)
                except OSError:
                    continue
                removed += 1
                kept_bytes -= size
                if kept_bytes <= limit * 3 // 4:
                    break
        return removed, kept_bytes


def doc_of():
    return globals().get('__rhino_doc__') or sc.doc


def pick():
    return globals().get('HIDDEN')


# ---------------------------------------------------------------- the view

def view_of(req, doc):
    """(ViewportInfo, world-to-camera Transform, view direction, frame half width and height in drawing units, pt per
    model unit at the request's scale, true-length factor, and for a perspective a dict of the camera's location, L
    (the depth drawn at the request's scale), the near distance and the frame's shift up the page; None for a
    parallel view)"""
    unit_mm = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
    k = PT_PER_MM * unit_mm / float(req['scale'])
    v = req['view']
    target = G.Point3d(*v['target'])
    lens = v.get('lens_mm')
    if lens and v.get('camera'):
        d = target - G.Point3d(*v['camera'])
    elif 'direction' in v:
        d = G.Vector3d(*v['direction'])
    else:
        b, e = math.radians(v['bearing']), math.radians(v['elevation'])
        d = G.Vector3d(-math.sin(b) * math.cos(e), -math.cos(b) * math.cos(e), -math.sin(e))
    d.Unitize()
    up = G.Vector3d(*v.get('up', [0, 0, 1]))
    if G.Vector3d.CrossProduct(d, up).Length < 1e-9:      # looking straight down: north up the page
        up = G.Vector3d(0, 1, 0)
    far = float(v.get('depth', 4000.0 / unit_mm * 1000))     # model units; 4 km
    m = 1.02                                               # a margin past the frame; kit.py hidden-lines clips exactly
    W, H = float(req['frame']['w_pt']), float(req['frame']['h_pt'])
    vi = Rhino.DocObjects.ViewportInfo()
    if not lens:
        right = G.Vector3d.CrossProduct(d, up)
        right.Unitize()
        cup = G.Vector3d.CrossProduct(right, d)
        f = 1.0
        if v.get('true_along'):
            a = G.Vector3d(*v['true_along'])
            a.Unitize()
            f = 1.0 / math.hypot(a * right, a * cup)
        hw, hh = W / 2 / (k * f), H / 2 / (k * f)
        vi.ChangeToParallelProjection(True)
        vi.SetCameraLocation(target - d * far / 2)
        vi.SetCameraDirection(d)
        vi.SetCameraUp(cup)
        vi.SetFrustum(-hw * m, hw * m, -hh * m, hh * m, far / 1e4, far)
        xf = vi.GetXform(Rhino.DocObjects.CoordinateSystem.World, Rhino.DocObjects.CoordinateSystem.Camera)
        return vi, xf, d, hw, hh, k, f, None
    if v.get('true_along'):
        raise ValueError('true_along needs a parallel view: a perspective has no one scale along an axis')
    lens = float(lens)
    L = W / 2 * lens / 18.0 / k                            # 36 mm of film across the frame
    cam = G.Point3d(*v['camera']) if v.get('camera') else target - d * L
    look = G.Vector3d(d)
    if v.get('two_point'):                                 # the camera level, so verticals stay vertical
        look = G.Vector3d(d.X, d.Y, 0.0)
        if look.Length < 1e-9:
            raise ValueError('two_point needs a view that does not look straight up or down')
        look.Unitize()
        up = G.Vector3d(0, 0, 1)
    right = G.Vector3d.CrossProduct(look, up)
    right.Unitize()
    cup = G.Vector3d.CrossProduct(right, look)
    t = target - cam
    if t * look <= 0:
        raise ValueError('the target is behind the camera')
    shift = L * (t * cup) / (t * look) if v.get('two_point') else 0.0   # the target's height on the page
    hw, hh = W / 2 / k, H / 2 / k
    near = min(L, t.Length) / 1000.0
    vi.ChangeToPerspectiveProjection(L, not v.get('two_point'), lens)   # this moves the camera, so it is placed after
    vi.SetCameraLocation(cam)
    vi.SetCameraDirection(look)
    vi.SetCameraUp(cup)
    if v.get('two_point'):
        vi.UnlockFrustumSymmetry()
    q = near / L
    vi.SetFrustum(-hw * m * q, hw * m * q, (shift - hh * m) * q, (shift + hh * m) * q, near, far)
    if vi.CameraLocation.DistanceTo(cam) > 1e-6 * max(1.0, L):
        raise ValueError('the viewport moved the camera to %s' % vi.CameraLocation)
    xf = vi.GetXform(Rhino.DocObjects.CoordinateSystem.World, Rhino.DocObjects.CoordinateSystem.Camera)
    return vi, xf, look, hw, hh, k, 1.0, dict(cam=cam, L=L, near=near, shift=shift, lens=lens)


def planes_of(req):
    """the request's clip planes, [(origin, unit normal into the part kept)]: one {origin, normal} or a list"""
    spec = req.get('clip') or []
    out = []
    for c in ([spec] if isinstance(spec, dict) else spec):
        n = G.Vector3d(*c['normal'])
        if n.Length < 1e-12:
            raise ValueError('a clip plane with no normal: %s' % c)
        n.Unitize()
        out.append((G.Point3d(*c['origin']), n))
    return out


def back_of(st, po, pn):
    """is the clip plane through po, keeping the half pn points into, seen from that half, so its cut faces away"""
    if st['persp'] is not None:
        return (st['persp']['cam'] - po) * pn > 0
    return st['dir'] * pn < 0


def project(st, p):
    """a camera point (x, y, z) as drawing coordinates, depth kept: x and y as they are in a parallel view"""
    P = st['persp']
    if P is None:
        return p
    x, y, z = p
    return (P['L'] * x / -z, P['L'] * y / -z - P['shift'], z)


def clip_poly(pts, f):
    """the part of a closed polygon (points) where the affine f(p) >= 0, closed along f = 0"""
    out = []
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        a, b = f(p), f(q)
        if a >= 0:
            out.append(p)
        if (a >= 0) != (b >= 0):
            t = a / (a - b)
            out.append(tuple(p[j] + (q[j] - p[j]) * t for j in range(3)))
    return out


def clip_tri(tri, f):
    """the parts of a triangle (three points) where the affine f(p) >= 0, as triangles"""
    poly = clip_poly(list(tri), f)
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


# ---------------------------------------------------------------- objects

def in_poly(p, ring):
    x, y, inside = p[0], p[1], False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def geoms(o, doc, xf=None, depth=0):
    """[(kind, geometry)] of an object, block instances opened, extrusions and SubDs made breps"""
    g = o.Geometry
    out = []
    if isinstance(g, G.InstanceReferenceGeometry):
        if depth > 8:
            return out
        idef = doc.InstanceDefinitions.FindId(g.ParentIdefId)
        x = g.Xform if xf is None else xf * g.Xform
        for sub in (idef.GetObjects() if idef else []):
            out += geoms(sub, doc, x, depth + 1)
        return out
    if isinstance(g, G.Extrusion):
        out.append(('brep', g.ToBrep(True)))
    elif isinstance(g, G.SubD):
        out.append(('brep', g.ToBrep(G.SubDToBrepOptions.Default)))
    elif isinstance(g, G.Brep):
        out.append(('brep', g.DuplicateBrep()))
    elif isinstance(g, G.Surface):
        out.append(('brep', g.ToBrep()))
    elif isinstance(g, G.Mesh):
        out.append(('mesh', g.DuplicateMesh()))
    elif isinstance(g, G.Curve):
        out.append(('curve', g.DuplicateCurve()))
    if xf is not None:
        for _, x in out:
            x.Transform(xf)
    return [(kd, x) for kd, x in out if x is not None]


def collect(req, doc, st):
    groups = req['groups']
    xf, hw, hh = st['xf'], st['hw'] * 1.02, st['hh'] * 1.02
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = True
    s.LockedObjects = True
    s.IncludeLights = False
    s.IncludeGrips = False
    objs, culled, clipped, layer_of = [], 0, 0, {}
    P = st['persp']
    only = set(req['objects']) if req.get('objects') is not None else None   # ids, the HL command's
    for o in doc.Objects.GetObjectList(s):
        li = o.Attributes.LayerIndex
        if li not in layer_of:
            layer_of[li] = doc.Layers[li].FullPath
        lay = layer_of[li]
        if lay.split('::')[0] == OUT_LAYER:               # a drawing the command added
            continue
        if only is not None and str(o.Id) not in only:
            continue
        gi = next((n for n, g in enumerate(groups) if any(fnmatch.fnmatchcase(lay, p) for p in g['layers'])
                   and not any(fnmatch.fnmatchcase(lay, p) for p in g.get('not_layers', []))), None)
        if gi is None:
            continue
        g = groups[gi]
        user = lambda k: o.Attributes.GetUserString(k)
        if any(user(k) not in (v if isinstance(v, list) else [v]) for k, v in g.get('where', {}).items()):
            continue
        ex = g.get('exclude', {})
        if any(user(k) in v for k, v in ex.get('user', {}).items()):
            continue
        bb = o.Geometry.GetBoundingBox(True)
        if not bb.IsValid:
            continue
        if ex.get('within') and any(in_poly((bb.Center.X, bb.Center.Y), [tuple(p) for p in ring]) for ring in rings(ex['within'])):
            continue
        corners = bb.GetCorners()
        if globals().get('CHECK'):                        # a check covers every object the groups name
            pass
        elif not g.get('above') and any(all((c - po) * pn < -st['tol'] for c in corners) for po, pn in st['planes']):
            clipped += 1                                  # wholly in the half a clip plane takes away (kept for above)
            continue
        cs = [] if globals().get('CHECK') else [xf * c for c in corners]
        if P is not None and cs:
            if max(c.Z for c in cs) < -P['near']:         # wholly in front of the camera: its projection's box
                cs = [G.Point3d(*project(st, (c.X, c.Y, c.Z))) for c in cs]
            elif min(c.Z for c in cs) >= -P['near']:      # wholly behind the camera
                culled += 1
                continue
            else:                                         # round the camera: kept
                cs = []
        if cs and (min(c.X for c in cs) > hw or max(c.X for c in cs) < -hw or min(c.Y for c in cs) > hh or max(c.Y for c in cs) < -hh):
            culled += 1
            continue
        keys = union_keys(g)
        for kind, geo in geoms(o, doc):
            objs.append(dict(ids=[str(o.Id)], group=g['id'], layer=lay, kind=kind, geom=geo,
                             user={k: user(k) for k in keys + g.get('keep_user', []) if user(k) is not None},
                             issues=repair(kind, geo)))
    st['objs'] = objs
    st['log'].append('collect: %d objects in %d groups, %d outside the frame%s' % (
        len(objs), len(groups), culled, ', %d taken away whole by the clip planes' % clipped if st['planes'] else ''))


def repair(kind, g):
    """repairs that leave the shape as it is, made on the copy drawn and reported so the model can be fixed too: a face
    creased inside split at the crease (the engine draws no line there), a solid turned the right way out"""
    out = []
    if kind != 'brep':
        return out
    n = g.Faces.Count
    if g.Faces.SplitKinkyFaces(Rhino.RhinoMath.DefaultAngleTolerance, True) and g.Faces.Count > n:
        out.append('creased inside: %d faces split at their creases on the copy drawn; split them in the model'
                   % (g.Faces.Count - n))
    if g.IsSolid and g.SolidOrientation == G.BrepSolidOrientation.Inward:
        g.Flip()
        out.append('inside out: turned the right way on the copy drawn; flip it in the model')
    return out


def union_keys(g):
    """the user-text keys whose values a union's parts share: a key or a list of them"""
    u = g.get('union')
    return [u] if isinstance(u, str) else list(u) if isinstance(u, list) else []


def rings(spec):
    """a polygon [[x, y],...] or a list of them"""
    return [spec] if spec and isinstance(spec[0][0], (int, float)) else spec


def boxes_touch(a, b, tol):
    return (a.Min.X <= b.Max.X + tol and b.Min.X <= a.Max.X + tol and a.Min.Y <= b.Max.Y + tol and b.Min.Y <= a.Max.Y + tol
            and a.Min.Z <= b.Max.Z + tol and b.Min.Z <= a.Max.Z + tol)


def components(items, tol):
    """indices of items (with 'bb') joined where their boxes touch"""
    n = len(items)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = sorted(range(n), key=lambda i: items[i]['bb'].Min.X)
    for a in range(n):
        i = order[a]
        for b in range(a + 1, n):
            j = order[b]
            if items[j]['bb'].Min.X > items[i]['bb'].Max.X + tol:
                break
            if boxes_touch(items[i]['bb'], items[j]['bb'], tol):
                parent[find(i)] = find(j)
    out = {}
    for i in range(n):
        out.setdefault(find(i), []).append(i)
    return list(out.values())


def union_jobs(req, st):
    by = {g['id']: g for g in req['groups']}
    jobs, keep = [], []
    clusters = {}
    for n, o in enumerate(st['objs']):
        g = by[o['group']]
        keys = union_keys(g)
        vals = tuple(o['user'].get(k) for k in keys)
        if g.get('union') and o['kind'] == 'brep' and o['geom'].IsSolid and None not in vals:
            clusters.setdefault((o['group'], vals), []).append(n)
        else:
            keep.append(n)
    for (gid, val), idx in clusters.items():
        items = [dict(n=n, bb=st['objs'][n]['geom'].GetBoundingBox(True)) for n in idx]
        for comp in components(items, st['ctol']):
            ns = [items[c]['n'] for c in comp]
            if len(ns) == 1:
                keep.append(ns[0])
            else:
                jobs.append(ns)
    st['union_jobs'], st['union_keep'], st['union_out'] = jobs, keep, []


def union_one(st, ns):
    objs, tol = st['objs'], st['ctol']
    parts = [objs[n] for n in ns]
    res = G.Brep.CreateBooleanUnion([p['geom'] for p in parts], tol)
    ok = res is not None and len(res) >= 1 and all(r.IsValid and r.IsSolid for r in res) and len(res) < len(parts)
    if not ok:
        why = 'failed' if not res else 'left %d pieces, %d closed' % (len(res), sum(1 for r in res if r.IsSolid))
        for p in parts:
            p['issues'].append('union with %d parts %s; kept apart' % (len(parts) - 1, why))
        st['union_out'] += parts
        return
    ids = [i for p in parts for i in p['ids']]
    layers = [p['layer'] for p in parts]
    layer = max(layers, key=lambda L: (layers.count(L), -layers.index(L)))     # the parts' commonest layer
    for r in res:
        r.MergeCoplanarFaces(tol)
        st['union_out'].append(dict(ids=ids, group=parts[0]['group'], layer=layer, kind='brep', geom=r,
                                    user=parts[0]['user'], issues=[], parts=len(parts)))


def cut_one(st, o, prisms):
    """o less the parts inside the group's cut prisms: [] when all of it is inside, [o] when none is"""
    tol = st['ctol']
    g = o['geom']
    bb = g.GetBoundingBox(True)
    pieces = [g]
    for prism, ring, pbb in prisms:
        if not boxes_touch(bb, pbb, tol):
            continue
        nxt = []
        for p in pieces:
            if o['kind'] == 'curve':
                ts = []
                ok, cs, ps = Intersection.CurveBrep(p, prism, tol)
                for c in (cs or []):
                    ts += [p.ClosestPoint(c.PointAtStart)[1], p.ClosestPoint(c.PointAtEnd)[1]]
                for q in (ps or []):
                    ts.append(p.ClosestPoint(q)[1])
                parts = p.Split(sorted(set(ts))) if ts else None
                parts = list(parts) if parts else [p]
                mid = lambda c: c.PointAt(c.Domain.Mid)
            elif o['kind'] == 'brep' and p.IsSolid:
                parts = G.Brep.CreateBooleanDifference(p, prism, tol)
                parts = list(parts) if parts is not None else [p]
                mid = None
            elif o['kind'] == 'brep':
                parts = p.Split(prism, tol)
                parts = list(parts) if parts else [p]
                mid = lambda b: getattr(G.AreaMassProperties.Compute(b), 'Centroid', None) or b.GetBoundingBox(True).Center
            else:
                parts = [p]
                mid = lambda m: m.GetBoundingBox(True).Center
            for q in parts:
                c = mid(q) if mid else None
                if c is not None and in_poly((c.X, c.Y), ring):
                    continue
                nxt.append(q)
        pieces = nxt
    return [dict(o, geom=q, issues=list(o['issues'])) for q in pieces]


def prisms_of(ring, zmin, zmax, tol):
    pts = [G.Point3d(x, y, zmin - 1) for x, y in ring] + [G.Point3d(ring[0][0], ring[0][1], zmin - 1)]
    c = G.PolylineCurve(pts)
    ex = G.Extrusion.Create(c, (zmax - zmin) + 2, True)
    b = ex.ToBrep(True)
    if b.SolidOrientation == G.BrepSolidOrientation.Inward:
        b.Flip()
    return b, [tuple(p) for p in ring], b.GetBoundingBox(True)


def validate_one(o, st):
    """what in an object will draw wrong: invalid or open geometry, faces turned in, crossing their own boundary,
    nearly planar or creased inside, edges too short to draw, and a place far from the origin"""
    g = o['geom']
    mt, un = st['mtol'], st['unit']
    if o['kind'] == 'brep':
        if not g.IsValid:
            ok, log = g.IsValidWithLog()
            line = next((x.strip() for x in (log or '').splitlines() if x.strip()), '')
            o['issues'].append('invalid brep' + (': ' + line[:100] if line else ''))
        naked = sum(1 for e in g.Edges if e.Valence == G.EdgeAdjacency.Naked)
        nm = sum(1 for e in g.Edges if e.Valence == G.EdgeAdjacency.NonManifold)
        if naked and g.Faces.Count > 1:
            o['issues'].append('open polysurface: %d naked edges' % naked)
        if nm:
            o['issues'].append('%d non-manifold edges' % nm)
        o['solid'] = g.IsSolid
        if g.IsSolid and g.SolidOrientation == G.BrepSolidOrientation.Inward:
            o['issues'].append('inside out: its faces point inward')
        nearly = crossing = kinked = 0
        for f in g.Faces:
            if not f.IsPlanar(mt) and f.IsPlanar(mt * 10):
                nearly += 1
            # in the face's own parameters: a closed surface's loop runs along its seam twice in the model
            t2 = 1e-6 * max(f.Domain(0).Length, f.Domain(1).Length)
            if any(c is not None and Intersection.CurveSelf(c, t2).Count for c in (lp.To2dCurve() for lp in f.Loops)):
                crossing += 1
            if creased(f, 0) or creased(f, 1):
                kinked += 1
        if crossing:
            o['issues'].append('%d faces cross their own boundary (a profile that crosses itself)' % crossing)
        if nearly:
            o['issues'].append('%d faces nearly planar: flat within %g %s, not within %g' % (nearly, mt * 10, un, mt))
        if kinked:
            o['issues'].append('%d faces creased inside (split them at the crease: the engine draws no line there)' % kinked)
        tiny = sum(1 for e in g.Edges if e.GetLength() < mt * 10)
        if tiny:
            o['issues'].append('%d edges under %g %s' % (tiny, mt * 10, un))
    elif o['kind'] == 'mesh':
        if not g.IsValid:
            o['issues'].append('invalid mesh')
        o['solid'] = g.IsClosed
        if not g.IsClosed and g.Faces.Count > 1:
            o['issues'].append('open mesh')
        manifold, oriented, edged = g.IsManifold(True)
        if not manifold:
            o['issues'].append('non-manifold mesh')
        elif not oriented:
            o['issues'].append('mesh faces point both ways')
    bb = g.GetBoundingBox(True)
    if max(abs(v) for v in (bb.Min.X, bb.Min.Y, bb.Min.Z, bb.Max.X, bb.Max.Y, bb.Max.Z)) > FAR_M * 1000 / st['unit_mm']:
        o['issues'].append('more than %g km from the origin, where precision suffers' % (FAR_M / 1000))


def creased(f, d):
    """whether face f turns by more than the angle tolerance across one of its knot lines in direction d (0 u, 1 v).
    The G1 test also reports the double knots of a NURBS surface's circle direction that run into its poles
    (NurbsSurface.CreateFromSphere's at u = pi/2), across which the normal turns 0.0 degrees, so each knot it reports
    is sampled at 19 points along its line, clear of the line's ends, a millionth of the domain either side"""
    dom, along = f.Domain(d), f.Domain(1 - d)
    e = dom.Length * 1e-6
    t0 = dom.Min
    while True:
        ok, t = f.GetNextDiscontinuity(d, G.Continuity.G1_continuous, t0, dom.Max)   # the locus test also reports a
        if not ok or not t0 < t < dom.Max:                                           # closed surface's seam
            return False
        for k in range(1, 20):
            s = along.ParameterAt(k / 20.0)
            a, b = ((t - e, s), (t + e, s)) if d == 0 else ((s, t - e), (s, t + e))
            if G.Vector3d.VectorAngle(f.NormalAt(*a), f.NormalAt(*b)) > Rhino.RhinoMath.DefaultAngleTolerance:
                return True
        t0 = t


def duplicates(st):
    """objects of one kind whose boxes, faces and edges agree within ten tolerances: the later is a duplicate"""
    seen = {}
    q = st['mtol'] * 10
    for o in st['objs']:
        bb = o['geom'].GetBoundingBox(True)
        size = (o['geom'].Faces.Count, o['geom'].Edges.Count) if o['kind'] == 'brep' else (
            (o['geom'].Faces.Count,) if o['kind'] == 'mesh' else (o['geom'].GetLength(),))
        key = (o['kind'],) + tuple(int(round(v / q)) for v in (bb.Min.X, bb.Min.Y, bb.Min.Z, bb.Max.X, bb.Max.Y, bb.Max.Z)) + size
        if key in seen:
            o['issues'].append('duplicate of %s' % seen[key]['ids'][0])
        else:
            seen[key] = o


def planes_of_faces(o, mt):
    """an object's planar faces: [(plane, outer boundary curve, box)]"""
    out = []
    if o['kind'] != 'brep':
        return out
    for f in o['geom'].Faces:
        ok, pl = f.TryGetPlane(mt)
        if ok:
            if f.OrientationIsReversed:
                pl.Flip()
            out.append((pl, f.OuterLoop.To3dCurve(), f.GetBoundingBox(True)))
    return out


def faces_of(st, n):
    """planes_of_faces of object n, worked out once an export"""
    if n not in st['faces']:
        st['faces'][n] = planes_of_faces(st['objs'][n], st['mtol'])
    return st['faces'][n]


def naked_of(st, n):
    """object n's naked edges as curves, worked out once an export"""
    if n not in st['naked']:
        st['naked'][n] = st['objs'][n]['geom'].DuplicateNakedEdgeCurves(True, True) or []
    return st['naked'][n]


def serial():
    """Rhino's serialization of geometry alone: no render or analysis meshes, no user data"""
    so = Rhino.FileIO.SerializationOptions()
    so.WriteUserData = so.WriteRenderMeshes = so.WriteAnalysisMeshes = False
    return so


def digest_of(st, n):
    """the SHA-256 of object n's copy as Rhino writes it (serial), worked out once an export: after collect, union, cut
    and repair, so the store's entries follow the geometry and not the model's ids"""
    if n not in st['digest']:
        st['digest'][n] = hashlib.sha256(st['objs'][n]['geom'].ToJSON(serial()).encode('utf-8')).hexdigest()
    return st['digest'][n]


def pair_key(st, op, tol, i, j):
    """the store's name for op on objects i and j, in that order, at tol: the cache's version, Rhino's build and the
    platform, the units, and the two copies' digests"""
    return cache_key(op, CACHE_VERSION, st['build'], st['unit_mm'], tol, digest_of(st, i), digest_of(st, j))


def remembered(st, op, tol, i, j, work):
    """work for objects i and j, a value JSON keeps exactly, from the store, or worked out and kept there"""
    key = pair_key(st, op, tol, i, j)
    got = cache_get(st['cache'], key)
    if got is not None:
        return json.loads(got.decode('utf-8'))
    val = work()
    cache_put(st['cache'], key, json.dumps(val).encode('utf-8'))
    return val


def faces_meet(st, i, j):
    """[the area of faces of i and j lying on each other facing the same way, the count of their faces touching
    facing apart (solids)], for check_pair"""
    a, b, mt = st['objs'][i], st['objs'][j], st['mtol']
    same = touch = 0.0
    sa, sb = bool(a.get('solid')), bool(b.get('solid'))
    for pa, ca, ba in faces_of(st, i):
        for pb, cb, bb in faces_of(st, j):
            if not boxes_touch(ba, bb, mt * 2):
                continue
            c = pa.ZAxis * pb.ZAxis
            if abs(c) < COS_FLAT or abs(pa.DistanceTo(pb.Origin)) > mt * 2:
                continue
            if c < 0 and sa and sb:
                touch += 1
                continue
            if (sa and sb) or (sa and pa.ZAxis.Z < -0.7) or (sb and pb.ZAxis.Z < -0.7):
                continue
            r = G.Curve.CreateBooleanIntersection(ca, cb, mt)
            area = sum(m.Area for m in (G.AreaMassProperties.Compute(x) for x in (r or []) if x.IsClosed) if m)
            same += area
    return [same, touch]


def check_pair(st, i, j):
    """what two objects whose boxes touch do to each other: a surface lying on another, or on a solid's face, which only
    group order settles (a solid's face turned down onto a surface is where it stands, and is left alone; two solids
    sharing a face the same way run into each other, reported as that); solids running into each other, unless one is
    seen through (crowns overlap as they like); touching faces, counted for a group that unions nothing. What the
    geometry gives is kept in the store (remembered); what it says is worked out afresh for this request"""
    objs, mt, un = st['objs'], st['mtol'], st['unit']
    a, b = objs[i], objs[j]
    same, touch = remembered(st, 'faces', mt, i, j, lambda: faces_meet(st, i, j))
    if same > (mt * 10) ** 2:
        for x, y in ((a, b), (b, a)):
            x['issues'].append('lies on %s, face on face facing the same way (%.3g %s2): the earlier group\'s is drawn'
                               % (y['ids'][0], same, un))
    if touch and a['group'] == b['group'] and a['kind'] == b['kind'] == 'brep':
        st['touching'][a['group']] = st['touching'].get(a['group'], 0) + 1
    if a.get('solid') and b.get('solid') and st['hides'][a['group']] and st['hides'][b['group']]:
        A, B = a['geom'].GetBoundingBox(True), b['geom'].GetBoundingBox(True)
        if min(A.Max.X, B.Max.X) - max(A.Min.X, B.Min.X) > mt * 10 and min(A.Max.Y, B.Max.Y) - max(A.Min.Y, B.Min.Y) > mt * 10 \
                and min(A.Max.Z, B.Max.Z) - max(A.Min.Z, B.Min.Z) > mt * 10:
            def clash():
                r = G.Brep.CreateBooleanIntersection(a['geom'], b['geom'], mt)
                return sum(abs(m.Volume) for m in (G.VolumeMassProperties.Compute(x) for x in (r or []) if x.IsSolid) if m)   # None for a degenerate one
            vol = remembered(st, 'clash', mt, i, j, clash)
            if vol > (mt * 10) ** 3:
                for x, y in ((a, b), (b, a)):
                    x['issues'].append('runs into %s by %.3g %s3' % (y['ids'][0], vol, un))


def open_pairs(req, st):
    """open surfaces of one group whose boxes touch, to look for an edge they share unjoined: [(i, j)]; not on the
    ground, whose pieces are apart on purpose, each its own surface"""
    tol = st['mtol'] * 2
    ground = {g['id'] for g in req['groups'] if g.get('ground')}
    items = [dict(n=n, bb=o['geom'].GetBoundingBox(True)) for n, o in enumerate(st['objs'])
             if o['kind'] == 'brep' and not o['geom'].IsSolid and o['group'] not in ground]
    order = sorted(items, key=lambda it: it['bb'].Min.X)
    out = []
    for a in range(len(order)):
        for b in range(a + 1, len(order)):
            if order[b]['bb'].Min.X > order[a]['bb'].Max.X + tol:
                break
            i, j = order[a]['n'], order[b]['n']
            if st['objs'][i]['group'] == st['objs'][j]['group'] and boxes_touch(order[a]['bb'], order[b]['bb'], tol):
                out.append((i, j))
    return out


def check_open(st, i, j):
    objs, tol = st['objs'], st['mtol'] * 2

    def shared():
        for c in naked_of(st, i):
            pts = [c.PointAtStart, c.PointAt(c.Domain.Mid), c.PointAtEnd]
            for d in naked_of(st, j):
                if all(d.ClosestPoint(q)[0] and d.PointAt(d.ClosestPoint(q)[1]).DistanceTo(q) < tol for q in pts):
                    return True
        return False
    if remembered(st, 'open', tol, i, j, shared):
        for x, y in ((objs[i], objs[j]), (objs[j], objs[i])):
            x['issues'].append('shares an edge with %s: join them' % y['ids'][0])


# ---------------------------------------------------------------- contacts

def pair_list(req, st):
    hides = {g['id']: g.get('hides', True) for g in req['groups']}
    tol = st['tol'] * 2
    items = [dict(n=n, bb=o['geom'].GetBoundingBox(True)) for n, o in enumerate(st['objs']) if o['kind'] == 'brep']
    order = sorted(items, key=lambda it: it['bb'].Min.X)
    pairs = []
    for a in range(len(order)):
        A = order[a]
        oa = st['objs'][A['n']]
        for b in range(a + 1, len(order)):
            B = order[b]
            if B['bb'].Min.X > A['bb'].Max.X + tol:
                break
            if not boxes_touch(A['bb'], B['bb'], tol):
                continue
            ob = st['objs'][B['n']]
            if not (hides[oa['group']] or hides[ob['group']]):
                continue                                  # see-through things hide nothing, so meet nothing
            if not oa['geom'].IsSolid and not ob['geom'].IsSolid:
                continue                                  # two surfaces meet along their naked edges, drawn already
            pairs.append((A['n'], B['n']))
    st['pairs'], st['contacts'] = pairs, []
    st['log'].append('pairs: %d whose boxes touch' % len(pairs))


def owner(req, st, i, j):
    """the object a contact line belongs to: the one in the earlier group, or the one not on the ground"""
    order = {g['id']: n for n, g in enumerate(req['groups'])}
    ground = {g['id'] for g in req['groups'] if g.get('ground')}
    a, b = st['objs'][i], st['objs'][j]
    if (a['group'] in ground) != (b['group'] in ground):
        return j if a['group'] in ground else i
    return i if order[a['group']] <= order[b['group']] else j


def contact_one(req, st, i, j):
    """the curves where objects i and j meet, from the store if they were worked out before for the same two copies at
    the same tolerance (Rhino writes and reads them back exactly: 348 curves of the model's,); a failed
    intersection is not kept. Who owns them, and which are long enough, are worked out afresh"""
    key = pair_key(st, 'contact', st['ctol'], i, j)
    got = cache_get(st['cache'], key)
    if got is not None:
        crv = [Rhino.Runtime.CommonObject.FromJSON(x) for x in json.loads(got.decode('utf-8'))]
    else:
        ok, crv, pts = Intersection.BrepBrep(st['objs'][i]['geom'], st['objs'][j]['geom'], st['ctol'])
        if not ok:
            return
        crv = list(crv or [])
        cache_put(st['cache'], key, json.dumps([c.ToJSON(serial()) for c in crv]).encode('utf-8'))
    if not crv:
        return
    w = owner(req, st, i, j)
    for c in crv:
        if c.GetLength() > st['tol']:
            st['contacts'].append((w, i if w == j else j, c))


# ---------------------------------------------------------------- the engine

def segments_of(h, keep, pass_id, st, moved, hidden_o=(), tag=None, under=False):
    """the visible segments of objects in keep, and every cut segment, in drawing coordinates with camera depth; the
    sources in moved have their depth put back (moved(p) inverts their move in camera coordinates). The hidden ones
    of objects in hidden_o too, as vis 'hidden', and with under those of the rest, as vis 'under', for kit.py
    hidden-lines to keep where only a surface they lie on hides them, and the Duplicate ones, as vis 'dup'; with tag,
    every segment is vis tag and cuts are left out"""
    out = []
    digits = st['digits']
    V = G.HiddenLineDrawingSegment.Visibility
    h2w = h.WorldToHiddenLine.TryGetInverse()[1]
    xf = st['xf']
    planes = st['planes']
    chord = st['chord'] * st.get('hld_c', 1.0)       # in the engine's units: a perspective's are c / L of the drawing's
    for s in h.Segments:
        vis = s.SegmentVisibility
        pc = s.ParentCurve
        if pc is None or pc.SourceObject is None:
            continue
        cut = pc.SilhouetteType == G.SilhouetteType.SectionCut
        if cut and tag:
            continue
        name = str(pc.SourceObject.Tag)
        n, src = int(name.split(':')[0]), name.split(':')[1]
        if n not in keep:
            continue
        dup = vis == V.Duplicate and under
        if vis != V.Visible and not dup and not (vis == V.Hidden and not cut and (under or n in hidden_o)):
            continue
        c = s.CurveGeometry
        if c is None:
            continue
        ok, pl = c.TryGetPolyline()
        if not ok:
            q = c.ToPolyline(chord, math.radians(3.0), 0.0, 0.0)
            if q is None:
                continue
            pl = q.ToPolyline()
        world = [h2w * q for q in pl]
        cam = [xf * q for q in world]
        cam = [moved(q) if src in ('curve', 'naked', 'contact') else (q.X, q.Y, q.Z) for q in cam]
        pts = [[round(v, digits) for v in project(st, q)] for q in cam]
        if len(pts) < 2:
            continue
        fills = s.CurveSideFills
        rec = dict(o=n, src=src, sil=str(pc.SilhouetteType), pass_=pass_id, pts=pts,
                   sides=''.join(SIDE.get(str(x), '?') for x in fills) if fills is not None else '',
                   scene=bool(s.IsSceneSilhouette))
        if vis == V.Hidden or tag:
            rec['vis'] = ('hidden' if n in hidden_o else 'under') if vis == V.Hidden else tag
        elif dup:
            rec['vis'] = 'dup'
        if cut:                                      # the plane it lies on; -1 for the view's own edge in a perspective
            on = [i for i, (po, pn) in enumerate(planes) if max(abs((q - po) * pn) for q in world) < st['tol'] * 50]
            rec['cut'] = on[0] if on else -1
        if src == 'contact':
            rec['with'] = int(name.split(':')[2])
        out.append(rec)
    return out


def hld_one(req, st, pass_id):
    hides = {g['id']: g.get('hides', True) for g in req['groups']}
    draws = {g['id']: g.get('draw', True) for g in req['groups']}
    objs = st['objs']
    geo = {}
    if pass_id == 'main':
        add = [n for n, o in enumerate(objs) if hides[o['group']] or o['kind'] == 'curve']
        keep = set(n for n in add if draws[objs[n]['group']])
    elif pass_id == 'above':
        # what the first plane takes away from the groups marked above, mirrored through it into the half it keeps and
        # so seen from the plane: a plan's roof edges and beams as seen looking up, in the plan's own place
        above = {g['id'] for g in req['groups'] if g.get('above')}
        add = [n for n, o in enumerate(objs) if o['group'] in above and o['kind'] != 'curve']
        keep = set(add)
        M = G.Transform.Mirror(G.Plane(st['planes'][0][0], st['planes'][0][1]))
        for n in add:
            g2 = objs[n]['geom'].Duplicate()
            g2.Transform(M)
            geo[n] = g2
    else:
        add = [n for n, o in enumerate(objs) if hides[o['group']] or o['group'] == pass_id]
        keep = set(n for n, o in enumerate(objs) if o['group'] == pass_id)
    if not add:
        st['log'].append('hld %s: nothing to draw' % pass_id)
        return
    contacts = [(w, other, c) for w, other, c in st['contacts'] if w in keep] if pass_id != 'above' else []
    hidden_g = {g['id'] for g in req['groups'] if g.get('hidden')}
    hidden_o = set(n for n in keep if objs[n]['group'] in hidden_g) if pass_id != 'above' else set()
    P = st['persp']
    tol = st['tol']
    planes = st['planes']
    ident = G.Transform.Identity

    items = []                                      # (geometry, moved toward the camera, tag, its cut face hides)
    for n in add:
        o = objs[n]
        gm = geo.get(n, o['geom'])
        if o['kind'] == 'curve':
            items.append((gm, True, '%d:curve' % n, False))
            continue
        items.append((gm, False, '%d:geom' % n, bool(planes and o.get('solid') and hides[o['group']])))
        if o['kind'] == 'brep' and not gm.IsSolid and n in keep:
            for c in (naked_of(st, n) if n not in geo else gm.DuplicateNakedEdgeCurves(True, True) or []):
                items.append((c, True, '%d:naked' % n, False))
    for w, other, c in contacts:
        items.append((c, True, '%d:contact:%d' % (w, other), False))

    def compute(hld_tol, shift, only=None):
        hp = G.HiddenLineDrawingParameters()
        hp.AbsoluteTolerance = hld_tol
        hp.Flatten = False
        hp.IncludeHiddenCurves = True               # off, the engine called a curve half hidden by a sphere wholly visible
        hp.IncludeTangentEdges = False
        hp.IncludeTangentSeams = False
        hp.SetViewport(st['vi'])
        for g, mv, tag, cuts in (only or items):
            if cuts:
                hp.AddGeometry(g, ident, tag, True)         # its cut face hides what lies behind it
            else:
                hp.AddGeometry(g, shift if mv else ident, tag)
        for po, pn in planes:
            hp.AddClippingPlane(G.Plane(po, -pn))           # the engine takes away the half its normal points into
        return G.HiddenLineDrawing.Compute(hp, False)    # threaded, the same input came out different run to run

    def unit_of(h):
        w2h = h.WorldToHiddenLine
        j = max(range(4), key=lambda j: abs(w2h[3, j]))
        return -st['xf'][2, j] / w2h[3, j]

    def unit_ahead(hld_tol, shift):
        """the depth unit the engine will compute in, from a box brep of the box round the loose boxes of all it is
        given, which gives the engine's unit to the last digit (Rhino 8.35, measured), in milliseconds; None where that
        box has no volume or the engine returns nothing"""
        bb = G.BoundingBox.Empty
        for g, mv, tag, cuts in items:
            b = g.GetBoundingBox(False)
            bb.Union(G.BoundingBox([shift * q for q in b.GetCorners()]) if mv else b)
        d = bb.Diagonal
        if not (d.X > 0 and d.Y > 0 and d.Z > 0):
            return None
        h = compute(hld_tol, shift, [(G.Box(bb).ToBrep(), False, 'box', False)])
        return unit_of(h) if h is not None else None

    if P is None:
        b = tol * BIAS
        h = compute(tol, G.Transform.Translation(-st['dir'] * b))
        moved = lambda q: (q.X, q.Y, q.Z - b)
        if h is not None:
            w2h = h.WorldToHiddenLine
            off = max(abs(w2h[i, j] - st['xf'][i, j]) for i in range(4) for j in range(4))
            if off > 1e-9:
                st['log'].append('hld %s: the engine\'s transform differs from the viewport\'s by %g' % (pass_id, off))
    else:
        # the engine's space: x c / -z and depth c - c^2 / -z, c its depth unit (Rhino 8, measured: from the box round
        # the loose boxes of what it draws, about half its farthest depth). A lateral tolerance tol_h there is tol on
        # paper's scale at L when tol_h = tol c / L; scaling every moved curve about the camera by s = 1 - 2 BIAS tol_h
        # / c moves each of its points at least BIAS tol_h in the engine's depth. c is estimated from the boxes' corners
        # and drawn at that within 5 percent of the engine's, else at the engine's: found ahead (unit_ahead) and checked
        # against the engine's after, else read from a first compute and computed again
        far = 0.0
        for n in add:
            for q in geo.get(n, objs[n]['geom']).GetBoundingBox(True).GetCorners():
                far = max(far, -(st['xf'] * q).Z)
        for w, other, c in contacts:
            for q in c.GetBoundingBox(True).GetCorners():
                far = max(far, -(st['xf'] * q).Z)
        cc = max(far / 2, P['near'])
        hld_tol = tol * cc / P['L']
        sc_ = 1.0 - 2 * BIAS * hld_tol / cc
        ahead = unit_ahead(hld_tol, G.Transform.Scale(P['cam'], sc_))
        h = None
        if ahead is not None and abs(ahead / cc - 1) > 0.05:
            hld_tol = tol * ahead / P['L']
            sc_ = 1.0 - 2 * BIAS * hld_tol / ahead
            h = compute(hld_tol, G.Transform.Scale(P['cam'], sc_))
            if h is not None and unit_of(h) == ahead:
                st['log'].append('hld %s: the engine\'s depth unit is %.4g, not %.4g; found ahead' % (pass_id, ahead, cc))
                cc = ahead
            else:
                h = None
        if h is None:
            for attempt in range(2):
                hld_tol = tol * cc / P['L']
                sc_ = 1.0 - 2 * BIAS * hld_tol / cc
                h = compute(hld_tol, G.Transform.Scale(P['cam'], sc_))
                if h is None:
                    break
                c_eng = unit_of(h)
                if abs(c_eng / cc - 1) <= 0.05:
                    break
                st['log'].append('hld %s: the engine\'s depth unit is %.4g, not %.4g; %s' % (
                    pass_id, c_eng, cc, 'computed again' if attempt == 0 else 'kept'))
                cc = c_eng
        moved = lambda q: (q.X / sc_, q.Y / sc_, q.Z / sc_)
        st['hld_c'] = cc / P['L']
    if h is None:
        st['log'].append('hld %s: the engine returned nothing' % pass_id)
        return
    if pass_id == 'main':
        for i, (po, pn) in enumerate(planes):
            if back_of(st, po, pn):
                st['log'].append('clip plane %d is seen from the half it keeps: its cut faces away from the camera' % i)
    segs = segments_of(h, keep, pass_id, st, moved, hidden_o, 'above' if pass_id == 'above' else None, pass_id != 'above')
    st['segs'] += segs
    cuts = [x for x in segs if 'cut' in x]
    st['log'].append('hld %s: %d objects in, %d segments%s' % (pass_id, len(add), len(segs), ', %d of them cuts (%d on the view\'s edge)' % (
        len(cuts), sum(1 for x in cuts if x['cut'] < 0)) if cuts else ''))


# ---------------------------------------------------------------- rings

def rings_one(req, st, n):
    """the cut of object n by every clip plane facing the camera, from the model: closed polylines in drawing
    coordinates, each clipped by the other planes' kept halves and, in a perspective, by the view. The engine's own
    cut segments are not enough: on the P2 site model it left out one home's edge where the home below shared it"""
    o = st['objs'][n]
    tol = st['tol']
    out = []
    for i, (po, pn) in enumerate(st['planes']):
        if back_of(st, po, pn):
            continue
        pl = G.Plane(po, pn)
        if o['kind'] == 'brep':
            ok, crvs, pts = Intersection.BrepPlane(o['geom'], pl, tol)
            crvs = list(G.Curve.JoinCurves(crvs, tol * 2)) if ok and crvs else []
            polys = []
            for c in crvs:
                ok, q = c.TryGetPolyline()
                if not ok:
                    q = c.ToPolyline(st['chord'], math.radians(3.0), 0.0, 0.0)
                    q = q.ToPolyline() if q is not None else None
                if q is not None:
                    polys.append((list(q), c.IsClosed))
        else:
            polys = [(list(q), q.IsClosed) for q in (Intersection.MeshPlane(o['geom'], pl) or [])]
        for q, closed in polys:
            if not closed:
                o['issues'].append('the cut by clip plane %d does not close' % i)
                continue
            ring = [(p.X, p.Y, p.Z) for p in q]
            if ring[0] == ring[-1]:
                ring = ring[:-1]
            for j, (qo, qn) in enumerate(st['planes']):
                if j != i:
                    ring = clip_poly(ring, lambda p: (p[0] - qo.X) * qn.X + (p[1] - qo.Y) * qn.Y + (p[2] - qo.Z) * qn.Z)
            r = [[st['xf'][a, b] for b in range(4)] for a in range(3)]
            ring = [tuple(r[a][0] * p[0] + r[a][1] * p[1] + r[a][2] * p[2] + r[a][3] for a in range(3)) for p in ring]
            P = st['persp']
            if P is not None:                            # the view's pyramid, in camera coordinates
                L, sh, a_, b_ = P['L'], P['shift'], st['hw'] * 1.02, st['hh'] * 1.02
                for f in (lambda p: -P['near'] - p[2], lambda p: -(L * p[0] + a_ * p[2]), lambda p: L * p[0] - a_ * p[2],
                          lambda p: -(L * p[1] + (b_ + sh) * p[2]), lambda p: L * p[1] + (sh - b_) * p[2]):
                    ring = clip_poly(ring, f)
            if len(ring) >= 3:
                out.append(dict(o=n, cut=i, pts=[[round(v, st['digits']) for v in project(st, p)] for p in ring]))
    return out


# ---------------------------------------------------------------- meshes

def twist_cap(face, tol, mtol):
    """the longest mesh edge that keeps a twisted ruled face within tol of its mesh, or None: a face straight in one
    direction and not planar (a roof lofted between an eave and a ridge). Rhino's mesher tests a quad's edges, which on
    such a face lie on it, and not the diagonal each quad is split along: the model's twisted roof faces meshed up to
    200 mm off at a tolerance of 1.8 mm"""
    srf = face.UnderlyingSurface()
    ns = srf.ToNurbsSurface()
    if ns is None or min(ns.Degree(0), ns.Degree(1)) > 1 or face.IsPlanar(mtol):
        return None
    su = sv = tw = 0.0
    us, vs = list(srf.GetSpanVector(0)), list(srf.GetSpanVector(1))
    for i in range(len(us) - 1):
        for j in range(len(vs) - 1):
            for a in range(5):
                for b in range(5):
                    ok, p, d = srf.Evaluate(us[i] + (us[i + 1] - us[i]) * a / 4, vs[j] + (vs[j + 1] - vs[j]) * b / 4, 2)
                    if not ok:
                        continue
                    su, sv = max(su, d[0].Length), max(sv, d[1].Length)
                    nrm = G.Vector3d.CrossProduct(d[0], d[1])
                    if nrm.Length > 0:
                        tw = max(tw, abs(d[3] * nrm) / nrm.Length)
    # the grid is even across a face, a cell L / max |Su| by L / max |Sv| in its parameters, and split in two it strays
    # |Suv. n| du dv / 4 off; half that for the triangles along trims (on the model's outer roof skin, 1.6 times tol at
    # the full length and within 1.06 times it at 0.7 of it)
    return math.sqrt(2 * tol * su * sv / tw) if tw > 0 else None


def pinned(a, out):
    """numpy array out filled with the bytes of.NET array a, copied whole while it is pinned"""
    import ctypes
    import System
    if out.nbytes:
        h = System.Runtime.InteropServices.GCHandle.Alloc(a, System.Runtime.InteropServices.GCHandleType.Pinned)
        try:
            ctypes.memmove(out.ctypes.data, h.AddrOfPinnedObject().ToInt64(), out.nbytes)
        finally:
            h.Free()
    return out


def mesh_arrays(m):
    """a mesh's vertices in double precision, (n, 3), and its triangles, (m, 3): a Point3d is three doubles, and the
    faces are triangles by now. 160,000 vertices took 0.7 ms against 276 ms read one by one """
    pts, fs = m.Vertices.ToPoint3dArray(), m.Faces.ToIntArray(True)
    return pinned(pts, np.empty((len(pts), 3))), pinned(fs, np.empty((len(fs) // 3, 3), dtype=np.int32))


def clip_batch(tris, distances):
    """clip_tri for many triangles (n, 3, 3) at once, their vertices' distances (n, 3) given: the parts where the
    distance is not negative, as triangles in clip_tri's fan order and with its arithmetic in the same order"""
    inside = distances >= 0
    count = inside.sum(axis=1)
    if np.all(count == 3):
        return tris
    if np.all(count == 0):
        return tris[:0]
    tris, distances, inside = tris[count > 0], distances[count > 0], inside[count > 0]
    poly = np.empty((len(tris), 4, 3), dtype=np.float64)
    cursor = np.zeros(len(tris), dtype=np.intp)
    rows = np.arange(len(tris))
    for i in range(3):
        j = (i + 1) % 3
        keep = inside[:, i]
        poly[rows[keep], cursor[keep]] = tris[keep, i]
        cursor[keep] += 1
        cross = keep != inside[:, j]
        a, b = distances[cross, i], distances[cross, j]
        t = a / (a - b)
        p, q = tris[cross, i], tris[cross, j]
        poly[rows[cross], cursor[cross]] = p + (q - p) * t[:, None]
        cursor[cross] += 1
    sizes = cursor - 2
    offsets = np.cumsum(sizes) - sizes
    out = np.empty((int(sizes.sum()), 3, 3), dtype=np.float64)
    out[offsets] = poly[:, :3]
    quad = sizes == 2
    out[offsets[quad] + 1] = poly[quad][:, [0, 2, 3]]
    return out


def mesh_camera(points, r):
    """points (..., 3) in camera space by the world-to-camera rows r, summed in the order mesh_one's cam sums them"""
    out = np.empty_like(points)
    for i in range(3):
        out[..., i] = (r[i, 0] * points[..., 0] + r[i, 1] * points[..., 1]
                       + r[i, 2] * points[..., 2] + r[i, 3])
    return out


def mesh_tail(st, n, V, F):
    """mesh_one's writing of a mesh, vertices V (n, 3) and triangles F (m, 3), in numpy and in chunks of 32,768
    triangles: the same bytes as the Python tail (tests/run.py, export-mesh)"""
    v0, f0 = len(st['mesh_v']) // 3, len(st['mesh_f']) // 3
    r = np.array([[st['xf'][i, j] for j in range(4)] for i in range(3)])
    P = st['persp']
    if not st['planes'] and P is None:
        out = mesh_camera(V, r) - st['origin']
        st['mesh_v'].frombytes(out.astype(np.float32).tobytes())
        st['mesh_f'].frombytes(F.tobytes())
        st['mesh_items'].append(dict(o=n, v0=v0, nv=len(V), f0=f0, nf=len(F)))
        return
    nv = 0
    for start in range(0, len(F), 32768):
        tris = V[F[start:start + 32768]]
        for po, pn in st['planes']:
            d = ((tris[..., 0] - po.X) * pn.X + (tris[..., 1] - po.Y) * pn.Y
                 + (tris[..., 2] - po.Z) * pn.Z)
            tris = clip_batch(tris, d)
        tris = mesh_camera(tris, r)
        if P is not None:
            tris = clip_batch(tris, -P['near'] - tris[..., 2])
            z = -tris[..., 2]
            tris[..., 0] = P['L'] * tris[..., 0] / z
            tris[..., 1] = P['L'] * tris[..., 1] / z - P['shift']
        out = tris - st['origin']
        st['mesh_v'].frombytes(out.astype(np.float32).tobytes())
        size = 3 * len(tris)
        st['mesh_f'].frombytes(np.arange(nv, nv + size, dtype=np.int32).tobytes())
        nv += size
    st['mesh_items'].append(dict(o=n, v0=v0, nv=nv, f0=f0, nf=nv // 3))


def mesh_one(st, n, mp):
    o = st['objs'][n]
    if o['kind'] == 'brep':
        b = o['geom']
        ms = G.Mesh.CreateFromBrep(b, mp)
        if not ms:
            o['issues'].append('no mesh')
            return
        ms = list(ms)
        caps = [twist_cap(fc, mp.Tolerance, st['mtol']) for fc in b.Faces]
        caps = [c if c is not None and c < fc.GetBoundingBox(True).Diagonal.Length else None for c, fc in zip(caps, b.Faces)]
        if len(ms) != b.Faces.Count and any(c is not None for c in caps):
            # the mesher left a face out (one of no area, on the model's roof) and its meshes no longer follow the faces: each
            # face meshed on its own, so a twisted one is capped (the roof's meshed 0.65 ft off at 0.0056 ft)
            ms = []
            for fc in b.Faces:
                one = G.Mesh()
                for x in G.Mesh.CreateFromBrep(fc.DuplicateFace(False), mp) or []:
                    one.Append(x)
                ms.append(one)
        if len(ms) == b.Faces.Count:                       # a mesh a face, in the faces' order
            for i, fc in enumerate(b.Faces):
                cap = caps[i]
                if cap is not None:
                    fp = G.MeshingParameters()
                    fp.CopyFrom(mp)
                    fp.MaximumEdgeLength = cap
                    fm = G.Mesh.CreateFromBrep(fc.DuplicateFace(False), fp)
                    if fm:
                        ms[i] = G.Mesh()
                        for x in fm:
                            ms[i].Append(x)
        m = G.Mesh()
        for x in ms:
            m.Append(x)
    elif o['kind'] == 'mesh':
        m = o['geom'].DuplicateMesh()
    else:
        return
    m.Faces.ConvertQuadsToTriangles()
    if np is not None:
        V, F = mesh_arrays(m)
        mesh_tail(st, n, V, F)
        return
    v0 = len(st['mesh_v']) // 3
    f0 = len(st['mesh_f']) // 3
    P = st['persp']
    xf = st['xf']
    r = [[xf[i, j] for j in range(4)] for i in range(3)]
    cam = lambda q: tuple(r[i][0] * q[0] + r[i][1] * q[1] + r[i][2] * q[2] + r[i][3] for i in range(3))
    ox_, oy_, oz_ = st['origin']
    # in double precision, transformed here: a mesh's own vertices may be single, which at 78,740 in rounds 0.2 pt off
    V = [(p.X, p.Y, p.Z) for p in m.Vertices.ToPoint3dArray()]
    if not st['planes'] and P is None:
        for p in V:
            q = cam(p)
            st['mesh_v'].extend((q[0] - ox_, q[1] - oy_, q[2] - oz_))
        nf = 0
        for f in m.Faces:
            st['mesh_f'].extend((f.A + 0, f.B + 0, f.C + 0))
            nf += 1
        st['mesh_items'].append(dict(o=n, v0=v0, nv=len(V), f0=f0, nf=nf))
        return
    # clipped as the drawing is: by the planes in the model, then by the camera's near plane, each triangle apart
    tris = [(V[f.A], V[f.B], V[f.C]) for f in m.Faces]
    for po, pn in st['planes']:
        ox, oy, oz, nx, ny, nz = po.X, po.Y, po.Z, pn.X, pn.Y, pn.Z
        f = lambda q: (q[0] - ox) * nx + (q[1] - oy) * ny + (q[2] - oz) * nz
        tris = [t for tri in tris for t in clip_tri(tri, f)]
    tris = [tuple(cam(q) for q in tri) for tri in tris]
    if P is not None:
        near = P['near']
        tris = [t for tri in tris for t in clip_tri(tri, lambda q: -near - q[2])]
        tris = [tuple(project(st, q) for q in tri) for tri in tris]
    for tri in tris:
        for q in tri:
            st['mesh_v'].extend((q[0] - ox_, q[1] - oy_, q[2] - oz_))
    nv = 3 * len(tris)
    st['mesh_f'].extend(range(nv))
    st['mesh_items'].append(dict(o=n, v0=v0, nv=nv, f0=f0, nf=len(tris)))


# ---------------------------------------------------------------- run

def write(req, st, out, t0):
    """scene.json and meshes.bin in out; the write's own seconds (from t0) in scene.json, all but writing its text"""
    objs = []
    for n, o in enumerate(st['objs']):
        objs.append(dict(i=n, ids=o['ids'], group=o['group'], layer=o['layer'], kind=o['kind'], solid=o.get('solid'),
                         user=o['user'], issues=o['issues'], parts=o.get('parts', 1)))
    xf = st['xf']
    view = dict(xform=[[xf[i, j] for j in range(4)] for i in range(4)], half_w=st['hw'], half_h=st['hh'],
                pt_per_unit=st['k'], true_factor=st['f'], direction=[st['dir'].X, st['dir'].Y, st['dir'].Z],
                projection='parallel' if st['persp'] is None else 'perspective')
    P = st['persp']
    if P is not None:
        view.update(camera=[P['cam'].X, P['cam'].Y, P['cam'].Z], focal=P['L'], near=P['near'], shift=P['shift'],
                    lens_mm=P['lens'])
    scene = dict(version=4, request=os.path.basename(st['path']), model=st['model'], units=st['units'], unit_mm=st['unit_mm'],
                 tolerance=st['tol'], bias=st['tol'] * BIAS, view=view,
                 clip=[dict(origin=[po.X, po.Y, po.Z], normal=[pn.X, pn.Y, pn.Z]) for po, pn in st['planes']],
                 objects=objs, rings=st.get('rings', []), contacts=len(st['contacts']), segments=[dict((k.rstrip('_'), v) for k, v in s.items()) for s in st['segs']],
                 meshes=dict(file='meshes.bin', vertices=len(st['mesh_v']) // 3, triangles=len(st['mesh_f']) // 3, items=st['mesh_items'],
                             origin=list(st['origin'])),
                 log=st['log'])
    if not os.path.isdir(out):
        os.makedirs(out)
    with open(os.path.join(out, 'meshes.bin'), 'wb') as fh:
        st['mesh_v'].tofile(fh)
        st['mesh_f'].tofile(fh)
    text = json.dumps(scene)
    st['seconds']['write'] = round(st['seconds'].get('write', 0) + time.time() - t0, 2)
    with open(os.path.join(out, 'scene.json'), 'w') as fh:
        fh.write(text[:-1] + ', "seconds": ' + json.dumps(st['seconds']) + '}')   # json.dump's text, seconds last
    bad = sum(1 for o in objs if o['issues'])
    return 'done: %d objects (%d with issues), %d contact curves, %d segments, %d triangles, in %s' % (
        len(objs), bad, len(st['contacts']), len(st['segs']), len(st['mesh_f']) // 3, out)


def write_check(st, out):
    """check.json: each object with issues, its ids, group and layer"""
    rows = [dict(ids=o['ids'], group=o['group'], layer=o['layer'], issues=o['issues']) for o in st['objs'] if o['issues']]
    if not os.path.isdir(out):
        os.makedirs(out)
    with open(os.path.join(out, 'check.json'), 'w') as fh:
        json.dump(dict(model=st['model'], objects=len(st['objs']), with_issues=rows, log=st['log']), fh, indent=1)
    kinds = {}
    for r in rows:
        for i in r['issues']:
            k = re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27}', 'another', i).split(':')[0].split(' (')[0].split(' by ')[0]
            k = ' '.join(w for w in k.split() if not re.match(r'^[\d.]+$', w))
            kinds[k] = kinds.get(k, 0) + 1
    return 'checked: %d of %d objects with issues (%s), in %s' % (len(rows), len(st['objs']),
                                                                ', '.join('%s %d' % kv for kv in sorted(kinds.items())), out)


def main():
    doc = doc_of()
    path = pick()
    if not path:
        return 'no request'
    path = os.path.abspath(path)
    req = json.load(open(path))
    budget = float(globals().get('BUDGET', 40.0))
    key = (path, os.path.getmtime(path), str(doc.RuntimeSerialNumber))
    st = sc.sticky.get(KEY)
    if st is None or st.get('key') != key or globals().get('RESET'):
        try:
            vi, xf, d, hw, hh, k, f, persp = view_of(req, doc)
            planes = planes_of(req)
        except ValueError as e:
            return 'error: %s' % e
        unit_mm = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
        tol = float(req.get('tolerance_pt', TOL_PT)) / k
        tq = xf * G.Point3d(*req['view']['target'])
        origin = (0.0, 0.0, tq.Z)                      # the meshes are written less this, in camera space
        st = dict(key=key, path=path, model=doc.Path or doc.Name or '', units=str(doc.ModelUnitSystem), unit_mm=unit_mm,
                  mtol=doc.ModelAbsoluteTolerance, unit={1.0: 'mm', 10.0: 'cm', 1000.0: 'm', 25.4: 'in', 304.8: 'ft'}.get(round(unit_mm, 6), 'units'),
                  vi=vi, xf=xf, dir=d, hw=hw, hh=hh, k=k, f=f, persp=persp, planes=planes, tol=tol,
                  chord=float(req.get('tolerance_pt', TOL_PT)) / k,
                  ctol=2.0 ** (math.frexp(tol)[1] - 1),     # the union's, the cut's and the contacts' (ladder)
                  digits=max(0, int(math.ceil(-math.log10(tol))) + 2),
                  stage=0, cursor=0, log=[], seconds={}, segs=[], mesh_v=array.array('f'), mesh_f=array.array('i'),
                  mesh_items=[], origin=origin, naked={}, digest={}, cache=CACHE,
                  build='%s %s %s' % (Rhino.RhinoApp.Version, sys.platform, platform.machine()))
        sc.sticky[KEY] = st
    out = os.path.join(os.path.dirname(path), req.get('out', 'hidden-lines'))
    t0 = time.time()
    left = lambda: budget - (time.time() - t0)
    ts = None
    while st['stage'] < len(STAGES):
        name = STAGES[st['stage']]
        ts = time.time()
        if name == 'collect':
            collect(req, doc, st)
        elif name == 'union':
            if st['cursor'] == 0:
                union_jobs(req, st)
            jobs = st['union_jobs']
            while st['cursor'] < len(jobs) and left() > 0:
                union_one(st, jobs[st['cursor']])
                st['cursor'] += 1
            if st['cursor'] < len(jobs):
                break
            joined = sum(1 for o in st['union_out'] if o.get('parts', 1) > 1)
            st['objs'] = [st['objs'][n] for n in st['union_keep']] + st['union_out']
            st['log'].append('union: %d unions of %d parts' % (joined, sum(o.get('parts', 1) for o in st['union_out'] if o.get('parts', 1) > 1)))
        elif name == 'cut':
            if st['cursor'] == 0:
                st['cut_out'] = []
                st['cut_prisms'] = {}
                for g in req['groups']:
                    if g.get('cut'):
                        st['cut_prisms'][g['id']] = [prisms_of(r, -1000.0, 1000.0, st['ctol']) for r in rings(g['cut'])]
            objs = st['objs']
            while st['cursor'] < len(objs) and left() > 0:
                o = objs[st['cursor']]
                pr = st['cut_prisms'].get(o['group'])
                st['cut_out'] += cut_one(st, o, pr) if pr else [o]
                st['cursor'] += 1
            if st['cursor'] < len(objs):
                break
            st['log'].append('cut: %d objects become %d' % (len(objs), len(st['cut_out'])))
            st['objs'] = st['cut_out']
        elif name == 'validate':
            for o in st['objs']:
                validate_one(o, st)
            duplicates(st)
        elif name == 'pairs':
            cache_trim(st['cache'])
            pair_list(req, st)
        elif name == 'checks':
            if st['cursor'] == 0:
                st['faces'], st['touching'], st['opens'] = {}, {}, open_pairs(req, st)
                st['hides'] = {g['id']: g.get('hides', True) for g in req['groups']}
                # two objects of context are not checked against each other but in a check of the model: a site's
                # bought or traced buildings run into themselves everywhere (the model's 7,943 clashes and 5,018 shared
                # edges among window frames), which says nothing of the design and took 15 of the export's 23 minutes
                ctx = set() if globals().get('CHECK') else {g['id'] for g in req['groups'] if g.get('layer', 'CONTEXT') == 'CONTEXT'}
                grp = [o['group'] for o in st['objs']]
                st['check_pairs'] = [(i, j) for i, j in st['pairs'] if not (grp[i] in ctx and grp[j] in ctx)]
                st['opens'] = [(i, j) for i, j in st['opens'] if grp[i] not in ctx]
            jobs = st['check_pairs'] + st['opens']
            while st['cursor'] < len(jobs) and left() > 0:
                i, j = jobs[st['cursor']]
                (check_pair if st['cursor'] < len(st['check_pairs']) else check_open)(st, i, j)
                st['cursor'] += 1
            if st['cursor'] < len(jobs):
                break
            unions = {g['id'] for g in req['groups'] if g.get('union')}
            for gid, n in sorted(st['touching'].items()):
                if gid not in unions:
                    st['log'].append('checks: %d pairs of %s touch face to face with no union key; their shared faces '
                                     'draw as seams' % (n, gid))
            st['faces'] = None
            bad = sum(1 for o in st['objs'] if o['issues'])
            st['log'].append('checks: %d of %d objects with issues' % (bad, len(st['objs'])))
            if globals().get('CHECK'):
                msg = write_check(st, out)
                sc.sticky.pop(KEY, None)
                return msg
        elif name == 'contacts':
            while st['cursor'] < len(st['pairs']) and left() > 0:
                i, j = st['pairs'][st['cursor']]
                contact_one(req, st, i, j)
                st['cursor'] += 1
            if st['cursor'] < len(st['pairs']):
                break
            st['log'].append('contacts: %d curves' % len(st['contacts']))
        elif name == 'hld':
            passes = ['main'] + [g['id'] for g in req['groups'] if not g.get('hides', True) and g.get('draw', True)] + (
                ['above'] if st['planes'] and any(g.get('above') for g in req['groups']) else [])
            while st['cursor'] < len(passes) and left() > 0:
                hld_one(req, st, passes[st['cursor']])
                st['cursor'] += 1
            if st['cursor'] < len(passes):
                break
        elif name == 'rings':
            if st['cursor'] == 0:
                st['rings'] = []
            if st['planes']:
                hides = {g['id']: g.get('hides', True) for g in req['groups']}
                draws = {g['id']: g.get('draw', True) for g in req['groups']}
                objs = st['objs']
                while st['cursor'] < len(objs) and left() > 0:
                    o = objs[st['cursor']]
                    if o.get('solid') and hides[o['group']] and draws[o['group']]:
                        st['rings'] += rings_one(req, st, st['cursor'])
                    st['cursor'] += 1
                if st['cursor'] < len(objs):
                    break
                st['log'].append('rings: %d cuts of %d objects' % (len(st['rings']), len(set(r['o'] for r in st['rings']))))
        elif name == 'meshes':
            mp = G.MeshingParameters()
            mp.Tolerance = MESH_PT / st['k']
            mp.JaggedSeams = False
            mp.SimplePlanes = True
            mp.RefineGrid = True
            mp.GridAngle = math.radians(15.0)
            meshed = {g['id']: g.get('mesh', g.get('hides', True)) for g in req['groups']}
            while st['cursor'] < len(st['objs']) and left() > 0:
                if meshed[st['objs'][st['cursor']]['group']]:
                    mesh_one(st, st['cursor'], mp)
                st['cursor'] += 1
            if st['cursor'] < len(st['objs']):
                break
        elif name == 'write':
            msg = write(req, st, out, ts)
            sc.sticky.pop(KEY, None)
            print('hidden_lines: ' + msg)
            return msg
        st['seconds'][name] = round(st['seconds'].get(name, 0) + time.time() - ts, 2)
        ts = None
        st['stage'] += 1
        st['cursor'] = 0
        if left() <= 0:
            break
    if ts is not None:                                 # a stage left part done: its time so far
        cur = STAGES[st['stage']]
        st['seconds'][cur] = round(st['seconds'].get(cur, 0) + time.time() - ts, 2)
    name = STAGES[st['stage']] if st['stage'] < len(STAGES) else 'write'
    return 'more: %s %d, %s' % (name, st['cursor'], '; '.join(st['log'][-2:]))


# ---------------------------------------------------------------- the HL command

OUT_LAYER = 'HL'                  # the command adds drawings under this layer, which collect never reads
SECTION = 'kit.hidden_lines'      # the document's strings holding the command's last choices
RESULTS = 'kit.hl.results'        # sticky key of the open results window
DRAWING_KEY = 'kit.hl.drawing'    # a layer's user text marking a drawing HL added, which HL does not draw again
RUNNING = 'kit.hl.running'        # sticky key naming the drawing an HL in this Rhino is making
HL_HOME = os.path.join(os.path.expanduser('~'), '.rhinocode', 'kit-hl')   # HL's kit, uv, downloads and logs
LOG = []                          # this run's lines, kept for hl.log
# kit.py hidden-lines and lint, at the last versions with wheels for Rhino 8's Python 3.9
PACKAGES = ['numpy==2.0.2', 'shapely==2.0.7', 'scipy==1.13.1', 'ezdxf==1.4.2', 'pillow==11.3.0', 'numba==0.60.0',
            'zstandard==0.25.0']


def hl_module():
    """rhino/hl.py, the command's choices worked out without Rhino, read fresh from beside this script"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('kit_hl', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hl.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rhino_python():
    """(Rhino's own Python 3, the folder HL installs the drawing's packages into for it)"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.__file__)))    #.../py39-rh8/lib/python3.9/os.py
    exe = os.path.join(root, 'python.exe' if os.name == 'nt' else 'python3.9')
    return exe, os.path.join(os.path.expanduser('~'), '.rhinocode', 'kit-hl', 'site')


STOPPED = -2                      # wait_for's exit code when Esc stopped the process


def say(line=''):
    """a line on the command line, kept for the run's log"""
    print(line)
    LOG.append(line)


def mac_malloc(env):
    """env with macOS's malloc returning freed large blocks at once, for the drawing it starts: on a drawing of 7
    million triangles a peak 0.6 to 0.8 GB lower and the same on every run, for about 4 percent more time"""
    if sys.platform == 'darwin':
        env.setdefault('MallocLargeCache', '0')
    return env


def kit_dir():
    """the folder holding the kit.py and archkit that draw: KIT_ROOT where the script that runs this one names it (a
    kit carrying its own tokens), else the folder above this script"""
    return globals().get('KIT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_log(folder=None):
    """the run's log, hl.log in folder, else hl-TIME.log in ~/.rhinocode/kit-hl/logs: what HL, Rhino and the computer
    are, then every line the run said; its path, or None where neither can be written"""
    import platform, sys
    kit = kit_dir()
    head = ['HL log, %s' % time.strftime('%Y-%m-%d %H:%M:%S'),
            'HL: %s' % ('plug-in %s' % KIT_VERSION if globals().get('KIT_VERSION') else 'the kit in %s' % kit),
            'Rhino %s on %s (%s)' % (Rhino.RhinoApp.Version, platform.platform(), platform.machine()),
            "Rhino's Python %s; the drawing step on %s" % (sys.version.split()[0],
                                                          globals().get('KIT_RUNTIME') or "the machine's python3"), '']
    for d in ([folder] if folder else []) + [os.path.join(os.path.expanduser('~'), '.rhinocode', 'kit-hl', 'logs')]:
        try:
            if not os.path.isdir(d):
                os.makedirs(d)
            path = os.path.join(d, 'hl.log' if d == folder else 'hl-%s.log' % time.strftime('%Y%m%d-%H%M%S'))
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(head + LOG) + '\n')
            return path
        except OSError:
            continue
    return None


def settings():
    """the user's HL settings across models (HL_HOME/settings.json): drawing choices and the update check"""
    try:
        return json.load(open(os.path.join(HL_HOME, 'settings.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_settings(**kw):
    s = dict(settings(), **kw)
    try:
        if not os.path.isdir(HL_HOME):
            os.makedirs(HL_HOME)
        with open(os.path.join(HL_HOME, 'settings.json'), 'w', encoding='utf-8') as fh:
            json.dump(s, fh, indent=1)
    except OSError:                                    # a setting not kept is no reason to stop a drawing
        pass


def kill_tree(p):
    """process p and what it started (uv's Python)"""
    import subprocess, signal
    if os.name == 'nt':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True)
    else:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except OSError:                                # gone already
            pass


def folder_lock(folder):
    """an open file holding a lock on folder/.hl-lock while this run draws there; False when another process holds it
    (another Rhino drawing the same name); None where the folder's file system has no locks (a network share)"""
    path = os.path.join(folder, '.hl-lock')
    fh = open(path, 'a+')
    try:
        if os.name == 'nt':
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError as e:
        fh.close()
        import errno
        return False if os.name == 'nt' or e.errno in (errno.EWOULDBLOCK, errno.EAGAIN) else None


def unlock(fh):
    """the folder's lock let go, and its file removed"""
    if fh:
        try:
            fh.close()
            os.remove(fh.name)
        except OSError:
            pass


def memory_gb():
    """the computer's memory in GB, as.NET reads it, or None"""
    import System
    try:
        return System.GC.GetGCMemoryInfo().TotalAvailableMemoryBytes / 1e9
    except Exception:                                  #.NET Framework 4.8 (Rhino's SetDotNetRuntime) has no such call
        return None


def redownload():
    """HL's downloaded Python and packages removed and downloaded again (setup), where they are HL's own; True once
    they are"""
    import shutil
    if globals().get('KIT_RUNTIME') == 'uv':
        own = [os.path.join(HL_HOME, 'uv')] if not ({'UV_CACHE_DIR', 'UV_PYTHON_INSTALL_DIR'} & set(os.environ)) else []
        marks = [os.path.join(HL_HOME, 'uv-ready')]
    else:
        own, marks = [rhino_python()[1]], []
    for d in own:
        shutil.rmtree(d, ignore_errors=True)
    for m in marks:
        if os.path.exists(m):
            os.remove(m)
    return setup(ask=False)


def wait_for(cmd, env):
    """a process run while Rhino keeps drawing, Esc stopping it and what it started, and so does Rhino closing the
    document or quitting: (exit code, output)"""
    import subprocess, tempfile
    with tempfile.TemporaryFile('w+', encoding='utf-8') as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env, start_new_session=os.name != 'nt')
        closed = []

        def gone(s, e):                                # else it runs on for minutes after Rhino has gone
            closed.append(True)
            kill_tree(p)
        Rhino.RhinoApp.Closing += gone
        Rhino.RhinoDoc.CloseDocument += gone
        try:
            while p.poll() is None:
                Rhino.RhinoApp.Wait()
                if sc.escape_test(False):
                    kill_tree(p)
                    p.wait()
                    return STOPPED, 'stopped'
                time.sleep(0.05)
        finally:
            Rhino.RhinoApp.Closing -= gone
            Rhino.RhinoDoc.CloseDocument -= gone
        if closed:                                     # stopped with Rhino or its document: no window to show
            return STOPPED, 'stopped: Rhino closed'
        fh.seek(0)
        return p.returncode, fh.read().strip()


def uv_command(kit):
    """(the command that runs kit.py through the uv the plug-in carries, on uv's own Python 3.12, its environment): the
    uv on the PATH, so kit.py reruns through it for its packages, uv's Python preferred to any on the machine, and no
    package built from source"""
    import shutil, stat
    src = globals()['KIT_UV_BIN']
    # kit.py reruns itself through the uv it finds by the name uv, and the plug-in's is named for its platform
    uv = os.path.join(os.path.expanduser('~'), '.rhinocode', 'kit-hl', 'bin', 'uv.exe' if os.name == 'nt' else 'uv')
    if not os.path.exists(uv) or os.path.getsize(uv) != os.path.getsize(src):
        if not os.path.isdir(os.path.dirname(uv)):
            os.makedirs(os.path.dirname(uv))
        shutil.copyfile(src, uv)
        os.chmod(uv, os.stat(uv).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    # UV_NO_BUILD: wheels only, so an Intel Mac takes numba 0.62.1, the last with its wheels, where llvmlite 0.50's
    # source build needs cmake
    env = dict(os.environ, PYTHONIOENCODING='utf-8', UV_PYTHON_PREFERENCE='only-managed', UV_NO_BUILD='1',
               PATH=os.pathsep.join([os.path.dirname(uv), os.environ.get('PATH', '')]))
    # uv's Python and packages in HL's own folders, which redownload can remove without touching another uv's cache
    mac_malloc(env)
    env.setdefault('UV_CACHE_DIR', os.path.join(HL_HOME, 'uv', 'cache'))
    env.setdefault('UV_PYTHON_INSTALL_DIR', os.path.join(HL_HOME, 'uv', 'python'))
    return [uv, 'run', '--quiet', '--no-project', '--python', '3.12', 'python', os.path.join(kit, 'kit.py')], env


def kit_run(args):
    """kit.py of this script's kit run outside Rhino: (exit code, output). With KIT_RUNTIME in the script's globals
    (the plug-in), 'uv' runs it through the uv it carries (uv_command) and 'rhino' on Rhino's own Python with the
    packages setup installed; otherwise it runs on the machine's python3, which reruns through uv for its packages"""
    import shutil
    kit = kit_dir()
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    mac_malloc(env)
    if globals().get('KIT_RUNTIME') == 'uv':
        cmd, env = uv_command(kit)
        return wait_for(cmd + args, env)
    if globals().get('KIT_RUNTIME') == 'rhino':
        py, site = rhino_python()
        if not os.path.isdir(site):
            return 1, 'the packages the drawing needs are not installed (HL installs them on its first run)'
        compat = os.path.join(kit, 'rhino', 'plugin', 'compat')       # shapely 2.1's maximum_inscribed_circle on 2.0
        env.update(PYTHONPATH=os.pathsep.join([compat, site]), PYTHONNOUSERSITE='1',
                   NUMBA_CACHE_DIR=os.path.join(os.path.dirname(site), 'numba'))
        return wait_for([py, '-B', os.path.join(kit, 'kit.py')] + args, env)
    path = os.pathsep.join([os.environ.get('PATH', ''), '/opt/homebrew/bin', '/usr/local/bin'])
    py = shutil.which('python3', path=path) or shutil.which('python', path=path)
    if not py:
        return 1, 'no python3 on the PATH'
    env['PATH'] = path
    return wait_for([py, os.path.join(kit, 'kit.py')] + args, env)


def setup(ask=True):
    """what the drawing runs on, downloaded once if the user agrees: for the uv runtime, Python 3.12 and the kit's
    packages into uv's cache, marked done in ~/.rhinocode/kit-hl/uv-ready; for the rhino runtime, the packages for
    Rhino's own Python into rhino_python's folder. True once they are there"""
    import Eto.Forms as forms
    if globals().get('KIT_RUNTIME') == 'uv':
        mark = os.path.join(os.path.expanduser('~'), '.rhinocode', 'kit-hl', 'uv-ready')
        if os.path.exists(mark):
            return True
        if ask and forms.MessageBox.Show(Rhino.UI.RhinoEtoApp.MainWindow, 'HL draws with Python 3.12 and a few '
                                         'packages (numpy, shapely and others), which it downloads once, about 700 '
                                         'MB, into its own folder. Download them now?', 'HL: first run',
                                         forms.MessageBoxButtons.YesNo) != forms.DialogResult.Yes:
            return False
        print('HL: downloading what the drawing needs, once (about 700 MB; a minute or two)')
        Rhino.UI.StatusBar.SetMessagePane('HL: downloading Python and packages...')
        cmd, env = uv_command(kit_dir())
        code, text = wait_for(cmd + ['hidden-lines'], env)    # kit.py installs the packages, then exits on its usage
        Rhino.UI.StatusBar.ClearMessagePane()
        if 'kit.py hidden-lines REQUEST' not in text:
            say(text[-1500:])
            log = write_log()
            forms.MessageBox.Show(Rhino.UI.RhinoEtoApp.MainWindow, 'The download stopped (is the computer online?). '
                                  'Run HL again to retry. uv\'s last words are in the log: %s' % log, 'HL',
                                  forms.MessageBoxType.Error)
            return False
        if not os.path.isdir(os.path.dirname(mark)):
            os.makedirs(os.path.dirname(mark))
        open(mark, 'w').write(text[-200:])
        return True
    py, site = rhino_python()
    if os.path.isdir(site):
        return True
    if ask and forms.MessageBox.Show(Rhino.UI.RhinoEtoApp.MainWindow, 'HL draws with a few Python packages (numpy, shapely '
                             'and others), which it downloads once, about 300 MB, into %s. Download them now?' % site,
                             'HL: first run', forms.MessageBoxButtons.YesNo) != forms.DialogResult.Yes:
        return False
    print('HL: downloading what the drawing needs, once (about 300 MB; a minute or two)')
    Rhino.UI.StatusBar.SetMessagePane('HL: downloading packages...')
    tmp = site + '.part'
    code, text = wait_for([py, '-m', 'pip', 'install', '--disable-pip-version-check', '--target', tmp] + PACKAGES,
                          dict(os.environ, PYTHONNOUSERSITE='1'))
    Rhino.UI.StatusBar.ClearMessagePane()
    if code:
        say(text[-1500:])
        log = write_log()
        forms.MessageBox.Show(Rhino.UI.RhinoEtoApp.MainWindow, 'The download stopped (is the computer online?). Run HL '
                              'again to retry. pip\'s last words are in the log: %s' % log, 'HL', forms.MessageBoxType.Error)
        return False
    os.rename(tmp, site)
    return True


def from_viewport(doc, vp, scale, frame=None, info=None):
    """a request's view, frame and clip planes from a viewport, or from info, a named view's ViewportInfo, read as it
    was saved without changing the viewport: its camera aimed at the middle of what it shows, its extent at the scale
    (a perspective's at its target's depth) or the frame given, and the clipping planes that clip the viewport, a plane
    with a depth adding the plane that faces it at that depth"""
    unit_mm = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
    k = PT_PER_MM * unit_mm / float(scale)
    src = info or vp
    ok, l, r, b, t, n, f = src.GetFrustum()
    cam = src.CameraLocation
    if info:
        right, up, d = info.CameraX, info.CameraY, info.CameraZ * -1.0
        depth = info.TargetDistance(True)              # the frustum's middle where the view saved no target
    else:
        fr = vp.GetCameraFrame()[1]                    # x right, y up the view, z back toward the camera
        right, up, d = fr.XAxis, fr.YAxis, fr.ZAxis * -1.0
        depth = (vp.CameraTarget - cam) * d
    q = 1.0 if src.IsParallelProjection else depth / n    # the frustum's extent at the target per its extent at near
    c = cam + d * depth + right * ((l + r) / 2 * q) + up * ((b + t) / 2 * q)
    view = dict(target=[c.X, c.Y, c.Z], up=[up.X, up.Y, up.Z])
    if src.IsParallelProjection:
        view['direction'] = [d.X, d.Y, d.Z]
    else:
        view.update(camera=[cam.X, cam.Y, cam.Z], lens_mm=round(36.0 * n / (r - l), 4))   # 36 mm of film across
        if src.IsTwoPointPerspectiveProjection:
            view['two_point'] = True
    w, h = (r - l) * q * k, (t - b) * q * k
    if frame:
        w, h = float(frame['w_pt']), float(frame['h_pt'])
    clip = []
    for o in clip_objects(doc):
        if vp.Id in list(o.Geometry.ViewportIds()):
            clip += plane_spec(o.Geometry)
    return view, dict(w_pt=round(w, 2), h_pt=round(h, 2)), clip


def clip_objects(doc):
    """the document's clipping planes, hidden ones too: hiding one is how one is kept"""
    es = Rhino.DocObjects.ObjectEnumeratorSettings()
    es.HiddenObjects = True
    es.ObjectTypeFilter = Rhino.DocObjects.ObjectType.ClipPlane
    return list(doc.Objects.GetObjectList(es))


def plane_spec(g):
    """a clipping plane as the request's clip: its plane, normal into the half it keeps, and with a depth the plane
    facing it at that depth"""
    p = g.Plane
    out = [dict(origin=[p.Origin.X, p.Origin.Y, p.Origin.Z], normal=[p.Normal.X, p.Normal.Y, p.Normal.Z])]
    if g.PlaneDepthEnabled:
        e = p.Origin + p.Normal * g.PlaneDepth
        out.append(dict(origin=[e.X, e.Y, e.Z], normal=[-p.Normal.X, -p.Normal.Y, -p.Normal.Z]))
    return out


def drawable(doc, vp, selected):
    """[(object, layer path)] HL draws: the objects selected, or everything shown in the viewport; never a clipping
    plane, a light, text, a dimension or what is on HL"""
    T = Rhino.DocObjects.ObjectType
    kinds = int(T.Brep) | int(T.Surface) | int(T.Extrusion) | int(T.SubD) | int(T.Mesh) | int(T.Curve) | int(T.InstanceReference)
    if selected:
        objs = [o for o in doc.Objects.GetSelectedObjects(False, False) if int(o.ObjectType) & kinds]
    else:
        s = Rhino.DocObjects.ObjectEnumeratorSettings()
        s.VisibleFilter = True
        s.ViewportFilter = vp
        s.LockedObjects = True
        s.ObjectTypeFilter = T(kinds)
        objs = list(doc.Objects.GetObjectList(s))
    paths = {}
    out = []
    drawn_ = drawing_layers(doc)
    for o in objs:
        i = o.Attributes.LayerIndex
        if i not in paths:
            paths[i] = doc.Layers[i].FullPath
        if paths[i] not in drawn_ and paths[i].split('::')[0] != OUT_LAYER:
            out.append((o, paths[i]))
    return out


def house_band(start):
    """a token layer id to its weight (a band name, or pt) in the tokens kit.py resolves from start: the house's under
    any overlay above it"""
    import sys
    kit = kit_dir()
    if kit not in sys.path:
        sys.path.insert(0, kit)
    from archkit.project import load
    t = load(start)

    def band(lid):
        L = t.layer('drawing', lid)
        return L.get('weight') or t['roles'][L['role']].get('weight')
    return band


def drawing_layers(doc):
    """the full paths of the layers holding a drawing HL added, under whatever parent, and their sublayers"""
    marked = [L.FullPath for L in doc.Layers if not L.IsDeleted and L.GetUserString(DRAWING_KEY)]
    return set(L.FullPath for L in doc.Layers if not L.IsDeleted
               and any(L.FullPath == m or L.FullPath.startswith(m + '::') for m in marked))


def left_out(doc):
    """{kind: count} of the selected objects HL does not draw: text, dimensions, hatches, points and the like"""
    T = Rhino.DocObjects.ObjectType
    names = {T.Annotation: 'annotation', T.TextDot: 'text dot', T.Hatch: 'hatch', T.Point: 'point',
             T.PointSet: 'point cloud', T.Light: 'light', T.Detail: 'detail view'}
    out = {}
    for o in doc.Objects.GetSelectedObjects(False, False):
        k = names.get(o.ObjectType)
        if k:
            out[k] = out.get(k, 0) + 1
    return out


def stored_roles(doc, hl):
    """{full path: role} kept on the document's layers"""
    out = {}
    for L in doc.Layers:
        if not L.IsDeleted:
            v = L.GetUserString(hl.ROLE_KEY)
            if v:
                out[L.FullPath] = v
    return out


def store_roles(doc, hl, roles):
    """each layer's role ({full path: role}) kept on the layer, so the next HL opens with it"""
    for p, r in roles.items():
        i = doc.Layers.FindByFullPath(p, -1)
        if i >= 0 and doc.Layers[i].GetUserString(hl.ROLE_KEY) != r:
            doc.Layers[i].SetUserString(hl.ROLE_KEY, r)


def corners(o):
    """the corners of what HL draws of an object: a block's own geometry, not its text or hatches"""
    if isinstance(o.Geometry, G.InstanceReferenceGeometry):
        b = G.BoundingBox.Empty
        for _, g in geoms(o, o.Document):
            b.Union(g.GetBoundingBox(True))
    else:
        b = o.Geometry.GetBoundingBox(True)
    return [(c.X, c.Y, c.Z) for c in b.GetCorners()] if b.IsValid else []


def view_list(doc, vp, req):
    """the views HL offers: [(key, label)]"""
    hl = hl_module()
    out = [('viewport', 'This viewport (%s)' % vp.Name)]
    if req is not None and req.get('view'):
        out.append(('request', "The request file's view"))
    out += [('std:' + k, lab) for k, lab, _, _ in hl.VIEWS]
    out += [('named:%d' % i, 'Named view: %s' % doc.NamedViews[i].Name) for i in range(doc.NamedViews.Count)]
    for n, o in enumerate(clip_objects(doc)):
        out.append(('clip:%s' % o.Id, 'Section: %s' % (o.Attributes.Name or 'clipping plane %d' % (n + 1))))
    return out


def view_for(doc, vp, key, scale, fit, req):
    """(view, frame, clip) of a view the dialog lists, at the scale, a frame round fit (points) where the view has
    none of its own"""
    hl = hl_module()
    unit_mm = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
    k = PT_PER_MM * unit_mm / float(scale)
    if key == 'viewport':
        return from_viewport(doc, vp, scale)
    if key == 'request':
        return req['view'], req['frame'], req.get('clip') or []      # as written: one plane or a list
    if key.startswith('named:'):
        return from_viewport(doc, vp, scale, info=doc.NamedViews[int(key[6:])].Viewport)
    if key.startswith('std:'):
        _, _, d, up = next(v for v in hl.VIEWS if v[0] == key[4:])
        if not fit:
            return None, None, []
        view, frame = hl.frame_round(fit, d, up, k)
        return view, frame, []
    o = doc.Objects.FindId(System_guid(key[5:]))
    g = o.Geometry
    p = g.Plane
    n = (p.Normal.X, p.Normal.Y, p.Normal.Z)
    clip = plane_spec(g)
    kept = [c for c in fit if all((c[0] - s['origin'][0]) * s['normal'][0] + (c[1] - s['origin'][1]) * s['normal'][1]
                                  + (c[2] - s['origin'][2]) * s['normal'][2] >= 0 for s in clip)]
    if not kept:
        return None, None, clip
    view, frame = hl.frame_round(kept, n, (0, 1, 0) if abs(n[2]) > 0.99 else (0, 0, 1), k)
    return view, frame, clip


def System_guid(s):
    import System
    return System.Guid(s)


def dialog(doc, vp):
    """the HL dialog, Make2D's in kind: what to draw (the selection, or everything shown), the view, the scale and
    name, what a section cuts, each layer's role, and whether to add the drawing to the model; a request file for the
    rest. The choices: dict(req, folder, name, add, check, roles), or None"""
    import Eto.Forms as forms
    import Eto.Drawing as drawing
    hl = hl_module()
    last = json.loads(doc.Strings.GetValue(SECTION, 'last') or '{}')
    if last.get('view') in ('request',) and not last.get('request'):
        last.pop('view')
    sel = drawable(doc, vp, True)
    skipped = left_out(doc)
    st = dict(req=None, path=None, objs=None, rows=[], chosen={}, boxes={}, built=None, form=None)

    def label(text='', wrap=False, left=False, hint=False):
        x = forms.Label()
        x.Text = text
        if wrap:
            x.Wrap = forms.WrapMode.Word
        if wrap or left:
            x.TextAlignment = forms.TextAlignment.Left
        if hint:                                       # a line saying what the control above it does
            x.TextColor = drawing.SystemColors.DisabledText
            x.Width = 330
        return x

    dlg = forms.Dialog[bool]()
    dlg.Title = 'Hidden lines'
    dlg.Padding = drawing.Padding(12)
    dlg.Resizable = True
    what = forms.DropDown()
    view = forms.DropDown()
    scale = forms.NumericStepper()
    scale.MinValue = 1
    scale.MaxValue = 100000
    scale.DecimalPlaces = 0
    name = forms.TextBox()
    size = label(left=True)
    cut_text = label(left=True)
    cut = forms.DropDown()
    count_text = label(left=True)
    weights = forms.DropDown()
    for _, lab in hl.WEIGHTS:
        weights.Items.Add(lab)
    wkeys = [k for k, _ in hl.WEIGHTS]
    weights_say = label('', True, hint=True)
    layer_tree = forms.DropDown()
    for _, lab in hl.LAYER_TREES:
        layer_tree.Items.Add(lab)
    tree_keys = [k for k, _ in hl.LAYER_TREES]
    layer_tree.SelectedIndex = tree_keys.index(hl.layer_tree_choice(last.get('layer_tree'), settings().get('layer_tree')))
    tree_say = label(hl.LAYER_TREES_SAY[tree_keys[layer_tree.SelectedIndex]], True, hint=True)

    def on_tree(*_):
        tree_say.Text = hl.LAYER_TREES_SAY[tree_keys[layer_tree.SelectedIndex]]
    layer_tree.SelectedIndexChanged += on_tree
    depth = forms.CheckBox()
    depth.Text = 'Lighter with distance'
    depth.Checked = last.get('depth', True)
    depth_say = label('', True, hint=True)
    merge = forms.CheckBox()
    merge.Text = 'Merge close lines'
    merge.Checked = bool(last.get('merge'))
    merge_say = label('Where two lines run closer than about 0.2 mm on paper, only the heavier is drawn. Off, both '
                      'are drawn.', True, hint=True)
    hidden = forms.CheckBox()
    hidden.Text = 'Draw hidden lines'
    hidden.Checked = bool(last.get('hidden'))
    hidden_say = label('Also draws the lines hidden behind surfaces, dashed, on their own layer, as Make2D\'s option '
                       'does; drawing takes longer.', True, hint=True)
    add = forms.CheckBox()
    add.Text = 'Add the drawing to this model'
    add.Checked = last.get('add', True)
    parent = forms.TextBox()
    parent.Text = last.get('parent') or OUT_LAYER
    parent.Width = 220
    import System
    out_default = os.path.dirname(hl.out_folder(doc.Path, 'x', System.Environment.GetFolderPath(
        System.Environment.SpecialFolder.MyDocuments) or os.path.join(os.path.expanduser('~'), 'Documents')))
    out_box = forms.TextBox()
    out_box.Text = (last.get('out') or {}).get(doc.Path or '', out_default)
    out_box.Width = 220
    out_pick = forms.Button()
    out_pick.Text = 'Choose...'
    ticked = last['save'] if 'save' in last else settings().get('save', [])   # the model's, else the user's last
    save_boxes = []
    for k, lab, _ in hl.SAVES:
        b_ = forms.CheckBox()
        b_.Text, b_.Checked = lab, k in ticked
        save_boxes.append((k, b_))
    save_label = label('Save files in')
    save_row = forms.DynamicLayout()                  # shown only when a file is ticked under Also save
    save_row.Spacing = drawing.Size(6, 0)
    save_row.AddRow(out_box, out_pick)
    subs = forms.CheckBox()
    subs.Text = 'Show sublayers'
    subs.Checked = bool(last.get('subs'))
    check = forms.CheckBox()
    check.Text = 'Only check the model, no drawing'
    updates = forms.CheckBox()
    updates.Text = 'Check GitHub for a newer HL once a day'
    updates.Checked = settings().get('update_check', True)
    updates.CheckedChanged += lambda s, e: save_settings(update_check=bool(updates.Checked))
    forget = forms.Button()
    forget.Text = "Remove HL's settings from this model"
    req_text = label('No request file: the layers decide.', left=True)
    req_open, req_clear, req_save = forms.Button(), forms.Button(), forms.Button()
    req_open.Text, req_clear.Text, req_save.Text = 'Open...', 'Clear', 'Save as...'
    msg = label('', True)
    msg.Width = 760                                  # a long message wraps, so Cancel and Draw stay in view
    dest = label('', True)
    dest.Width = 900
    go, cancel = forms.Button(), forms.Button()
    go.Text, cancel.Text = 'Draw', 'Cancel'

    grid = forms.GridView()
    grid.Size = drawing.Size(660, 360)
    labels = [lab for _, lab, _, _ in hl.ROLES]
    for i, (head, w, cell) in enumerate((('Layer', 170, None), ('Objects', 60, None), ('Draws as', 130, labels),
                                          ('Why', 290, None))):
        c = forms.GridColumn()
        c.HeaderText = head
        c.Width = w
        if cell:
            cc = forms.ComboBoxCell(i)
            cc.DataStore = cell
            c.DataCell = cc
            c.Editable = True
        else:
            c.DataCell = forms.TextBoxCell(i)
        grid.Columns.Add(c)
    grid.ToolTip = '\n'.join('%s: %s' % (lab, say) for _, lab, say, _ in hl.ROLES)
    NOTE = ('To change how a layer draws, choose its role under Draws as; point at the list to read what each role '
            'does. A sublayer takes its parent\'s role unless its name says otherwise: tick Show sublayers to set one '
            'on its own. The roles you set are saved on the layers, so the next HL opens with them.')
    grid_note = label(NOTE, True)
    grid_note.Width = 660
    unknown = label('', True)                         # layers HL knew no name of, drawn as Building
    unknown.Width = 660
    unknown.TextColor = drawing.Colors.DarkOrange

    def drawn():
        """[(object, layer path)] the dialog's choice draws"""
        return sel if what.SelectedIndex == 0 and sel else drawable(doc, vp, False)

    def fill_rows():
        """the layers of what is drawn, with their roles: a row a top-level layer, or with Show sublayers a row a
        layer holding what is drawn"""
        objs = drawn()
        st['objs'] = objs
        count = {}
        for _, p in objs:
            count[p] = count.get(p, 0) + 1
        order = {L.FullPath: L.SortIndex for L in doc.Layers if not L.IsDeleted}
        tops = sorted(set(p.split('::')[0] for p in count), key=lambda p: order.get(p, 0))
        res = hl.resolve(list(count) + [t_ for t_ in tops if t_ not in count], dict(stored_roles(doc, hl), **st['chosen']))
        st['res'], st['count'] = res, count
        st['notice'] = hl.unknown_notice(res, list(count))
        unknown.Text = st['notice'] or ''
        paths = sorted(count, key=lambda p: (res[p][0] == hl.SKIP, order.get(p, 0)))   # those left out last
        if subs.Checked:
            st['rows'] = [forms.GridItem(p, str(count[p]), hl.LABEL[res[p][0]], hl.why(res[p][1])) for p in paths]
        else:
            rows = hl.top_rows(sorted(count, key=lambda p: order.get(p, 0)), res, count)
            rows.sort(key=lambda r: r[2] == hl.SKIP)
            st['rows'] = [forms.GridItem(t_, str(n), hl.LABEL[r], hl.why(h, d)) for t_, n, r, h, d in rows]
        grid.DataStore = st['rows']
        r_ = roles()
        drawn_ = [p for _, p in objs if r_.get(p) != hl.SKIP]
        st['n'] = len(drawn_)
        count_text.Text = '{:,} object{} on {} layer{} drawn'.format(len(drawn_), '' if len(drawn_) == 1 else 's',
                                                                     len(set(drawn_)), '' if len(set(drawn_)) == 1 else 's')
        if what.SelectedIndex == 0 and skipped:
            count_text.Text += '; not drawn: ' + ', '.join('%d %s%s' % (n, k, '' if n == 1 else 'es' if k.endswith('h') else 's')
                                                           for k, n in sorted(skipped.items()))

    def roles():
        """{layer path: role} of the layers holding what is drawn"""
        return {p: st['res'][p][0] for p in st['count']}

    def on_edit(sender, e):
        it = e.Item
        if it is None:
            return
        key = {lab: k for k, lab, _, _ in hl.ROLES}
        st['chosen'][str(it.Values[0])] = key.get(str(it.Values[2]), 'building')
        fill_rows()
        refresh()

    def fit_points():
        """the corners of what a frame fits round: the drawn objects of the subject's roles, or all drawn, curves
        only where nothing else is drawn"""
        r = roles()
        crv = Rhino.DocObjects.ObjectType.Curve
        objs = [(o, p) for o, p in st['objs'] if r.get(p) != hl.SKIP]
        objs = [(o, p) for o, p in objs if o.ObjectType != crv] or objs        # curves alone do not set the frame
        subj = [o for o, p in objs if r.get(p) in hl.SUBJECT] or [o for o, _ in objs]
        pts = []
        for o in subj:
            if o.Id not in st['boxes']:
                st['boxes'][o.Id] = corners(o)
            pts += st['boxes'][o.Id]
        return pts

    def keys():
        return [k for k, _ in st['views']]

    def build():
        """the request the choices draw, or a reason it cannot be drawn"""
        key = keys()[view.SelectedIndex] if view.SelectedIndex >= 0 else 'viewport'
        if key == 'request' and not st['req']:                # the list is being refilled after Clear
            key = 'viewport'
        s = float(scale.Value or 1)
        v, fr, clip = view_for(doc, vp, key, s, fit_points() if key.startswith(('std:', 'clip:')) else None, st['req'])
        if v is None:
            return 'Nothing to draw in this view.'
        nm = name.Text.strip()
        groups = st['req']['groups'] if st['req'] else None
        if st['req']:
            req = dict(st['req'], id=nm, title=st['req'].get('title', nm), scale=s)
        else:
            r = roles()
            ids = [str(o.Id) for o, p in st['objs'] if r.get(p) != hl.SKIP]
            if not ids:
                return 'Every layer is left out: give one a role.'
            req = hl.request_from(nm, s, dict((p, x) for p, x in r.items() if x != hl.SKIP), ids)
        req = weigh(hl.with_lines(req, bool(depth.Checked), bool(merge.Checked), bool(hidden.Checked)))
        req['view'], req['frame'] = v, fr
        req.pop('clip', None)
        if clip:
            req['clip'] = clip
            gid = cut_ids()[cut.SelectedIndex] if cut.SelectedIndex >= 0 else None
            if gid:
                req = hl.with_cut(req, gid)
        return req

    def weigh(req):
        """the request at the line weights chosen (hl.with_weights): the layers' roles, or a request file's groups
        by the layers they name, with the layers' print widths and the house's weights of the token layers"""
        mode = wkeys[weights.SelectedIndex]
        if mode == 'house':
            return req
        if st['req']:
            import fnmatch
            by = {}
            for L in doc.Layers:
                g = next((g for g in req['groups'] if any(fnmatch.fnmatchcase(L.FullPath, p) for p in g['layers'])
                          and not any(fnmatch.fnmatchcase(L.FullPath, p) for p in g.get('not_layers', []))), None)
                if g and not L.IsDeleted:
                    by[L.FullPath] = g['id']
        else:
            by = roles()
        widths = {L.FullPath: L.PlotWeight for L in doc.Layers if not L.IsDeleted}
        start = st['path'] or out_box.Text.strip() or out_default   # where kit.py will find the tokens from
        return hl.with_weights(req, mode, by, widths, house_band(start))

    def cut_ids():
        if st['req']:
            return [g['id'] for g in st['req']['groups']]
        drawn_roles = set(roles().values())
        return [k for k, _, _, g in hl.ROLES if g is not None and k in drawn_roles]

    def saves():
        """the files ticked under Also save; a request file's drawing writes them all, in its own folder"""
        return [k for k, _, _ in hl.SAVES] if st['path'] else [k for k, b_ in save_boxes if b_.Checked]

    def say_dest(*_):
        nm = name.Text.strip() or 'NAME'
        dest.Text = hl.destination(nm, bool(add.Checked), parent.Text.strip() or OUT_LAYER, folder_of(nm),
                                   os.path.expanduser('~'), saves())

    def show_save(*_):
        vis = bool(saves()) and not st['path']
        if save_label.Visible != vis:
            save_label.Visible = save_row.Visible = vis
            win = st.get('form') or dlg
            if win.Loaded:                             # a shown window keeps its height: fitted again to the row
                pad = win.Padding.Top + win.Padding.Bottom
                s = win.Content.GetPreferredSize(drawing.SizeF(float(win.ClientSize.Width - win.Padding.Left -
                                                                     win.Padding.Right), float('inf')))
                win.ClientSize = drawing.Size(win.ClientSize.Width, int(math.ceil(s.Height)) + pad)
        say_dest()

    def refresh(*_):
        mode = wkeys[weights.SelectedIndex]
        weights_say.Text = hl.WEIGHTS_SAY[mode]
        depth.Enabled = mode != 'single'
        depth_say.Text = ('One weight per role draws every line of a role at one weight, so lines are not lighter '
                          'with distance.' if mode == 'single' else
                          'Lines further past the section, or further back without one, are drawn a step lighter.')
        say_dest()
        if view.SelectedIndex < 0:
            return
        b = build()
        st['built'] = b
        if isinstance(b, str):
            size.Text, cut_text.Text = b, ''
            cut.Enabled = False
            return
        fr = b['frame']
        mm = (fr['w_pt'] / PT_PER_MM, fr['h_pt'] / PT_PER_MM)
        size.Text = '%.0f x %.0f mm on paper%s' % (mm[0], mm[1], '; larger than A0, check the scale' if max(mm) > 1189 else '')
        c = b.get('clip') or []
        n = 1 if isinstance(c, dict) else len(c)
        cut_text.Text = ('%d clipping plane%s this view' % (n, ' cuts' if n == 1 else 's cut')) if n else 'No section in this view'
        cut.Enabled = n > 0

    def fill_cut():
        ids = cut_ids()
        prev = cut.Items[cut.SelectedIndex].Text if cut.SelectedIndex >= 0 else last.get('cut')
        cut.Items.Clear()
        for i in ids:
            cut.Items.Add(hl.LABEL.get(i, i) if not st['req'] else i)
        if ids:
            shown = [cut.Items[n].Text for n in range(len(ids))]
            first = ([g['id'] for g in st['req']['groups'] if g.get('layer') == 'CUT'] +   # as the request has it
                     [g['id'] for g in st['req']['groups'] if g.get('profile_layer')] if st['req'] else ['building'])
            want = [x for x in [prev] + [shown[ids.index(i)] for i in first if i in ids] if x in shown]
            cut.SelectedIndex = shown.index(want[0]) if want else 0

    def fill_views(prefer=None):
        st['views'] = view_list(doc, vp, st['req'])
        view.Items.Clear()
        for _, lab in st['views']:
            view.Items.Add(lab)
        ks = keys()
        k = prefer if prefer in ks else (last.get('view') if last.get('view') in ks else 'viewport')
        view.SelectedIndex = ks.index(k)

    def on_view(*_):
        if view.SelectedIndex < 0:
            return
        k = keys()[view.SelectedIndex]
        names = last.get('names', {})
        if st['req'] and k == 'request':
            name.Text = st['req'].get('id') or 'drawing'
        else:
            name.Text = names.get(k) or hl.slug(st['views'][view.SelectedIndex][1].replace('This viewport', '')
                                                .replace('Section: ', ''))
        refresh()

    def on_what(*_):
        fill_rows()
        fill_cut()
        refresh()

    def on_out(*_):
        import System
        fd = forms.SelectFolderDialog()
        fd.Title = 'Save the drawing\'s files in'
        if os.path.isdir(out_box.Text):
            fd.Directory = out_box.Text
        if fd.ShowDialog(dlg) == forms.DialogResult.Ok:
            out_box.Text = fd.Directory

    def load(path):
        try:
            req = json.load(open(path, encoding='utf-8'))
            if not req.get('groups'):
                raise ValueError('it names no groups')
        except Exception as e:
            msg.Text = 'Cannot read %s: %s' % (os.path.basename(path), e)
            return False
        st['req'], st['path'] = req, path
        req_text.Text = path
        depth.Checked = bool(req.get('depth_bands_share') or req.get('depth_bands_m'))   # as the file has them
        merge.Checked = bool(req.get('simplify_doubles'))
        hidden.Checked = bool(req.get('show_hidden'))
        what.Enabled = grid.Enabled = subs.Enabled = out_box.Enabled = out_pick.Enabled = False
        for _, b_ in save_boxes:
            b_.Enabled = False
        show_save()
        grid_note.Text = "The request file's groups decide what is drawn and how; its layers' roles here are not used."
        unknown.Text = ''
        if req.get('scale'):
            scale.Value = float(req['scale'])
        fill_cut()
        fill_views('request' if req.get('view') else None)
        return True

    def clear_req(*_):
        st['req'] = st['path'] = None
        req_text.Text = 'No request file: the layers decide.'
        depth.Checked, merge.Checked = last.get('depth', True), bool(last.get('merge'))
        hidden.Checked = bool(last.get('hidden'))
        what.Enabled = grid.Enabled = subs.Enabled = out_box.Enabled = out_pick.Enabled = True
        for _, b_ in save_boxes:
            b_.Enabled = True
        show_save()
        grid_note.Text = NOTE
        unknown.Text = st.get('notice') or ''
        fill_views()
        fill_cut()

    def on_open(*_):
        od = forms.OpenFileDialog()
        od.Title = 'A hidden-lines request'
        od.Filters.Add(forms.FileFilter('Request', '.json'))
        if od.ShowDialog(dlg) == forms.DialogResult.Ok:
            load(od.FileName)

    def on_save(*_):
        import System
        b = build()
        if isinstance(b, str):
            msg.Text = b
            return
        sd = forms.SaveFileDialog()
        sd.Title = 'Save the request'
        sd.Filters.Add(forms.FileFilter('Request', '.json'))
        if doc.Path:
            sd.Directory = System.Uri(os.path.dirname(doc.Path))
        sd.FileName = '%s.json' % b['id']
        if sd.ShowDialog(dlg) != forms.DialogResult.Ok:
            return
        path = sd.FileName if sd.FileName.endswith('.json') else sd.FileName + '.json'
        with open(path, 'w') as fh:
            json.dump(dict(b, out='hidden-lines'), fh, indent=1)
        msg.Text = 'Saved %s' % path

    def on_forget(*_):
        """the roles HL kept on the layers and the dialog's last choices taken out of the model, once confirmed; the
        drawings and their layers' kit.hl.drawing marks stay"""
        held = [L.Index for L in doc.Layers if not L.IsDeleted and L.GetUserString(hl.ROLE_KEY)]
        entries = list(doc.Strings.GetEntryNames(SECTION))
        r = hl.removal(len(held), bool(entries))
        if not r:
            msg.Text = 'This model holds no HL settings.'
            return
        if globals().get('HL_TEST'):
            st['asked'] = r[0]
        elif forms.MessageBox.Show(dlg, r[0], 'HL', forms.MessageBoxButtons.YesNo) != forms.DialogResult.Yes:
            return
        for i in held:
            doc.Layers[i].DeleteUserString(hl.ROLE_KEY)
        for e in entries:
            doc.Strings.Delete(SECTION, e)
        last.clear()                                   # so a Draw from this dialog keeps only its own choices
        st['chosen'] = {}
        fill_rows()
        refresh()
        msg.Text = r[1]

    def on_draw(*_):
        bad = hl.name_problem(name.Text.strip())
        if bad:
            msg.Text = bad
            return
        if not re.match(r'^[^:]+(::[^:]+)*$', parent.Text.strip()):
            msg.Text = 'The layer to add it under is a layer path, its levels joined by ::.'
            return
        refresh()
        if isinstance(st['built'], str):
            msg.Text = st['built']
            return
        fr = st['built']['frame']
        if hl.frame_problem(fr['w_pt'], fr['h_pt']):            # one stray object far off makes a sheet of kilometres
            boxes = [(o.Id, o.Geometry.GetBoundingBox(True).Center) for o, _ in st['objs']]
            far = hl.far_ones([(i, (c.X, c.Y, c.Z)) for i, c in boxes])
            doc.Objects.UnselectAll()
            for i in far:
                doc.Objects.Select(i, True)
            doc.Views.Redraw()
            msg.Text = hl.frame_problem(fr['w_pt'], fr['h_pt'], len(far), st['built'].get('scale'))
            return
        if not (add.Checked or saves() or check.Checked):
            msg.Text = 'Tick Add the drawing to this model, or a file under Also save: as it is, Draw makes nothing.'
            return
        folder = folder_of(name.Text.strip())
        too_long = hl.long_path(folder, name.Text.strip()) if os.name == 'nt' and saves() else None
        if too_long:
            msg.Text = too_long
            return
        try:                                           # a drive that is not mounted, or a folder not to write in
            if saves() and not os.path.isdir(folder):
                os.makedirs(folder)
            if saves():
                probe = os.path.join(folder, '.hl-probe')
                open(probe, 'w').close()
                os.remove(probe)
        except OSError as e:
            msg.Text = hl.folder_problem(folder, e)
            return
        if not st['req'] and what.SelectedIndex == 1 and st['n'] > hl.BIG:
            ask = 'Nothing is selected: draw everything shown, %s? A drawing this size can take many minutes.' % (
                count_text.Text.replace(' drawn', ''))
            if globals().get('HL_TEST'):
                st['asked'] = ask
            elif forms.MessageBox.Show(dlg, ask, 'HL', forms.MessageBoxButtons.YesNo) != forms.DialogResult.Yes:
                return
        close(True)

    def footer():
        """the dialog's last line, in small type: HL's version, Help, Report a problem, About, and a newer release when
        GitHub has one"""
        import platform, System
        ver = hl.short_version(globals().get('KIT_VERSION'))
        main = Rhino.UI.RhinoEtoApp.MainWindow
        small = drawing.Font(drawing.SystemFonts.Default().Family, drawing.SystemFonts.Default().Size - 2)

        def web(url):
            import webbrowser
            webbrowser.open(url)

        def link(text, fn, tip=None):
            b_ = forms.LinkButton()
            b_.Text, b_.Font = text, small
            if tip:
                b_.ToolTip = tip
            b_.Click += lambda s, e: fn()
            return b_
        about = 'HL %s\n\nby %s\n%s licence\n%s' % (ver or 'from the kit', hl.AUTHOR, hl.LICENCE, hl.REPO)
        upd = link('', lambda: web(st.get('update_url') or hl.REPO + '/releases'),
                   'Opens the release notes. To update, install the newer package as you installed this one, then '
                   'restart Rhino.')
        upd.Visible = False
        name_ = label('HL %s' % ver if ver else 'HL, from the kit')
        name_.Font, name_.TextColor = small, drawing.SystemColors.DisabledText
        f_ = forms.StackLayout()                      # kept on one baseline when the window leaves the row spare height
        f_.Orientation, f_.Spacing, f_.VerticalContentAlignment = (forms.Orientation.Horizontal, 14,
                                                                   forms.VerticalAlignment.Bottom)
        for c in (name_, link('Help', lambda: web(hl.REPO + '#readme'), 'Opens the guide on GitHub'),
                  link('Report a problem', lambda: web(hl.issue_url(ver, Rhino.RhinoApp.Version, platform.platform())),
                       'Opens a new issue on GitHub with the versions of HL, Rhino and your system filled in'),
                  link('About', lambda: forms.MessageBox.Show(main, about, 'About HL')), upd):
            f_.Items.Add(forms.StackLayoutItem(c))

        def show(c):
            try:
                if hl.newer(c.get('tag'), ver):
                    st['update_url'] = c.get('url')
                    upd.Text = 'Update available: %s' % str(c['tag']).lstrip('v')
                    upd.Visible = True
            except Exception:                          # the dialog closed before GitHub answered
                pass
        st['footer'] = dict(upd=upd, show=show)
        cache = os.path.join(HL_HOME, 'update.json')
        try:
            c0 = json.load(open(cache, encoding='utf-8'))
        except (OSError, ValueError):
            c0 = {}
        if not ver or not settings().get('update_check', True):
            return f_
        if not hl.update_due(c0, time.time()):
            show(c0)
            return f_

        def ask():
            import urllib.request
            c1 = dict(c0, checked=time.time())
            try:
                r = json.load(urllib.request.urlopen(urllib.request.Request(hl.LATEST, headers={'User-Agent': 'HL'}),
                                                     timeout=3))
                c1.update(tag=r.get('tag_name'), url=r.get('html_url'))
            except Exception:                          # offline, or no release yet: nothing said, asked again tomorrow
                pass
            try:
                with open(cache, 'w', encoding='utf-8') as fh:
                    json.dump(c1, fh)
            except OSError:
                pass
            Rhino.RhinoApp.InvokeOnUiThread(System.Action(lambda: show(c1)))
        import threading
        threading.Thread(target=ask, daemon=True).start()
        return f_

    def folder_of(nm):
        """the folder the drawing nm goes in"""
        if st['path']:
            return os.path.join(os.path.dirname(st['path']), st['req'].get('out', 'hidden-lines'), nm)
        return os.path.join(out_box.Text.strip() or out_default, nm)

    def close(ok):
        st['ok'] = ok
        if st.get('form') is not None:
            st['form'].Close()
        else:
            dlg.Close(ok)

    what.Items.Add('Selected objects (%d)' % len(sel) if sel else 'Nothing is selected')
    what.Items.Add('Everything visible in %s' % vp.Name)
    what.SelectedIndex = 0 if sel else 1
    scale.Value = float(last.get('scale', 100))
    fill_rows()
    drawn_widths = [L.PlotWeight for L in doc.Layers if not L.IsDeleted and L.FullPath in st['count']]
    weights.SelectedIndex = wkeys.index(hl.weights_choice(last.get('weights'), settings().get('weights'), drawn_widths))
    fill_cut()
    st['views'] = []
    view.SelectedIndexChanged += on_view
    fill_views()
    on_view()
    what.SelectedIndexChanged += on_what
    subs.CheckedChanged += lambda s, e: fill_rows()
    weights.SelectedIndexChanged += refresh
    depth.CheckedChanged += refresh
    merge.CheckedChanged += refresh
    hidden.CheckedChanged += refresh
    for c_ in (name, parent, out_box):
        c_.TextChanged += say_dest
    add.CheckedChanged += say_dest
    for _, b_ in save_boxes:
        b_.CheckedChanged += show_save
    out_pick.Click += on_out
    scale.ValueChanged += refresh
    cut.SelectedIndexChanged += refresh
    grid.CellEdited += on_edit
    req_open.Click += on_open
    req_clear.Click += clear_req
    req_save.Click += on_save
    forget.Click += on_forget
    go.Click += on_draw
    cancel.Click += lambda s, e: close(False)
    dlg.DefaultButton, dlg.AbortButton = go, cancel
    if last.get('request') and os.path.exists(last['request']):
        load(last['request'])

    top = forms.DynamicLayout()
    top.Spacing = drawing.Size(8, 8)
    top.AddRow(label('Objects'), what)
    top.AddRow(label(''), count_text)
    top.AddRow(label('View'), view)
    top.AddRow(label('Scale 1:'), scale)
    top.AddRow(label('Name'), name)
    top.AddRow(label(''), size)
    top.AddRow(label('Section'), cut_text)
    top.AddRow(label('Draw as cut'), cut)
    top.AddRow(label('Line weights'), weights)
    top.AddRow(label(''), weights_say)
    top.AddRow(label(''), depth)
    top.AddRow(label(''), depth_say)
    top.AddRow(label(''), merge)
    top.AddRow(label(''), merge_say)
    top.AddRow(label(''), hidden)
    top.AddRow(label(''), hidden_say)
    top.AddRow(label('Layers in the model'), layer_tree)
    top.AddRow(label(''), tree_say)
    top.AddRow(label(''), add)
    sb = forms.DynamicLayout()
    sb.Spacing = drawing.Size(14, 0)
    sb.AddRow(*([b_ for _, b_ in save_boxes] + [None]))
    top.AddRow(label('Also save'), sb)
    top.AddRow(save_label, save_row)
    show_save()
    adv = forms.DynamicLayout()
    adv.Spacing = drawing.Size(6, 6)
    adv.AddRow(req_text)
    rb = forms.DynamicLayout()
    rb.Spacing = drawing.Size(6, 6)
    rb.AddRow(req_open, req_clear, req_save, None)
    adv.AddRow(rb)
    adv.AddRow(check)
    adv.AddRow(updates)
    lay_row = forms.DynamicLayout()
    lay_row.Spacing = drawing.Size(6, 6)
    lay_row.AddRow(label('Add it under layer'), parent)
    adv.AddRow(lay_row)
    fb = forms.DynamicLayout()
    fb.AddRow(forget, None)
    adv.AddRow(fb)
    box = forms.GroupBox()
    box.Text = 'Advanced'
    box.Padding = drawing.Padding(6)
    box.Content = adv
    left = forms.DynamicLayout()                 # the box in a row of its own, so the labels stay narrow
    left.Spacing = drawing.Size(8, 8)
    left.AddRow(top)
    left.AddRow(box)
    left.AddRow(None)
    right = forms.DynamicLayout()
    right.Spacing = drawing.Size(6, 6)
    head = forms.DynamicLayout()
    head.AddRow(label('Layers in this drawing', left=True), None, subs)
    right.AddRow(head)
    right.AddRow(grid)
    right.AddRow(unknown)
    right.AddRow(grid_note)
    cols = forms.DynamicLayout()
    cols.Spacing = drawing.Size(16, 8)
    cols.AddRow(left, right)
    row = forms.DynamicLayout()
    row.Spacing = drawing.Size(8, 8)
    row.AddRow(msg, None, cancel, go)
    lay = forms.DynamicLayout()                  # each row its own cell, so the bottom lines set no column's width
    lay.Spacing = drawing.Size(8, 8)
    lay.AddRow(cols)
    lay.AddRow(dest)
    lay.AddRow(row)
    lay.AddRow(footer())
    dlg.Content = lay
    def finish():
        """the choices once Draw closed the dialog, the last of them and the layers' roles kept in the model"""
        req = st['built']
        nm = name.Text.strip()
        k = keys()[view.SelectedIndex]
        names = dict(last.get('names', {}))
        names[k] = nm
        outs = dict(last.get('out') or {})
        if out_box.Text.strip() and out_box.Text.strip() != out_default:
            outs[doc.Path or ''] = out_box.Text.strip()
        else:
            outs.pop(doc.Path or '', None)
        o = dict(request=st['path'], view=k, names=names, scale=float(scale.Value), add=bool(add.Checked),
                 cut=cut.Items[cut.SelectedIndex].Text if cut.SelectedIndex >= 0 else None,
                 weights=wkeys[weights.SelectedIndex], parent=parent.Text.strip(), out=outs, subs=bool(subs.Checked),
                 layer_tree=tree_keys[layer_tree.SelectedIndex],
                 depth=last.get('depth', True) if st['path'] else bool(depth.Checked),
                 merge=last.get('merge', False) if st['path'] else bool(merge.Checked),
                 hidden=last.get('hidden', False) if st['path'] else bool(hidden.Checked),
                 save=[k for k, b_ in save_boxes if b_.Checked])
        doc.Strings.SetString(SECTION, 'last', json.dumps(o))
        save_settings(weights=o['weights'], save=o['save'], layer_tree=o['layer_tree'])
        folder = folder_of(nm)
        if not st['path']:
            store_roles(doc, hl, st['chosen'])
        return dict(req=req, folder=folder, name=nm, add=bool(add.Checked), check=bool(check.Checked),
                    label=st['views'][view.SelectedIndex][1], parent=parent.Text.strip() or OUT_LAYER,
                    save=saves(), keep_all=bool(st['path']),
                    layer_tree=o['layer_tree'],
                    tokens_from=st['path'] or out_box.Text.strip() or out_default,
                    notice=None if st['path'] else st.get('notice'))

    if globals().get('HL_TEST'):                      # the dialog left open for a test to drive through the connector
        sc.sticky['kit.hl.test'] = dict(dlg=dlg, st=st, what=what, view=view, scale=scale, name=name, cut=cut,
                                        grid=grid, add=add, check=check, size=size, cut_text=cut_text, msg=msg,
                                        subs=subs, weights=weights, parent=parent, out_box=out_box, count=count_text,
                                        depth=depth, merge=merge, dest=dest, weights_say=weights_say, unknown=unknown,
                                        layer_tree=layer_tree, tree_say=tree_say,
                                        updates=updates, forget=forget, on_forget=on_forget, hidden=hidden,
                                        save_boxes=save_boxes, save_label=save_label, show_save=show_save,
                                        on_edit=on_edit, on_draw=on_draw, load=load, refresh=refresh, finish=finish)
        dlg.Content = None
        f = st['form'] = forms.Form()
        f.Title, f.Padding, f.Resizable, f.Content = dlg.Title, dlg.Padding, True, lay
        dlg.Dispose()
        f.Owner = Rhino.UI.RhinoEtoApp.MainWindow
        f.Show()
        return None
    if not dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow):
        dlg.Dispose()
        return None
    o = finish()
    dlg.Dispose()                                      # a closed dialog's window otherwise lingers until collected
    return o


def color(hex_):
    import System
    return System.Drawing.Color.FromArgb(int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16))


def layer_at(doc, name, parent, ink=None, weight=None, lt=-1):
    """the index of the layer name under parent (an index, or None for the top), added if missing; with ink, its colour,
    print colour and width (mm; -1 does not print) and linetype set"""
    full = name if parent is None else doc.Layers[parent].FullPath + '::' + name
    i = doc.Layers.FindByFullPath(full, -1)
    L = Rhino.DocObjects.Layer() if i < 0 else doc.Layers[i]
    before = (L.Color.ToArgb(), L.PlotColor.ToArgb(), L.PlotWeight, L.LinetypeIndex)
    if ink:
        c = color(ink)
        L.Color = c if c.R + c.G + c.B < 3 * 215 else color('#bebebe')   # near-white inks show grey on screen
        L.PlotColor = c
        if weight is not None:
            L.PlotWeight = weight
        L.LinetypeIndex = lt
    if i < 0:                                          # set before it is added: each change to the layer table
        L.Name = name                                  # costs the layer panel a rebuild
        if parent is not None:
            L.ParentLayerId = doc.Layers[parent].Id
        if ink:                                        # a kit layer shows folded in the layer panel
            L.IsExpanded = False
        i = doc.Layers.Add(L)
    elif ink and (L.Color.ToArgb(), L.PlotColor.ToArgb(), L.PlotWeight, L.LinetypeIndex) != before:
        doc.Layers.Modify(L, i, True)
    return i


def layer_path(doc, path):
    """the index of the layer at a full path, its levels added where missing"""
    i = None
    for part in path.split('::'):
        i = layer_at(doc, part, i)
    return i


def bring_in(doc, name, path, parent=OUT_LAYER, layer_tree='role'):
    """the drawing kit.py wrote for Rhino (hiddenlines/hidden.py, for_rhino) added under parent::name (a layer path, HL
    unless given), the name's layer marked with DRAWING_KEY so HL never draws it. role keeps the kit layers; model
    nests source layers and classes with object print attributes. Every curve keeps its source in user text, on the
    world's XY plane with the frame's lower left corner at the origin, replacing the previous run; one undo.
    (curves, fills)"""
    import System
    data = json.load(open(path, encoding='utf-8'))
    rec = doc.BeginUndoRecord('HL %s' % name)
    nc = nf = 0
    panel = Rhino.UI.PanelIds.Layers
    shown = Rhino.UI.Panels.IsPanelVisible(panel, True)
    if shown:                                          # on screen it redraws for every layer added: the model's 107
        Rhino.UI.Panels.ClosePanel(panel)              # took 15 s, under 2 s with it closed; a background tab costs nothing
    try:
        base = layer_at(doc, name, layer_path(doc, parent))
        doc.Layers[base].SetUserString(DRAWING_KEY, name)
        root = doc.Layers[base].FullPath
        for L in list(doc.Layers):
            if not L.IsDeleted and (L.FullPath == root or L.FullPath.startswith(root + '::')):
                for o in doc.Objects.FindByLayer(L) or []:
                    doc.Objects.Delete(o, True)
        solid = doc.HatchPatterns.FindName('Solid')
        solid = solid.Index if solid else doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Solid)
        tol = doc.ModelAbsoluteTolerance
        hl = hl_module()
        linetypes = {}

        def linetype(dash, lengths):
            if not dash:
                return -1
            if dash not in linetypes:
                lname = 'KIT_%s 1:%g' % (dash.upper(), data['scale'])
                found = doc.Linetypes.FindName(lname)
                if found is not None and found.Index >= 0:
                    linetypes[dash] = found.Index
                else:
                    t = Rhino.DocObjects.Linetype()
                    t.Name = lname
                    for j, v in enumerate(lengths):
                        t.AppendSegment(v, j % 2 == 0)
                    linetypes[dash] = doc.Linetypes.Add(t)
            return linetypes[dash]

        order = dict((L.FullPath, L.SortIndex) for L in doc.Layers if not L.IsDeleted)
        for s in hl.layer_tree(data, layer_tree, order):
            lt = linetype(s['dash'], s['dash_model'])
            si = base
            for j, part in enumerate(s['path']):
                si = layer_at(doc, part, si, s['ink'], s['weight_mm'] if j == len(s['path']) - 1 else None, lt)
            attr = Rhino.DocObjects.ObjectAttributes()
            attr.LayerIndex = si
            for ln in s['lines']:
                a = attr.Duplicate()
                attrs = ln['attributes']
                for key, value in attrs['user_text'].items():
                    a.SetUserString(key, value)
                if layer_tree == 'model':
                    a.PlotWeightSource = Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromObject
                    a.PlotWeight = attrs['weight_mm']
                    a.LinetypeSource = Rhino.DocObjects.ObjectLinetypeSource.LinetypeFromObject
                    a.LinetypeIndex = linetype(attrs['dash'], attrs['dash_model'])
                    a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                    a.ObjectColor = color(attrs['ink'])
                    a.PlotColorSource = Rhino.DocObjects.ObjectPlotColorSource.PlotColorFromObject
                    a.PlotColor = color(attrs['ink'])
                pl = G.Polyline()
                for x, y in ln['pts']:
                    pl.Add(x, y, 0.0)
                if ln['closed']:
                    pl.Add(pl[0])
                doc.Objects.AddCurve(G.PolylineCurve(pl), a)
                nc += 1
            for fl in s['fills']:
                crvs = System.Collections.Generic.List[G.Curve]()
                for ring in fl['rings']:
                    pl = G.Polyline()
                    for x, y in ring + ring[:1]:
                        pl.Add(x, y, 0.0)
                    crvs.Add(G.PolylineCurve(pl))
                a = attr.Duplicate()
                a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                a.ObjectColor = color(fl['ink'])
                a.PlotColorSource = Rhino.DocObjects.ObjectPlotColorSource.PlotColorFromObject
                a.PlotColor = color(fl['ink'])
                a.DisplayOrder = -1                 # behind the lines
                for h in G.Hatch.Create(crvs, solid, 0.0, 1.0, tol) or []:
                    doc.Objects.AddHatch(h, a)
                    nf += 1
        counts = dict((L.FullPath, len(doc.Objects.FindByLayer(L) or [])) for L in doc.Layers
                      if not L.IsDeleted and L.FullPath.startswith(root + '::'))
        for p in hl.stale_layers(counts, root):        # sublayers of an earlier run's bands, empty now
            i = doc.Layers.FindByFullPath(p, -1)
            if i >= 0 and i != doc.Layers.CurrentLayerIndex:
                doc.Layers.Delete(i, True)
    finally:
        doc.EndUndoRecord(rec)
        if shown:
            Rhino.UI.Panels.OpenPanel(panel)
    doc.Views.Redraw()
    return nc, nf


def layer_of_id(doc, s):
    """the layer of the object with id s, or ''"""
    import System
    o = doc.Objects.FindId(System.Guid(s))
    return doc.Layers[o.Attributes.LayerIndex].FullPath if o is not None else ''


def results(doc, title, summary, rows, folder, where=None, log=None):
    """the window HL leaves open after a run: what it drew and lint's verdict, and the model's faults, a row each with
    its fix; choosing rows selects their objects in the model and zooms to them, and a lint row selects the drawing's
    curves at its places, given where (the drawing's layer path, pt per model unit); with log, a button opens it"""
    import System
    import Eto.Forms as forms
    import Eto.Drawing as drawing
    old = sc.sticky.pop(RESULTS, None)
    if old is not None:
        try:
            old.Close()
            old.Dispose()
        except Exception:                              # closed and disposed by the user already
            pass
    f = forms.Form()
    f.Title = title
    f.Padding = drawing.Padding(12)
    f.Resizable = True
    f.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    text = forms.Label()
    text.Text = summary
    text.Wrap = forms.WrapMode.Word
    text.TextAlignment = forms.TextAlignment.Left
    text.Width = 640
    grid = forms.GridView()
    grid.Size = drawing.Size(640, 240)
    grid.AllowMultipleSelection = True
    for i, (head, w) in enumerate((('Problem', 220), ('Layer', 220), ('Where', 180))):
        c = forms.GridColumn()
        c.HeaderText = head
        c.Width = w
        c.DataCell = forms.TextBoxCell(i)
        grid.Columns.Add(c)
    where_ = hl_module().where
    grid.DataStore = [forms.GridItem(r['short'], r['layer'], where_(r)) for r in rows]
    detail = forms.Label()
    detail.Wrap = forms.WrapMode.Word
    detail.TextAlignment = forms.TextAlignment.Left
    detail.Size = drawing.Size(640, 96)
    detail.Text = 'Choose a row to select its objects and read its fix.' if rows else ''

    def pick(ids, zoom=True):
        doc.Objects.UnselectAll()
        bb = G.BoundingBox.Empty
        for s in ids:
            o = doc.Objects.FindId(System.Guid(s))
            if o is not None and not o.IsDeleted:
                if o.IsHidden or not doc.Layers[o.Attributes.LayerIndex].IsVisible:
                    continue
                doc.Objects.Select(o.Id, True)
                bb.Union(o.Geometry.GetBoundingBox(True))
        if zoom and bb.IsValid and doc.Views.ActiveView is not None:
            bb.Inflate(bb.Diagonal.Length * 0.1)
            doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(bb)
        doc.Views.Redraw()

    def near(places):
        """the drawing's curves within 2 pt of places selected, and the view zoomed to them"""
        doc.Objects.UnselectAll()
        root, k = where
        r_ = 2.0 / k
        bb = G.BoundingBox.Empty
        for L in doc.Layers:
            if L.IsDeleted or not (L.FullPath == root or L.FullPath.startswith(root + '::')):
                continue
            for o in doc.Objects.FindByLayer(L) or []:
                c = o.Geometry
                if isinstance(c, G.Curve) and any(c.ClosestPoint(G.Point3d(x, y, 0), r_)[0] for x, y in places):
                    doc.Objects.Select(o.Id, True)
        for x, y in places:
            bb.Union(G.Point3d(x, y, 0))
        if bb.IsValid and doc.Views.ActiveView is not None:
            bb.Inflate(30 * r_)
            doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(bb)
        doc.Views.Redraw()

    def on_select(*_):
        sel = [rows[int(i)] for i in grid.SelectedRows]
        if not sel:
            return
        places = [p for r in sel for p in r.get('places', [])]
        if where and places:
            near(places)
        else:
            pick([i for r in sel for i in r['ids']])
        r = sel[0]
        detail.Text = '%s\n%s\n\nAs reported: %s' % (
            r['say'], ('What to do: ' + r['fix']) if r['fix'] else '',
            '; '.join(r['issues'][:2]) + (' ...' if len(r['issues']) > 2 else ''))

    grid.SelectionChanged += on_select
    every, show, close, see = forms.Button(), forms.Button(), forms.Button(), forms.Button()
    n_ = len(set(i for r in rows for i in r['objects']))   # suspects' objects among them; a lint row has none
    every.Text = 'Select all %d' % n_
    every.Enabled = n_ > 0
    show.Text = 'Open the folder'
    show.Enabled = bool(folder) and os.path.isdir(folder)
    see.Text = 'Open the log'
    close.Text = 'Close'
    every.Click += lambda s, e: pick([i for r in rows for i in r['objects']], zoom=False)

    def opener(path):
        def on_click(*_):
            import subprocess
            if os.name == 'nt':
                os.startfile(path)
            else:
                subprocess.Popen(['open', path])
        return on_click
    show.Click += opener(folder)
    see.Click += opener(log)
    close.Click += lambda s, e: f.Close()
    f.Closed += lambda s, e: sc.sticky.pop(RESULTS, None)
    lay = forms.DynamicLayout()
    lay.Spacing = drawing.Size(8, 8)
    lay.AddRow(text)
    if rows:
        lay.AddRow(grid)
        lay.AddRow(detail)
    row = forms.DynamicLayout()
    row.Spacing = drawing.Size(8, 8)
    row.AddRow(every if rows else None, show, see if log else None, None, close)
    lay.AddRow(row)
    f.Content = lay
    sc.sticky[RESULTS] = f
    f.Show()
    return f


def alias():
    """the HL command: the dialog, then the drawing, one at a time in a Rhino; an error HL did not expect said plainly
    in the results window, with the run's log"""
    import traceback
    doc = sc.doc
    if doc.Views.ActiveView is None:
        print('HL: no active view')
        return
    if sc.sticky.get(RUNNING):                         # a second HL would take over the first one's export
        import Eto.Forms as forms
        forms.MessageBox.Show(Rhino.UI.RhinoEtoApp.MainWindow, 'HL is already drawing %s in this Rhino. Wait for it '
                              'to finish, or press Esc in its window to stop it.' % sc.sticky[RUNNING], 'HL')
        return
    vp = doc.Views.ActiveView.ActiveViewport
    o = None
    del LOG[:]
    try:
        if globals().get('KIT_RUNTIME') and not setup():
            return
        o = dialog(doc, vp)
        if o:
            sc.sticky[RUNNING] = o['name']
            draw(doc, o)
    except Exception:
        say(traceback.format_exc())
        log = write_log(o['folder'] if o and o.get('save') and os.path.isdir(o['folder']) else None)
        last = [x for x in traceback.format_exc().strip().splitlines() if x.strip()][-1]
        results(doc, 'HL stopped', 'HL stopped on an error it did not expect: %s\n\nYour model\'s file is as it was; '
                'anything HL added to the model can be undone. To report the problem, attach the log: %s'
                % (last, log or 'it could not be written'), [], os.path.dirname(log) if log else None, log=log)
    finally:
        sc.sticky.pop(RUNNING, None)


def fail(doc, nm, text, folder):
    """a run that did not draw: what went wrong said in the results window, with the log written"""
    say('HL: %s did not draw: %s' % (nm, text.splitlines()[0]))
    log = write_log(folder if folder and os.path.isdir(folder) else None)
    results(doc, 'HL: %s did not draw' % nm, text + '\n\nThe log: %s' % (log or 'it could not be written'), [],
            folder if folder and os.path.isdir(folder) else (os.path.dirname(log) if log else None), log=log)


def draw(doc, o):
    """the dialog's choices drawn: the export and what kit.py writes in a working folder of the system's, removed after
    the run, or in o['folder'] for a request file's drawing (o['keep_all']), as it always was"""
    import tempfile, shutil
    work = o['folder'] if o.get('keep_all') else tempfile.mkdtemp(prefix='hl-work-')
    try:
        drawn(doc, o, work)
    finally:
        if work != o['folder']:
            shutil.rmtree(work, ignore_errors=True)


def drawn(doc, o, folder):
    """the dialog's choices drawn into folder, with the request they make (request.json): the export in calls of two
    seconds (Esc stops it), kit.py hidden-lines and lint on what it wrote, the drawing added to the model, the files
    ticked under Also save copied to o['folder'], and the results window; o['folder'] locked against another Rhino
    saving there, and every line said kept in hl.log beside the files saved, else in HL's logs folder"""
    import tempfile, shutil
    hl = hl_module()
    t0 = time.time()
    nm = o['name']
    keep = o['folder'] if o['save'] else None          # the folder of the files saved, and the run's log
    req = dict(o['req'], out='.')
    rpath = os.path.join(folder, 'request.json')
    say('HL: %s at 1:%g, %s' % (nm, req['scale'], o['label']))
    say('Model: %s, in %s; %d objects drawn' % (doc.Path or 'not saved', doc.ModelUnitSystem,
                                                 len(req.get('objects') or [])))
    if o.get('notice'):
        say('HL: ' + o['notice'])
    lock = None
    try:
        for d in (folder, keep):
            if d and not os.path.isdir(d):
                os.makedirs(d)
        if keep:
            lock = folder_lock(keep)
            if lock is False:
                fail(doc, nm, 'HL is already drawing %s here, in another Rhino. Wait for it to finish, or give this '
                     'drawing another name.' % nm, None)
                return
        if not o.get('keep_all'):                      # the project's own tokens, which kit.py finds above a request
            import sys
            kit = kit_dir()
            if kit not in sys.path:
                sys.path.insert(0, kit)
            from archkit.project import find_overlay
            ov = find_overlay(o['tokens_from'])
            if ov:
                with open(os.path.join(folder, 'tokens.json'), 'w', encoding='utf-8') as fh:
                    json.dump({'extends': str(ov)}, fh)
        with open(rpath, 'w') as fh:
            json.dump(req, fh, indent=1)
    except OSError as e:
        unlock(lock)
        fail(doc, nm, hl.folder_problem(keep or folder, e), None)
        return
    g = globals()
    g.update(HIDDEN=rpath, BUDGET=2.0, CHECK=o['check'])
    sc.sticky.pop(KEY, None)
    bar = Rhino.UI.StatusBar
    bar.ShowProgressMeter(0, len(STAGES) + 2, 'HL %s (Esc stops it)' % nm, True, True)
    awake = None
    if os.name != 'nt':
        # macOS slows Rhino while another app is in front: the model's section from the store took 743 to 940 s in 7 of
        # 13 exports with Rhino behind and 328 to 334 s in the rest, and 332 to 334 s in each of 4 with this held
        import Foundation
        awake = Foundation.NSProcessInfo.ProcessInfo.BeginActivity(Foundation.NSActivityOptions.UserInitiated, 'HL drawing')
    try:
        stage = None
        try:
            while True:
                r = main()
                if not r or not r.startswith('more'):
                    break
                s = r.split()[1]
                if s != stage:
                    stage = s
                    bar.UpdateProgressMeter('HL: %s' % s, STAGES.index(s) if s in STAGES else 0, True)
                Rhino.RhinoApp.Wait()
                if sc.escape_test(False):
                    sc.sticky.pop(KEY, None)
                    say('HL: stopped')
                    write_log(keep)
                    return
        except OSError as e:                           # the disk full, or its drive gone, as the export writes
            sc.sticky.pop(KEY, None)
            fail(doc, nm, hl.folder_problem(folder, e), keep)
            return
        say('HL: %s' % r)
        if not r.startswith(('done', 'checked')):
            fail(doc, nm, 'Reading the model stopped: %s' % r, keep)
            return
        if o['check']:
            data = json.load(open(os.path.join(folder, 'check.json'), encoding='utf-8'))
            rows = hl.fault_rows(data['with_issues'], req)
            n = len(set(i for r in rows for i in r['objects']))
            results(doc, 'HL: %s, the model checked' % nm, '%d of %d objects have faults (rhino/MODELLING.md). Choose '
                    'a row to select its objects.' % (n, data['objects']), rows, keep, log=write_log(keep))
            return
        m = re.search(r'([\d,]+) segments, ([\d,]+) triangles', r)
        ask = hl.memory_problem(int(m.group(2).replace(',', '')), int(m.group(1).replace(',', '')),
                                float(req['frame']['w_pt']), float(req['frame']['h_pt']), memory_gb()) if m else None
        if ask:
            say('HL: ' + ask)
            import Eto.Forms as forms
            if globals().get('HL_TEST'):
                sc.sticky['kit.hl.asked'] = ask
            elif forms.MessageBox.Show(Rhino.UI.RhinoEtoApp.MainWindow, ask, 'HL',
                                       forms.MessageBoxButtons.YesNo) != forms.DialogResult.Yes:
                say('HL: not drawn, for memory')
                write_log(keep)
                return
        bar.UpdateProgressMeter('HL: drawing', len(STAGES), True)
        tmp = os.path.join(tempfile.gettempdir(), 'hl-%s.json' % os.getpid())
        draw_args = ['hidden-lines', rpath] + (['--rhino', tmp] if o['add'] else [])
        code, text = kit_run(draw_args)
        if code and code != STOPPED and globals().get('KIT_RUNTIME') and hl.damaged(text):
            say(text)
            import Eto.Forms as forms
            if forms.MessageBox.Show(Rhino.UI.RhinoEtoApp.MainWindow, 'The Python and packages HL downloaded look '
                                     'damaged or incomplete. Download them again (about 700 MB)?', 'HL',
                                     forms.MessageBoxButtons.YesNo) == forms.DialogResult.Yes and redownload():
                say('HL: downloaded again; drawing again')
                code, text = kit_run(draw_args)
        if code == STOPPED:
            say('HL: stopped')
            write_log(keep)
            return
        for line in text.splitlines():
            say('  ' + line)
        if code or (o['add'] and not os.path.exists(tmp)):
            why = ('It ran out of memory. ' if re.search(r'MemoryError|Killed|out of memory', text) else
                   'The disk is full. ' if 'No space left' in text else
                   'The folder is gone: was its drive disconnected? ' if not os.path.isdir(folder) else '')
            fail(doc, nm, 'The drawing step failed (exit %d), after the model was read. %sIts last words:\n\n%s'
                 % (code, why, '\n'.join(text.splitlines()[-8:])), keep)
            return
        bar.UpdateProgressMeter('HL: checking the drawing', len(STAGES) + 1, True)
        code, text = kit_run(['lint', os.path.join(folder, nm + '.svg')])
        if code == STOPPED:
            text = 'lint stopped'
        lines = [x.strip() for x in text.splitlines()]
        verdict = lines[-1] if lines else 'no output'
        say('HL lint: ' + verdict)
        for line in [x for x in lines if x.startswith(('error', 'warning'))]:
            say('  ' + line)
        k = PT_PER_MM * Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters) / req['scale']
        lint = hl.lint_rows(lines, k, req['frame']['h_pt'])
        added = ''
        if o['add']:
            nc, nf = bring_in(doc, nm, tmp, o['parent'], o['layer_tree'])
            os.remove(tmp)
            added = '%d curves and %d fills on %s::%s. ' % (nc, nf, o['parent'], nm)
            say('HL: ' + added)
        saved = ''
        if keep and keep != folder:
            try:
                for k in o['save']:
                    shutil.copyfile(os.path.join(folder, '%s.%s' % (nm, k)), os.path.join(keep, '%s.%s' % (nm, k)))
            except OSError as e:
                fail(doc, nm, hl.folder_problem(keep, e), keep)
                return
        if keep:
            saved = hl.destination(nm, False, '', keep, None, o['save']).replace('. Nothing is added to the model.',
                                                                                 '. ')
            say('HL: ' + saved)
        say('HL: in %.0f s' % (time.time() - t0))
        rep = os.path.join(folder, nm + '-report.json')
        data = json.load(open(rep, encoding='utf-8')) if os.path.exists(rep) else {}
        sus = hl.suspect_rows(data.get('suspects', []), lambda i: layer_of_id(doc, i))
        rows = sus + lint + hl.fault_rows(data.get('issues', []), req)
        n = len(set(i for r in rows if r['kind'] not in ('suspect', 'lint') for i in r['objects']))
        summary = 'Drawn in %.0f s. %s%sThe drawing\'s own check: %s%s.%s%s' % (
            time.time() - t0, added, saved, verdict.rstrip('.'), ', listed here' if lint else '',
            ' %d place%s in the drawing trace to the model, listed first.' % (len(sus), '' if len(sus) == 1 else 's')
            if sus else '',
            ' %d object%s in the model can break lines.' % (n, '' if n == 1 else 's') if n else
            ' No faults found in the model.')
        log = write_log(keep)
        results(doc, 'HL: %s' % nm, summary, rows, keep,
                ('%s::%s' % (o['parent'], nm), k) if o['add'] else None, log)
    finally:
        bar.HideProgressMeter()
        unlock(lock)
        if awake is not None:
            Foundation.NSProcessInfo.ProcessInfo.EndActivity(awake)

if __name__ == '__main__':
    alias()
