from shapely.geometry import LineString, Point


class Piece:
    def __init__(self, ls: LineString) -> None:
        assert len(ls.coords) == 2, \
            "Expect LineString to make Piece from to have only two points."
        self.ls = ls

    def get_start(self) -> Point:
        return Point(self.ls.coords[0])

    def get_end(self) -> Point:
        return Point(self.ls.coords[-1])
