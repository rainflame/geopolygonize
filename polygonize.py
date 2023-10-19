import glob
import os
import click 
import multiprocessing

from tqdm import tqdm
from shapely.geometry import Polygon, MultiPolygon
from shapely.wkb import loads
from osgeo import gdal, ogr, osr

from utils.simplification import chaikins_corner_cutting

gdal.UseExceptions()

@click.command()
@click.option("--simplification", default=40, help="Simplification factor")
@click.option("--smoothing", default=5, help="Number of smoothing iterations")
@click.option("--workers", default=4, help="Number of workers to use")
def cli(simplification, smoothing, workers):

    # delete everythin in data/temp except for .tif files 
    temp_files = glob.glob("data/temp/*")
    for file in temp_files:
        if file.split(".")[-1] != "tif":
            os.remove(file)

    files = glob.glob("data/temp/*.tif")
    inputs = [(file, simplification, smoothing) for file in files]

    print("Polygonizing and simplifying rasters...")
    # use multiprocessing to create the layers, reporting progress with tqdm
    with multiprocessing.Pool(processes=workers) as pool:
        for _ in tqdm(pool.imap_unordered(convert_and_simplify_raster, inputs), total=len(files)):
            pass
        pool.close()
        pool.join()
    
    print("Cleaning up...")
    # delete the temp datasets
    temp_files = glob.glob("data/temp/temp_*")
    for file in temp_files:
        os.remove(file)

    print("Merging shapefiles...")
    # merge all the shapefiles into one new shapefile data/temp/merged.shp
    merge_command = "ogrmerge.py -o data/temp/merged.shp data/temp/*.shp -single -overwrite_ds"
    os.system(merge_command)
    
    print("Done!")


def convert_and_simplify_raster(args):

    tif_path, simplification, smoothing = args
    classname = tif_path.split("/")[-1].split(".")[0]

    # use the original raster as geo reference 
    base_raster = gdal.Open(glob.glob("data/sources/*.tif")[0])
    raster_srs = osr.SpatialReference()
    raster_srs.ImportFromWkt(base_raster.GetProjection())

    # create shapefiles for polygonized output 
    temp_dataset = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource("data/temp/temp_{}.shp".format(classname))
    output_dataset = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource("data/temp/{}.shp".format(classname))

    # open the tif raster dataset
    raster_dataset = gdal.Open(tif_path)
    band = raster_dataset.GetRasterBand(1)
    band.SetNoDataValue(0)

    # layer to put the polygonized raster
    temp_layer = temp_dataset.CreateLayer(classname, geom_type=ogr.wkbPolygon, srs=raster_srs)
    temp_layer.CreateField(ogr.FieldDefn("class", ogr.OFTString))

    # layer to put the smoothed polygonized raster
    output_layer = output_dataset.CreateLayer(classname, geom_type=ogr.wkbPolygon, srs=raster_srs)
    output_layer.CreateField(ogr.FieldDefn("class", ogr.OFTString))
    
    # polygonize the raster band
    # the second argument is the mask band; we can use the same band since 0 is no-data and 1 is data
    gdal.Polygonize(band, band, temp_layer, -1, [], callback=None)

    # loop over the features, simplifying the geometry, then smoothing the result 
    while True:
        feature = temp_layer.GetNextFeature()
        if not feature:
            break
        geom = feature.GetGeometryRef()
        if not geom:
            continue

        geom = geom.Simplify(simplification)
        wkb = geom.ExportToWkb()
        wkb = bytes(wkb)
        polygon = loads(wkb)

        if polygon.is_valid:
            polygons = []
            smoothed_polygons = []

            # conver the multipolygon to invidual polygons
            if polygon.geom_type == "MultiPolygon":
                polygons = list(polygon.geoms)
            else:
                polygons = [polygon]

            for polygon in polygons:

                # smooth the interior coords with chaikin's alg
                smoothed_interior_coords = []
                for interior in polygon.interiors:
                    smoothed_interior = chaikins_corner_cutting(interior.coords, smoothing)
                    smoothed_interior_coords.append(smoothed_interior)
                
                # smooth the exterior coords with chaikin's alg 
                smoothed_exteriror_coords = chaikins_corner_cutting(polygon.exterior.coords, smoothing)

                # create the new polygon with exterior, interior coords 
                smoothed_poly = Polygon(smoothed_exteriror_coords, smoothed_interior_coords)
                smoothed_polygons.append(smoothed_poly)

            smoothed_polygon = None 

            if len(smoothed_polygons) > 1:
                smoothed_polygon = MultiPolygon(smoothed_polygons)
            else: 
                smoothed_polygon = smoothed_polygons[0]
        
            # convert back to ogr geometry
            geom = ogr.CreateGeometryFromWkb(smoothed_polygon.wkb)

        # add the new feature to the output layer
        featDef = ogr.Feature(temp_layer.GetLayerDefn())        
        featDef.SetField("class", classname)
        featDef.SetGeometry(geom)
        output_layer.CreateFeature(featDef)
        




if __name__ == "__main__":
    cli()
