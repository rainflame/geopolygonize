from shapely.geometry import Polygon


class Cover:
    def __init__(self, polygon, label):
        self.polygon = polygon
        self.label = label
        
        self.exterior_idx = None
        self.interior_idxes = []

        self.modified_polygon = None

    def rebuild(self, exterior, interiors):
        modified_polygon = Polygon(exterior, interiors)
        self.modified_polygon = modified_polygon