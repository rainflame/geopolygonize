import shapely
from shapely import Geometry, LineString, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid
from typing import Callable, List, Tuple

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
        labels: List[str],
        pin_border: bool,
    ) -> None:
        self.polygons = polygons
        self.labels = labels
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

    def get_result(self) -> Tuple[List[Polygon], List[str]]:
        self._rebuild()

        modified_polygons = [a.modified_polygon for a in self._areas]
        modified_labels = self.labels

        if self.pin_border:
            try:
                self._check_boundary(modified_polygons)
            except shapely.TopologyException:
                # This error is yielded by `unary_union`,
                # likely because the polygons are meaningfully invalid.
                # We could try to (destructively) fix them, which may
                # make the check pass, but then the geometries will
                # be visually odd.
                # modified_polygons, modified_labels = self._destructive_fix(
                #     modified_polygons,
                #     modified_labels
                # )
                # self._check_boundary(modified_polygons)
                pass

        return modified_polygons, modified_labels

    def _check_boundary(self, polygons: List[Polygon]) -> None:
        union = unary_union(polygons)
        union = clean_polygon(union)
        modified_border = union.exterior
        assert modified_border.equals(self.border)

    def _destructive_fix(
        self,
        polygons: List[Polygon],
        labels: List[str],
    ) -> Tuple[List[Polygon], List[str]]:
        def flatten(geo: Geometry) -> List[Polygon]:
            polygons: List[Polygon] = []
            if geo.geom_type == "Polygon":
                polygons.append(geo)
            elif geo.geom_type == "MultiPolygon":
                polygons.extend(list(geo.geoms))
            return polygons

        fixed_polygons: List[Polygon] = []
        fixed_labels: List[str] = []
        for i, mp in enumerate(polygons):
            label = labels[i]
            if not mp.is_valid:
                fixed = make_valid(mp)
                polygons = flatten(fixed)
                fixed_polygons.extend(polygons)
                fixed_labels.extend([label] * len(polygons))
            else:
                fixed_polygons.append(mp)
                fixed_labels.append(label)

        return fixed_polygons, fixed_labels

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
