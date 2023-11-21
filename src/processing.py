import os
import sys

from shapely.geometry import LineString
from shapely.affinity import translate
import geopandas as gpd
import rasterio

from .utils.smoothing import chaikins_corner_cutting
from .utils.blobifier import blobify
from .utils.segmenter.segmenter import Segmenter


class VectorizerParameters:
    def __init__(
        self,
        input_filepath,
        label_name='label',
        min_blob_size=5,
        pixel_size=0,
        simplification_pixel_window=1,
        smoothing_iterations=0,
    ):
        self.min_blob_size = min_blob_size
        self.pixel_size = pixel_size
        self.simplification_pixel_window = simplification_pixel_window
        self.smoothing_iterations = smoothing_iterations

        self.label_name = label_name
        with rasterio.open(input_filepath) as src:
            self.meta = src.meta
            self.crs = self.meta['crs']
            self.transform = src.transform
            self.data = src.read(1)
            self.res = src.res


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

    pixel_size = parameters.pixel_size
    # get the resolution from the input file if the user hasn't specified one
    if pixel_size == 0:
        pixel_size = abs(parameters.res[0])
        parameters.pixel_size = pixel_size
        
    simplify = generate_simplify_func(
        parameters.pixel_size,
        parameters.simplification_pixel_window,
    )
    smooth = generate_smoothing_func(
        parameters.smoothing_iterations
    )
    segmenter = Segmenter(
        tile,
        parameters.transform,
    )

    segmenter.run_per_segment(simplify)
    segmenter.run_per_segment(smooth)
    segmenter.rebuild()
    simplified_polygons, labels = segmenter.get_result()

    gdf = gpd.GeoDataFrame(geometry=simplified_polygons)
    gdf[parameters.label_name] = labels
    return gdf


def process_tile(tile_constraints, tiler_parameters, parameters):
    start_x, start_y, width, height = tile_constraints

    buffer = parameters.min_blob_size - 1
    bx0 = max(start_x-buffer, 0)
    by0 = max(start_y-buffer, 0)
    bx1 = min(start_x+width+buffer, tiler_parameters.endx)
    by1 = min(start_y+height+buffer, tiler_parameters.endy)

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
    gdf.to_file(os.path.join(
        tiler_parameters.temp_dir,
        f"tile-{start_x}-{start_y}.shp",
    ))
    return gdf
