#! python3
"""Builds the synthetic scenes of the hidden-lines tests in an empty Rhino document and runs rhino/hidden_lines.py on
each, writing request.json, scene.json and meshes.bin into a folder per scene beside this file. Run it through the
connector's run_python in a new document (spawn_slot): exec(open(PATH).read, {'__rhino_doc__': __rhino_doc__,
'__name__': 'make_scenes'}); ns 'ONLY' names the scenes to record, all of them unless given. Metres; a scene is seen
from the south-east as a true isometric at 1:200 unless it names its own view.

  touching   six homes as touching boxes, one a storey taller, on a ground plane
  coplanar   a terrace on a roof, a gallery flush with a wall, a box across the shared edge of two ground patches
  tjunction  a long wall behind a box and a post, so the wall's edges pass behind them
  open       a tilted porch roof as one open surface over a box, and a box missing its top
  roof       two houses of walls, an overhanging gable roof and a chimney through it, one keyed for a union; a tree
             whose trunk goes into the ground; a box sunk into the ground
  cut-box    a box on the ground cut by a vertical plane through its middle, the half toward the camera taken away;
             the box's group is on CUT, so its lines seen past the plane go to BEYOND
  cut-lwall  walls in an L, overlapping at the corner, a post touching one and a post standing free, cut in plan at
             1.2 m and seen from above at 1:100
  cut-rooms  two touching rooms and one over both, one building, cut by a vertical plane and seen square to it, a
             lower annex behind them partly hidden by the cut, the ground cut too
  persp      a street at eye level in a two-point perspective (35 mm, the camera named): buildings either side, one in
             front of a taller one, curbs on the ground, a box behind the camera and one outside the view
  persp-aim  the same street from above, the camera placed by the scale (no camera named), three-point
  persp-cut  a perimeter block round a court and a long wall running out of the view, cut in plan at 1.5 m and seen
             from above in perspective, the ground filled
  bad        a model check: an extrusion of a profile that crosses itself, a quad warped 2 cm, a solid whose side is
             one face creased at three corners (added without Rhino's split), a duplicate, a box with a 3 mm sliver, a
             sheet lying on a slab, two boxes running into each other, two roof surfaces sharing an edge unjoined, a
             mesh of three quads on one edge, and a row of touching boxes with no union key. Rhino turns a solid added
             inside out the right way, so the scene has none
  curved     a cylinder, a sphere on the ground, a box with filleted edges, a wall on an arc, a cone, a barrel vault on
             a box and a torus
  curved-cut the same cut by a vertical plane through their middles
  knots      a NURBS sphere, whose double knots run into its poles, and a tree revolved from a polyline, both added
             without Rhino's split, as a script writing a file headless leaves them: the model check finds the tree's
             creases and none in the sphere
  above      a room's walls cut in plan at 1.2 m under a roof slab overhanging them by a metre and a beam across the
             room, both marked above, so they are drawn dashed as seen looking up
  hidden     a house cut by a vertical plane on a block of earth cut with it, its footing inside the earth behind the
             plane, marked hidden, so it is drawn dashed
  twisted    the model the model's tall roof: its top turned and tilted against its base, so each of its four faces is twisted,
             joined as one open polysurface; rafters 2 cm behind the front face and purlins across them, and tile
             lines along the front face's rulings; seen square from the front at 1:100. The engine draws the frame's
             contact curves through the roof, as it does not with the front face alone
"""
import json, math, os
import Rhino
import Rhino.Geometry as G

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.expanduser(
    globals().get('FIXTURES', '.'))
KIT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
doc = globals().get('__rhino_doc__')


def box(x0, y0, z0, x1, y1, z1):
    return G.Brep.CreateFromBox(G.BoundingBox(G.Point3d(x0, y0, z0), G.Point3d(x1, y1, z1)))


def plane(pts):
    return G.Brep.CreateFromCornerPoints(*[G.Point3d(*p) for p in pts], 0.001)


def prism(ring, z0, z1):
    c = G.PolylineCurve([G.Point3d(x, y, z0) for x, y in ring] + [G.Point3d(ring[0][0], ring[0][1], z0)])
    return G.Extrusion.Create(c, z1 - z0, True).ToBrep(True)


