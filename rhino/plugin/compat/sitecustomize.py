import shapely
if not hasattr(shapely, 'maximum_inscribed_circle'):                # shapely 2.1; Rhino 8's Python 3.9 gets 2.0
    from shapely.ops import nearest_points, polylabel

    def maximum_inscribed_circle(geom, tolerance=None):
        p = polylabel(geom, tolerance or 1.0)
        return shapely.LineString([p, nearest_points(p, geom.boundary)[1]])
    shapely.maximum_inscribed_circle = maximum_inscribed_circle
