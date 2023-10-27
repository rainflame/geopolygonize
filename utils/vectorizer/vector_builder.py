import os
import sys

vectorizer_dir = os.path.dirname(__file__)
sys.path.append(vectorizer_dir)
import area_computer as ac
import loop_computer as lc
import segments_computer as sc


class VectorBuilder:
    def __init__(self, data, transform):
        self.data = data
        self.transform = transform
        self.build()

    def build(self):
        self.areas = ac.build(self.data, self.transform)
        self.loops = lc.build(self.areas)
        self.segments = sc.build(self.loops)

    def run_per_segment(self, per_segment_function):
        sc.update(self.segments, per_segment_function)
    
    def rebuild(self):
        lc.rebuild(self.loops)
        ac.rebuild(self.areas)

    def get_result(self):
        modified_polygons = [c.modified_polygon for c in self.areas]
        labels = [c.label for c in self.areas]
        return modified_polygons, labels