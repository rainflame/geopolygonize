from rasterio.transform import xy
from shapely.geometry import Polygon

from .area_computer import build as area_build, rebuild as area_rebuild
from .loop_computer import build as loop_build, rebuild as loop_rebuild
from .segment_computer import build as segment_build, update as segment_update


class Segmenter:
    def __init__(self, data, transform):
        self.data = data
        self.transform = transform
        self.build()

    def build(self):
        self.areas = area_build(self.data, self.transform)

        # Add a polygon that is the perimeter of data.
        # This ensures that we fix the boundary of the data in place.
        self.perimeter = self.build_perimeter()
        self.loops = loop_build(self.perimeter, self.areas)

        self.segments = segment_build(self.loops)

    def build_perimeter(self):
        (width, height) = self.data.shape
        left, bottom, right, top = 0, 0, width, height
        left, bottom = xy(self.transform, bottom, left)
        right, top = xy(self.transform, top, right)

        perimeter = Polygon([
            (left, bottom),
            (right, bottom),
            (right, top),
            (left, top),
            (left, bottom),
        ]).exterior
        return perimeter

    def run_per_segment(self, per_segment_function):
        segment_update(self.segments, per_segment_function)

    def rebuild(self):
        loop_rebuild(self.loops)
        area_rebuild(self.areas)

    def get_result(self):
        modified_polygons = [c.modified_polygon for c in self.areas]
        labels = [c.label for c in self.areas]
        return modified_polygons, labels
