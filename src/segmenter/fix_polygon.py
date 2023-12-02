from typing import List

from shapely import LineString, Polygon
from shapely.ops import polygonize, unary_union


def fix_polygon(polygon: Polygon) -> List[Polygon]:
    # https://gis.stackexchange.com/questions/423351/identifying-self-intersections-in-linestring-using-shapely
    exterior = polygon.exterior
    exterior_polygons = list(polygonize(unary_union(exterior)))
    fixed_polygon_exterior: List[LineString] = [
        ep.exterior for ep in exterior_polygons
    ]

    interior_polygons = [
        p
        for interior in polygon.interiors
        for p in list(polygonize(unary_union(interior)))
    ]
    fixed_polygon_interiors: List[List[LineString]] = [
        [] for i in range(len(exterior_polygons))
    ]
    for ip in interior_polygons:
        for e, ep in enumerate(exterior_polygons):
            if ep.contains(ip):
                fixed_polygon_interiors[e].append(ip.exterior)
                break

    fixed_polygons = []
    for fe, fis in list(zip(fixed_polygon_exterior, fixed_polygon_interiors)):
        fixed_polygon = Polygon(fe, fis)
        fixed_polygons.append(fixed_polygon)
    return fixed_polygons
