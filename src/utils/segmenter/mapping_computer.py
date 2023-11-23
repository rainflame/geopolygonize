from typing import List

from shapely.geometry import LineString

from .boundary_cutter import BoundaryCutter
from .segment import Segment


class MappingComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ):
        self.boundaries = boundaries

    def _compute_segments_per_boundary(self):
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]

            cutpoints_with_end = boundary.cutpoints + [boundary.cutpoints[0]]
            boundary_cutter = BoundaryCutter(boundary, cutpoints_with_end)
            segment_lines = boundary_cutter.cut_boundary()
            boundary.segments = [Segment(boundary, sl) for sl in segment_lines]
            assert len(boundary.cutpoints) == len(boundary.segments), \
                "Expect number of segments " \
                "to equal number of cutpoints."
            boundary.segment_map = {
                (s.start, s.end): i for i, s in enumerate(boundary.segments)
            }

    def compute_mapping(self):
        self._compute_segments_per_boundary()
