from shapely import LineString, Polygon
from typing import Callable, List

from .area import Area
from .boundary import Boundary
from .intersections_computer import IntersectionsComputer
from .cutpoints_computer import CutpointsComputer
from .mapping_computer import MappingComputer
from .references_computer import ReferencesComputer


class Segmenter:
    def __init__(
        self,
        polygons: List[Polygon]
    ) -> None:
        self.polygons = polygons

        self._build()

    def run_per_segment(
        self,
        per_segment_function: Callable[[LineString], LineString]
    ) -> None:
        for reference in self._references:
            modified_line = per_segment_function(
                reference.modified_line
            )
            reference.modified_line = modified_line

    def get_result(self) -> List[Polygon]:
        self._rebuild()

        modified_polygons = [a.modified_polygon for a in self._areas]
        return modified_polygons

    def _build(self) -> None:
        self._area_build()
        self._boundary_build()
        self._reference_build()

    def _rebuild(self) -> None:
        self._boundary_rebuild()
        self._area_rebuild()

    def _area_build(self) -> None:
        areas = [Area(p) for p in self.polygons]
        self._areas = areas

    def _area_rebuild(self) -> None:
        for i in range(len(self._areas)):
            area = self._areas[i]
            area.rebuild()

    def _boundary_build(self) -> None:
        boundaries = []
        boundary_count = 0

        for i in range(len(self._areas)):
            area = self._areas[i]

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

        self._boundaries = boundaries

    def _boundary_rebuild(self) -> None:
        for b in range(len(self._boundaries)):
            boundary = self._boundaries[b]
            boundary.rebuild()

    def _reference_build(self) -> None:
        IntersectionsComputer(self._boundaries).compute_intersections()
        CutpointsComputer(self._boundaries).compute_cutpoints()
        MappingComputer(self._boundaries).compute_mapping()
        references = ReferencesComputer(self._boundaries).compute_references()
        self._references = references
