from dataclasses import dataclass
import glob
import multiprocessing
import os
import shutil
import tempfile
from tqdm import tqdm
from typing import Any, Callable, Dict, List

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
from .utils.clean_exit import kill_self
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

        self._temp_dir = tempfile.mkdtemp()

        with rasterio.open(params.input_file) as src:
            self._data: np.ndarray = src.read(1)
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

            self._endx: int = self._data.shape[0]
            self._endy: int = self._data.shape[1]

        fd, filepath = tempfile.mkstemp()
        print(f"Logs at {filepath}")
        self._log_fd = fd

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

    def _clean(self, tile: np.ndarray) -> np.ndarray:
        blobifier = Blobifier(tile, self._min_blob_size)
        cleaned = blobifier.blobify()
        return cleaned

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

    def _vectorize(self, tile: np.ndarray) -> gpd.GeoDataFrame:
        shapes_gen = shapes(tile, transform=self._transform)
        polygons_and_labels = list(zip(*shapes_gen))
        polygons: List[Polygon] = [shape(s) for s in polygons_and_labels[0]]
        labels: List[Any] = [v for v in polygons_and_labels[1]]

        segmenter = Segmenter(
            polygons=polygons,
            pin_border=True,
        )
        segmenter.run_per_segment(self._generate_simplify_func())
        segmenter.run_per_segment(self._generate_smoothing_func())
        modified_polygons = segmenter.get_result()

        gdf = gpd.GeoDataFrame(geometry=modified_polygons)
        gdf[self._label_name] = labels
        return gdf

    def _process_tile(
        self,
        tile_parameters: TileParameters,
        tiler_parameters: TilerParameters,
    ) -> None:
        try:
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

            if bx1 - bx0 <= 2 * buffer or by1 - by0 <= 2 * buffer:
                empty = gpd.GeoDataFrame({"geometry": []})
                empty = empty.set_geometry("geometry")
                return empty

            tile_raster = self._data[bx0:bx1, by0:by1]
            cleaned = self._clean(tile_raster)

            rel_start_x = tile_parameters.start_x - bx0
            rel_start_y = tile_parameters.start_y - by0
            rel_end_x = min(rel_start_x + tile_parameters.width, bx1)
            rel_end_y = min(rel_start_y + tile_parameters.height, by1)

            unbuffered = cleaned[rel_start_x:rel_end_x, rel_start_y:rel_end_y]
            gdf = self._vectorize(unbuffered)

            # in physical space, x and y are reversed
            shift_x = tile_parameters.start_y * self._pixel_size
            shift_y = -(tile_parameters.start_x * self._pixel_size)
            gdf['geometry'] = gdf['geometry'].apply(
                lambda geom: translate(geom, xoff=shift_x, yoff=shift_y)
            )
            gdf.crs = self._crs

            gdf.to_file(os.path.join(
                self._temp_dir,
                "tile-"
                f"{tile_parameters.start_x}-{tile_parameters.start_y}.shp",
            ))
        except Exception as e:
            message = f"[{os.getpid()}] Exception at " \
                f"({tile_parameters.start_x}, {tile_parameters.start_y}): " \
                f"{e}\n"
            with os.fdopen(self._log_fd, 'w') as tmp:
                tmp.write(message)

    def _stitch_tiles(self) -> gpd.GeoDataFrame:
        all_gdfs = []

        for filepath in tqdm(
            glob.glob(os.path.join(self._temp_dir, "*.shp")),
            desc="Stitching tiles",
        ):
            gdf = gpd.read_file(filepath)
            all_gdfs.append(gdf)

        output_gdf = pd.concat(all_gdfs)
        output_gdf = unify_by_label(output_gdf, self._label_name)
        return output_gdf

    def geopolygonize(self) -> None:
        """
        Process inputs to get output.
        """

        try:
            tiler_parameters = TilerParameters(
                endx=self._endx,
                endy=self._endy,
                tile_size=self._tile_size,
                num_processes=self._workers,
            )
            rz = Tiler(
                tiler_parameters=tiler_parameters,
                process_tile=self._process_tile,
                stitch_tiles=self._stitch_tiles,
            )
            gdf = rz.process()
            gdf.to_file(self._output_file)

            shutil.rmtree(self._temp_dir)
            os.close(self._log_fd)
        except Exception as e:
            print(f"Geopolygonizer encountered error: {e}")
            kill_self()
