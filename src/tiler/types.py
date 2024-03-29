from dataclasses import dataclass
from typing import Callable, Iterator, List, Tuple, Union

import numpy as np
import geopandas as gpd


class TileParameters:
    def __init__(
        self,
        start_x: int,
        start_y: int,
        width: int,
        height: int,
    ) -> None:
        self.start_x = start_x
        self.start_y = start_y
        self.width = width
        self.height = height

    def __str__(self):
        return f"[{self.start_x}:{self.start_y}] ({self.width},{self.height})"

    def __hash__(self):
        return hash(self.__str__())

    def __eq__(self, other):
        return self.__str__() == other.__str__()


TileData = Union[np.ndarray, gpd.GeoDataFrame]


StepFunction = Callable[[
    TileParameters,
    Callable[[TileParameters], TileData],  # get_prev_tile
    Callable[[TileParameters], TileData],  # get_prev_region
    Callable[[TileParameters, TileData], None],  # save_curr_tile
], None]


UnionFunction = Callable[[
    Callable[[], Iterator[Tuple[TileParameters, TileData]]],  # get_prev_tiles
], None]


class StepParameters:
    def __init__(self, name: str, data_type: TileData) -> None:
        self.name = name
        self.data_type = data_type

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.__str__())

    def __eq__(self, other):
        return self.__str__() == other.__str__()


@dataclass
class PipelineParameters:
    width: int
    height: int
    steps: List[Tuple[StepParameters, StepFunction]]
    union_function: UnionFunction
    debug: bool = False
    # True when all steps only depend on former tile, i.e. only
    # use get_prev_tile and not get_prev_region.
    independent: bool = False
