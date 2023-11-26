from shapely.geometry import LineString, Point


class Piece:
    def __init__(self, ls: LineString) -> None:
        assert len(ls.coords) == 2, \
            "Expect LineString to make Piece from to have only two points."
        self.ls = ls
        self.start = Point(self.ls.coords[0])
        self.end = Point(self.ls.coords[-1])
