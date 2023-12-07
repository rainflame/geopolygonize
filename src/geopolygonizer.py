from dataclasses import dataclass
import glob
import multiprocessing
import os
import re
import tempfile
from tqdm import tqdm
from typing import Any, Callable, Dict, List, Tuple

from affine import Affine
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import DatasetReader
from rasterio.crs import CRS
from rasterio.features import shapes
from rasterio.windows import Window
from shapely.affinity import translate
from shapely.geometry import shape, LineString, Point, Polygon
import warnings

from .blobifier.blobifier import Blobifier
from .segmenter.segmenter import Segmenter
from .utils.smoothing import chaikins_corner_cutting
from .utils.tiler import Tiler, TileParameters, TilerParameters
from .utils.unifier import unify_by_label

warnings.filterwarnings("ignore", category=RuntimeWarning)

_EPSILON = 1.0e-10


@dataclass
class GeoPolygonizerParams:
    """User-inputtable parameters to `GeoPolygonizer`."""

    input_file: str
    """Input TIF file path"""
    output_file: str
    """Output gpkg file path"""
    label_name: str = 'label'
    """The name of the attribute each pixel value represents."""
    min_blob_size: int = 5
    """The mininum number of pixels a blob can have and not be filtered out."""
    pixel_size: int = 0
    """
    Override on the size of each pixel in units of the
    input file's coordinate reference system.
    """
    simplification_pixel_window: int = 1
    """The amount of simplification applied relative to the pixel size."""
    smoothing_iterations: int = 0
    """The number of iterations of smoothing to run on the output polygons."""
    tile_size: int = 100
    """Tile size in pixels"""
    tile_dir: str | None = None
    """
    The directory to create tiles in.
    If a tile already exists, it will not be recreated.
    If this parameter is `None`,
    the directory will be a temporary directory that is reported.
    """
    workers: int = 1
    """
    Number of processes to spawn to process tiles in parallel.
    Input 0 to use all available CPUs.
    """