def gable(x0, y0, x1, y1, z, ridge, over):
    """a closed gable roof over the box x0..x1, y0..y1 at eave height z, ridge along x, overhanging by over"""
    xa, xb, ya, yb, ym = x0 - over, x1 + over, y0 - over, y1 + over, (y0 + y1) / 2
    prof = G.PolylineCurve([G.Point3d(xa, ya, z), G.Point3d(xa, yb, z), G.Point3d(xa, ym, ridge), G.Point3d(xa, ya, z)])
    return G.Surface.CreateExtrusion(prof, G.Vector3d(xb - xa, 0, 0)).ToBrep().CapPlanarHoles(0.001)


def tree(x, y, z0, trunk_r, top):
    prof = G.Polyline([G.Point3d(0, 0, z0), G.Point3d(trunk_r, 0, z0), G.Point3d(trunk_r, 0, 3), G.Point3d(2.2, 0, 4.5),
                       G.Point3d(1.8, 0, 7), G.Point3d(0, 0, top)]).ToPolylineCurve()
    rev = G.RevSurface.Create(prof, G.Line(G.Point3d(0, 0, 0), G.Point3d(0, 0, 1)))
    b = G.Brep.CreateFromRevSurface(rev, False, False)
    b.Translate(G.Vector3d(x, y, 0))
    return b


def layer(path):
    i = doc.Layers.FindByFullPath(path, -1)
    if i >= 0:
        return i
    parent = None
    for n, name in enumerate(path.split('::')):
        full = '::'.join(path.split('::')[:n + 1])
        i = doc.Layers.FindByFullPath(full, -1)
        if i < 0:
            L = Rhino.DocObjects.Layer()
            L.Name = name
            if parent is not None:
                L.ParentLayerId = doc.Layers[parent].Id
            i = doc.Layers.Add(L)
        parent = i
    return i


def add(path, g, **user):
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = layer(path)
    for k, v in user.items():
        a.SetUserString(k, str(v))
    if isinstance(g, G.Curve):
        return doc.Objects.AddCurve(g, a)
    if isinstance(g, G.Mesh):
        return doc.Objects.AddMesh(g, a)
    split = path != 'hl::bad::creased' and not path.startswith('hl::knots::')    # Rhino splits a creased face unless told
    return doc.Objects.AddBrep(g, a, None, False, split)


GROUND = [(-12, -12, 0), (24, -12, 0), (24, 20, 0), (-12, 20, 0)]


