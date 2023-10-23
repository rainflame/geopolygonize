import rasterio
import geopandas as gpd

import os
import sys

vectorizer_dir = os.path.dirname(__file__)
sys.path.append(vectorizer_dir)
import cover_computer as cc
import loop_computer as lc
import oriented_potential_computer as opc


class VectorBuilder:
    def __init__(self, raster_filepath):
        self.raster_filepath = raster_filepath
        self.get_data_and_transform()
        self.build()

    def get_data_and_transform(self):
        with rasterio.open(self.raster_filepath,) as src:
            self.meta = src.meta
            self.data = src.read(1)
            self.transform = src.transform

        #self.data = self.data[10:60, 60:120]

    def build(self):
        self.covers = cc.build(self.data, self.transform)
        self.loops = lc.build(self.covers)
        self.oriented_potentials = opc.build(self.loops)

    def run_per_segment(self, per_segment_function):
        opc.update(self.oriented_potentials, per_segment_function)
    
    def rebuild(self):
        opc.rebuild(self.loops, self.oriented_potentials)
        lc.rebuild(self.loops)
        cc.rebuild(self.covers, self.loops)

    def save(self, output_filepath):
        modified_polygons = [c.modified_polygon for c in self.covers]
        labels = [c.label for c in self.covers]
        crs = self.meta['crs']

        gdf = gpd.GeoDataFrame(geometry=modified_polygons)
        gdf['label'] = labels
        gdf.crs = crs
        gdf.to_file(output_filepath)