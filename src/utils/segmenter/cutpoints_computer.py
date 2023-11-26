from typing import List

from shapely.geometry import LineString, Point


"""
Computes cutpoints of boundaries by which to then split them into segments.
"""


class CutpointsComputer:
    def __init__(
        self,
        boundaries: List[LineString],
    ) -> None:
        self.boundaries = boundaries

    def _use_cutpoints_from_neighbor_start_points(self) -> None:
        for b in range(len(self.boundaries)):
            curr_boundary = self.boundaries[b]
            for n, _segments in curr_boundary.get_intersections():
                other_boundary = self.boundaries[n]

                other_start = Point(other_boundary.line.coords[0])
                on_curr_boundary = curr_boundary.on_boundary(other_start)
                if on_curr_boundary:
                    curr_boundary.add_cutpoint(other_start)

                curr_start = Point(curr_boundary.line.coords[0])
                on_other_boundary = other_boundary.on_boundary(curr_start)
                if on_other_boundary:
                    other_boundary.add_cutpoint(curr_start)

    def _use_cutpoints_from_intersection_endpoints(self) -> None:
        for b in range(len(self.boundaries)):
            boundary = self.boundaries[b]
            boundary_start_end = Point(boundary.line.coords[0])

            cutpoints = [boundary_start_end]
            for _n, intersection_segments in boundary.get_intersections():
                for intersection_segment in intersection_segments:
                    if intersection_segment.is_ring:
                        continue
                    start = Point(intersection_segment.coords[0])
                    end = Point(intersection_segment.coords[-1])
                    cutpoints.extend([start, end])

            for cutpoint in cutpoints:
                boundary.add_cutpoint(cutpoint)

    def compute_cutpoints(self) -> None:
        self._use_cutpoints_from_neighbor_start_points()
        self._use_cutpoints_from_intersection_endpoints()
