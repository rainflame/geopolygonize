from shapely import LineString, Polygon
from shapely.ops import unary_union
from typing import Callable, List

from .area import Area
from .boundary import Boundary
from .clean_polygon import clean_polygon
from .intersections_computer import IntersectionsComputer
from .cutpoints_computer import CutpointsComputer
from .mapping_computer import MappingComputer
from .references_computer import ReferencesComputer


class Segmenter:
    def __init__(
        self,
        polygons: List[Polygon],
        pin_border: bool,
    ) -> None:
        self.polygons = polygons
        self.pin_border = pin_border

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

        # TODO: Hypothesis: A polygon is invalid.
        # I.e. An interior boundary is touching exterior boundary.
        # https://groups.google.com/g/postgis-users/c/kdWJRt0PYKc/m/SubzGr2ceZAJ
        # https://stackoverflow.com/questions/20833344/fix-invalid-polygon-in-shapely
        for mp in modified_polygons:
            if not mp.is_valid:
                raise ValueError(f"Found invalid polygon: {mp.coords}")

        if self.pin_border:
            union = unary_union(modified_polygons)
            modified_border = clean_polygon(union).exterior
            assert modified_border.equals(self.border)

        return modified_polygons

    def _build(self) -> None:
        if self.pin_border:
            self._border_build()

        self._area_build()
        self._boundary_build()
        self._reference_build()

    def _rebuild(self) -> None:
        self._boundary_rebuild()
        self._area_rebuild()

    def _border_build(self) -> None:
        union = unary_union(self.polygons)
        self.border: LineString = clean_polygon(union).exterior

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
        intersections_computer = IntersectionsComputer(self._boundaries)
        intersections_computer.compute_intersections()
        if self.pin_border:
            intersections_computer.compute_border_intersections(self.border)

        cutpoints_computer = CutpointsComputer(self._boundaries)
        cutpoints_computer.compute_cutpoints()
        if self.pin_border:
            cutpoints_computer.compute_border_cutpoints(self.border)

        MappingComputer(self._boundaries).compute_mapping()

        references = ReferencesComputer(self._boundaries).compute_references()
        self._references = references
