# Modelling for drawings

How to model in Rhino so that a model draws cleanly through HL, Make2D, clipping planes and booleans. Bad geometry in gives broken lines out, and most of what lint flags in a drawing from a model starts as one of the faults below. `rhino/hidden_lines.py` checks every model it draws against these rules and reports each fault on the object that has it, with the object's id (`SelId` in Rhino). It writes the faults into the drawing's report, and with `CHECK` set it writes `check.json` for every object the request's groups name, without drawing (`rhino/RHINO.md`).

## Solids

1. **A solid is closed.** A wall, slab, roof, room or house is one closed polysurface. An open part has no cut region, since its cut by a plane is an open line, and it hides nothing through its gaps. The check reports an open polysurface with its count of naked edges. What is a surface by nature, such as ground pieces, sheets or glazing, is one surface, not a box missing a face.
2. **A profile is closed, simple and planar before it is extruded.** A profile that crosses itself makes faces that cross their own boundary ("faces cross their own boundary"). An open one makes an open polysurface, and one off its plane cannot be capped. Clean a ring before extruding: drop points nearer than 1 mm, close it exactly, and set it at one z. Cut across material, never along an edge, or the cut leaves hairline fins.
3. **A flat face is exactly flat.** A face meant to be flat but a few millimetres off is a curved surface to the engine. Its sections bend, and it merges with no coplanar neighbour. The check reports a face flat within ten tolerances but not within one ("nearly planar"). Build flat faces from planar curves, or move the stray point onto the plane.
4. **A face has no crease inside it.** The engine draws no line along a crease inside one face. Rhino splits such faces when it adds them through its commands, but not when geometry comes from a script or an import. The P2 site model's 966 tree solids were revolved headless from polylines and are creased this way. The drawing splits creased faces on its own copy and reports them ("creased inside"); split them in the model too (`DivideAlongCreases`). The check counts a knot line as a crease where the normal turns by more than a degree across it, so the double knots of a NURBS sphere, an ellipsoid or a capsule, smooth across, are not counted.
5. **A solid faces outward.** A solid turned inside out reads to the engine as a hole. The drawing turns it the right way on its copy and reports it; `Flip` it in the model.
6. **No edge is shared by three faces, and meshes are closed, welded and oriented.** The check reports non-manifold edges, open meshes and meshes whose faces point both ways.

## Between objects

7. **Each face has one owner.** Two faces that lie on each other facing the same way leave the engine to choose which is seen: a terrace surface on a roof, ground pieces that overlap, a duplicate. The drawing gives the face to the earlier group in the request, and the check names both objects ("lies on"). Trim one to the other, lift the upper one more than two tolerances (over 2 mm at the usual 1 mm, the distance within which the check takes two faces to lie on each other), or order the groups as intended.
8. **Nothing runs into anything else unless it is meant to.** Where two solids interpenetrate, the engine draws both, and a section has to clip one by the other: a chimney standing inside its walls, wall boxes overlapping at a corner, a house reaching into its neighbour. If they are one thing, union them; if one should be cut by the other, use `BooleanDifference`. The check reports the overlap's volume ("runs into"); groups seen through, such as trees, are left out.
9. **The parts of one thing are joined, or share a key.** The rooms of one home and the walls, roof and chimney of one house are either unioned in the model or carry the same user text (`id`, or `home` and `floor`), so the drawing unions them. Parts that only touch draw a seam where they meet. The drawing's log counts touching pairs in each group that has no union key.
10. **Surfaces that share an edge are joined.** Two roof planes meeting at a ridge as separate surfaces draw that edge twice and break at it; join them. The check reports "shares an edge". Ground pieces stay apart on purpose, one surface for each material, and their shared edges coincide exactly.
11. **No duplicates.** `SelDup` finds exact ones; the check also finds near ones, within ten tolerances ("duplicate of").

## Size and place

12. **No edge is shorter than ten tolerances**, 1 cm at the usual 1 mm. Short edges come from slivers, notches and simplified outlines, and they print as strays and near misses. The check counts them per object.
13. **The model stays within 10 km of the origin.** Further out, precision suffers. Survey coordinates go in less an offset, as the P2 grid does (EPSG:2952 less E 324000, N 4844000).
14. **Curved forms are true curves.** Arcs, circles and NURBS surfaces of few spans, not faceted polylines or meshes converted to polysurfaces. A faceted cylinder draws every facet edge as a crease, where a true cylinder draws its silhouette alone. The engine leaves out tangent edges and the seams of closed surfaces.

## The P2 site model

Checked on 14 October 2026, the 19:53 save, through the section request's groups: 1,586 of 4,565 objects have faults (`docs/checked.md`).

- **Trees.** 966 tree solids are creased inside: they were revolved headless from polylines.
- **Ground and paving.** 415 objects have edges under 1 cm, and 85 have faces whose loops cross or touch themselves, mostly boulevards and lawns. Both come from the coverage's simplification.
- **Clashes.** 36 objects run into another. Cornellà's ground floor and units run into the walls of three existing houses standing on its lots (142, 114 and 62 m³): the crit request's parcel filter left those houses in, and Cornellà hid them in the isometric. The rest are chimneys, dormers and porches in LOD2 houses whose 40 unions fail to close, and two garages that overlap.
- **Faces lying on each other.** 18 objects: Cornellà's court galleries on its ground floor, and the roof terraces on its homes' roofs.
- **Unjoined surfaces.** 40 gallery surfaces share an edge with another without being joined.
- **Open polysurfaces.** 58 on the ground layer (the curb faces, not drawn).
