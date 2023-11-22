from shapely.geometry import Point


def use_cutpoints_from_neighbor_start_points(all_boundaries):
    for b in range(len(all_boundaries)):
        curr_boundary = all_boundaries[b]
        for n in curr_boundary.intersections:
            other_boundary = all_boundaries[n]

            other_start = Point(other_boundary.line.coords[0])
            on_curr_boundary = curr_boundary.on_boundary(other_start)
            if on_curr_boundary:
                curr_boundary.cutpoints.append(other_start)

            curr_start = Point(curr_boundary.line.coords[0])
            on_other_boundary = other_boundary.on_boundary(curr_start)
            if on_other_boundary:
                other_boundary.cutpoints.append(curr_start)


def use_cutpoints_from_intersection_endpoints(all_boundaries):
    for b in range(len(all_boundaries)):
        boundary = all_boundaries[b]
        boundary_start_end = Point(boundary.line.coords[0])

        cutpoints = [boundary_start_end]
        for _n, intersection_segments in boundary.intersections.items():
            for intersection_segment in intersection_segments:
                if intersection_segment.is_ring:
                    continue
                start = Point(intersection_segment.coords[0])
                end = Point(intersection_segment.coords[-1])
                cutpoints.extend([start, end])

        boundary.cutpoints.extend(cutpoints)


def set_sorted_unique_cutpoints(all_boundaries):
    for b in range(len(all_boundaries)):
        boundary = all_boundaries[b]
        boundary.cutpoints = list(set(boundary.cutpoints))
        boundary.cutpoints.sort(key=boundary.point_sort_key)


def compute_cutpoints(all_boundaries):
    use_cutpoints_from_neighbor_start_points(all_boundaries)
    use_cutpoints_from_intersection_endpoints(all_boundaries)
    set_sorted_unique_cutpoints(all_boundaries)
