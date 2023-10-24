from shapely.geometry import LineString, Point


def is_along_line(line, point):
    start = Point(line.coords[0])
    end = Point(line.coords[-1])
    return point.intersects(line) or point.equals(start) or point.equals(end)

def get_distance(line, point):
    key = (line, point)

    distance = 0
    for i in range(len(line.coords) - 1):
        segment = LineString([line.coords[i], line.coords[i + 1]])
        if is_along_line(segment, point):
            distance += segment.project(point)
            break
        else:
            distance += segment.length
    return distance

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
        return is_along_line(self.line, point)
    
    def point_sort_key(self, point):
        if point in self.sort_cache:
            return self.sort_cache[point]
        distance = get_distance(self.line, point)
        self.sort_cache[point] = distance
        return distance
    
    def potential_sort_key(self, op):
        (start_pos, _end_pos) = op.get_positions()
        reference = op.reference
        return (start_pos, reference)
    
    def rebuild(self, oriented_potentials):
        for op in self.oriented_potentials:
            ref_op = oriented_potentials[op.get_key()]
            op.rebuild(ref_op)

        segments = []
        for op in self.oriented_potentials:
            segment = op.get_oriented_modified_segment()
            segments.append(segment)
        
        modified_line = LineString([c for s in segments for c in s.coords[:-1]] + [segments[-1].coords[-1]])
        self.modified_line = modified_line