def scenes():
    s = {}
    # touching: homes 4 x 6 x 3, two rows of three, the middle back one 6 m tall
    t = []
    for i in range(3):
        for j in range(2):
            h = 6 if (i, j) == (1, 1) else 3
            t.append(('homes', box(i * 4, j * 6, 0, i * 4 + 4, j * 6 + 6, h), dict(home='h%d%d' % (i, j))))
    t.append(('ground', plane(GROUND), {}))
    s['touching'] = dict(objects=t, groups=[
        dict(id='homes', layers=['hl::touching::homes'], layer='DETAIL', profile_layer='OUTLINE'),
        dict(id='ground', layers=['hl::touching::ground'], layer='CONTEXT', ground=True, fill='K6')],
        target=[6, 6, 2])
    # coplanar: a 10 x 6 x 6 box with a terrace 4 x 3 on its roof and a gallery 6 x 1.5 flush with its south face;
    # a 3 x 3 x 3 box across the line where the lawn meets the paving
    c = [('block', box(0, 0, 0, 10, 6, 6), {}),
         ('terraces', plane([(1, 1.5, 6), (5, 1.5, 6), (5, 4.5, 6), (1, 4.5, 6)]), {}),
         ('galleries', plane([(2, 0, 2), (8, 0, 2), (8, 0, 3.5), (2, 0, 3.5)]), {}),
         ('block', box(13, 2, 0, 16, 5, 3), {}),
         ('lawn', plane([(-12, -12, 0), (14.5, -12, 0), (14.5, 20, 0), (-12, 20, 0)]), {}),
         ('paving', plane([(14.5, -12, 0), (24, -12, 0), (24, 20, 0), (14.5, 20, 0)]), {})]
    s['coplanar'] = dict(objects=c, groups=[
        dict(id='terraces', layers=['hl::coplanar::terraces', 'hl::coplanar::galleries'], layer='DETAIL', fill='Accent'),
        dict(id='block', layers=['hl::coplanar::block'], layer='DETAIL', profile_layer='OUTLINE'),
        dict(id='ground', layers=['hl::coplanar::lawn', 'hl::coplanar::paving'], layer='CONTEXT', ground=True,
             fills={'hl::coplanar::paving': 'K20', 'hl::coplanar::lawn': 'K6'})], target=[8, 4, 2])
    # tjunction: a wall 16 x 1 x 5 behind a 3 x 3 x 3 box and a 0.4 x 0.4 x 4 post
    j = [('wall', box(0, 6, 0, 16, 7, 5), {}), ('box', box(5, 2, 0, 8, 5, 3), {}), ('box', box(11, 1, 0, 11.4, 1.4, 4), {}),
         ('ground', plane(GROUND), {})]
    s['tjunction'] = dict(objects=j, groups=[
        dict(id='front', layers=['hl::tjunction::box'], layer='DETAIL', profile_layer='OUTLINE'),
        dict(id='wall', layers=['hl::tjunction::wall'], layer='CONTEXT'),
        dict(id='ground', layers=['hl::tjunction::ground'], layer='CONTEXT', ground=True)], target=[8, 4, 2])
    # open: a porch roof tilted over a 6 x 4 x 3 box's south side; a box with no top (five faces joined)
    sides = [[(10, 0, 0), (14, 0, 0), (14, 4, 0), (10, 4, 0)], [(10, 0, 0), (14, 0, 0), (14, 0, 3), (10, 0, 3)],
             [(14, 0, 0), (14, 4, 0), (14, 4, 3), (14, 0, 3)], [(14, 4, 0), (10, 4, 0), (10, 4, 3), (14, 4, 3)],
             [(10, 4, 0), (10, 0, 0), (10, 0, 3), (10, 4, 3)]]
    b = G.Brep.JoinBreps([plane(f) for f in sides], 0.001)[0]
    o = [('house', box(0, 2, 0, 6, 6, 3), {}),
         ('porch', plane([(0, 0.5, 2.2), (6, 0.5, 2.2), (6, 2, 2.6), (0, 2, 2.6)]), {}),
         ('house', b, {}), ('ground', plane(GROUND), {})]
    s['open'] = dict(objects=o, groups=[
        dict(id='house', layers=['hl::open::house', 'hl::open::porch'], layer='DETAIL', profile_layer='OUTLINE'),
        dict(id='ground', layers=['hl::open::ground'], layer='CONTEXT', ground=True)], target=[7, 3, 1.5])
    # roof: house A keyed for a union (walls, roof, chimney through the roof), house B the same unkeyed; a tree with its
    # trunk 0.5 m into the ground, seen through; a box sunk 1 m into the ground
    r = []
    for name, x0, key in (('a', 0, 'A'), ('b', 9, None)):
        u = dict(id=key) if key else {}
        r.append(('walls', box(x0, 0, 0, x0 + 6, 5, 3), dict(u, part='walls')))
        r.append(('roofs', gable(x0, 0, x0 + 6, 5, 3, 5, 0.4), dict(u, part='roof')))
        r.append(('chimneys', box(x0 + 4.2, 3, 0, x0 + 4.8, 3.6, 5.6), dict(u, part='chimney')))
    r.append(('trees', tree(4, 10, -0.5, 0.2, 9), {}))
    r.append(('sunk', box(16, 9, -1, 19, 12, 2), {}))
    r.append(('ground', plane(GROUND), {}))
    s['roof'] = dict(objects=r, groups=[
        dict(id='houses', layers=['hl::roof::walls', 'hl::roof::roofs', 'hl::roof::chimneys'], union='id', layer='DETAIL',
             profile_layer='OUTLINE'),
        dict(id='sunk', layers=['hl::roof::sunk'], layer='DETAIL'),
        dict(id='trees', layers=['hl::roof::trees'], hides=False, layer='CONTEXT'),
        dict(id='ground', layers=['hl::roof::ground'], layer='CONTEXT', ground=True)], target=[9, 5, 2])
    # cut-box: a 10 x 6 x 4 box on the ground, cut at x = 5, the east half (toward the camera) taken away
    s['cut-box'] = dict(objects=[('box', box(0, 0, 0, 10, 6, 4), {}), ('ground', plane(GROUND), {})], groups=[
        dict(id='box', layers=['hl::cut-box::box'], layer='CUT'),
        dict(id='ground', layers=['hl::cut-box::ground'], layer='CONTEXT', ground=True, fill='K6')],
        target=[5, 3, 2], clip=dict(origin=[5, 3, 2], normal=[-1, 0, 0]))
    # cut-lwall: walls 0.3 thick and 3 high along x (8 m) and y (6 m) overlapping in the corner, a 0.4 m post against
    # the first wall's inner face, a free post; cut at 1.2 m
    w = [('walls', box(0, 0, 0, 8, 0.3, 3), {}), ('walls', box(0, 0, 0, 0.3, 6, 3), {}),
         ('walls', box(3.8, 0.3, 0, 4.2, 0.7, 3), {}), ('walls', box(5.8, 3.8, 0, 6.2, 4.2, 3), {}),
         ('ground', plane(GROUND), {})]
    s['cut-lwall'] = dict(objects=w, groups=[
        dict(id='walls', layers=['hl::cut-lwall::walls'], layer='CUT'),
        dict(id='ground', layers=['hl::cut-lwall::ground'], layer='CONTEXT', ground=True)],
        target=[4, 3, 1], scale=100, clip=dict(origin=[0, 0, 1.2], normal=[0, 0, -1]))
    # cut-rooms: rooms 4 x 6 x 3 side by side and one 8 x 6 x 3 over both; an annex 8 x 4 x 2.5 behind, from x = 6;
    # cut at y = 3 looking north
    c = [('rooms', box(0, 0, 0, 4, 6, 3), dict(home='a')), ('rooms', box(4, 0, 0, 8, 6, 3), dict(home='b')),
         ('rooms', box(0, 0, 3, 8, 6, 6), dict(home='c')), ('annex', box(6, 8, 0, 14, 12, 2.5), {}),
         ('ground', plane(GROUND), {})]
    s['cut-rooms'] = dict(objects=c, groups=[
        dict(id='rooms', layers=['hl::cut-rooms::rooms'], layer='CUT'),
        dict(id='annex', layers=['hl::cut-rooms::annex'], layer='DETAIL', profile_layer='OUTLINE'),
        dict(id='ground', layers=['hl::cut-rooms::ground'], layer='CONTEXT', ground=True)],
        view=dict(direction=[0, 1, 0], target=[7, 3, 3]), clip=dict(origin=[4, 3, 0], normal=[0, 1, 0]))
    # persp: a street along x; the left row 8 m north of the axis, the right row south; the camera at eye level
    street = [('buildings', box(0, 8, 0, 10, 16, 9), {}), ('buildings', box(12, 8, 0, 20, 14, 6), {}),
              ('buildings', box(22, 8, 0, 34, 18, 12), {}), ('buildings', box(5, -16, 0, 15, -8, 7), {}),
              ('buildings', box(18, -14, 0, 28, -8, 4), {}),
              ('buildings', box(-40, -3, 0, -36, 3, 3), {}),          # behind the camera
              ('buildings', box(10, 80, 0, 14, 84, 3), {}),           # outside the view
              ('curbs', G.LineCurve(G.Point3d(-10, -6, 0), G.Point3d(100, -6, 0)), {}),
              ('curbs', G.LineCurve(G.Point3d(-10, 6, 0), G.Point3d(100, 6, 0)), {}),
              ('ground', plane([(-60, -40, 0), (160, -40, 0), (160, 40, 0), (-60, 40, 0)]), {})]
    groups = lambda n: [
        dict(id='buildings', layers=['hl::%s::buildings' % n], layer='DETAIL', profile_layer='OUTLINE'),
        dict(id='curbs', layers=['hl::%s::curbs' % n], layer='FLOOR'),
        dict(id='ground', layers=['hl::%s::ground' % n], layer='CONTEXT', ground=True, fill='K6')]
    s['persp'] = dict(objects=street, groups=groups('persp'),
                      view=dict(lens_mm=35, camera=[-15, 0, 1.6], target=[30, 0, 4], two_point=True))
    s['persp-aim'] = dict(objects=street, groups=groups('persp-aim'), scale=500,
                          view=dict(lens_mm=28, bearing=230, elevation=25, target=[14, 0, 3]))
    # persp-cut: a block 24 x 18 x 9 round a 12 x 8 court, and a wall 0.4 thick, 3 high and 120 long beside it
    ring = G.Brep.CreateBooleanDifference(box(0, 0, 0, 24, 18, 9), box(6, 5, -1, 18, 13, 10), 0.001)[0]
    k = [('block', ring, {}), ('wall', box(-50, -6, 0, 70, -5.6, 3), {}),
         ('ground', plane([(-80, -60, 0), (100, -60, 0), (100, 80, 0), (-80, 80, 0)]), {})]
    s['persp-cut'] = dict(objects=k, groups=[
        dict(id='block', layers=['hl::persp-cut::block', 'hl::persp-cut::wall'], layer='CUT'),
        dict(id='ground', layers=['hl::persp-cut::ground'], layer='CONTEXT', ground=True, fill='K6')],
        view=dict(lens_mm=24, camera=[-10, -30, 40], target=[12, 9, 0]), clip=dict(origin=[0, 0, 1.5], normal=[0, 0, -1]))
    # bad: one fault an object, in a row along x, each 3 m apart
    bad = []
    bow = G.PolylineCurve([G.Point3d(0, 0, 0), G.Point3d(2, 2, 0), G.Point3d(2, 0, 0), G.Point3d(0, 2, 0), G.Point3d(0, 0, 0)])
    ext = G.Extrusion.Create(bow, 2.0, True)
    bad.append(('crossing', ext.ToBrep(True) if ext else G.Brep.CreateFromSurface(G.Surface.CreateExtrusion(bow, G.Vector3d(0, 0, 2))), {}))
    bad.append(('warped', G.Brep.CreateFromCornerPoints(G.Point3d(4, 0, 2), G.Point3d(6, 0, 2), G.Point3d(6, 2, 2.02),
                                                       G.Point3d(4, 2, 2), 0.0001), {}))
    kink = G.PolylineCurve([G.Point3d(8, 0, 0), G.Point3d(9, 1.5, 0), G.Point3d(10, 0, 0), G.Point3d(8, 0, 0)])
    bad.append(('creased', G.Surface.CreateExtrusion(kink, G.Vector3d(0, 0, 2)).ToBrep().CapPlanarHoles(0.001), {}))
    bad.append(('duplicates', box(12, 0, 0, 14, 2, 2), {}))
    bad.append(('duplicates', box(12, 0, 0, 14, 2, 2), {}))
    notch = G.Brep.CreateBooleanDifference(box(20, 0, 0, 22, 2, 2), box(20.003, -1, 1, 22.5, 1, 3), 0.0001)[0]
    bad.append(('notched', notch, {}))
    bad.append(('slab', box(24, 0, 0, 27, 2, 0.3), {}))
    bad.append(('sheet', plane([(24.5, 0.5, 0.3), (26.5, 0.5, 0.3), (26.5, 1.5, 0.3), (24.5, 1.5, 0.3)]), {}))
    bad.append(('clash', box(29, 0, 0, 31, 2, 2), {}))
    bad.append(('clash', box(30, 1, 0, 32, 3, 2.5), {}))
    bad.append(('roof', plane([(34, 0, 2), (36, 0, 2), (36, 1, 3), (34, 1, 3)]), {}))
    bad.append(('roof', plane([(34, 1, 3), (36, 1, 3), (36, 2, 2), (34, 2, 2)]), {}))
    tee = G.Mesh()                                       # three quads on the edge x 38..40, z 2
    for q in ((38, 0, 2), (40, 0, 2), (40, 0, 0), (38, 0, 0), (40, 2, 2), (38, 2, 2), (40, -2, 2), (38, -2, 2)):
        tee.Vertices.Add(*q)
    for f in ((0, 1, 2, 3), (1, 0, 5, 4), (0, 1, 6, 7)):
        tee.Faces.AddFace(*f)
    tee.Normals.ComputeNormals()
    bad.append(('nonmanifold', tee, {}))
    for x in range(3):
        bad.append(('row', box(42 + 2 * x, 0, 0, 44 + 2 * x, 2, 2), {}))
    bad.append(('ground', plane([(-4, -6, 0), (52, -6, 0), (52, 8, 0), (-4, 8, 0)]), {}))
    # curved: one form every 5 m along x, centred on y = 0
    cv = [('forms', G.Cylinder(G.Circle(G.Plane.WorldXY, 1.2), 3.0).ToBrep(True, True), {}),
          ('forms', G.Sphere(G.Point3d(5, 0, 1.2), 1.2).ToBrep(), {})]
    fb = box(8.8, -1.2, 0, 11.2, 1.2, 2.4)
    fl = G.Brep.CreateFilletEdges(fb, [e.EdgeIndex for e in fb.Edges], [0.4] * fb.Edges.Count, [0.4] * fb.Edges.Count,
                                  G.BlendType.Fillet, G.RailType.RollingBall, 0.001)
    cv.append(('forms', fl[0] if fl else fb, {}))
    arc_in = G.ArcCurve(G.Arc(G.Plane(G.Point3d(15, -2, 0), G.Vector3d.ZAxis), 2.0, math.radians(150)))
    arc_out = G.ArcCurve(G.Arc(G.Plane(G.Point3d(15, -2, 0), G.Vector3d.ZAxis), 2.3, math.radians(150)))
    arc_out.Reverse()
    ring = G.Curve.JoinCurves([arc_in, G.LineCurve(arc_in.PointAtEnd, arc_out.PointAtStart), arc_out,
                               G.LineCurve(arc_out.PointAtEnd, arc_in.PointAtStart)], 0.001)[0]
    if ring.ClosedCurveOrientation(G.Vector3d.ZAxis) == G.CurveOrientation.Clockwise:
        ring.Reverse()                                   # a clockwise profile extrudes down, into the ground
    cv.append(('forms', G.Extrusion.Create(ring, 2.5, True).ToBrep(True), {}))
    cv.append(('forms', G.Cone(G.Plane(G.Point3d(20, 0, 3), G.Vector3d(0, 0, -1)), 3.0, 1.2).ToBrep(True), {}))
    cv.append(('forms', box(23.5, -1.2, 0, 26.5, 1.2, 2.0), {}))
    vault = G.Cylinder(G.Circle(G.Plane(G.Point3d(23.5, 0, 2.0), G.Vector3d.XAxis), 1.2), 3.0).ToBrep(True, True)
    cv.append(('forms', G.Brep.CreateBooleanDifference(vault, box(23, -2, 0, 27, 2, 2.0), 0.001)[0], {}))
    cv.append(('forms', G.Torus(G.Plane(G.Point3d(30, 0, 0.4), G.Vector3d.ZAxis), 1.2, 0.4).ToRevSurface().ToBrep(), {}))
    for name, extra in (('curved', {}), ('curved-cut', dict(clip=dict(origin=[0, 0, 0], normal=[0, 1, 0])))):
        forms = dict(id='forms', layers=['hl::%s::forms' % name], layer='CUT') if extra else \
            dict(id='forms', layers=['hl::%s::forms' % name], layer='DETAIL', profile_layer='OUTLINE')
        s[name] = dict(objects=cv + [('ground', plane([(-3, -6, 0), (33, -6, 0), (33, 5, 0), (-3, 5, 0)]), {})],
                       groups=[forms, dict(id='ground', layers=['hl::%s::ground' % name], layer='CONTEXT', ground=True)],
                       scale=200, view=dict(bearing=150, elevation=30, target=[15, 0, 1.2]), **extra)
    # knots: a sphere 1.2 m in radius as NurbsSurface.CreateFromSphere makes it, and a tree 8 m high 5 m east of it
    sphere = G.NurbsSurface.CreateFromSphere(G.Sphere(G.Point3d(0, 0, 1.2), 1.2))
    s['knots'] = dict(objects=[('sphere', G.Brep.CreateFromSurface(sphere), {}), ('revolved', tree(5, 0, 0, 0.3, 8), {})],
                      groups=[dict(id='forms', layers=['hl::knots::sphere', 'hl::knots::revolved'], layer='DETAIL')],
                      target=[2.5, 0, 2])
    # above: walls 0.2 thick round a 6 x 4 room, 3 m high; a roof slab 3 to 3.2 m over -1..7 x -1..5; a beam 0.3 wide
    # and 0.4 deep under it across the room at x = 3; cut at 1.2 m and seen from above at 1:100
    a = [('walls', box(0, 0, 0, 6, 0.2, 3), {}), ('walls', box(0, 3.8, 0, 6, 4, 3), {}),
         ('walls', box(0, 0.2, 0, 0.2, 3.8, 3), {}), ('walls', box(5.8, 0.2, 0, 6, 3.8, 3), {}),
         ('roof', box(-1, -1, 3, 7, 5, 3.2), {}), ('roof', box(2.85, 0.2, 2.6, 3.15, 3.8, 3), {}),
         ('ground', plane([(-3, -3, 0), (9, -3, 0), (9, 7, 0), (-3, 7, 0)]), {})]
    s['above'] = dict(objects=a, groups=[
        dict(id='walls', layers=['hl::above::walls'], layer='CUT', union=True),
        dict(id='roof', layers=['hl::above::roof'], layer='DETAIL', above=True),
        dict(id='ground', layers=['hl::above::ground'], layer='CONTEXT', ground=True)],
        view=dict(direction=[0, 0, -1], up=[0, 1, 0], target=[3, 2, 1]), scale=100,
        clip=dict(origin=[0, 0, 1.2], normal=[0, 0, -1]))
    # hidden: a 6 x 6 x 3 house on a block of earth 3 m deep, both cut at y = 3 looking north; a footing 7 x 2 x 1
    # under the house's back half, inside the earth and behind the plane
    hd = [('house', box(0, 1, 0, 6, 7, 3), {}), ('earth', box(-4, -1, -3, 10, 9, 0), {}),
          ('footing', box(-0.5, 4, -1, 6.5, 6, 0), {})]
    s['hidden'] = dict(objects=hd, groups=[
        dict(id='house', layers=['hl::hidden::house'], layer='CUT'),
        dict(id='footing', layers=['hl::hidden::footing'], layer='DETAIL', hidden=True),
        dict(id='earth', layers=['hl::hidden::earth'], layer='CONTEXT')],
        view=dict(direction=[0, 1, 0], target=[3, 3, 0]), scale=100, clip=dict(origin=[3, 3, 0], normal=[0, 1, 0]))
    # twisted: a roof 7.2 x 1.75 m at its eaves, its top 0.7 m square at 6.1 to 6.8 m, turned 16 degrees and tilted
    # back (the model the model's corners, moved to the origin); rafters 5 x 5 cm from 2 cm behind the front face up its slope,
    # purlins 6 x 6 cm across them from 6 cm behind it, so each meets a rafter in a loop; tile lines on the front face
    bs = [G.Point3d(0, 0, 0), G.Point3d(7.2221, 0, 0), G.Point3d(7.2221, 1.75, 0), G.Point3d(0, 1.75, 0)]
    ts = [G.Point3d(3.1627, 0.6265, 6.1), G.Point3d(3.8596, 0.4266, 6.1), G.Point3d(4.0594, 1.1235, 6.825),
          G.Point3d(3.3625, 1.3234, 6.825)]
    quads = [G.Brep.CreateFromCornerPoints(a, b, c, d, 0.001) for a, b, c, d in
             ((bs[0], bs[1], ts[1], ts[0]), (bs[1], bs[2], ts[2], ts[1]), (bs[2], bs[3], ts[3], ts[2]), (bs[3], bs[0], ts[0], ts[3]))]
    front = quads[0].Faces[0].UnderlyingSurface()
    du, dv = front.Domain(0), front.Domain(1)
    on = lambda s_, h_: front.PointAt(du.ParameterAt(s_), dv.ParameterAt(h_))      # s along the eave, h up the slope

    def batten(a, b, off, w):
        """a w by w beam from a to b, off behind the front face"""
        x = b - a
        x.Unitize()
        ok, u, v = front.ClosestPoint((a + b) / 2)
        n = front.NormalAt(u, v)
        if n.Y < 0:
            n.Reverse()
        y = G.Vector3d.CrossProduct(n, x)
        y.Unitize()
        z = G.Vector3d.CrossProduct(x, y)
        if z.Y < 0:
            y.Reverse()
            z.Reverse()
        return G.Box(G.Plane(a + z * off, x, y), G.Interval(0, a.DistanceTo(b)), G.Interval(-w / 2, w / 2),
                     G.Interval(0, w)).ToBrep()
    tw = [('roof', G.Brep.JoinBreps(quads, 0.001)[0], {})]
    tw += [('frame', batten(on(s_, 0.04), on(s_, 0.9), 0.02, 0.05), {}) for s_ in (0.2, 0.35, 0.5, 0.65, 0.8)]
    tw += [('frame', batten(on(0.12, h_), on(0.88, h_), 0.06, 0.06), {}) for h_ in (0.2, 0.45)]
    tw += [('tiles', front.IsoCurve(1, du.ParameterAt(i / 8.0)), {}) for i in range(1, 8)]
    tw += [('tiles', front.IsoCurve(0, dv.ParameterAt(i / 6.0)), {}) for i in range(1, 6)]
    s['twisted'] = dict(objects=tw, groups=[
        dict(id='roof', layers=['hl::twisted::roof'], layer='DETAIL', profile_layer='OUTLINE', body='house'),
        dict(id='frame', layers=['hl::twisted::frame'], layer='DETAIL', body='house'),
        dict(id='tiles', layers=['hl::twisted::tiles'], layer='TEXTURE')],
        view=dict(direction=[0, 1, 0], target=[3.6, 0.5, 3.4]), scale=100)
    return s


