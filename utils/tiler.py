
import glob
import os
import multiprocessing  as mp
import sys
from tqdm import tqdm

import rasterio
import pandas as pd
import geopandas as gpd

utils_dir = os.path.dirname(__file__)
sys.path.append(utils_dir)
import visualization as viz


class TilerParameters:
    def __init__(
        self,
        temp_dir=os.path.join("data", "temp"),
        num_processes=1,
        debug=False,
        startx=0,
        starty=0,
        tile_size=100,
    ):
        self.temp_dir = temp_dir
        self.num_processes = num_processes

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

    @staticmethod
    def process_tile_wrapper(args):
        tile_args, process_tile, tiler_parameters, processer_parameters = args
        if tiler_parameters.debug:
            print(f"Tile args: {tile_args}")
        process_tile(tile_args, tiler_parameters, processer_parameters)
        if tiler_parameters.debug:
            print()

    def process_tiles(self, all_tile_args):
        tp = self.tiler_parameters
        all_args = [
            (tile_args, self.process_tile, self.tiler_parameters, self.processer_parameters)
            for tile_args in all_tile_args
        ]
        with mp.Pool(processes=tp.num_processes) as pool:
            for _ in tqdm(pool.imap_unordered(self.process_tile_wrapper, all_args), total=len(all_args), desc="Processing tiles"):
                pass
            
    def stitch_tiles(self):
        tp = self.tiler_parameters
        all_gdfs = []
        for filepath in tqdm(glob.glob(os.path.join(tp.temp_dir, "*.shp")), desc="Stitching tiles"):
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