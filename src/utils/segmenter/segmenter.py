from shapely import LineString, Polygon
from typing import Callable, List

from .area import Area
from .boundary import Boundary
from .intersections_computer import IntersectionsComputer
from .cutpoints_computer import CutpointsComputer
from .references_computer import ReferencesComputer


class Segmenter:
    def __init__(
        self,
        polygons: List[Polygon]
    ):
        self.polygons = polygons

        self._build()

    def run_per_segment(
        self,
        per_segment_function: Callable[[LineString], LineString]
    ):
        for segment in self.segments:
            modified_line = per_segment_function(segment.modified_line)
            segment.modified_line = modified_line

    def get_result(self) -> List[Polygon]:
        self._rebuild()

        modified_polygons = [a.modified_polygon for a in self.areas]
        return modified_polygons

    def _build(self):
        self._area_build()
        self._boundary_build()
        self._segment_build()

    def _rebuild(self):
        self._boundary_rebuild()
        self._area_rebuild()

    def _area_build(self):
        areas = [Area(p) for p in self.polygons]
        self.areas = areas

    def _area_rebuild(self):
        for i in range(len(self.areas)):
            area = self.areas[i]
            area.rebuild()

    def _boundary_build(self):
        boundaries = []
        boundary_count = 0

        for i in range(len(self.areas)):
            area = self.areas[i]

            exterior = Boundary(boundary_count, area.polygon.exterior)
            boundary_count += 1

            interiors = [
                Boundary(boundary_count + j, l) for j, l
                in enumerate(area.polygon.interiors)
            ]
            boundary_count += len(area.polygon.interiors)

            area.exterior = exterior
            area.interiors = interiors

            boundaries.extend([exterior] + interiors)

        self.boundaries = boundaries

    def _boundary_rebuild(self):
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]
            boundary.rebuild()

    def _segment_build(self):
        IntersectionsComputer(self.boundaries).compute_intersections()
        CutpointsComputer(self.boundaries).compute_cutpoints()
        ReferencesComputer(self.boundaries).compute_references()

        segments = []
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]
            for segment in boundary.segments:
                if boundary.idx == segment.reference.boundary.idx:
                    segments.append(segment)
        self.segments = segments
