from typing import List

from shapely.geometry import LineString, Point


"""
Computes cutpoints of boundaries by which to then split them into segments.
"""
class CutpointsComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ):
        self.boundaries = boundaries

    def _use_cutpoints_from_neighbor_start_points(self):
        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            for n in curr_boundary.intersections:
                other_boundary = self.boundaries[n]

                other_start = Point(other_boundary.line.coords[0])
                on_curr_boundary = curr_boundary.on_boundary(other_start)
                if on_curr_boundary:
                    curr_boundary.cutpoints.append(other_start)

                curr_start = Point(curr_boundary.line.coords[0])
                on_other_boundary = other_boundary.on_boundary(curr_start)
                if on_other_boundary:
                    other_boundary.cutpoints.append(curr_start)

    def _use_cutpoints_from_intersection_endpoints(self):
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]
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

    def _set_sorted_unique_cutpoints(self):
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]
            boundary.cutpoints = list(set(boundary.cutpoints))
            boundary.cutpoints.sort(key=boundary.get_point_sort_key)

    def compute_cutpoints(self):
        self._use_cutpoints_from_neighbor_start_points()
        self._use_cutpoints_from_intersection_endpoints()
        self._set_sorted_unique_cutpoints()
