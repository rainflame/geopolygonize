from typing import Dict, List, Set

from shapely import Geometry
from shapely.geometry import \
    GeometryCollection, \
    LineString, \
    MultiLineString, \
    Point
from rtree import index

from .boundary import Boundary
from .piece import Piece


"""
Computes intersections between boundaries, each of which keeps a record
of which other boundaries it intersected with and where.
"""


class IntersectionsComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ) -> None:
        self.boundaries = boundaries

    def _make_index(self) -> index.Index:
        boundary_idx = index.Index()
        for i, boundary in enumerate(self.boundaries):
            bbox = boundary.line.bounds
            boundary_idx.insert(i, bbox)
        return boundary_idx

    def _line_string(self, ls: LineString) -> List[Piece]:
        if len(ls.coords) < 2:
            return []  # invalid segment, effectively skip
        return [Piece(ls)]

    def _multi_line_string(self, mls: MultiLineString) -> List[Piece]:
        pieces = []
        for b in mls.geoms:
            pieces.extend(self._line_string(b))
        return pieces

    def _geometry_collection(self, gc: GeometryCollection) -> List[Piece]:
        pieces = []
        for g in gc.geoms:
            pieces.extend(self._handle(g))
        return pieces

    def _handle(self, g: Geometry) -> List[Piece]:
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

    def _get_connected_segment(
        self,
        start_map: Dict[Point, Piece],
        end_map: Dict[Point, Piece],
        unvisited: Set[Piece],
        piece: Piece,
    ) -> LineString:
        curr = piece.start
        former_section = [piece.start]
        while curr in end_map:
            prev_piece = end_map[curr]
            curr = prev_piece.start
            former_section.append(curr)
            if prev_piece not in unvisited:
                break  # reached termination in former half of segment
            unvisited.remove(prev_piece)

        is_ring = len(former_section) > 2 \
            and Point(former_section[-1]) == piece.start
        if is_ring:
            latter_section = []
        else:
            curr = piece.end
            latter_section = [piece.end]
            while curr in start_map:
                next_piece = start_map[curr]
                curr = Point(next_piece.end)
                latter_section.append(curr)
                if next_piece not in unvisited:
                    break  # reached termination in latter half of segment
                unvisited.remove(next_piece)

        segment = LineString(former_section[::-1] + latter_section)
        return segment

    def _get_connected_segments(self, pieces: List[Piece]) -> List[LineString]:
        if len(pieces) == 0:
            return []

        start_map: Dict[Point, Piece] = {}
        end_map: Dict[Point, Piece] = {}
        for p in pieces:
            start_map[p.start] = p
            end_map[p.end] = p

        segments = []
        unvisited = set(pieces)
        while len(unvisited) > 0:
            piece = unvisited.pop()
            segment = self._get_connected_segment(
                start_map,
                end_map,
                unvisited,
                piece
            )
            segments.append(segment)

        return segments

    def _compute_intersection(self, curr: Boundary, other: Boundary) -> None:
        intersection = curr.line.intersection(other.line)
        intersection_pieces = self._handle(intersection)

        intersection_segments =\
            self._get_connected_segments(intersection_pieces)
        if len(intersection_segments) == 0:
            return

        is_ring = False
        for intersection_segment in intersection_segments:
            if intersection_segment.is_ring:
                is_ring = True

        if is_ring:
            assert len(intersection_segments) == 1, \
                "If the intersection with another boundary is a "\
                "ring, expect the ring to be the only intersection."
            ring = intersection_segments[0]
            curr.add_ring_intersection(other, ring)
            other.add_ring_intersection(curr, ring)
        else:
            curr.add_intersection(other, intersection_segments)
            other.add_intersection(curr, intersection_segments)

    def compute_intersections(self) -> None:
        boundary_idx = self._make_index()

        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]

            for o in boundary_idx.intersection(curr_boundary.line.bounds):
                if o == b:
                    continue
                if o < b:
                    continue  # handled already
                other_boundary = self.boundaries[o]

                self._compute_intersection(curr_boundary, other_boundary)
