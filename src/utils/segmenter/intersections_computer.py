from typing import List

from shapely.geometry import LineString, Point
from rtree import index


"""
Computes intersections between boundaries, each of which keeps a record
of which other boundaries it intersected with and where.
"""
class IntersectionsComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ):
        self.boundaries = boundaries

    def make_index(self):
        boundary_idx = index.Index()
        for i, boundary in enumerate(self.boundaries):
            bbox = boundary.line.bounds
            boundary_idx.insert(i, bbox)
        return boundary_idx

    def _line_string(self, ls):
        if len(ls.coords) < 2:
            return []  # invalid segment, effectively skip
        else:
            assert len(ls.coords) == 2, \
                "Expect LineString from intersection to have only two points."
            return [ls]

    def _multi_line_string(self, mls):
        pieces = []
        for b in mls.geoms:
            pieces.extend(self._line_string(b))
        return pieces

    def _geometry_collection(self, gc):
        pieces = []
        for g in gc.geoms:
            pieces.extend(self._handle(g))
        return pieces

    def _handle(self, g):
        pieces = []
        if g.geom_type == "LineString":
            pieces = self._line_string(g)
        elif g.geom_type == "MultiLineString":
            pieces = self._multi_line_string(g)
        elif g.geom_type == "GeometryCollection":
            pieces = self._geometry_collection(g)
        else:
            # skip Point, MultiPoint or non-existent intersection
            pass
        return pieces

    def _get_connected_segments(self, pieces):
        if len(pieces) == 0:
            return []

        start_map = {}
        end_map = {}
        for p in pieces:
            assert len(p.coords) == 2, \
                "Expect each piece to have only two points."
            start_map[Point(p.coords[0])] = p
            end_map[Point(p.coords[-1])] = p

        segments = []
        unvisited = set(pieces)
        while len(unvisited) > 0:
            piece = unvisited.pop()
            start = Point(piece.coords[0])
            end = Point(piece.coords[-1])

            curr = start
            former_section = [start]
            while curr in end_map:
                prev_piece = end_map[curr]
                curr = Point(prev_piece.coords[0])
                former_section.append(curr)
                if prev_piece not in unvisited:
                    break  # reached termination in former half of segment
                unvisited.remove(prev_piece)

            is_ring = len(former_section) > 2 \
                and Point(former_section[-1]) == start
            if is_ring:
                latter_section = []
            else:
                curr = end
                latter_section = [end]
                while curr in start_map:
                    next_piece = start_map[curr]
                    curr = Point(next_piece.coords[-1])
                    latter_section.append(curr)
                    if next_piece not in unvisited:
                        break  # reached termination in latter half of segment
                    unvisited.remove(next_piece)

            segment = LineString(former_section[::-1] + latter_section)
            segments.append(segment)

        return segments

    def compute_intersections(self):
        boundary_idx = self._make_index()

        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]

            for n in boundary_idx.intersection(curr_boundary.line.bounds):
                if n == b:
                    continue
                if n < b:
                    continue  # handled already
                other_boundary = self.boundaries[n]

                intersection =\
                    curr_boundary.line.intersection(other_boundary.line)
                intersection_pieces = self._handle(intersection)

                intersection_segments =\
                    self._get_connected_segments(intersection_pieces)
                if len(intersection_segments) == 0:
                    continue

                is_ring = False
                for intersection_segment in intersection_segments:
                    if intersection_segment.is_ring:
                        is_ring = True

                if is_ring:
                    assert len(intersection_segments) == 1, \
                        "If the intersection with another boundary is a "\
                        "ring, expect the ring to be the only intersection."
                    ring = intersection_segments[0]
                    curr_boundary.ring_intersections[n] = ring
                    other_boundary.ring_intersections[b] = ring
                else:
                    curr_boundary.intersections[n] = intersection_segments
                    other_boundary.intersections[b] = intersection_segments
