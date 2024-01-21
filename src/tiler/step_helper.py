from typing import Iterator, Tuple, Union

from .config import Config
from .store import TileStore
from .types import (
    StepParameters,
    TileParameters,
    TileData,
)


class StepHelper:
    def __init__(
        self,
        config: Config,
        tile_store: TileStore,
        curr_step_parameters: Union[StepParameters, None],
        prev_step_parameters: Union[StepParameters, None],
    ):
        self.config = config
        self.tile_store = tile_store
        self.curr_step_parameters = curr_step_parameters
        self.prev_step_parameters = prev_step_parameters

    def has_curr_tile(
        self,
        tile_parameters: TileParameters,
    ) -> bool:
        if self.curr_step_parameters is None:
            raise Exception("No current step")

        return self.tile_store.has_tile(
            self.curr_step_parameters,
            tile_parameters,
        )

    def save_curr_tile(
        self,
        tile_parameters: TileParameters,
        tile: TileData,
    ) -> None:
        if self.curr_step_parameters is None:
            raise Exception("No current step")

        self.tile_store.save_tile(
            self.curr_step_parameters,
            tile_parameters,
            tile,
        )

    def get_prev_tile(
        self,
        tile_parameters: TileParameters,
    ) -> TileData:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")

        return self.tile_store.get_tile(
            self.prev_step_parameters,
            tile_parameters,
        )

    def get_prev_region(
        self,
        region_parameters: TileParameters,
    ) -> TileData:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")

        return self.tile_store.get_region(
            self.prev_step_parameters,
            region_parameters,
        )

    def get_prev_tiles(self) -> Iterator[Tuple[TileParameters, TileData]]:
        if self.prev_step_parameters is None:
            raise Exception("No previous step")

        return self.tile_store.get_all_tiles(
            self.prev_step_parameters,
        )
