from shapely.geometry import LineString, Point

from oriented_potential import OrientedPotential


def get_pos(start, end, sort_key, length):
    start_pos = sort_key(start)
    end_pos = sort_key(end)
    assert start_pos != end_pos
    if start_pos > end_pos:
        end_pos += length
    return start_pos, end_pos

def get_iterations(line, sort_key):
    line_points = [Point(c) for c in line.coords]
    if line.is_ring:
        line_points = line_points[:-1]
    first_loop = [(p, sort_key(p)) for p in line_points]
    second_loop = [(p, pos + line.length) for (p, pos) in first_loop]
    if line.is_ring:
        second_loop.append((line_points[0], 2*line.length))
    return first_loop + second_loop

def get_points(iterations, start, end, start_pos, end_pos):
    hit_start = False
    points = []
    for (p, pos) in iterations:
        if hit_start == False:
            if pos == start_pos:
                hit_start = True
                points.append(p)
            elif pos > start_pos:
                hit_start = True
                points.append(start)
                points.append(p)
            else: pass
        else:
            if pos == end_pos:
                points.append(p)
                break
            elif pos > end_pos:
                points.append(end)
                break
            else: points.append(p)
    return points

def get_segment(line, start, end, sort_key):
    start_pos, end_pos = get_pos(start, end, sort_key, line.length)
    iterations = get_iterations(line, sort_key)  
    points = get_points(iterations, start, end, start_pos, end_pos) 
    segment = LineString(points)
    return segment

# Get cutpoints to split intersection by.
def get_relevant_cutpoints(loop, intersection):
    oriented_intersection = OrientedPotential(intersection, loop, loop)
    start, end = oriented_intersection.get_oriented_potential()

    super_line = LineString(loop.cutpoints)
    super_segment = get_segment(super_line, start, end, loop.point_sort_key)
    
    relevant_cutpoints = [Point(c) for c in super_segment.coords]
    return relevant_cutpoints

def get_segments(loop, cutpoints):
    segments = []
    for j in range(len(cutpoints) - 1):
        start = cutpoints[j]
        end = cutpoints[j+1]
        
        segment = get_segment(loop.line, start, end, loop.point_sort_key)
        segments.append(segment)
    return segments

def set_oriented_potentials(segments, first_loop, second_loop, ref_loop):
    for segment in segments:
        op_curr = OrientedPotential(segment, first_loop, ref_loop)
        first_loop.oriented_potentials.append(op_curr)

        op_other = OrientedPotential(segment, second_loop, ref_loop)
        second_loop.oriented_potentials.append(op_other)

def compute_oriented_potentials_from_intersections(all_loops):
    for l in range(len(all_loops)):
        curr_loop = all_loops[l]

        for n, intersection_segments in curr_loop.intersections.items():
            if n <= l: continue # handled already
            other_loop = all_loops[n]

            for intersection_segment in intersection_segments:
                rel_cutpoints = get_relevant_cutpoints(curr_loop, intersection_segment)
                segments = get_segments(curr_loop, rel_cutpoints)
                set_oriented_potentials(segments, curr_loop, other_loop, curr_loop)

def compute_split_oriented_potentials_for_whole_loops(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]

        if len(loop.oriented_potentials) == 0:
            midpoint_idx = len(loop.line.coords) // 2

            start = Point(loop.line.coords[0])
            midpoint = Point(loop.line.coords[midpoint_idx])

            first_segment = get_segment(loop.line, start, midpoint, loop.point_sort_key)
            second_segment = get_segment(loop.line, midpoint, start, loop.point_sort_key)
            
            first_op = OrientedPotential(first_segment, loop, loop)
            second_op = OrientedPotential(second_segment, loop, loop)
            halves = [first_op, second_op]
            loop.oriented_potentials = halves

def compute_remnant_oriented_potentials(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]
        
        sections = [op.get_oriented_potential() for op in loop.oriented_potentials]
        looping_cutpoints = loop.cutpoints + [loop.cutpoints[0]]
        remnants = []
        for j in range(len(looping_cutpoints)):
            if j == 0: continue
            start = looping_cutpoints[j-1]
            end = looping_cutpoints[j]

            if (start, end) in sections: continue
            if start == end: continue

            segment = get_segment(loop.line, start, end, loop.point_sort_key)
            op = OrientedPotential(segment, loop, loop)
            remnants.append(op)

        loop.oriented_potentials.extend(remnants)

def set_sorted_unique_oriented_potentials(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]
        loop.oriented_potentials.sort(key=loop.potential_sort_key)

        reference_oriented_potentials = []
        for j, op in enumerate(loop.oriented_potentials):
            if j == 0:
                reference_oriented_potentials.append(op)
            else:
                (curr_start, _curr_end) = op.get_oriented_potential()

                prev_op = loop.oriented_potentials[j-1]
                (_prev_start, prev_end) = prev_op.get_oriented_potential()

                if op == prev_op:
                    continue
                elif curr_start == prev_end:
                    reference_oriented_potentials.append(op)
                else:
                    raise Exception("Potential is neither connected nor equal to former potential")
        
        loop.oriented_potentials = reference_oriented_potentials

def compute_references(all_loops):
    compute_oriented_potentials_from_intersections(all_loops)
    compute_remnant_oriented_potentials(all_loops)
    compute_split_oriented_potentials_for_whole_loops(all_loops)
    set_sorted_unique_oriented_potentials(all_loops)