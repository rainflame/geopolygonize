class Cover:
    def __init__(self, polygon, label):
        self.polygon = polygon
        self.label = label
        
        self.exterior_idx = None
        self.interior_idxes = []

        self.modified_polygon = None