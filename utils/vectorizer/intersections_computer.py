from tqdm import tqdm

from shapely.geometry import LineString, Point
from rtree import index


def make_index(all_loops):
    loop_idx = index.Index()
    for i, loop in enumerate(all_loops):
        bbox = loop.line.bounds
        loop_idx.insert(i, bbox)
    return loop_idx

def line_string(ls):
    if len(ls.coords) < 2:
        return [] # invalid segment, effectively skip
    else:
        assert len(ls.coords) == 2, f"Expect LineString from intersection to have only two points."
        return [ls]

def multi_line_string(mls):
    pieces = []
    for l in mls.geoms:
        pieces.extend(line_string(l))
    return pieces

def geometry_collection(gc):
    pieces = []
    for g in gc.geoms:
        pieces.extend(handle(g))
    return pieces

def handle(g):
    pieces = []
    if g.geom_type == "LineString":
        pieces = line_string(g)
    elif g.geom_type == "MultiLineString":
        pieces = multi_line_string(g)
    elif g.geom_type == "GeometryCollection":
        pieces = geometry_collection(g)
    else:
        # skip Point, MultiPoint or non-existent intersection
        pass
    return pieces

def get_connected_segments(pieces):
    if len(pieces) == 0: return []

    start_map = {}
    end_map = {}
    for p in pieces:
        assert len(p.coords) == 2, f"Expect each piece to have only two points."
        start_map[Point(p.coords[0])] = p
        end_map[Point(p.coords[-1])] = p

    segments = []
    unvisited = set(pieces)
    while len(unvisited) > 0:
        piece = unvisited.pop()
        start = Point(piece.coords[0])
        end = Point(piece.coords[-1])
        
        curr = start
        former_section = [start]
        while curr in end_map:
            prev_piece = end_map[curr]
            curr = Point(prev_piece.coords[0])
            former_section.append(curr)
            if not prev_piece in unvisited: break # reached termination in former half of segment
            unvisited.remove(prev_piece)

        is_ring = len(former_section) > 2 and Point(former_section[-1]) == start
        if is_ring:
            latter_section = []
        else:
            curr = end
            latter_section = [end]
            while curr in start_map:
                next_piece = start_map[curr]
                curr = Point(next_piece.coords[-1])
                latter_section.append(curr)
                if not next_piece in unvisited: break # reached termination in latter half of segment
                unvisited.remove(next_piece)
        
        segment = LineString(former_section[::-1] + latter_section)
        segments.append(segment)
    
    return segments

def compute_intersections(all_loops):
    loop_idx = make_index(all_loops)

    for l in tqdm(range(len(all_loops)), desc="Computing loop intersections"):
        curr_loop = all_loops[l]
        
        for n in loop_idx.intersection(curr_loop.line.bounds):
            if n == l: continue
            if n < l: continue # handled already
            other_loop = all_loops[n]

            intersection = curr_loop.line.intersection(other_loop.line)
            intersection_pieces = handle(intersection)
            
            intersection_segments = get_connected_segments(intersection_pieces)
            if len(intersection_segments) == 0: continue
            
            is_ring = False
            for intersection_segment in intersection_segments:
                if intersection_segment.is_ring: is_ring = True

            if is_ring:
                assert len(intersection_segments) == 1, f"If the intersection with another loop is a ring, expect the ring to be the only intersection."
                ring = intersection_segments[0]
                curr_loop.ring_intersections[n] = ring
                other_loop.ring_intersections[l] = ring
            else:
                curr_loop.intersections[n] = intersection_segments
                other_loop.intersections[l] = intersection_segments