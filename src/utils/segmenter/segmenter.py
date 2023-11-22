from .area_computer import build as area_build, rebuild as area_rebuild
from .loop_computer import build as loop_build, rebuild as loop_rebuild
from .segment_computer import build as segment_build, update as segment_update


class Segmenter:
    def __init__(self, polygons):
        self.polygons = polygons
        self.build()

    def build(self):
        self.areas = area_build(self.polygons)
        self.loops = loop_build(self.areas)
        self.segments = segment_build(self.loops)

    def run_per_segment(self, per_segment_function):
        segment_update(self.segments, per_segment_function)

    def rebuild(self):
        loop_rebuild(self.loops)
        area_rebuild(self.areas)

    def get_result(self):
        modified_polygons = [a.modified_polygon for a in self.areas]
        return modified_polygons