class GeoPolygonizer:
    """
    `GeoPolygonizer` will convert a geographic raster input
    into an attractive gpkg file output.
    """

    def __init__(
        self,
        params: GeoPolygonizerParams,
    ) -> None:
        """
        Create a `GeoPolygonizer` and validate inputs.
        """

        inputs = glob.glob(params.input_file)
        if len(inputs) < 1:
            raise ValueError(f'Input file does not exist: {params.input_file}')
        self._input_file = inputs[0]

        output_dir = os.path.dirname(params.output_file)
        if not os.path.exists(output_dir):
            raise ValueError(f'Output directory does not exist: {output_dir}')
        self._output_file = params.output_file

        self._label_name = params.label_name

        self._check_is_non_negative(
            "--min-blob-size",
            params.min_blob_size
        )
        self._min_blob_size = params.min_blob_size

        self._check_is_non_negative(
            "--pixel-size",
            params.pixel_size
        )
        self._pixel_size = params.pixel_size

        self._check_is_non_negative(
            "--simplification-pixel-window",
            params.simplification_pixel_window
        )
        self._simplification_pixel_window = params.simplification_pixel_window

        self._check_is_non_negative(
            "--smoothing-iterations",
            params.smoothing_iterations
        )
        self._smoothing_iterations = params.smoothing_iterations

        self._check_is_positive(
            "--tile-size",
            params.tile_size
        )
        self._tile_size = params.tile_size

        self._check_is_non_negative(
            "--workers",
            params.workers
        )
        self._workers = multiprocessing.cpu_count() \
            if params.workers == 0 else params.workers

        with rasterio.open(params.input_file) as src:
            self._meta: Dict[str, Any] = src.meta
            self._crs: CRS = self._meta['crs']
            self._transform: Affine = src.transform
            self._set_dims(src)

            if params.pixel_size == 0:
                # assume pixel is square
                assert abs(src.res[0] - src.res[1]) < _EPSILON
                pixel_size = abs(src.res[0])
                if pixel_size == 0:
                    raise RuntimeError(
                        "Cannot infer pixel size from input file. "
                        "Please input it manually using `--pixel-size`."
                    )
                self._pixel_size = pixel_size

        if params.tile_dir is None:
            self._work_dir = tempfile.mkdtemp()
        else:
            self._work_dir = params.tile_dir
        print(f"Working directory: {self._work_dir}")
        self._log_dir = tempfile.mkdtemp()
        print(f"Logs directory: {self._log_dir}")

    def _set_dims(self, src: DatasetReader) -> None:
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
        self._width: int = width
        self._height: int = height

    def _check_is_positive(
        self,
        field_name: str,
        field_value: float,  # encompasses int
    ) -> None:
        if field_value <= 0:
            raise ValueError(f'Value for `{field_name}` must be positive.')

    def _check_is_non_negative(
        self,
        field_name: str,
        field_value: float,  # encompasses int
    ) -> None:
        if field_value < 0:
            raise ValueError(f'Value for `{field_name}` must be non-negative.')

    def _handle_exception(
        self,
        e: Exception,
        step: str,
        tile_parameters: TileParameters | None,
    ) -> None:
        pid = os.getpid()
        if tile_parameters is None:
            message = f"[{pid}] Exception in {step}: {e}\n"
        else:
            message = f"[{pid}] Exception in {step} at " \
                f"({tile_parameters.start_x}, {tile_parameters.start_y}): " \
                f"{e}\n"
        filepath = os.path.join(self._log_dir, f"log-{pid}")
        with open(filepath, 'w') as file:
            file.write(message)

    def _get_path(
        self,
        step: str,
        tile_parameters: TileParameters | None,
        file_extension: str,
    ) -> str:
        if tile_parameters is None:
            tile_path = os.path.join(
                self._work_dir,
                f"{step}.{file_extension}"
            )
        else:
            tile_path = os.path.join(
                self._work_dir,
                f"{step}-tile"
                f"_{tile_parameters.start_x}-{tile_parameters.start_y}"
                f"_{tile_parameters.width}-{tile_parameters.height}"
                f".{file_extension}",
            )
        return tile_path

    def _get_tile_glob(self, step: str, file_extension: str) -> str:
        glob_pattern = os.path.join(
            self._work_dir,
            f"{step}-tile_*_*"
            f".{file_extension}",
        )
        return glob_pattern

    def _get_tile_params_from_file(
        self,
        step: str,
        filepath: str,
    ) -> TileParameters | None:
        pattern = f"{step}-tile_(?P<start_x>[0-9]*)-(?P<start_y>[0-9]*)" \
                  f"_(?P<width>[0-9]*)-(?P<height>[0-9]*)"
        match = re.search(pattern, filepath)
        if match is None:
            return None

        start_x = int(match.group('start_x'))
        start_y = int(match.group('start_y'))
        width = int(match.group('width'))
        height = int(match.group('height'))
        return TileParameters(
            start_x=start_x,
            start_y=start_y,
            width=width,
            height=height,
        )

    # works for rasters (saved as npy)
    def _get_region(
        self,
        step: str,
        region_parameters: TileParameters,
    ) -> np.ndarray:
        data = np.zeros(
            (region_parameters.width, region_parameters.height)
        )
        region_start_x = region_parameters.start_x
        region_start_y = region_parameters.start_y
        region_end_x = region_parameters.start_x + region_parameters.width
        region_end_y = region_parameters.start_y + region_parameters.height

        for start_x in range(0, self._width, self._tile_size):
            if start_x + self._tile_size < region_start_x:
                continue
            if start_x >= region_end_x:
                break

            for start_y in range(0, self._height, self._tile_size):
                if start_y + self._tile_size < region_start_y:
                    continue
                if start_y >= region_end_y:
                    break

                tile_parameters = TileParameters(
                    start_x=start_x,
                    start_y=start_y,
                    width=self._tile_size,
                    height=self._tile_size,
                )
                tile_path = self._get_path(step, tile_parameters, "npy")
                tile = np.load(tile_path)
                tile_width = tile.shape[0]
                tile_height = tile.shape[1]
                end_x = start_x + tile_width
                end_y = start_y + tile_height

                if start_x < region_start_x:
                    rel_tile_start_x = region_start_x - start_x
                    rel_data_start_x = 0
                else:
                    rel_tile_start_x = 0
                    rel_data_start_x = start_x - region_start_x
                if end_x < region_end_x:
                    rel_tile_end_x = end_x - start_x
                    rel_data_end_x = end_x - region_start_x
                else:
                    rel_tile_end_x = region_end_x - start_x
                    rel_data_end_x = region_end_x - region_start_x
                    pass
                if start_y < region_start_y:
                    rel_tile_start_y = region_start_y - start_y
                    rel_data_start_y = 0
                else:
                    rel_tile_start_y = 0
                    rel_data_start_y = start_y - region_start_y
                if end_y < region_end_y:
                    rel_tile_end_y = end_y - start_y
                    rel_data_end_y = end_y - region_start_y
                else:
                    rel_tile_end_y = region_end_y - start_y
                    rel_data_end_y = region_end_y - region_start_y

                data[
                    rel_data_start_x:rel_data_end_x,
                    rel_data_start_y:rel_data_end_y
                ] = tile[
                    rel_tile_start_x:rel_tile_end_x,
                    rel_tile_start_y:rel_tile_end_y,
                ]

        return data

    def _input_tile(self, tile_parameters: TileParameters) -> None:
        step = "input"
        try:
            tile_path = self._get_path(step, tile_parameters, "npy")
            if os.path.exists(tile_path):
                return

            bx0 = max(tile_parameters.start_x, 0)
            by0 = max(tile_parameters.start_y, 0)
            bx1 = min(
                tile_parameters.start_x+tile_parameters.width,
                self._width
            )
            by1 = min(
                tile_parameters.start_y+tile_parameters.height,
                self._height
            )

            with rasterio.open(self._input_file) as src:
                # Window treats x as cols and y as rows,
                # whereas we treat x as rows and y as cols.
                tile = src.read(1, window=Window(by0, bx0, by1-by0, bx1-bx0))
                np.save(tile_path, tile)
        except Exception as e:
            self._handle_exception(e, step, tile_parameters)

    def _clean_tile(
        self,
        tile_parameters: TileParameters,
    ) -> None:
        step = "clean"
        prev_step = "input"
        try:
            tile_path = self._get_path(step, tile_parameters, "npy")
            if os.path.exists(tile_path):
                return

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

            buffered_region = self._get_region(prev_step, region_parameters)
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
            np.save(tile_path, tile)
        except Exception as e:
            self._handle_exception(e, step, tile_parameters)

    def _polygonize_tile(
        self,
        tile_parameters: TileParameters,
    ) -> None:
        step = "polygonize"
        prev_step = "clean"
        try:
            tile_path = self._get_path(step, tile_parameters, "gpkg")
            if os.path.exists(tile_path):
                return

            prev_tile_path = self._get_path(prev_step, tile_parameters, "npy")
            if not os.path.exists(prev_tile_path):
                return
            tile = np.load(prev_tile_path)
            tile = tile.astype('float32')

            shapes_gen = shapes(tile, transform=self._transform)
            polygons_and_labels = list(zip(*shapes_gen))
            polygons: List[Polygon] = [
                shape(s) for s in polygons_and_labels[0]
            ]
            labels: List[Any] = [v for v in polygons_and_labels[1]]

            gdf = gpd.GeoDataFrame(geometry=polygons)
            gdf[self._label_name] = labels
            # in physical space, x and y are reversed
            shift_x = tile_parameters.start_y * self._pixel_size
            shift_y = -(tile_parameters.start_x * self._pixel_size)
            gdf['geometry'] = gdf['geometry'].apply(
                lambda geom: translate(geom, xoff=shift_x, yoff=shift_y)
            )
            gdf.crs = self._crs
            gdf.to_file(tile_path)
        except Exception as e:
            self._handle_exception(e, step, tile_parameters)

    def _generate_smoothing_func(self) -> Callable[[LineString], LineString]:
        def smooth(segment: LineString) -> LineString:
            coords = chaikins_corner_cutting(
                segment.coords,
                self._smoothing_iterations
            )
            return LineString(coords)

        return smooth

    def _generate_simplify_func(self) -> Callable[[LineString], LineString]:
        tolerance = self._pixel_size * self._simplification_pixel_window

        def simplify(segment: LineString) -> LineString:
            # Simplification will turn rings into what are effectively points.
            # We cut the ring in half to provide simplification
            # with non-ring segments instead.
            if segment.is_ring:
                assert len(segment.coords) >= 3
                midpoint_idx = len(segment.coords) // 2
                segment1 = LineString(segment.coords[:midpoint_idx+1])
                segment2 = LineString(segment.coords[midpoint_idx:])
                simplified1 = segment1.simplify(tolerance)
                simplified2 = segment2.simplify(tolerance)
                coords =\
                    list(simplified1.coords)[:-1] + list(simplified2.coords)
                simplified = LineString(coords)
            else:
                simplified = segment.simplify(tolerance)
            return simplified

        return simplify

    def _vectorize_tile(
        self,
        tile_parameters: TileParameters,
    ) -> None:
        step = "vectorize"
        prev_step = "polygonize"
        try:
            tile_path = self._get_path(step, tile_parameters, "gpkg")
            if os.path.exists(tile_path):
                return

            prev_tile_path = self._get_path(prev_step, tile_parameters, "gpkg")
            if not os.path.exists(prev_tile_path):
                return
            gdf = gpd.read_file(prev_tile_path)
            polygons = gdf.geometry.to_list()
            labels = gdf[self._label_name].to_list()

            segmenter = Segmenter(
                polygons=polygons,
                labels=labels,
                pin_border=True,
            )
            segmenter.run_per_segment(self._generate_simplify_func())
            segmenter.run_per_segment(self._generate_smoothing_func())
            modified_polygons, modified_labels = segmenter.get_result()

            gdf = gpd.GeoDataFrame(geometry=modified_polygons)
            gdf[self._label_name] = modified_labels
            gdf.crs = self._crs
            gdf.to_file(tile_path)
        except Exception as e:
            self._handle_exception(e, step, tile_parameters)

    def _stitch(self) -> gpd.GeoDataFrame:
        step = "stitch"
        prev_step = "vectorize"
        try:
            all_gdfs = []
            for filepath in tqdm(
                glob.glob(self._get_tile_glob(prev_step, "gpkg")),
                desc="Stitching gpkg files",
            ):
                gdf = gpd.read_file(filepath)
                all_gdfs.append(gdf)

            output_gdf = pd.concat(all_gdfs)
            output_gdf = unify_by_label(output_gdf, self._label_name)
            output_gdf.to_file(self._output_file)
        except Exception as e:
            self._handle_exception(e, step, None)

    def geopolygonize(self) -> None:
        """
        Process inputs to get output.
        First, clean the input to take out small blobs of pixels,
        then vectorize the result to get the final output.
        """

        tiler_parameters = TilerParameters(
            endx=self._width,
            endy=self._height,
            tile_size=self._tile_size,
            num_processes=self._workers,
        )

        input_tiler = Tiler(
            tiler_parameters=tiler_parameters,
            step="input",
            process_tile=self._input_tile,
        )
        input_tiler.process()

        clean_tiler = Tiler(
            tiler_parameters=tiler_parameters,
            step="clean",
            process_tile=self._clean_tile,
        )
        clean_tiler.process()

        polygonize_tiler = Tiler(
            tiler_parameters=tiler_parameters,
            step="polygonize",
            process_tile=self._polygonize_tile,
        )
        polygonize_tiler.process()

        vectorize_tiler = Tiler(
            tiler_parameters=tiler_parameters,
            step="vectorize",
            process_tile=self._vectorize_tile,
        )
        vectorize_tiler.process()

        self._stitch()
