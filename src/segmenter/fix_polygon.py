from typing import Dict, List

from shapely import Point, Polygon


def _extract(coords: List[Point]) -> List[List[Point]]:
    curr_coords = coords.copy()
    visited: Dict[Point, int] = {}
    i = 0
    sections = []
    while len(curr_coords) > 0:
        c = curr_coords[i]
        if c in visited:
            prev_i = visited[c]
            section = curr_coords[prev_i:i]
            sections.append(section)
            curr_coords = curr_coords[:prev_i] + [c] + curr_coords[i:]
            i = prev_i
            for k, v in visited.items():
                if v >= i:
                    del visited[k]
        visited[c] = i
        i += 1
    assert i == 0
    return sections

def fix_polygon(polygon: Polygon) -> List[Polygon]:
    # TODO: Polygons likely will not have points at the intersection,
    # which the algorithm currently assumes to be the case.
    # Also, polygons have exteriors and interiors, which are LineStrings
    # that then have coords.
    coords = [Point(c) for c in polygon.coords]
    sections = _extract(coords)
    for s in sections:
        assert s[0] == s[-1]
    rings = [s for s in sections if len(s) > 3]
    polygons = [Polygon(ring) for ring in rings]
    return polygons
