from shapely.geometry import LineString, Point
from rtree import index


class Loop:
    def __init__(self, idx, loop):
        self.idx = idx
        self.line = LineString(loop.coords)
        self.ring_intersections = {} # neighbor idx -> ring
        self.intersections = {} # neighbor idx -> intersection segments
        self.cutpoints = []
        # If N loops share an oriented potential,
        # the reference associated with the oriented potential
        # will be the one with the lowest idx.
        # This allows us to perform processing on its associated segment 
        # once and only once and share the result of that processing 
        # with all N loops.
        self.oriented_potentials = []

        self.setup_sort_cache()

        self.modified_line = None

    def setup_sort_cache(self):
        self.sort_cache = {}

        start = Point(self.line.coords[0])
        self.cumulative_distances = {start: 0}
        for i in range(1, len(self.line.coords) - 1):
            seg_start = Point(self.line.coords[i-1])
            seg_end = Point(self.line.coords[i])
            segment = LineString([seg_start, seg_end])
            self.cumulative_distances[seg_end] = self.cumulative_distances[seg_start] + segment.length
        # end is same as beginning
        
        self.seg_idx = index.Index()
        for i in range(len(self.line.coords) - 1):
            segment = LineString([self.line.coords[i], self.line.coords[i + 1]])
            bbox = segment.bounds
            self.seg_idx.insert(i, bbox)
    
    def on_loop(self, point):
        start = Point(self.line.coords[0])
        end = Point(self.line.coords[-1])
        return point.intersects(self.line) or point.equals(start) or point.equals(end)
    
    def point_sort_key(self, point):
        if point in self.sort_cache:
            return self.sort_cache[point]
        
        if point in self.cumulative_distances:
            distance = self.cumulative_distances[point]
        else:
            s_idxes = list(self.seg_idx.intersection(point.bounds))
            if len(s_idxes) == 0: raise Exception('Point is not in line as expected.')
            if len(s_idxes) > 1: raise Exception('Point is not between just two line coordinates as expected.')
            s_idx = s_idxes[0]
            seg_start = Point(self.line.coords[s_idx])
            seg_end = Point(self.line.coords[s_idx + 1])
            segment = LineString([seg_start, seg_end])
            distance = self.cumulative_distances[seg_start] + segment.project(point)

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