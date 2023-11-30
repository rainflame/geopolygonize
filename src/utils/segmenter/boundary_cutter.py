from typing import Callable, List

from shapely.geometry import LineString, Point

from .boundary import Boundary
from .positioned_point import PositionedPoint


class BoundaryCutter:
    def __init__(
        self,
        boundary: Boundary,
        cutpoints: List[Point],
    ) -> None:
        self.boundary = boundary
        self.cutpoints = cutpoints

        self._preprocess()

    def _preprocess(self) -> None:
        self._positioned_coords = self._get_positioned_coords()
        self._positioned_cutpoints = self._get_positioned_cutpoints()

    def _get_positioned_cutpoints(self) -> List[PositionedPoint]:
        positioned_cutpoints: List[PositionedPoint] = []
        for i, cutpoint in enumerate(self.cutpoints):
            position = self.boundary.get_point_sort_key(cutpoint)
            if i > 0 and position <= positioned_cutpoints[i-1].position:
                position += self.boundary.line.length
                assert position > positioned_cutpoints[i-1].position, \
                    "Expect current position to be " \
                    "greater than previous position."
            positioned_cutpoint = PositionedPoint(cutpoint, position)
            positioned_cutpoints.append(positioned_cutpoint)
        return positioned_cutpoints

    def _get_positioned_coords(self) -> List[Point]:
        coords = [Point(c) for c in self.boundary.line.coords]
        if self.boundary.line.is_closed:
            coords = coords[:-1]

        first_boundary = [
            PositionedPoint(coord, self.boundary.get_point_sort_key(coord))
            for coord in coords
        ]
        second_boundary = [
            PositionedPoint(
                positioned_point.point,
                positioned_point.position + self.boundary.line.length
            ) for positioned_point in first_boundary
        ]

        if self.boundary.line.is_closed:
            positioned_point = \
                PositionedPoint(coords[0], 2*self.boundary.line.length)
            second_boundary.append(positioned_point)
        return first_boundary + second_boundary

    def _get_segments_between_cutpoints(self) -> List[LineString]:
        segments: List[LineString] = []
        segment_coords: None | List[Point] = None
        cutpoint_idx: int = 0

        for positioned_coord in self._positioned_coords:
            if cutpoint_idx == len(self._positioned_cutpoints):
                break

            if positioned_coord.position \
                    < self._positioned_cutpoints[cutpoint_idx].position:
                if segment_coords is None:
                    continue
                else:
                    segment_coords.append(positioned_coord.point)
            else:
                if segment_coords is None:
                    segment_coords = []
                while cutpoint_idx < len(self._positioned_cutpoints) \
                        and positioned_coord.position \
                        >= self._positioned_cutpoints[cutpoint_idx].position:
                    segment_coords.append(
                        self._positioned_cutpoints[cutpoint_idx].point
                    )
                    if cutpoint_idx > 0:
                        segments.append(LineString(segment_coords))
                        segment_coords = [
                            self._positioned_cutpoints[cutpoint_idx].point
                        ]
                        if positioned_coord.position \
                                > self._positioned_cutpoints[
                                    cutpoint_idx
                                ].position \
                                and positioned_coord.position \
                                < self._positioned_cutpoints[
                                    cutpoint_idx+1
                                ].position:
                            segment_coords.append(positioned_coord.point)
                    cutpoint_idx += 1

        return segments

    def cut_boundary(self) -> List[LineString]:
        segments = self._get_segments_between_cutpoints()
        assert len(segments) == len(self.cutpoints) - 1, \
            "Expect number of segments to be one " \
            "less than number of inputted cutpoints."
        return segments
