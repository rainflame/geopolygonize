from dataclasses import dataclass
from tqdm import tqdm
from typing import Any, Callable, Dict, Iterator, List

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

from .blobifier import Blobifier
from .segmenter.segmenter import Segmenter
from .utils import checkers
from .utils.io import to_file
from .utils.smoothing import chaikins_corner_cutting
from .utils.tiler import (
    Pipeline,
    PipelineParameters,
    TileData,
    StepParameters,
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
    debug: bool = False
    """enable debug mode"""


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

        self._debug = params.debug

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
        _get_prev_tile: Callable[[TileParameters], TileData],
        _get_prev_region: Callable[[TileParameters], TileData],
        save_curr_tile: Callable[[TileParameters, TileData], None],
    ) -> None:
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
            save_curr_tile(tile_parameters, tile)

    def _clean_tile(
        self,
        tile_parameters: TileParameters,
        _get_prev_tile: Callable[[TileParameters], TileData],
        get_prev_region: Callable[[TileParameters], TileData],
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
        buffered_region = get_prev_region(region_parameters)
        if buffered_region is None:
            return

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

    def _polygonize_tile(
        self,
        tile_parameters: TileParameters,
        get_prev_tile: Callable[[TileParameters], TileData],
        _get_prev_region: Callable[[TileParameters], TileData],
        save_curr_tile: Callable[[TileParameters, TileData], None],
    ) -> None:
        prev_tile = get_prev_tile(tile_parameters)
        if prev_tile is None:
            return
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
        save_curr_tile(tile_parameters, gdf)

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
        get_prev_tile: Callable[[TileParameters], TileData],
        _get_prev_region: Callable[[TileParameters], TileData],
        save_curr_tile: Callable[[TileParameters, TileData], None],
    ) -> None:
        prev_tile = get_prev_tile(tile_parameters)
        assert isinstance(prev_tile, gpd.GeoDataFrame)
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
        save_curr_tile(tile_parameters, gdf)

    def _stitch(
        self,
        get_prev_tiles: Callable[[], Iterator[TileData]],
    ) -> gpd.GeoDataFrame:
        union_dgdf = dgpd.from_geopandas(
            gpd.GeoDataFrame(),
            chunksize=_CHUNKSIZE
        )
        for prev_tile in tqdm(
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
                (
                    StepParameters(
                        name="input",
                        data_type=np.ndarray,
                    ),
                    self._input_tile,
                ),
                (
                    StepParameters(
                        name="clean",
                        data_type=np.ndarray,
                    ),
                    self._clean_tile,
                ),
                (
                    StepParameters(
                        name="polygonize",
                        data_type=gpd.GeoDataFrame,
                    ),
                    self._polygonize_tile,
                ),
                (
                    StepParameters(
                        name="vectorize",
                        data_type=gpd.GeoDataFrame,
                    ),
                    self._vectorize_tile,
                ),
            ],
            union_function=self._stitch,
            pipeline_parameters=PipelineParameters(
                endx=self._width,
                endy=self._height,
                tile_size=self._tile_size,
                debug=self._debug,
            )
        )
        pipeline.run()
