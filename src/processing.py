from dataclasses import dataclass

from affine import Affine
import geopandas as gpd
import numpy as np
from rasterio.crs import CRS
from rasterio.features import shapes
from shapely.affinity import translate
from shapely.geometry import shape, LineString
from typing import Dict

from .utils.smoothing import chaikins_corner_cutting
from .utils.blobifier import blobify
from .utils.segmenter.segmenter import Segmenter


@dataclass
class GeoPolygonizerParameters:
    data: np.ndarray
    meta: Dict[str, object]
    crs: CRS
    transform: Affine
    label_name: str = 'label'
    min_blob_size: int = 5
    pixel_size: int = 0
    simplification_pixel_window: int = 1
    smoothing_iterations: int = 0


def clean(tile, parameters):
    cleaned = blobify(tile, parameters.min_blob_size)
    return cleaned


def generate_smoothing_func(iterations):
    def smooth(segment):
        coords = chaikins_corner_cutting(segment.coords, iterations)
        return LineString(coords)
    return smooth


def generate_simplify_func(pixel_size, simplification_pixel_window):
    tolerance = pixel_size * simplification_pixel_window

    def simplify(segment):
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
            coords = list(simplified1.coords)[:-1] + list(simplified2.coords)
            simplified = LineString(coords)
        else:
            simplified = segment.simplify(tolerance)
        return simplified
    return simplify


def vectorize(tile, parameters):
    simplify = generate_simplify_func(
        parameters.pixel_size,
        parameters.simplification_pixel_window,
    )
    smooth = generate_smoothing_func(
        parameters.smoothing_iterations
    )

    shapes_gen = shapes(tile, transform=parameters.transform)
    polygons_and_labels = list(zip(*[(shape(s), v) for s, v in shapes_gen]))
    polygons = polygons_and_labels[0]
    labels = polygons_and_labels[1]

    segmenter = Segmenter(polygons)

    segmenter.run_per_segment(simplify)
    segmenter.run_per_segment(smooth)
    modified_polygons = segmenter.get_result()

    gdf = gpd.GeoDataFrame(geometry=modified_polygons)
    gdf[parameters.label_name] = labels
    return gdf


def process_tile(tile_parameters, tiler_parameters, parameters):
    buffer = parameters.min_blob_size - 1
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
        return gpd.GeoDataFrame()

    tile_raster = parameters.data[bx0:bx1, by0:by1]
    cleaned = clean(tile_raster, parameters)
    unbuffered = cleaned[buffer:-buffer, buffer:-buffer]
    gdf = vectorize(
        unbuffered,
        parameters,
    )

    # in physical space, x and y are reversed
    shift_x = (by0 + buffer) * parameters.pixel_size
    shift_y = -((bx0 + buffer) * parameters.pixel_size)
    gdf['geometry'] = gdf['geometry'].apply(
        lambda geom: translate(geom, xoff=shift_x, yoff=shift_y)
    )
    gdf.crs = parameters.crs
    return gdf
