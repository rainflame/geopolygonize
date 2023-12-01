from dataclasses import dataclass
import multiprocessing as mp
import os
from typing import Any, Callable, List, Tuple
from tqdm import tqdm

import geopandas as gpd

from .clean_exit import CleanExit, kill_children, set_clean_exit


@dataclass
class TilerParameters:
    endx: int
    endy: int
    startx: int = 0
    starty: int = 0
    tile_size: int = 100
    num_processes: int = 1


@dataclass
class TileParameters:
    start_x: int
    start_y: int
    width: int
    height: int


class Tiler:
    def __init__(
        self,
        tiler_parameters: TilerParameters,
        process_tile: Callable[
            [TileParameters, TilerParameters],
            Any
        ],
        stitch_tiles: Callable[[], Any],
    ) -> None:
        self.tiler_parameters = tiler_parameters
        self.process_tile = process_tile
        self.stitch_tiles = stitch_tiles

    def _generate_tiles(self) -> List[TileParameters]:
        tp = self.tiler_parameters
        all_tile_parameters = [
            TileParameters(x, y, tp.tile_size, tp.tile_size)
            for x in range(tp.startx, tp.endx, tp.tile_size)
            for y in range(tp.starty, tp.endy, tp.tile_size)
        ]
        return all_tile_parameters

    @staticmethod
    def _process_tile_wrapper(args: Tuple[
        TileParameters,
        Callable[
            [TileParameters, TilerParameters],
            gpd.GeoDataFrame
        ],
        TilerParameters,
    ]) -> None:
        try:
            tile_parameters, process_tile, tiler_parameters = args
            process_tile(
                tile_parameters,
                tiler_parameters,
            )
        except CleanExit:
            print(f"[{os.getpid()}] clean exit")
            pass

    def _process_tiles(
        self,
        all_tile_parameters: List[TileParameters],
    ) -> None:
        tp = self.tiler_parameters
        all_args = [(
            tile_parameters,
            self.process_tile,
            self.tiler_parameters,
        ) for tile_parameters in all_tile_parameters]

        pool = mp.Pool(processes=tp.num_processes)
        try:
            for _ in tqdm(
                pool.imap_unordered(self._process_tile_wrapper, all_args),
                total=len(all_args),
                desc="Processing tiles"
            ):
                pass
            pool.close()
            pool.join()
        except Exception as e:
            kill_children()
            raise e

    def process(self) -> Any:
        set_clean_exit()

        output = None
        all_tile_parameters = self._generate_tiles()
        some_tile_parameters = list(filter(
            lambda x: (x.start_x == 2400 and x.start_y == 2400),
            all_tile_parameters
        ))
        self._process_tiles(some_tile_parameters)
        output = self.stitch_tiles()
        return output
