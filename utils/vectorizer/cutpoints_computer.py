from tqdm import tqdm

from shapely.geometry import Point


def use_cutpoints_from_neighbor_start_points(all_loops):
    for l in tqdm(range(len(all_loops)), desc="Computing neighbor cutpoints along loop"):
        curr_loop = all_loops[l]
        for n in curr_loop.intersections:
            other_loop = all_loops[n]

            other_start = Point(other_loop.line.coords[0])
            on_curr_loop = curr_loop.on_loop(other_start)
            if on_curr_loop: curr_loop.cutpoints.append(other_start)
            
            curr_start = Point(curr_loop.line.coords[0])
            on_other_loop = other_loop.on_loop(curr_start)
            if on_other_loop: other_loop.cutpoints.append(curr_start)

def use_cutpoints_from_intersection_endpoints(all_loops):
    for l in tqdm(range(len(all_loops)), desc="Computing intersection cutpoints along loop"):
        loop = all_loops[l]
        loop_start_end = Point(loop.line.coords[0])

        cutpoints = [loop_start_end]
        for _n, intersection_segments in loop.intersections.items():
            for intersection_segment in intersection_segments:
                if intersection_segment.is_ring: continue
                start = Point(intersection_segment.coords[0])
                end = Point(intersection_segment.coords[-1])
                cutpoints.extend([start, end])
        
        loop.cutpoints.extend(cutpoints)

def set_sorted_unique_cutpoints(all_loops):
    for l in tqdm(range(len(all_loops)), desc="Sorting cutpoints along loop"):
        loop = all_loops[l]
        loop.cutpoints = list(set(loop.cutpoints))
        loop.cutpoints.sort(key=loop.point_sort_key)

def compute_cutpoints(all_loops):
    use_cutpoints_from_neighbor_start_points(all_loops)
    use_cutpoints_from_intersection_endpoints(all_loops)
    set_sorted_unique_cutpoints(all_loops)