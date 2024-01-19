from dataclasses import dataclass
import glob
import multiprocessing
import os
import shutil
import tempfile
from tqdm import tqdm
from typing import Any, Callable, Dict, List, Union

from affine import Affine
import dask.dataframe as dd
import dask_geopandas as dgpd
import geopandas as gpd
import numpy as np
import rasterio
from rasterio import DatasetReader
from rasterio.crs import CRS
from rasterio.features import shapes
from rasterio.windows import Window
from shapely.affinity import translate
from shapely.geometry import shape, LineString, Polygon
import warnings

from .blobifier.blobifier import Blobifier
from .segmenter.segmenter import Segmenter
from .utils import checkers
from .utils.io import to_file
from .utils.smoothing import chaikins_corner_cutting
from .utils.tiler import (
    Pipeline,
    PipelineParameters,
    StepParameters,
    StepHelper,
    TileParameters,
)

warnings.filterwarnings("ignore", category=RuntimeWarning)

_EPSILON = 1.0e-10
_CHUNKSIZE = int(1e4)


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
    tile_size: int = 1000
    """Tile size in pixels"""
    tile_dir: Union[str, None] = None
    """
    The directory to create tiles in.
    If a tile already exists, it will not be recreated.
    If this parameter is `None`,
    the directory will be a temporary directory that is reported.
    """
    cleanup: bool = True
    """
    By default, the `tile_dir` is removed after completion.
    Set this option to False to prevent the removal.
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

        self._input_file = checkers.check_and_retrieve_input_path(
            params.input_file
        )
        checkers.check_output_path(params.output_file)
        self._output_file = params.output_file

        self._label_name = params.label_name

        checkers.check_is_non_negative(
            "--min-blob-size",
            params.min_blob_size
        )
        self._min_blob_size = params.min_blob_size

        checkers.check_is_non_negative(
            "--pixel-size",
            params.pixel_size
        )
        self._pixel_size = params.pixel_size

        checkers.check_is_non_negative(
            "--simplification-pixel-window",
            params.simplification_pixel_window
        )
        self._simplification_pixel_window = params.simplification_pixel_window

        checkers.check_is_non_negative(
            "--smoothing-iterations",
            params.smoothing_iterations
        )
        self._smoothing_iterations = params.smoothing_iterations

        checkers.check_is_positive(
            "--tile-size",
            params.tile_size
        )
        self._tile_size = params.tile_size

        checkers.check_is_non_negative(
            "--workers",
            params.workers
        )
        self._workers = multiprocessing.cpu_count() \
            if params.workers == 0 else params.workers
        print(f"Using {self._workers} workers.")

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

        self.cleanup = params.cleanup

        if params.tile_dir is None:
            self._work_dir = tempfile.mkdtemp()
        else:
            self._work_dir = params.tile_dir
        print(f"Working directory: {self._work_dir}")
        self._log_dir = tempfile.mkdtemp()
        print(f"Logs directory: {self._log_dir}")

    def _cleanup(self):
        print(f"Removing working directory: {self._work_dir}")
        shutil.rmtree(self._work_dir)

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

    def _input_tile(
        self,
        tile_parameters: TileParameters,
        step_helper: StepHelper,
    ) -> None:
        curr_path = step_helper.get_curr_path(tile_parameters)
        if os.path.exists(curr_path):
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
            np.save(curr_path, tile)

    def _clean_tile(
        self,
        tile_parameters: TileParameters,
        step_helper: StepHelper,
    ) -> None:
        curr_path = step_helper.get_curr_path(tile_parameters)
        if os.path.exists(curr_path):
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

        buffered_region = step_helper.get_prev_region(region_parameters)

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
        np.save(curr_path, tile)

    def _polygonize_tile(
        self,
        tile_parameters: TileParameters,
        step_helper: StepHelper,
    ) -> None:
        curr_path = step_helper.get_curr_path(tile_parameters)
        if os.path.exists(curr_path):
            return

        prev_path = step_helper.get_prev_path(tile_parameters)
        if not os.path.exists(prev_path):
            return
        prev_tile = np.load(prev_path)
        prev_tile = prev_tile.astype('float32')

        shapes_gen = shapes(prev_tile, transform=self._transform)
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
        gdf.to_file(curr_path)

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
        step_helper: StepHelper,
    ) -> None:
        curr_path = step_helper.get_curr_path(tile_parameters)
        if os.path.exists(curr_path):
            return

        prev_path = step_helper.get_prev_path(tile_parameters)
        if not os.path.exists(prev_path):
            return
        prev_tile = gpd.read_file(prev_path)

        polygons = prev_tile.geometry.to_list()
        labels = prev_tile[self._label_name].to_list()

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
        gdf.to_file(curr_path)

    def _stitch(
        self,
        step_helper: StepHelper,
    ) -> gpd.GeoDataFrame:
        union_dgdf = dgpd.from_geopandas(
            gpd.GeoDataFrame(),
            chunksize=_CHUNKSIZE
        )
        for filepath in tqdm(
            glob.glob(step_helper.get_prev_tile_glob()),
            desc="Stitching gpkg files",
        ):
            gdf = gpd.read_file(filepath)
            dgdf = dgpd.from_geopandas(gdf, npartitions=1)
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
        partitions = num_rows // _CHUNKSIZE + 1
        print(
            f"# ROWS: {num_rows}"
            f"\tCHUNKSIZE: {_CHUNKSIZE}"
            f"\t# PARTITIONS: {partitions}"
        )
        union_dgdf = union_dgdf.dissolve(
            self._label_name,
            split_out=partitions
            #sort=True,
        )
        to_file(union_dgdf, self._output_file)

    def geopolygonize(self) -> None:
        """
        Geopolygonize input to get output.
        """

        pipeline = Pipeline(
            all_step_parameters=[
                StepParameters(
                    name="input",
                    function=self._input_tile,
                    file_extension="npy",
                ),
                StepParameters(
                    name="clean",
                    function=self._clean_tile,
                    file_extension="npy",
                ),
                StepParameters(
                    name="polygonize",
                    function=self._polygonize_tile,
                    file_extension="gpkg",
                ),
                StepParameters(
                    name="vectorize",
                    function=self._vectorize_tile,
                    file_extension="gpkg",
                ),
            ],
            union_function=self._stitch,
            pipeline_parameters=PipelineParameters(
                endx=self._width,
                endy=self._height,
                tile_size=self._tile_size,
                num_processes=self._workers,
                work_dir=self._work_dir,
                log_dir=self._log_dir,
            )
        )
        pipeline.run()

        if self.cleanup:
            self._cleanup()
