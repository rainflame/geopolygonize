from shapely.geometry import LineString

import line_utils


class Loop:
    def __init__(self, idx, loop):
        self.idx = idx
        self.line = LineString(loop.coords)
        self.intersections = {} # neighbor idx -> intersection segments
        self.cutpoints = []
        self.sort_cache = {}
        # If N loops share an oriented potential,
        # the reference associated with the oriented potential
        # will be the one with the lowest idx.
        # This allows us to perform processing on its associated segment 
        # once and only once and share the result of that processing 
        # with all N loops.
        self.oriented_potentials = []

        self.modified_line = None
    
    def on_loop(self, point):
        return line_utils.is_along_line(self.line, point)
    
    def point_sort_key(self, point):
        if point in self.sort_cache:
            return self.sort_cache[point]
        distance = line_utils.get_distance(self.line, point)
        self.sort_cache[point] = distance
        return distance
    
    def potential_sort_key(self, op):
        (start_pos, _end_pos) = op.get_positions()
        reference = op.reference
        return (start_pos, reference)