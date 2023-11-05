import os

from shapely.geometry import LineString
from shapely.affinity import translate
import geopandas as gpd

from simplification.cutil import simplify_coords

import utils.visualization as viz
from utils.blobifier import blobify
from utils.vectorizer.vector_builder import VectorBuilder


class VectorizerParameters:
    def __init__(
        self,
        min_blob_size=5,
        meters_per_pixel=1,
        simplification_pixel_window=1,
    ):
        self.min_blob_size = min_blob_size
        self.meters_per_pixel = meters_per_pixel
        self.simplification_pixel_window = simplification_pixel_window

def clean(tile, tiler_parameters, parameters):
    cleaned = blobify(tile, parameters.min_blob_size, tiler_parameters.debug)
    if tiler_parameters.debug:
        viz.show_raster(cleaned, *tiler_parameters.render_raster_config)
    return cleaned

def generate_simplify_func(meters_per_pixel, simplification_pixel_window):
    tolerance = meters_per_pixel * simplification_pixel_window
    def simplify(segment):
        # Simplification will turn rings into what are effectively points.
        # We cut the ring in half to provide simplification with non-ring segments instead.
        if segment.is_ring:
            assert len(segment.coords) >= 3
            midpoint_idx = len(segment.coords) // 2
            segment1 = LineString(segment.coords[:midpoint_idx+1])
            segment2 = LineString(segment.coords[midpoint_idx:])
            simplified_coords1 = simplify_coords(segment1.coords, tolerance)
            simplified_coords2 = simplify_coords(segment2.coords, tolerance)
            simplified = LineString(simplified_coords1[:-1] + simplified_coords2)
        else:
            simplified_coords = simplify_coords(segment.coords, tolerance)
            simplified = LineString(simplified_coords)
        return simplified
    return simplify

def vectorize(tile, tiler_parameters, parameters):
    simplify = generate_simplify_func(parameters.meters_per_pixel, parameters.simplification_pixel_window)
    vector_builder = VectorBuilder(tile, tiler_parameters.transform, tiler_parameters.debug)
    vector_builder.run_per_segment(simplify)
    vector_builder.rebuild()
    simplified_polygons, labels = vector_builder.get_result()

    if tiler_parameters.debug:
        cmap = viz.generate_color_map(labels)
        viz.show_polygons(simplified_polygons, labels, color_map=cmap)
    
    gdf = gpd.GeoDataFrame(geometry=simplified_polygons)
    gdf['label'] = labels
    return gdf

def process_tile(tile_constraints, tiler_parameters, parameters):
    start_x, start_y, width, height = tile_constraints

    buffer = parameters.min_blob_size - 1
    bx0 = max(start_x-buffer, 0)
    by0 = max(start_y-buffer, 0)
    bx1 = min(bx0+width+2*buffer, tiler_parameters.endx)
    by1 = min(by0+height+2*buffer, tiler_parameters.endy)

    if bx1 - bx0 <= 2 * buffer or by1 - by0 <= 2 * buffer:
        return gpd.GeoDataFrame()

    tile_raster = tiler_parameters.data[bx0:bx1, by0:by1]
    cleaned = clean(tile_raster, tiler_parameters, parameters)
    unbuffered = cleaned[buffer:-buffer, buffer:-buffer]
    gdf = vectorize(
        unbuffered,
        tiler_parameters,
        parameters,
    )

    # in physical space, x and y are reversed
    shift_x = (by0 + buffer) * parameters.meters_per_pixel
    shift_y = -((bx0 + buffer) * parameters.meters_per_pixel)
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: translate(geom, xoff=shift_x, yoff=shift_y))
    gdf.crs = tiler_parameters.crs
    gdf.to_file(os.path.join(tiler_parameters.temp_dir, f"tile-{start_x}-{start_y}.shp"))
    return gdf
