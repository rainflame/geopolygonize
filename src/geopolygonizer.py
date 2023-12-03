from dataclasses import dataclass
import glob
import multiprocessing
import os
import re
import shutil
import tempfile
from tqdm import tqdm
from typing import Any, Callable, Dict, List, Tuple

from affine import Affine
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.crs import CRS
from rasterio.features import shapes
from shapely.affinity import translate
from shapely.geometry import shape, LineString, Polygon
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
    """Output shapefile path"""
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
    into an attractive shapefile output.
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
            self._original: np.ndarray = src.read(1)
            self._meta: Dict[str, Any] = src.meta
            self._crs: CRS = self._meta['crs']
            self._transform: Affine = src.transform

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

            self._endx: int = self._original.shape[0]
            self._endy: int = self._original.shape[1]

        if params.tile_dir is None:
            self._work_dir = tempfile.mkdtemp()
        else:
            self._work_dir = params.tile_dir
        print(f"Working directory: {self._work_dir}")
        self._log_dir = tempfile.mkdtemp()
        print(f"Logs directory: {self._log_dir}")

        # to be generated
        self._cleaned: np.ndarray | None = None

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
                f"_{self._tile_size}-{self._tile_size}.{file_extension}",
            )
        return tile_path

    def _get_tile_glob(self, step: str, file_extension: str) -> str:
        glob_pattern = os.path.join(
            self._work_dir,
            f"{step}-tile_*_{self._tile_size}-{self._tile_size}"
            f".{file_extension}",
        )
        return glob_pattern

    def _get_start_from_file(
        self,
        step: str,
        filepath: str,
    ) -> Tuple[int, int] | None:
        pattern = f"{step}-tile_(?P<start_x>[0-9]*)-(?P<start_y>[0-9]*)" \
                  f"_{self._tile_size}-{self._tile_size}"
        match = re.search(pattern, filepath)
        if match is None:
            return None
        start_x = match.group('start_x')
        start_y = match.group('start_y')
        return int(start_x), int(start_y)

    def _clean_tile(
        self,
        tile_parameters: TileParameters,
        tiler_parameters: TilerParameters,
    ) -> None:
        step = "clean"
        data = self._original

        try:
            tile_path = self._get_path(step, tile_parameters, "npy")
            if os.path.exists(tile_path):
                return

            buffer = self._min_blob_size - 1
            bx0 = max(tile_parameters.start_x-buffer, 0)
            by0 = max(tile_parameters.start_y-buffer, 0)
            bx1 = min(
                tile_parameters.start_x+tile_parameters.width+buffer,
                tiler_parameters.endx
            )
            by1 = min(
                tile_parameters.start_y+tile_parameters.height+buffer,
                tiler_parameters.endy
            )
            buffered_tile_raster = data[bx0:bx1, by0:by1]

            blobifier = Blobifier(buffered_tile_raster, self._min_blob_size)
            cleaned = blobifier.blobify()

            rel_start_x = tile_parameters.start_x - bx0
            rel_start_y = tile_parameters.start_y - by0
            rel_end_x = min(rel_start_x + tile_parameters.width, bx1)
            rel_end_y = min(rel_start_y + tile_parameters.height, by1)
            if rel_end_x - rel_start_x <= 0 \
                    or rel_end_y - rel_start_y <= 0:
                return
            tile_raster = cleaned[rel_start_x:rel_end_x, rel_start_y:rel_end_y]

            np.save(tile_path, tile_raster)
        except Exception as e:
            self._handle_exception(e, step, tile_parameters)

    def _clean_stitch(self) -> None:
        step = "clean"
        try:
            file_path = self._get_path(step, None, "npy")
            if os.path.exists(file_path):
                return

            raster = np.empty_like(self._original)
            for filepath in tqdm(
                glob.glob(self._get_tile_glob(step, "npy")),
                desc=f"[{step}] Stitching rasters",
            ):
                starts = self._get_start_from_file(step, filepath)
                assert starts is not None, \
                    f"Could not get start values from {filepath}."
                start_x, start_y = starts

                tile = np.load(filepath)

                end_x = start_x+tile.shape[0]
                end_y = start_y+tile.shape[1]
                assert end_x <= self._endx and end_y <= self._endy, \
                    "Tile from cleaning step is not within bounds " \
                    "of input raster size."
                raster[start_x:end_x, start_y:end_y] = tile

            np.save(file_path, raster)
        except Exception as e:
            self._handle_exception(e, step, None)

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
        tiler_parameters: TilerParameters,
    ) -> None:
        step = "vectorize"
        data = self._cleaned
        assert data is not None

        try:
            tile_path = self._get_path(step, tile_parameters, "shp")
            if os.path.exists(tile_path):
                return

            x0 = tile_parameters.start_x
            x1 = tile_parameters.start_x + tile_parameters.width
            y0 = tile_parameters.start_y
            y1 = tile_parameters.start_y + tile_parameters.height
            tile = data[x0:x1, y0:y1]

            shapes_gen = shapes(tile, transform=self._transform)
            polygons_and_labels = list(zip(*shapes_gen))
            polygons: List[Polygon] = [
                shape(s) for s in polygons_and_labels[0]
            ]
            labels: List[Any] = [v for v in polygons_and_labels[1]]

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

    def _vectorize_stitch(self) -> gpd.GeoDataFrame:
        step = "vectorize"
        try:
            file_path = self._get_path(step, None, "shp")
            if os.path.exists(file_path):
                return
            all_gdfs = []

            for filepath in tqdm(
                glob.glob(self._get_tile_glob(step, "shp")),
                desc=f"[{step}] Stitching shapefiles",
            ):
                gdf = gpd.read_file(filepath)
                all_gdfs.append(gdf)

            output_gdf = pd.concat(all_gdfs)
            output_gdf = unify_by_label(output_gdf, self._label_name)
            output_gdf.to_file(file_path)
        except Exception as e:
            self._handle_exception(e, step, None)

    def _copy_shapefile(self, src: str, dst: str) -> None:
        if src[-4:] == ".shp":
            src = src[:-4]
        if dst[-4:] == ".shp":
            dst = dst[:-4]
        file_extensions = ["shp", "shx", "cpg", "dbf"]
        for fe in file_extensions:
            src_path = f"{src}.{fe}"
            dst_path = f"{dst}.{fe}"
            shutil.copy2(src_path, dst_path)

    def geopolygonize(self) -> None:
        """
        Process inputs to get output.
        First, clean the input to take out small blobs of pixels,
        then vectorize the result to get the final output.
        """

        step = "clean"
        tiler_parameters = TilerParameters(
            step=step,
            endx=self._endx,
            endy=self._endy,
            tile_size=self._tile_size,
            num_processes=self._workers,
        )
        clean_tiler = Tiler(
            tiler_parameters=tiler_parameters,
            process_tile=self._clean_tile,
            stitch_tiles=self._clean_stitch,
        )
        clean_tiler.process()
        clean_file = self._get_path(step, None, "npy")
        self._cleaned = np.load(clean_file)

        # TODO: Do the polygonization step here!

        step = "vectorize"
        tiler_parameters = TilerParameters(
            step=step,
            endx=self._endx,
            endy=self._endy,
            tile_size=self._tile_size,
            num_processes=self._workers,
        )
        vectorize_tiler = Tiler(
            tiler_parameters=tiler_parameters,
            process_tile=self._vectorize_tile,
            stitch_tiles=self._vectorize_stitch,
        )
        vectorize_tiler.process()
        vectorize_file = self._get_path(step, None, "shp")

        self._copy_shapefile(vectorize_file, self._output_file)
