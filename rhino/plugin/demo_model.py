#! python3
"""HL's demo model, for the README's examples and the demo GIFs (docs/hl-experience.md, Demo GIFs): a two-storey house
with a stair, a chimney through its roof, door swings on its floor, a tree, a ground plane and a clipping plane for a
section, in metres, built into the open document, which should be empty. It holds two cases Make2D draws wrongly and
one HL does:
  - the walls stand 0.15 m into the ground, the tree's trunk 0.5 m, and the chimney runs through the roof as a box of
    its own: Make2D draws no line where separate objects meet, so the house floats and its chimney's edges run on
    through the roof (checked, Make2D in Rhino 8.35); HL draws the lines where they meet;
  - the east wall is two loose surfaces, both facing east, as a wall drawn as surfaces often is: in section A, HL reads
    the room as solid where the inner surface faces into the wall (the engine's poche, reported to it),
    and draws the rooms when that surface faces the room or the wall is a closed solid.
Run with _-RunPythonScript, or through the connector's run_python, where __rhino_doc__ is the document."""
import System
import Rhino
import Rhino.Geometry as G

T = 0.25                                               # wall thickness, m


def build(doc):
    def layer(path):
        parent = None
        for part in path.split('::'):
            full = part if parent is None else doc.Layers[parent].FullPath + '::' + part
            i = doc.Layers.FindByFullPath(full, -1)
            if i < 0:
                L = Rhino.DocObjects.Layer()
                L.Name = part
                if parent is not None:
                    L.ParentLayerId = doc.Layers[parent].Id
                i = doc.Layers.Add(L)
            parent = i
        return parent

    def attr(path, name=None):
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = layer(path)
        if name:
            a.Name = name
        return a

    def box(x0, y0, z0, x1, y1, z1):
        return G.Box(G.BoundingBox(G.Point3d(x0, y0, z0), G.Point3d(x1, y1, z1))).ToBrep()

    doc.AdjustModelUnitSystem(Rhino.UnitSystem.Meters, False)
    doc.Objects.AddBrep(box(0, 0, -0.15, 10, T, 6), attr('House::Walls', 'south wall'))
    doc.Objects.AddBrep(box(0, 7 - T, -0.15, 10, 7, 6), attr('House::Walls', 'north wall'))
    doc.Objects.AddBrep(box(0, T, -0.15, T, 7 - T, 6), attr('House::Walls', 'west wall'))
    for x in (10 - T, 10):                             # the east wall as two loose surfaces, both facing +x
        s = G.Brep.CreateFromCornerPoints(G.Point3d(x, T, -0.15), G.Point3d(x, 7 - T, -0.15), G.Point3d(x, 7 - T, 6),
                                          G.Point3d(x, T, 6), 0.001)
        doc.Objects.AddBrep(s, attr('House::Walls', 'east wall face'))
    doc.Objects.AddBrep(box(T, T, -0.15, 10 - T, 7 - T, 0.15), attr('House::Floors', 'ground floor'))
    doc.Objects.AddBrep(box(T, T, 3.0, 10 - T, 7 - T, 3.25), attr('House::Floors', 'first floor'))
    gable = G.Polyline([G.Point3d(-0.3, -0.3, 6), G.Point3d(-0.3, 3.5, 8.5), G.Point3d(-0.3, 7.3, 6), G.Point3d(-0.3, -0.3, 6)])
    doc.Objects.AddBrep(G.Extrusion.Create(gable.ToNurbsCurve(), -10.6, True).ToBrep(), attr('House::Roof', 'roof'))
    doc.Objects.AddBrep(box(6.5, 4.6, 4.0, 7.3, 5.4, 9.3), attr('House::Chimney', 'chimney'))
    for i in range(12):                                # 12 risers of 0.2375 m up to the first floor
        doc.Objects.AddBrep(box(1.0 + i * 0.28, 0.4, 0.15 + i * 0.2375, 1.28 + i * 0.28, 1.4, 0.15 + (i + 1) * 0.2375),
                            attr('House::Stair'))
    for cx, cy, turn in ((4.0, T, 0.0), (8.0, 7 - T, -1.5707963)):
        c = G.Arc(G.Plane(G.Point3d(cx, cy, 0.15), G.Vector3d.ZAxis), 0.9, 1.5707963).ToNurbsCurve()
        c.Rotate(turn, G.Vector3d.ZAxis, G.Point3d(cx, cy, 0.15))
        doc.Objects.AddCurve(c, attr('House::Door Swings'))
    doc.Objects.AddBrep(G.Brep.CreateFromCornerPoints(G.Point3d(-6, -5, 0), G.Point3d(17, -5, 0), G.Point3d(17, 13, 0),
                                                      G.Point3d(-6, 13, 0), 0.001), attr('Site::Ground'))
    doc.Objects.AddBrep(G.Cylinder(G.Circle(G.Plane(G.Point3d(13.5, 2.5, -0.5), G.Vector3d.ZAxis), 0.18), 3.0).ToBrep(True, True),
                        attr('Site::Trees', 'trunk'))
    doc.Objects.AddBrep(G.Sphere(G.Point3d(13.5, 2.5, 3.6), 1.6).ToBrep(), attr('Site::Trees', 'crown'))
    front = next(v for v in doc.Views if v.ActiveViewport.Name == 'Front')
    ids = System.Collections.Generic.List[System.Guid]()
    ids.Add(front.ActiveViewport.Id)
    cid = doc.Objects.AddClippingPlane(G.Plane(G.Point3d(5, 3.0, 3), G.Vector3d(0, 1, 0)), 14, 12, ids)
    a = doc.Objects.FindId(cid).Attributes.Duplicate()
    a.Name, a.LayerIndex = 'section A', layer('Section')
    doc.Objects.ModifyAttributes(cid, a, True)
    doc.Views.Redraw()


if __name__ == '__main__':
    build(globals().get('__rhino_doc__') or Rhino.RhinoDoc.ActiveDoc)
