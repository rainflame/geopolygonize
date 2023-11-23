from dataclasses import dataclass

from shapely.geometry import Point


@dataclass
class PositionedPoint:
    point: Point
    position: float
