from shapely.geometry import Point


def compute_cutpoints(all_loops):
    for l in range(len(all_loops)):
        loop = all_loops[l]
        loop_start_end = Point(loop.line.coords[0])

        cutpoints = [loop_start_end]
        for n, intersection_segments in loop.intersections.items():
            for intersection_segment in intersection_segments:
                start = Point(intersection_segment.coords[0])
                end = Point(intersection_segment.coords[-1])
                cutpoints.extend([start, end])
        
        loop.cutpoints.extend(cutpoints)

    for l in range(len(all_loops)):
        loop = all_loops[l]
        loop.cutpoints = list(set(loop.cutpoints))
        loop.cutpoints.sort(key=loop.point_sort_key)

    return all_loops