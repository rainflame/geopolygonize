from affine import Affine
import geopandas as gpd
import numpy as np
from rasterio.crs import CRS
from rasterio.features import shapes
from shapely.affinity import translate
from shapely.geometry import shape, LineString, Polygon
from typing import Any, Callable, Dict, List

from .utils.smoothing import chaikins_corner_cutting
from .utils.blobifier import Blobifier
from .utils.segmenter.segmenter import Segmenter


class GeoPolygonizer:
    def __init__(
        self,
        data: np.ndarray,
        meta: Dict[str, Any],
        crs: CRS,
        transform: Affine,
        label_name: str = 'label',
        min_blob_size: int = 5,
        pixel_size: int = 0,
        simplification_pixel_window: int = 1,
        smoothing_iterations: int = 0,
    ):
        self.data = data
        self.meta = meta
        self.crs = crs
        self.transform = transform
        self.label_name = label_name
        self.min_blob_size = min_blob_size
        self.pixel_size = pixel_size
        self.simplification_pixel_window = simplification_pixel_window
        self.smoothing_iterations = smoothing_iterations

    def _clean(self, tile: np.ndarray) -> np.ndarray:
        blobifier = Blobifier(tile, self.min_blob_size)
        cleaned = blobifier.blobify()
        return cleaned

    def _generate_smoothing_func(self) -> Callable[[LineString], LineString]:
        def smooth(segment: LineString) -> LineString:
            coords = chaikins_corner_cutting(
                segment.coords,
                self.smoothing_iterations
            )
            return LineString(coords)

        return smooth

    def _generate_simplify_func(self) -> Callable[[LineString], LineString]:
        tolerance = self.pixel_size * self.simplification_pixel_window

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
        shapes_gen = shapes(tile, transform=self.transform)
        polygons_and_labels = list(zip(*shapes_gen))
        polygons: List[Polygon] = [shape(s) for s in polygons_and_labels[0]]
        labels: List[Any] = [v for v in polygons_and_labels[1]]

        segmenter = Segmenter(polygons)

        segmenter.run_per_segment(self._generate_simplify_func())
        segmenter.run_per_segment(self._generate_smoothing_func())
        modified_polygons = segmenter.get_result()

        gdf = gpd.GeoDataFrame(geometry=modified_polygons)
        gdf[self.label_name] = labels
        return gdf

    def process_tile(self, tile_parameters, tiler_parameters):
        buffer = self.min_blob_size - 1

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
            empty.set_geometry("geometry")
            return empty

        tile_raster = self.data[bx0:bx1, by0:by1]
        cleaned = self._clean(tile_raster)

        rel_start_x = tile_parameters.start_x - bx0
        rel_start_y = tile_parameters.start_y - by0
        rel_end_x = min(rel_start_x + tile_parameters.width, bx1)
        rel_end_y = min(rel_start_y + tile_parameters.height, by1)

        unbuffered = cleaned[rel_start_x:rel_end_x, rel_start_y:rel_end_y]
        gdf = self._vectorize(unbuffered)

        # in physical space, x and y are reversed
        shift_x = tile_parameters.start_y * self.pixel_size
        shift_y = -(tile_parameters.start_x * self.pixel_size)
        gdf['geometry'] = gdf['geometry'].apply(
            lambda geom: translate(geom, xoff=shift_x, yoff=shift_y)
        )
        gdf.crs = self.crs
        return gdf
