from shapely.geometry import Point
from shapely.geometry import LineString

from .orientation import Orientation


class Segment(object):
    def __enter__(self) -> 'Segment':
        return self

    def __init__(
        self,
        boundary, #: Boundary,
        line: LineString,
    ) -> None:
        self.boundary = boundary
        self.line = line

        self.start = Point(line.coords[0])
        self.end = Point(line.coords[-1])

        # Can iteratively apply as many operations,
        # which will update this value based on its previous value.
        self.modified_line = self.line

    def set_reference(
        self,
        segment #: Segment,
    ) -> None:
        self.reference = segment
        self.orientation = \
            self.boundary.get_orientation(self.reference)

    def rebuild(self) -> None:
        if self.orientation == Orientation.BACKWARD:
            self.modified_line = LineString(
                self.reference.modified_line.coords[::-1]
            )
        else:
            self.modified_line = self.reference.modified_line
