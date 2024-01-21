from tqdm import tqdm
from typing import Callable, Iterator, Tuple

import dask.dataframe as dd
import dask_geopandas as dgpd
import geopandas as gpd
import numpy as np
import rasterio
from rasterio import DatasetReader
from rasterio.profiles import Profile
from rasterio.windows import Window

from src.utils.io import to_file
from .types import (
    TileData,
    TileParameters,
    StepFunction,
)


CHUNKSIZE = int(1e4)


def get_dims(src: DatasetReader) -> Tuple[int, int]:
    width = 0
    height = 0
    for _i, window in src.block_windows(1):
        # Window treats x as cols and y as rows,
        # whereas we treat x as rows and y as cols.
        x_end = window.row_off + window.height
        y_end = window.col_off + window.width
        if x_end > width:
            width = x_end
        if y_end > height:
            height = y_end
    return width, height


def generate_input_tile_from_ndarray(
    input_path: str,
    width: int,
    height: int,
) -> StepFunction:
    def input_tile_from_ndarray(
        tile_parameters: TileParameters,
        _get_prev_tile: Callable[[TileParameters], TileData],
        _get_prev_region: Callable[[TileParameters], TileData],
        save_curr_tile: Callable[[TileParameters, TileData], None],
    ) -> None:
        bx0 = max(tile_parameters.start_x, 0)
        by0 = max(tile_parameters.start_y, 0)
        bx1 = min(
            tile_parameters.start_x+tile_parameters.width,
            width,
        )
        by1 = min(
            tile_parameters.start_y+tile_parameters.height,
            height,
        )
        with rasterio.open(input_path) as src:
            # Window treats x as cols and y as rows,
            # whereas we treat x as rows and y as cols.
            tile = src.read(1, window=Window(by0, bx0, by1-by0, bx1-bx0))
            save_curr_tile(tile_parameters, tile)
    return input_tile_from_ndarray


# Assumes size of array stays constant from beginning.
def generate_union_ndarray(
    output_path: str,
    profile: Profile,
    width: int,
    height: int,
) -> Callable[[Callable[[], Iterator[Tuple[TileParameters, TileData]]]], None]:
    def union_ndarray(
        get_prev_tiles: Callable[
            [],
            Iterator[Tuple[TileParameters, TileData]]
        ],
    ) -> None:
        data = np.zeros((width, height))
        for tile_parameters, prev_tile in tqdm(
            get_prev_tiles(),
            desc="Stitching npy files",
        ):
            startx = tile_parameters.start_x
            endx = tile_parameters.start_x+prev_tile.shape[0]
            starty = tile_parameters.start_y
            endy = tile_parameters.start_y+prev_tile.shape[1]
            data[startx:endx, starty:endy] = prev_tile

        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(data, 1)  # write to band 1
    return union_ndarray


def generate_union_gdf(
    output_path: str,
    label_name: str,
) -> Callable[[Callable[[], Iterator[Tuple[TileParameters, TileData]]]], None]:
    def union_gdf(
        get_prev_tiles: Callable[[], Iterator[TileData]],
    ) -> None:
        union_dgdf = dgpd.from_geopandas(
            gpd.GeoDataFrame(),
            chunksize=CHUNKSIZE
        )
        for tile_parameters, prev_tile in tqdm(
            get_prev_tiles(),
            desc="Stitching gpkg files",
        ):
            assert isinstance(prev_tile, gpd.GeoDataFrame)
            dgdf = dgpd.from_geopandas(prev_tile, npartitions=1)
            union_dgdf = dd.concat([union_dgdf, dgdf])

        # Dask recommends using split_out = 1
        # to use sort=True, which allows for determinism,
        # and because split_out > 1  may not work
        # with newer versions of Dask.
        # However, this will require all the data
        # to fit on the memory, which is not always possible.
        # Unfortunately, the lack of determinism
        # means that sometimes the dissolve outputs
        # a suboptimal join of the polygons.
        # This should be remedied with a rerun on the
        # same tile directory.
        #
        # https://dask-geopandas.readthedocs.io/en/stable/guide/dissolve.html
        num_rows = len(union_dgdf.index)
        partitions = num_rows // CHUNKSIZE + 1
        print(
            f"# ROWS: {num_rows}"
            f"\tCHUNKSIZE: {CHUNKSIZE}"
            f"\t# PARTITIONS: {partitions}"
        )
        union_dgdf = union_dgdf.dissolve(
            label_name,
            split_out=partitions
            #sort=True,
        )
        to_file(union_dgdf, output_path)
    return union_gdf
