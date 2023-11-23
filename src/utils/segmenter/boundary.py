from shapely.geometry import LineString, Point
from rtree import index

from .orientation import Orientation


class Boundary:
    def __init__(self, idx, boundary):
        self.idx = idx
        self.line = LineString(boundary.coords)
        self.setup_sort_cache()
        self.setup_temporary_variables()

        # If N boundaries share a segment, the reference boundary
        # is the boundary with the min idx.
        self.segment_map = {}
        self.segments = []

        self.modified_line = None

    def setup_sort_cache(self):
        self.sort_cache = {}

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

    def setup_temporary_variables(self):
        self.ring_intersections = {}  # neighbor idx -> ring
        self.intersections = {}  # neighbor idx -> intersection segments

        # Cutpoints are points that define the endpoints of the segments.
        # If boundaries A and B share an intersection,
        # they are expected to have all the same cutpoints between them.
        # Will be sorted before use.
        self.cutpoints = []
        self.segment_idx_to_potential_reference_boundaries = None

    def on_boundary(self, point):
        start = Point(self.line.coords[0])
        end = Point(self.line.coords[-1])
        return point.intersects(self.line) \
            or point.equals(start) \
            or point.equals(end)

    def get_point_sort_key(self, point):
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

    def get_segment_idx_and_orientation(self, start, end, line):
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

    def get_segment(self, start, end):
        seg_idx = self.segment_map[(start, end)]
        return self.segments[seg_idx]

    def rebuild(self):
        segments = []
        for segment in self.segments:
            segment.rebuild()
            segments.append(segment.modified_line)

        modified_line = LineString(
            [c for segment in segments for c in segment.coords[:-1]]
            + [segments[-1].coords[-1]]
        )
        self.modified_line = modified_line
