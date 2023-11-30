from typing import List

from shapely.geometry import LineString, Polygon


class Area:
    def __init__(self, polygon: Polygon) -> None:
        self.polygon = polygon

        self.exterior: LineString | None = None
        self.interiors: List[LineString] = []

        self.modified_polygon: Polygon = None

    def rebuild(self) -> None:
        assert self.exterior is not None

        modified_polygon = Polygon(
            self.exterior.modified_line,
            [interior.modified_line for interior in self.interiors]
        )
        self.modified_polygon = modified_polygon
