from dataclasses import dataclass
import glob
import os
import multiprocessing as mp
from typing import Callable, List, Tuple
from tqdm import tqdm

import pandas as pd
import geopandas as gpd


@dataclass
class TilerParameters:
    endx: int
    endy: int
    startx: int = 0
    starty: int = 0
    tile_size: int = 100
    num_processes: int = 1
    temp_dir: str = os.path.join("data", "temp")


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
            gpd.GeoDataFrame
        ],
    ):
        self.tiler_parameters = tiler_parameters
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
        Callable[
            [TileParameters, TilerParameters],
            gpd.GeoDataFrame
        ],
        TilerParameters,
    ]):
        tile_parameters, process_tile, tiler_parameters = args
        gdf = process_tile(
            tile_parameters,
            tiler_parameters,
        )

        gdf.to_file(os.path.join(
            tiler_parameters.temp_dir,
            f"tile-{tile_parameters.start_x}-{tile_parameters.start_y}.shp",
        ))

    def _process_tiles(self, all_tile_parameters: List[TileParameters]):
        tp = self.tiler_parameters
        all_args = [(
            tile_parameters,
            self.process_tile,
            self.tiler_parameters,
        ) for tile_parameters in all_tile_parameters]

        with mp.Pool(processes=tp.num_processes) as pool:
            for _ in tqdm(
                pool.imap_unordered(self._process_tile_wrapper, all_args),
                total=len(all_args),
                desc="Processing tiles"
            ):
                pass

    def _stitch_tiles(self) -> gpd.GeoDataFrame:
        tp = self.tiler_parameters
        all_gdfs = []
        for filepath in tqdm(
            glob.glob(os.path.join(tp.temp_dir, "*.shp")),
            desc="Stitching tiles",
        ):
            gdf = gpd.read_file(filepath)
            all_gdfs.append(gdf)
        output_gdf = pd.concat(all_gdfs)
        return output_gdf

    def process(self) -> gpd.GeoDataFrame:
        all_tile_parameters = self._generate_tiles()
        self._process_tiles(all_tile_parameters)
        output = self._stitch_tiles()
        return output
