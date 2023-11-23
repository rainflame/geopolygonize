from typing import List

from shapely.geometry import LineString, Point

from .boundary_cutter import BoundaryCutter
from .boundary import Boundary


"""
Identifies boundaries that share a common segment and determines
the reference segment object from which duplicates of the segment
in the boundaries should copy from.
"""


class ReferencesComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ):
        self.boundaries = boundaries

    def _consider_boundary_for_segments(self, curr_boundary):
        curr_boundary = self.boundaries[curr_boundary.idx]
        curr_boundary.segment_idx_to_neighbors = [
            [(curr_boundary.idx, curr_boundary.segments[i], False)]
            for i in range(len(curr_boundary.segments))
        ]

    def _consider_neighbor_for_loop_segments(self, curr_boundary):
        for o in curr_boundary.ring_intersections:
            if o <= curr_boundary.idx:
                continue
            other_boundary = self.boundaries[o]

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
                other_boundary\
                    .segment_idx_to_neighbors[
                        other_seg_idx
                    ] \
                    .append((curr_boundary.idx, segment, reverse))

    # Get cutpoints to split intersection by.
    def _get_relevant_cutpoints(
        self,
        boundary: Boundary,
        intersection: LineString
    ) -> List[Point]:
        start = Point(intersection.coords[0])
        end = Point(intersection.coords[-1])

        cutpoints_with_end = boundary.cutpoints + [boundary.cutpoints[0]]
        boundary_with_just_cutpoints = \
            Boundary(-1, LineString(cutpoints_with_end))
        boundary_cutter = BoundaryCutter(
            boundary_with_just_cutpoints,
            [start, end],
        )
        super_segments = boundary_cutter.cut_boundary()
        super_segment = super_segments[0]

        relevant_cutpoints = [Point(c) for c in super_segment.coords]
        return relevant_cutpoints

    def _consider_neighbor_for_line_segments(self, curr_boundary):
        for o, intersection_segments \
                in curr_boundary.intersections.items():
            if o <= curr_boundary.idx:
                continue  # handled already
            other_boundary = self.boundaries[o]

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
                        .segment_idx_to_neighbors[
                            other_seg_idx
                        ] \
                        .append((curr_boundary.idx, segment, reverse))

    def _compute_reference_options_per_segment(self):
        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            self._consider_boundary_for_segments(curr_boundary)

        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            self._consider_neighbor_for_loop_segments(curr_boundary)

        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            self._consider_neighbor_for_line_segments(curr_boundary)

    def _choose_reference_option_per_segment(self):
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]

            for i, nps in enumerate(boundary.segment_idx_to_neighbors):
                _reference_idx, reference_segment, reverse = \
                    min(nps, key=lambda x: x[0])
                boundary.segments[i].set_reference(reference_segment, reverse)

    def compute_references(self):
        self._compute_reference_options_per_segment()
        self._choose_reference_option_per_segment()
