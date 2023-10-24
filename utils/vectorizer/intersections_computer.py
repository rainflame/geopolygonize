from shapely.geometry import LineString, Point
from rtree import index

from oriented_potential import OrientedPotential


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
        assert len(ls.coords) == 2
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

def get_sorted_oriented_potentials(loop, pieces):
    oriented_potentials = []
    for p in pieces:
        oriented_potential = OrientedPotential(p, loop, loop)
        oriented_potentials.append(oriented_potential)
    oriented_potentials.sort(key=loop.potential_sort_key)
    return oriented_potentials

def get_sections(oriented_potentials):
    sections = []
    section = None
    for i in range(len(oriented_potentials)):
        op = oriented_potentials[i]
        oriented_piece = op.get_oriented_segment()
        
        if i == 0:
            section = [oriented_piece]
        else:
            prev_op = oriented_potentials[i-1]

            if prev_op.is_prev(op):
                section.append(oriented_piece)
            else:
                sections.append(section)
                section = [oriented_piece]

        if i == len(oriented_potentials) - 1:
            first_op = oriented_potentials[0]
            if op.is_prev(first_op) and len(sections) > 0:
                first_section = sections[0]
                sections[0] = section + first_section
            else:
                sections.append(section)

    assert len(sections) > 0
    return sections

def get_segments(sections):
    segments = []
    for s in sections:
        line_coords = []
        for l in s:
            assert len(l.coords) == 2
            line_coords.append(l.coords[0])
        l = s[-1]
        line_coords.append(l.coords[-1])

        segment = LineString(line_coords)
        segments.append(segment)
    return segments

def get_connected_segments(loop, pieces):
    if len(pieces) == 0: return []
    for p in pieces:
        assert len(p.coords) == 2

    oriented_potentials = get_sorted_oriented_potentials(loop, pieces)
    sections = get_sections(oriented_potentials)
    segments = get_segments(sections)
    return segments

def compute_intersections(all_loops):
    loop_idx = make_index(all_loops)

    for l in range(len(all_loops)):
        curr_loop = all_loops[l]
        
        for n in loop_idx.intersection(curr_loop.line.bounds):
            if n == l: continue
            if n < l: continue # handled already
            other_loop = all_loops[n]

            intersection = curr_loop.line.intersection(other_loop.line)
            intersection_pieces = handle(intersection)
            intersection_segments = get_connected_segments(curr_loop, intersection_pieces)
            if len(intersection_segments) == 0: continue
            if len(intersection_segments) == 1 and intersection_segments[0].is_ring: continue

            curr_loop.intersections[n] = intersection_segments
            other_loop.intersections[l] = intersection_segments