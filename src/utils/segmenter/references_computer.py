from typing import List

from shapely.geometry import LineString, Point

from .boundary_cutter import BoundaryCutter
from .boundary import Boundary
from .segment import Segment


"""
Identifies boundaries that share a common segment and determines
the reference segment object from which duplicates of the segment
in the boundaries should copy from.
"""


class ReferencesComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ) -> None:
        self.boundaries = boundaries

    def _consider_boundary_for_segments(
        self,
        curr_boundary: Boundary,
    ) -> None:
        curr_boundary = self.boundaries[curr_boundary.idx]
        for i, segment in enumerate(curr_boundary.segments):
            curr_boundary.add_potential_reference(segment)

    def _consider_neighbor_for_closed_segments(
        self,
        curr_boundary: Boundary,
    ) -> None:
        for o, _closed in curr_boundary.get_closed_intersections():
            if o <= curr_boundary.idx:
                continue
            other_boundary = self.boundaries[o]

            cutpoints = curr_boundary.get_cutpoints()
            cutpoints_with_end = cutpoints + [cutpoints[0]]

            for i in range(len(cutpoints_with_end)-1):
                start = cutpoints_with_end[i]
                end = cutpoints_with_end[i+1]
                segment = curr_boundary.get_segment(start, end)
                other_boundary.add_potential_reference(segment)

    # Get cutpoints to split intersection by.
    def _get_relevant_cutpoints(
        self,
        boundary: Boundary,
        intersection: LineString,
    ) -> List[Point]:
        start = Point(intersection.coords[0])
        end = Point(intersection.coords[-1])

        cutpoints = boundary.get_cutpoints()
        cutpoints_with_end = cutpoints + [cutpoints[0]]
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

    def _consider_neighbor_for_line_segments(
        self,
        curr_boundary: Boundary,
    ) -> None:
        for o, intersection_segments \
                in curr_boundary.get_intersections():
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
                    other_boundary.add_potential_reference(segment)

    def _compute_reference_options_per_segment(self) -> None:
        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            self._consider_boundary_for_segments(curr_boundary)

        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            self._consider_neighbor_for_closed_segments(curr_boundary)

        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            self._consider_neighbor_for_line_segments(curr_boundary)

    def _choose_references(self) -> List[Segment]:
        references = []
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]

            for segment, potential_references in \
                    boundary.get_segments_with_potential_references():
                reference = min(
                    potential_references,
                    key=lambda r: r.boundary.idx
                )
                segment.set_reference(reference)

                if segment.is_reference():
                    references.append(reference)

        return references

    def compute_references(self) -> List[Segment]:
        self._compute_reference_options_per_segment()
        references = self._choose_references()
        return references
