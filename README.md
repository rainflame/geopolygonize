# Landcover tiles

Here we create vector landcover tiles from [USGS Landfire](https://landfire.gov/index.php) landcover classification. These are considerably more detailed than the landcover tiles you'll get from OpenStreetMap or the [National Land Cover Database](https://www.usgs.gov/centers/eros/science/national-land-cover-database). Landfire uses the [U.S. National Vegetation Classification System](https://usnvc.org/), and includes around 1,000 different vegetation classes.

## Install

You'll need `GDAL` and `pmtiles` installed on your machine to run these scripts.

Install the python dependencies:

```
pip install -r requirements.txt
```

If the GDAL python library isn't building, manually install it so the python version matches the version of GDAL that's installed on your system:

```
pip install GDAL==$(gdal-config --version)
```

## Download landcover data

Run this script to download raster data from Landfire for a particular bounding box to `data/sources/`:

```
python download_landcover_data.py --bbox='-124.566244,46.864746,-116.463504,41.991794'
```

## Convert raster data to vectors

The raster file represents each vegetation class as a different value in the first band. To turn the raster file a shape-file of `shapely.Polygon` vectors, run `demo.py`. This script will do the following:

1. Remove small blobs of each vegetation class from the raster file,
2. Vectorize the remaining blobs by using the [iterative end-point fit simplification algorithm](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) on their boundaries,
3. Output a shapefile of the vectors with the same CRS as the raster image.
