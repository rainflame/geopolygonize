from typing import List

from shapely.geometry import LineString

from .boundary_cutter import BoundaryCutter
from .segment import Segment


class MappingComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ) -> None:
        self.boundaries = boundaries

    def _compute_segments_per_boundary(self) -> None:
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]

            cutpoints = boundary.get_cutpoints()
            cutpoints_with_end = cutpoints + [cutpoints[0]]
            boundary_cutter = BoundaryCutter(boundary, cutpoints_with_end)
            segments = [
                Segment(boundary, sl) for sl in boundary_cutter.cut_boundary()
            ]
            boundary.set_segments(segments)

    def compute_mapping(self) -> None:
        self._compute_segments_per_boundary()
