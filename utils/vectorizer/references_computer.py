from shapely.geometry import LineString, Point

from segment import Segment


def get_positions(sort_key, length, points):
    positions = []
    for i, p in enumerate(points):
        position = sort_key(p)
        if i > 0 and position <= positions[i-1]:
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
                    if pos > positions[cutpoint_idx] and pos < positions[cutpoint_idx+1]:
                        segment_coords.append(p)
                cutpoint_idx += 1

    return segments

def get_segments(loop, cutpoints):
    segments = get_segments_helper(loop.line, loop.point_sort_key, loop.line.length, cutpoints)
    assert len(segments) == len(cutpoints) - 1, f"Expect number of segments to be one less than number of inputted cutpoints."
    return segments

def compute_segments_per_loop(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]

        cutpoints_with_end = loop.cutpoints + [loop.cutpoints[0]]
        segment_lines = get_segments(loop, cutpoints_with_end)
        loop.segments = [Segment(loop, sl) for sl in segment_lines]
        assert len(loop.cutpoints) == len(loop.segments), f"Expect number of segments to equal number of cutpoints."
        loop.segment_map = {(s.start, s.end): i for i, s in enumerate(loop.segments)}

# Get cutpoints to split intersection by.
def get_relevant_cutpoints(loop, intersection):
    start = Point(intersection.coords[0])
    end = Point(intersection.coords[-1])

    super_line = LineString(loop.cutpoints)
    super_segments = get_segments_helper(super_line, loop.point_sort_key, loop.line.length, [start, end])
    super_segment = super_segments[0]
    
    relevant_cutpoints = [Point(c) for c in super_segment.coords]
    return relevant_cutpoints

def compute_loops_per_segment(all_loops):
    for l in range(len(all_loops)):
        curr_loop = all_loops[l]
        curr_loop.segment_idx_to_neighbors = [[(l, curr_loop.segments[i], False)] for i in range(len(curr_loop.segments))]

    for l in range(len(all_loops)):
        curr_loop = all_loops[l]

        for n in curr_loop.ring_intersections:
            if n <= l: continue
            other_loop = all_loops[n]
            cutpoints_with_end = curr_loop.cutpoints + [curr_loop.cutpoints[0]]
            for i in range(len(cutpoints_with_end)-1):
                start = cutpoints_with_end[i]
                end = cutpoints_with_end[i+1]
                segment = curr_loop.get_segment(start, end)

                other_seg_idx, reverse = other_loop.get_segment_idx_and_reverse(start, end, segment.line)
                other_loop.segment_idx_to_neighbors[other_seg_idx].append((l, segment, reverse))

        for n, intersection_segments in curr_loop.intersections.items():
            if n <= l: continue # handled already
            other_loop = all_loops[n]

            for intersection_segment in intersection_segments:
                rel_cutpoints = get_relevant_cutpoints(curr_loop, intersection_segment)
                
                for i in range(len(rel_cutpoints)-1):
                    start = rel_cutpoints[i]
                    end = rel_cutpoints[i+1]
                    segment = curr_loop.get_segment(start, end)

                    other_seg_idx, reverse = other_loop.get_segment_idx_and_reverse(start, end, segment.line)
                    other_loop.segment_idx_to_neighbors[other_seg_idx].append((l, segment, reverse))

def compute_reference_per_segment(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]
        
        for i, nps in enumerate(loop.segment_idx_to_neighbors):
            _reference_idx, reference_segment, reverse = min(nps, key=lambda x: x[0])
            loop.segments[i].set_reference(reference_segment, reverse)

def compute_references(all_loops):
    compute_segments_per_loop(all_loops)
    compute_loops_per_segment(all_loops)
    compute_reference_per_segment(all_loops)