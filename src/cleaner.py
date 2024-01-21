from dataclasses import dataclass
from typing import Callable, Iterator, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window
import warnings

from .blobifier import Blobifier
from .utils import checkers
from .utils.tiler import (
    PipelineParameters,
    TileData,
    StepParameters,
    TileParameters,
    create_config,
    get_dims,
    generate_union_ndarray,
    pipe,
)

warnings.filterwarnings("ignore", category=RuntimeWarning)


@dataclass
class CleanerParams:
    """User-inputtable parameters to `Cleaner`."""

    input_file: str
    """Input TIF file path"""
    output_file: str
    """Output gpkg file path"""
    min_blob_size: int = 5
    """The mininum number of pixels a blob can have and not be filtered out."""
    tile_size: int = 1000
    """Tile size in pixels"""
    debug: bool = False
    """enable debug mode"""


class Cleaner:
    """
    Cleaner preprocesses the input TIF file for geopolygonization.
    """

    def __init__(
        self,
        params: CleanerParams,
    ) -> None:
        """
        Create a `Cleaner` and validate inputs.
        """

        self._input_file = checkers.check_and_retrieve_input_path(
            params.input_file
        )
        checkers.check_output_path(params.output_file)
        self._output_file = params.output_file

        checkers.check_is_non_negative(
            "--min-blob-size",
            params.min_blob_size
        )
        self._min_blob_size = params.min_blob_size

        checkers.check_is_positive(
            "--tile-size",
            params.tile_size
        )
        self._tile_size = params.tile_size

        with rasterio.open(params.input_file) as src:
            self._profile = src.profile.copy()
            width, height = get_dims(src)
            self._width, self._height = width, height

        self._debug = params.debug

    def _clean_tile(
        self,
        tile_parameters: TileParameters,
        _get_prev_tile: Callable[[TileParameters], TileData],
        _get_prev_region: Callable[[TileParameters], TileData],
        save_curr_tile: Callable[[TileParameters, TileData], None],
    ) -> None:
        buffer = self._min_blob_size - 1
        bx0 = max(tile_parameters.start_x-buffer, 0)
        by0 = max(tile_parameters.start_y-buffer, 0)
        bx1 = min(
            tile_parameters.start_x+tile_parameters.width+buffer,
            self._width
        )
        by1 = min(
            tile_parameters.start_y+tile_parameters.height+buffer,
            self._height
        )
        region_parameters = TileParameters(
            start_x=bx0,
            start_y=by0,
            width=bx1-bx0,
            height=by1-by0,
        )
        if region_parameters.width <= 0 or region_parameters.height <= 0:
            return

        with rasterio.open(self._input_file) as src:
            # Window treats x as cols and y as rows,
            # whereas we treat x as rows and y as cols.
            buffered_region = \
                src.read(1, window=Window(by0, bx0, by1-by0, bx1-bx0))

        blobifier = Blobifier(buffered_region, self._min_blob_size)
        cleaned = blobifier.blobify()

        rel_start_x = tile_parameters.start_x - region_parameters.start_x
        rel_start_y = tile_parameters.start_y - region_parameters.start_y
        rel_end_x = min(
            rel_start_x + tile_parameters.width,
            region_parameters.start_x + region_parameters.width
        )
        rel_end_y = min(
            rel_start_y + tile_parameters.height,
            region_parameters.start_y + region_parameters.height
        )
        tile = cleaned[rel_start_x:rel_end_x, rel_start_y:rel_end_y]
        save_curr_tile(tile_parameters, tile)

    def _union(
        self,
        get_prev_tiles: Callable[
            [],
            Iterator[Tuple[TileParameters, TileData]]
        ],
    ) -> None:
        return generate_union_ndarray(
            self._output_file,
            self._profile,
            self._width,
            self._height,
        )(get_prev_tiles)

    def clean(self) -> None:
        """
        Clean input to get output.
        """

        pipeline_parameters = PipelineParameters(
            width=self._width,
            height=self._height,
            steps=[
                (
                    StepParameters(
                        name="clean",
                        data_type=np.ndarray,
                    ),
                    self._clean_tile,
                ),
            ],
            union_function=self._union,
            tile_size=self._tile_size,
            debug=self._debug,
            independent=True,
        )
        config = create_config(pipeline_parameters)
        pipe(pipeline_parameters, config)
