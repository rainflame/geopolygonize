from sortedcontainers import SortedDict
from typing import Dict, ItemsView, List, Tuple, TypeAlias

from shapely.geometry import LineString, Point
from rtree import index

from .orientation import Orientation
from .segment import Segment

NeighborIdx: TypeAlias = int


class Boundary(object):
    def __enter__(self) -> 'Boundary':
        return self

    def __init__(
        self,
        idx: int,
        boundary: LineString,
    ) -> None:
        self.idx = idx
        self.line = LineString(boundary.coords)
        self.setup_sort_cache()
        self.setup_temporary_variables()

        self.segment_map: Dict[Tuple[int, int], int] | None = None
        self.segments: List[Segment] = []

        self.modified_line: LineString | None = None

    def setup_sort_cache(self) -> None:
        self.sort_cache: Dict[Point, float] = {}

        start = Point(self.line.coords[0])
        self.cumulative_distances = {start: 0}
        for i in range(1, len(self.line.coords) - 1):
            seg_start = Point(self.line.coords[i-1])
            seg_end = Point(self.line.coords[i])
            segment = LineString([seg_start, seg_end])
            self.cumulative_distances[seg_end] = \
                self.cumulative_distances[seg_start] + segment.length
        # end is same as beginning

        self.seg_idx = index.Index()
        for i in range(len(self.line.coords) - 1):
            segment = LineString(
                [self.line.coords[i], self.line.coords[i + 1]]
            )
            bbox = segment.bounds
            self.seg_idx.insert(i, bbox)

    def setup_temporary_variables(self) -> None:
        self.ring_intersections: Dict[NeighborIdx, LineString] = {}
        self.intersections: Dict[NeighborIdx, List[LineString]] = {}

        # Cutpoints are points that define the endpoints of the segments.
        # If boundaries A and B share an intersection,
        # they are expected to have all the same cutpoints between them.
        self.cutpoints = SortedDict()

        # Index i is potential references for self.segments[i].
        self.potential_references: List[List[Segment]] = []

    def on_boundary(self, point: Point) -> bool:
        start = Point(self.line.coords[0])
        end = Point(self.line.coords[-1])
        return point.intersects(self.line) \
            or point.equals(start) \
            or point.equals(end)

    def get_point_sort_key(self, point: Point) -> float:
        if point in self.sort_cache:
            return self.sort_cache[point]

        if point in self.cumulative_distances:
            distance = self.cumulative_distances[point]
        else:
            s_idxes = list(self.seg_idx.intersection(point.bounds))
            if len(s_idxes) == 0:
                raise Exception('Point is not in line as expected.')
            if len(s_idxes) > 1:
                raise Exception(
                    'Point is not between just two '
                    'line coordinates as expected.'
                )
            s_idx = s_idxes[0]
            seg_start = Point(self.line.coords[s_idx])
            seg_end = Point(self.line.coords[s_idx + 1])
            segment = LineString([seg_start, seg_end])
            distance = \
                self.cumulative_distances[seg_start] + segment.project(point)

        self.sort_cache[point] = distance
        return distance

    def add_ring_intersection(
        self,
        other, #: Boundary,
        ring: LineString,
    ) -> None:
        assert ring.is_ring
        self.ring_intersections[other.idx] = ring

    def get_ring_intersections(self) -> ItemsView[NeighborIdx, LineString]:
        return self.ring_intersections.items()

    def add_intersection(
        self,
        other, #: Boundary,
        segments: List[LineString],
    ) -> None:
        self.intersections[other.idx] = segments

    def get_intersections(self) -> ItemsView[NeighborIdx, List[LineString]]:
        return self.intersections.items()

    def add_cutpoint(self, cutpoint: Point) -> None:
        key = self.get_point_sort_key(cutpoint)
        self.cutpoints[key] = cutpoint

    def get_cutpoints(self) -> List[Point]:
        return list(self.cutpoints.values())

    def set_segments(self, segments: List[Segment]) -> None:
        assert len(self.cutpoints) == len(segments), \
            "Expect number of segments " \
            "to equal number of cutpoints."
        self.segments = segments
        self.segment_map = {
            (s.start, s.end): i for i, s in enumerate(self.segments)
        }
        self.potential_references = [
            [] for i in range(len(self.segments))
        ]

    def add_potential_reference(
        self,
        reference: Segment,
    ) -> None:
        idx, _orientation = self.get_segment_idx_and_orientation(
            reference.start,
            reference.end,
            reference.line
        )
        self.potential_references[idx].append(reference)

    def get_segments_with_potential_references(
        self
    ) -> List[Tuple[Segment, List[Segment]]]:
        assert len(self.segments) == len(self.potential_references)
        return list(zip(self.segments, self.potential_references))

    def get_orientation(self, segment: Segment) -> Orientation:
        _idx, orientation = self.get_segment_idx_and_orientation(
            segment.start,
            segment.end,
            segment.line
        )
        return orientation

    def get_segment_idx_and_orientation(
        self,
        start: int,
        end: int,
        line: LineString,
    ) -> Tuple[int, Orientation]:
        assert self.segment_map is not None and self.segments is not None

        if len(self.segments) == 1:
            if (start, end) in self.segment_map:
                assert start == end
                seg_idx = self.segment_map[(start, end)]
                assert seg_idx == 0
                orientation = Orientation.FORWARD
            else:
                raise Exception(
                    "Could not find segment idx "
                    "for given start and end points."
                )
        elif len(self.segments) == 2:
            first_seg_idx = self.segment_map[(start, end)]
            first_segment = self.segments[first_seg_idx]
            second_seg_idx = self.segment_map[(end, start)]
            second_segment = self.segments[second_seg_idx]
            reverse_line = LineString(line.coords[::-1])

            if first_segment.line.equals(line):
                seg_idx = first_seg_idx
                orientation = Orientation.FORWARD
            elif first_segment.line.equals(reverse_line):
                seg_idx = first_seg_idx
                orientation = Orientation.BACKWARD
            elif second_segment.line.equals(line):
                seg_idx = second_seg_idx
                orientation = Orientation.BACKWARD
            elif second_segment.line.equals(reverse_line):
                seg_idx = second_seg_idx
                orientation = Orientation.FORWARD
            else:
                raise Exception(
                    "Could not find segment idx for "
                    "given start and end points and line."
                )
        else:
            if (start, end) in self.segment_map:
                seg_idx = self.segment_map[(start, end)]
                orientation = Orientation.FORWARD
            elif (end, start) in self.segment_map:
                seg_idx = self.segment_map[(end, start)]
                orientation = Orientation.BACKWARD
            else:
                raise Exception(
                    "Could not find segment idx "
                    "for given start and end points."
                )

        return seg_idx, orientation

    def get_segment(self, start: int, end: int) -> Segment:
        assert self.segment_map is not None and self.segments is not None

        seg_idx = self.segment_map[(start, end)]
        return self.segments[seg_idx]

    def rebuild(self) -> None:
        assert self.segments is not None

        segments = []
        for segment in self.segments:
            segment.rebuild()
            segments.append(segment.modified_line)

        modified_line = LineString(
            [c for segment in segments for c in segment.coords[:-1]]
            + [segments[-1].coords[-1]]
        )
        self.modified_line = modified_line
