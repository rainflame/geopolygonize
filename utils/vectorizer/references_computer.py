from shapely.geometry import LineString, Point

from oriented_potential import OrientedPotential


def get_positions(sort_key, length, points):
    positions = []
    for i, p in enumerate(points):
        position = sort_key(p)
        if i > 0 and position < positions[i-1]:
            position += length
            assert position > positions[i-1], f"Expect current position to be greater than previous position."
        positions.append(position)
    return positions

def get_iterations(line, sort_key, length):
    line_points = [Point(c) for c in line.coords]
    if line.is_ring:
        line_points = line_points[:-1]
    first_loop = [(p, sort_key(p)) for p in line_points]
    second_loop = [(p, pos + length) for (p, pos) in first_loop]
    if line.is_ring:
        second_loop.append((line_points[0], 2*length))
    return first_loop + second_loop

def get_segments_helper(line, sort_key, length, cutpoints):
    positions = get_positions(sort_key, length, cutpoints)
    assert len(positions) == len(cutpoints), f"Expect the number of positions to be the same as the number of cutpoints."
    iterations = get_iterations(line, sort_key, length)

    segments = []
    segment_coords = None
    cutpoint_idx = 0
    for (p, pos) in iterations:
        if cutpoint_idx == len(cutpoints): break

        if pos < positions[cutpoint_idx]:
            if segment_coords == None: continue
            else: segment_coords.append(p)
        else:
            if segment_coords == None: segment_coords = []
            while cutpoint_idx < len(cutpoints) and pos >= positions[cutpoint_idx]:
                segment_coords.append(cutpoints[cutpoint_idx])
                if cutpoint_idx > 0:
                    segments.append(LineString(segment_coords))
                    segment_coords = [cutpoints[cutpoint_idx]]
                cutpoint_idx += 1

    return segments

# Get cutpoints to split intersection by.
def get_relevant_cutpoints(loop, intersection):
    oriented_intersection = OrientedPotential(intersection, loop, loop)
    start, end = oriented_intersection.get_oriented_potential()

    super_line = LineString(loop.cutpoints)
    super_segments = get_segments_helper(super_line, loop.point_sort_key, loop.line.length, [start, end])
    super_segment = super_segments[0]
    
    relevant_cutpoints = [Point(c) for c in super_segment.coords]
    return relevant_cutpoints

def get_segments(loop, cutpoints):
    segments = get_segments_helper(loop.line, loop.point_sort_key, loop.line.length, cutpoints)
    assert len(segments) == len(cutpoints) - 1, f"Expect number of segments to be one less than number of inputted cutpoints."
    return segments

def get_oriented_potentials(segments, first_loop, second_loop, ref_loop):
    pairs = []
    for segment in segments:
        op_curr = OrientedPotential(segment, first_loop, ref_loop)
        op_other = OrientedPotential(segment, second_loop, ref_loop)
        pairs.append((op_curr, op_other))
    return pairs

def compute_oriented_potentials_from_intersections(all_loops):
    for l in range(len(all_loops)):
        curr_loop = all_loops[l] # acts as reference loop for oriented potentials

        for n, intersection_segments in curr_loop.intersections.items():
            if n <= l: continue # handled already
            other_loop = all_loops[n]

            for intersection_segment in intersection_segments:
                if intersection_segment.is_ring: continue
                rel_cutpoints = get_relevant_cutpoints(curr_loop, intersection_segment)
                segments = get_segments(curr_loop, rel_cutpoints)
                pairs = get_oriented_potentials(segments, curr_loop, other_loop, curr_loop)

                for (curr_op, other_op) in pairs:
                    curr_loop.oriented_potentials.append(curr_op)
                    other_loop.oriented_potentials.append(other_op)

def compute_remnant_oriented_potentials(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]
        
        sections = [op.get_oriented_potential() for op in loop.oriented_potentials]
        assert len(loop.cutpoints) > 0, f"Loop {l} should at least have its own start/end as a cutpoint."
        looping_cutpoints = loop.cutpoints + [loop.cutpoints[0]]
        if len(looping_cutpoints) == 2 and looping_cutpoints[0] == looping_cutpoints[1]:
            continue

        remnants = []
        for j in range(len(looping_cutpoints)):
            if j == 0: continue
            start = looping_cutpoints[j-1]
            end = looping_cutpoints[j]
            if (start, end) in sections: continue

            segments = get_segments(loop, [start, end])
            segment = segments[0]
            op = OrientedPotential(segment, loop, loop)
            remnants.append(op)

        loop.oriented_potentials.extend(remnants)

def compute_split_oriented_potentials_for_whole_loops(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]

        if len(loop.oriented_potentials) == 0:

            midpoint_idx = len(loop.line.coords) // 2

            start = Point(loop.line.coords[0])
            midpoint = Point(loop.line.coords[midpoint_idx])
            end = Point(loop.line.coords[-1])

            segments = get_segments(loop, [start, midpoint, end])

            first_op = OrientedPotential(segments[0], loop, loop)
            second_op = OrientedPotential(segments[1], loop, loop)
            halves = [first_op, second_op]

            for n, intersection_segments in loop.intersections.items():
                for intersection_segment in intersection_segments:
                    if intersection_segment.is_ring:
                        if n < l:
                            continue # already handled
                        else:
                            other_loop = all_loops[n]
                            loop.oriented_potentials = halves
                            other_loop.oriented_potentials = halves

def set_sorted_unique_oriented_potentials(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]
        loop.oriented_potentials.sort(key=loop.potential_sort_key)

        reference_oriented_potentials = []
        for j, op in enumerate(loop.oriented_potentials):
            if j == 0:
                reference_oriented_potentials.append(op)
            else:
                (curr_start, curr_end) = op.get_oriented_potential()

                prev_op = loop.oriented_potentials[j-1]
                (prev_start, prev_end) = prev_op.get_oriented_potential()

                if (curr_start, curr_end) == (prev_start, prev_end):
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