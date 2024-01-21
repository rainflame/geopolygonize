from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Tuple

from affine import Affine
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.features import shapes
from shapely.affinity import translate
from shapely.geometry import shape, LineString, Polygon
import warnings

from .segmenter.segmenter import Segmenter
from .utils import checkers
from .utils.smoothing import chaikins_corner_cutting
from .utils.tiler import (
    PipelineParameters,
    TileData,
    StepParameters,
    TileParameters,
    create_config,
    get_dims,
    generate_input_tile_from_ndarray,
    generate_union_gdf,
    pipe,
)

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
            width, height = get_dims(src)
            self._width, self._height = width, height

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

    def _input(
        self,
        tile_parameters: TileParameters,
        get_prev_tile: Callable[[TileParameters], TileData],
        get_prev_region: Callable[[TileParameters], TileData],
        save_curr_tile: Callable[[TileParameters, TileData], None],
    ) -> None:
        generate_input_tile_from_ndarray(
            self._input_file,
            self._width,
            self._height,
        )(tile_parameters, get_prev_tile, get_prev_region, save_curr_tile)

    def _union(
        self,
        get_prev_tiles: Callable[
            [],
            Iterator[Tuple[TileParameters, TileData]]
        ],
    ) -> None:
        return generate_union_gdf(
            self._output_file,
            self._label_name,
        )(get_prev_tiles)

    def geopolygonize(self) -> None:
        """
        Geopolygonize input to get output.
        """

        pipeline_parameters = PipelineParameters(
            width=self._width,
            height=self._height,
            steps=[
                (
                    StepParameters(
                        name="input",
                        data_type=np.ndarray,
                    ),
                    self._input,
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
            union_function=self._union,
            tile_size=self._tile_size,
            debug=self._debug,
            independent=True,
        )
        config = create_config(pipeline_parameters)
        pipe(pipeline_parameters, config)
