from .area_computer import build as area_build, rebuild as area_rebuild
from .boundary_computer import\
    build as boundary_build, \
    rebuild as boundary_rebuild
from .segment_computer import build as segment_build, update as segment_update


class Segmenter:
    def __init__(self, polygons):
        self.polygons = polygons

        self._build()

    def run_per_segment(self, per_segment_function):
        segment_update(self.segments, per_segment_function)

    def get_result(self):
        self._rebuild()

        modified_polygons = [a.modified_polygon for a in self.areas]
        return modified_polygons

    def _build(self):
        self.areas = area_build(self.polygons)
        self.boundaries = boundary_build(self.areas)
        self.segments = segment_build(self.boundaries)

    def _rebuild(self):
        boundary_rebuild(self.boundaries)
        area_rebuild(self.areas)
