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

Run this script to download data from Landfire for a particular bounding box to `data/sources/`:

```
python download_landcover_data.py --bbox='-124.566244,46.864746,-116.463504,41.991794'
```

## Convert raster data to vectors

### Split the raster into individual layers

The data is structured such that each vegetation class appears as a separate band in a single raster file. Next we'll split out the bands into their own files:

```
python split_raster.py
```

Now you should have a series of tif files like `/data/temp/012345.tif`. Each represents a vegetation class. The csv at `/data/sources/values.csv` contains the class names.

### Polygonize and simplify

Run the script to convert the rasters to polygons. Because each pixel of the raster is 30 meters these polygons will appear to have jagged edges. So we also need to simplify and smooth the polygons using the [Douglas-Peucker Algorithm](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) and [Chaikin’s Algorithm](http://graphics.cs.ucdavis.edu/education/CAGDNotes/Chaikins-Algorithm/Chaikins-Algorithm.html), respectively.

```
python polygonize.py --workers=8 --simplification=20 --smoothing=5
```

Adjust the number of workers to process more rasters in parallel.
