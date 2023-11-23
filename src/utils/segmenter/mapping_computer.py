from typing import Callable, List

from shapely.geometry import LineString, Point

from .boundary import Boundary
from .segment import Segment


class MappingComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ):
        self.boundaries = boundaries

    def _get_positions(
        self,
        get_sort_key: Callable[[Point], float],
        length: float,
        points: List[Point]
    ) -> List[float]:
        positions: List[float] = []
        for i, p in enumerate(points):
            position = get_sort_key(p)
            if i > 0 and position <= positions[i-1]:
                position += length
                assert position > positions[i-1], \
                    "Expect current position to be " \
                    "greater than previous position."
            positions.append(position)
        return positions

    def _get_iterations(
        self,
        line: LineString,
        get_sort_key: Callable[[Point], float],
        length: float,
    ) -> List[Point]:
        line_points = [Point(c) for c in line.coords]
        if line.is_ring:
            line_points = line_points[:-1]
        first_boundary = [(p, get_sort_key(p)) for p in line_points]
        second_boundary = [(p, pos + length) for (p, pos) in first_boundary]
        if line.is_ring:
            second_boundary.append((line_points[0], 2*length))
        return first_boundary + second_boundary

    def _get_segments_helper(
        self,
        line: LineString,
        get_sort_key: Callable[[Point], float],
        length: float,
        cutpoints: List[Point]
    ) -> List[LineString]:
        positions = self._get_positions(get_sort_key, length, cutpoints)
        assert len(positions) == len(cutpoints), \
            "Expect the number of positions to be " \
            "the same as the number of cutpoints."
        iterations = self._get_iterations(line, get_sort_key, length)

        segments = []
        segment_coords = None
        cutpoint_idx = 0
        for (p, pos) in iterations:
            if cutpoint_idx == len(cutpoints):
                break

            if pos < positions[cutpoint_idx]:
                if segment_coords is None:
                    continue
                else:
                    segment_coords.append(p)
            else:
                if segment_coords is None:
                    segment_coords = []
                while cutpoint_idx < len(cutpoints) \
                        and pos >= positions[cutpoint_idx]:
                    segment_coords.append(cutpoints[cutpoint_idx])
                    if cutpoint_idx > 0:
                        segments.append(LineString(segment_coords))
                        segment_coords = [cutpoints[cutpoint_idx]]
                        if pos > positions[cutpoint_idx] \
                                and pos < positions[cutpoint_idx+1]:
                            segment_coords.append(p)
                    cutpoint_idx += 1

        return segments

    def _get_segments(
        self,
        boundary: Boundary,
        cutpoints: List[Point],
    ) -> List[LineString]:
        segments = self._get_segments_helper(
            boundary.line,
            boundary.get_point_sort_key,
            boundary.line.length, cutpoints,
        )
        assert len(segments) == len(cutpoints) - 1, \
            "Expect number of segments to be one " \
            "less than number of inputted cutpoints."
        return segments

    def _compute_segments_per_boundary(self):
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]

            cutpoints_with_end = boundary.cutpoints + [boundary.cutpoints[0]]
            segment_lines = self._get_segments(boundary, cutpoints_with_end)
            boundary.segments = [Segment(boundary, sl) for sl in segment_lines]
            assert len(boundary.cutpoints) == len(boundary.segments), \
                "Expect number of segments " \
                "to equal number of cutpoints."
            boundary.segment_map = {
                (s.start, s.end): i for i, s in enumerate(boundary.segments)
            }

    def compute_mapping(self):
        self._compute_segments_per_boundary()