def main():
    doc.AdjustModelUnitSystem(Rhino.UnitSystem.Meters, False)
    doc.ModelAbsoluteTolerance = 0.001
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = True
    for o in list(doc.Objects.GetObjectList(s)):              # a rerun starts from an empty document
        if doc.Layers[o.Attributes.LayerIndex].FullPath.startswith('hl::'):
            doc.Objects.Delete(o, True)
    ns = {'__rhino_doc__': doc, '__name__': 'hidden_lines', 'BUDGET': 1e9}
    exec(open(os.path.join(KIT, 'rhino', 'hidden_lines.py')).read(), ns)
    done = []
    only = globals().get('ONLY')
    for name, sc_ in scenes().items():
        if only and name not in only:
            continue
        for part, g, user in sc_['objects']:
            add('hl::%s::%s' % (name, part), g, **user)
        folder = os.path.join(HERE, name)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        view = sc_.get('view') or dict(bearing=135.0, elevation=math.degrees(math.atan(1 / math.sqrt(2))),
                                       target=sc_['target'], true_along=[1, 0, 0])
        req = dict(id=name, title='hidden-lines test scene: ' + name, scale=sc_.get('scale', 200), out='.', view=view,
                   frame=dict(w_pt=560, h_pt=400), groups=sc_['groups'])
        if sc_.get('clip'):
            req['clip'] = sc_['clip']
        path = os.path.join(folder, 'request.json')
        with open(path, 'w') as fh:
            json.dump(req, fh, indent=1)
        ns['HIDDEN'] = path
        ns['RESET'] = True
        r = ns['main']()
        ns['RESET'] = False
        while r.startswith('more'):
            r = ns['main']()
        done.append('%s: %s' % (name, r))
    print('\n'.join(done))
    return done


if __name__ == 'make_scenes':
    main()
