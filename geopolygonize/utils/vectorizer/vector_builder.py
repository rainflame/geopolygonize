import os
import sys

from rasterio.transform import xy
from shapely.geometry import Polygon

vectorizer_dir = os.path.dirname(__file__)
sys.path.append(vectorizer_dir)
import area_computer as ac
import loop_computer as lc
import segment_computer as sc


class VectorBuilder:
    def __init__(self, data, transform, debug):
        self.data = data
        self.transform = transform
        self.debug = debug
        self.build()

    def build(self):
        if self.debug:
            print("Computing areas...")
        self.areas = ac.build(self.data, self.transform)

        # Add a polygon that is the perimeter of data.
        # This ensures that we fix the boundary of the data in place.
        self.perimeter = self.build_perimeter()
        if self.debug:
            print("Computing loops...")
        self.loops = lc.build(self.perimeter, self.areas)

        if self.debug:
            print("Computing segments...")
        self.segments = sc.build(self.loops)

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
        if self.debug:
            print("Running per-segment function...")
        sc.update(self.segments, per_segment_function)

    def rebuild(self):
        if self.debug:
            print("Rebuilding loops...")
        lc.rebuild(self.loops)
        if self.debug:
            print("Rebuilding areas...")
        ac.rebuild(self.areas)

    def get_result(self):
        modified_polygons = [c.modified_polygon for c in self.areas]
        labels = [c.label for c in self.areas]
        return modified_polygons, labels
