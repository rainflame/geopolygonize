from shapely.geometry import Point
from shapely.geometry import LineString


class Segment:
    def __init__(self, loop, line):
        self.loop = loop
        self.line = line

        self.start = Point(line.coords[0])
        self.end = Point(line.coords[-1])

        # Can iteratively apply as many operations,
        # which will update this value based on its previous value.
        self.modified_line = self.line
    
    def set_reference(self, reference, reverse):
        self.reference = reference
        self.reverse = reverse

    def rebuild(self):
        if self.reverse:
            self.modified_line = LineString(self.reference.modified_line.coords[::-1])
        else:
            self.modified_line = self.reference.modified_line