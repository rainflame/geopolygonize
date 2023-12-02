from typing import List

from shapely import Polygon
from shapely.ops import polygonize, unary_union


def fix_polygon(polygon: Polygon) -> List[Polygon]:
    # https://gis.stackexchange.com/questions/423351/identifying-self-intersections-in-linestring-using-shapely
    exterior = polygon.exterior
    polygons = list(polygonize(unary_union(exterior)))
    # TODO: Figure out how to deal with interior boundaries if necessary.
    return polygons
