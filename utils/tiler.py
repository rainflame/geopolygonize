
import glob
import os
import sys

import rasterio
import pandas as pd
import geopandas as gpd

utils_dir = os.path.dirname(__file__)
sys.path.append(utils_dir)
import visualization as viz


class TilerParameters:
    def __init__(
        self,
        temp_dir=os.path.join("data", "intermediates"),
        debug=False,
        startx=0,
        starty=0,
        tile_size=100,
    ):
        self.temp_dir = temp_dir

        self.tile_size = tile_size
        self.startx = startx
        self.starty = starty

        self.debug = debug

    def set_data_parameters(
        self, 
        meta,
        transform,
        data,
    ):
        self.meta = meta 
        self.crs = self.meta['crs']
        self.transform = transform 
        self.data = data

        self.endx = data.shape[0]
        self.endy = data.shape[1]

        self.render_raster_config = viz.get_show_config(data)

class Tiler:
    def __init__(
        self,
        input_filepath,
        output_filepath,
        tiler_parameters,
        process_tile,
        processer_parameters,
    ):
        self.input_filepath = input_filepath
        self.output_filepath = output_filepath

        self.tiler_parameters = tiler_parameters
        self.process_tile = process_tile
        self.processer_parameters = processer_parameters

        with rasterio.open(self.input_filepath) as src:
            meta = src.meta
            transform = src.transform
            data = src.read(1)
            tiler_parameters.set_data_parameters(meta, transform, data)

    def generate_tiles(self):
        tp = self.tiler_parameters
        all_tile_args = [
            (x, y, tp.tile_size, tp.tile_size)
            for x in range(tp.startx, tp.endx, tp.tile_size)
            for y in range(tp.starty, tp.endy, tp.tile_size)
        ]
        return all_tile_args

    # TODO: This is parallelizable.
    def process_tiles(self, all_tile_args):
        tp = self.tiler_parameters
        for tile_args in all_tile_args:
            if tp.debug:
                print(f"Tile args: {tile_args}")
            self.process_tile(tile_args, self.tiler_parameters, self.processer_parameters)
            if tp.debug:
                print()

    def stitch_tiles(self):
        tp = self.tiler_parameters
        all_gdfs = []
        for filepath in glob.glob(os.path.join(tp.temp_dir, "*.shp")):
            gdf = gpd.read_file(filepath)
            all_gdfs.append(gdf)
        output_gdf = pd.concat(all_gdfs)
        output_gdf.to_file(self.output_filepath)
        return all_gdfs

    def process(self):
        tp = self.tiler_parameters
        if tp.debug:
            viz.show_raster(tp.data, *tp.render_raster_config)
        all_tile_args = self.generate_tiles()
        self.process_tiles(all_tile_args)
        self.stitch_tiles()