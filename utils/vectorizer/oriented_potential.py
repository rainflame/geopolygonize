from enum import Enum

from shapely.geometry import LineString, Point


class Orientation(Enum):
    FORWARD = 1
    REVERSE = 2

class OrientedPotential:
    def __init__(self, segment, user_loop, reference_loop):
        self.segment = segment
        self.user = user_loop.idx
        self.reference = reference_loop.idx

        e1 = Point(segment.coords[0])
        e2 = Point(segment.coords[-1])
        self.potential = (e1, e2)

        oriented_potential, positions, orientation = self.compute_orientation(user_loop)
        self.oriented_potential = oriented_potential 
        self.positions = positions
        self.orientation = orientation

        self.modified_segment = None

    def compute_orientation(self, user_loop):
        (e1, e2) = self.potential
        e1_pos = user_loop.point_sort_key(e1)
        e2_pos = user_loop.point_sort_key(e2)

        start, end = e1, e2
        if e2_pos < e1_pos:
            start, end = e2, e1
        start_pos = user_loop.point_sort_key(start)
        end_pos = user_loop.point_sort_key(end)

        assert start_pos != end_pos
        assert start_pos < end_pos

        test_point = None
        for c in user_loop.line.coords:
            pc = Point(c)
            if not (pc == start or pc == end):
                test_point = pc
                break
        
        assert test_point != None, f"Loop {user_loop} must have a point that is not the endpoint of a non-loop segment."
        in_seg = (test_point.x, test_point.y) in self.segment.coords

        test_pos = user_loop.point_sort_key(test_point)
        inside = test_pos > start_pos and test_pos < end_pos
        
        is_forward = (inside and in_seg) or (not inside and not in_seg)
        if not is_forward:
            start, end = end, start
            start_pos, end_pos = end_pos, start_pos
            end_pos += user_loop.line.length
        assert start_pos < end_pos

        orientation = Orientation.FORWARD if e1 == start else Orientation.REVERSE

        return (start, end), (start_pos, end_pos), orientation

    def get_oriented_potential(self):
        return self.oriented_potential 
    
    def get_positions(self):
        return self.positions
        
    def get_oriented_segment(self):
        if self.orientation == Orientation.FORWARD:
            return self.segment
        else:
            reversed_segment = LineString(self.segment.coords[::-1])
            return reversed_segment
        
    def get_oriented_modified_segment(self):
        if self.orientation == Orientation.FORWARD:
            return self.modified_segment
        else:
            reversed_segment = LineString(self.modified_segment.coords[::-1])
            return reversed_segment
    
    def get_key(self):
        return (self.potential, self.reference)
    
    def is_prev(self, other):
        (_curr_start, curr_end) = self.get_oriented_potential()
        (other_start, _other_end) = other.get_oriented_potential()
        return curr_end == other_start