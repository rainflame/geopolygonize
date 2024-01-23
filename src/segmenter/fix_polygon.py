import networkx as nx
from typing import List

from shapely import LineString, Polygon
from shapely.geometry import mapping
from shapely.ops import polygonize, unary_union


# intersection is not just a point
def meaningful_intersection(p1: Polygon, p2: Polygon) -> bool:
    p1b = LineString(p1.exterior.coords)
    p2b = LineString(p2.exterior.coords)
    intersection = p1b.intersection(p2b)
    result = False
    if intersection.geom_type != "Point":
        if not intersection.is_empty:
            result = True
    return result


def handle_merges(polygons: List[Polygon]) -> List[Polygon]:
    # remove holes
    shells = [Polygon(polygon.exterior) for polygon in polygons]

    N = len(shells)
    G = nx.Graph()
    for i in range(N):
        p1 = shells[i]
        for j in range(i+1, N):
            p2 = shells[j]

            merge = False
            if p2.contains(p1) or p1.contains(p2):
                merge = True
            if meaningful_intersection(p1, p2):
                merge = True

            if merge:
                G.add_edge(i, j)

    mergable_sets = list(nx.connected_components(G))
    for i in range(N):
        if not any(i in ms for ms in mergable_sets):
            mergable_sets.append({i})

    results = []
    for mergable_set in mergable_sets:
        relevant = [shells[i] for i in mergable_set]
        if len(relevant) == 1:
            result = relevant[0]
        else:
            result = unary_union(relevant)
        results.append(result)

    return results


# All interior polygons should be within exterior polygon at start.
def handle_cuts(
    exterior_polygon: Polygon,
    interior_polygons: List[Polygon],
) -> List[Polygon]:
    cut_exterior_polygons = []
    remaining_interior_polygons = []
    for ip in interior_polygons:
        if meaningful_intersection(exterior_polygon, ip):
            exterior_polygon = exterior_polygon.difference(ip)
        else:
            remaining_interior_polygons.append(ip)
    return exterior_polygon, remaining_interior_polygons


def fix_polygon(polygon: Polygon) -> List[Polygon]:
    # https://gis.stackexchange.com/questions/423351/identifying-self-intersections-in-linestring-using-shapely
    exterior = polygon.exterior
    exterior_polygons = list(polygonize(unary_union(exterior)))
    exterior_polygons = handle_merges(exterior_polygons)

    all_interior_polygons = []
    for interior in polygon.interiors:
        interior_polygons = list(polygonize(unary_union(interior)))
        for ip in interior_polygons:
            all_interior_polygons.append(ip)
    all_interior_polygons = handle_merges(all_interior_polygons)

    per_polygon_interiors: List[List[Polygon]] = [
        [] for i in range(len(exterior_polygons))
    ]
    for ip in all_interior_polygons:
        for e, ep in enumerate(exterior_polygons):
            if ep.contains(ip):
                per_polygon_interiors[e].append(ip)
                break

    fixed_polygons = []
    for ep, ips in list(zip(exterior_polygons, per_polygon_interiors)):
        ep, ips = handle_cuts(ep, ips)
        fixed_polygon = Polygon(ep.exterior, [ip.exterior for ip in ips])

        if not fixed_polygon.is_valid:
            import uuid
            import geojson

            instance_id = uuid.uuid4().int
            orig_json = mapping(polygon)
            orig_file = f"/tmp/orig_polygon_{instance_id}"
            with open(orig_file, "w") as file:
                geojson.dump(orig_json, file)

            fixed_json = mapping(fixed_polygon)
            fixed_file = f"/tmp/fixed_polygon_{instance_id}"
            with open(fixed_file, "w") as file:
                geojson.dump(fixed_json, file)

            info_msg = f"Original polygon saved to {orig_file}. " \
                 + f"'Fixed' polygon saved to {fixed_file}."

            raise Exception(
                f"Polygon is not valid after fixing.\n{info_msg}"
            )

        fixed_polygons.append(fixed_polygon)
    return fixed_polygons
