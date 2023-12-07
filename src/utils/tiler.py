from dataclasses import dataclass
from itertools import count, takewhile
import multiprocessing as mp
import os
from typing import Any, Callable, List, Tuple
from tqdm import tqdm

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
        step: str,
        process_tile: Callable[
            [TileParameters],
            Any
        ],
    ) -> None:
        self.tiler_parameters = tiler_parameters
        self.step = step
        self.process_tile = process_tile

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
        Callable[[TileParameters], None],
    ]) -> None:
        try:
            tile_parameters, process_tile = args
            process_tile(tile_parameters)
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
        ) for tile_parameters in all_tile_parameters]

        pool = mp.Pool(processes=tp.num_processes)
        try:
            for _ in tqdm(
                pool.imap_unordered(self._process_tile_wrapper, all_args),
                total=len(all_args),
                desc=f"[{self.step}] Processing tiles"
            ):
                pass
            pool.close()
            pool.join()
        except Exception as e:
            kill_children()
            raise e

    def process(self) -> Any:
        set_clean_exit()

        all_tile_parameters = self._generate_tiles()
        self._process_tiles(all_tile_parameters)
