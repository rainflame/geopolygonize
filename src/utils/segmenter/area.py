from shapely.geometry import Polygon


class Area:
    def __init__(self, polygon):
        self.polygon = polygon

        self.exterior = None
        self.interiors = []

        self.modified_polygon = None

    def rebuild(self):
        modified_polygon = Polygon(
            self.exterior.modified_line,
            [interior.modified_line for interior in self.interiors]
        )
        self.modified_polygon = modified_polygon
