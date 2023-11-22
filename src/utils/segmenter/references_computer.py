from typing import List

from shapely.geometry import LineString, Point

from .segment import Segment


class ReferencesComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ):
        self.boundaries = boundaries

    def _get_positions(self, sort_key, length, points):
        positions = []
        for i, p in enumerate(points):
            position = sort_key(p)
            if i > 0 and position <= positions[i-1]:
                position += length
                assert position > positions[i-1], \
                    "Expect current position to be " \
                    "greater than previous position."
            positions.append(position)
        return positions

    def _get_iterations(self, line, sort_key, length):
        line_points = [Point(c) for c in line.coords]
        if line.is_ring:
            line_points = line_points[:-1]
        first_boundary = [(p, sort_key(p)) for p in line_points]
        second_boundary = [(p, pos + length) for (p, pos) in first_boundary]
        if line.is_ring:
            second_boundary.append((line_points[0], 2*length))
        return first_boundary + second_boundary

    def _get_segments_helper(self, line, sort_key, length, cutpoints):
        positions = self._get_positions(sort_key, length, cutpoints)
        assert len(positions) == len(cutpoints), \
            "Expect the number of positions to be " \
            "the same as the number of cutpoints."
        iterations = self._get_iterations(line, sort_key, length)

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

    def _get_segments(self, boundary, cutpoints):
        segments = self._get_segments_helper(
            boundary.line,
            boundary.point_sort_key,
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

    # Get cutpoints to split intersection by.
    def _get_relevant_cutpoints(self, boundary, intersection):
        start = Point(intersection.coords[0])
        end = Point(intersection.coords[-1])

        super_line = LineString(boundary.cutpoints)
        super_segments = self._get_segments_helper(
            super_line,
            boundary.point_sort_key,
            boundary.line.length,
            [start, end],
        )
        super_segment = super_segments[0]

        relevant_cutpoints = [Point(c) for c in super_segment.coords]
        return relevant_cutpoints

    def _compute_boundaries_per_segment(self):
        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            curr_boundary.segment_idx_to_neighbors = [
                [(b, curr_boundary.segments[i], False)]
                for i in range(len(curr_boundary.segments))
            ]

        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]

            for n in curr_boundary.ring_intersections:
                if n <= b:
                    continue
                other_boundary = self.boundaries[n]
                cutpoints_with_end =\
                    curr_boundary.cutpoints + [curr_boundary.cutpoints[0]]
                for i in range(len(cutpoints_with_end)-1):
                    start = cutpoints_with_end[i]
                    end = cutpoints_with_end[i+1]
                    segment = curr_boundary.get_segment(start, end)

                    other_seg_idx, reverse = \
                        other_boundary.get_segment_idx_and_reverse(
                            start, end, segment.line
                        )
                    other_boundary.segment_idx_to_neighbors[other_seg_idx] \
                        .append((b, segment, reverse))

            for n, intersection_segments \
                    in curr_boundary.intersections.items():
                if n <= b:
                    continue  # handled already
                other_boundary = self.boundaries[n]

                for intersection_segment in intersection_segments:
                    rel_cutpoints = self._get_relevant_cutpoints(
                        curr_boundary,
                        intersection_segment,
                    )

                    for i in range(len(rel_cutpoints)-1):
                        start = rel_cutpoints[i]
                        end = rel_cutpoints[i+1]
                        segment = curr_boundary.get_segment(start, end)

                        other_seg_idx, reverse = \
                            other_boundary.get_segment_idx_and_reverse(
                                start, end, segment.line
                            )
                        other_boundary \
                            .segment_idx_to_neighbors[other_seg_idx] \
                            .append((b, segment, reverse))

    def _compute_reference_per_segment(self):
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]

            for i, nps in enumerate(boundary.segment_idx_to_neighbors):
                _reference_idx, reference_segment, reverse = \
                    min(nps, key=lambda x: x[0])
                boundary.segments[i].set_reference(reference_segment, reverse)

    def compute_references(self):
        self._compute_segments_per_boundary()
        self._compute_boundaries_per_segment()
        self._compute_reference_per_segment()
