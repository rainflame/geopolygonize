# Geopolygonize

Convert geographic rasters into simplified polygons. Given an input raster file, this tool produces a shapefile representation of the raster that simplifies out pixelation. It also maintains shapes' relations to one another such that the output is guaranteed to have no gaps.

## Install

```
pip install geopolygonize
```

## Quickstart

To convert a raster to simplified polygons, run:

```
python geopolygonize.py --input-file="data/input.tif" --output-file="data/output.shp"
```

## Algorithm and options

Most existing methods for polygon simplification such as the [Douglas–Peucker simplification algorithm](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) or [concave hulls](http://lin-ear-th-inking.blogspot.com/2022/04/outer-and-inner-concave-polygon-hulls.html) operate on a single polygon at a time. This presents a problem when run on a collection of polygons that fit together perfectly–simplifying each polygon separately will introduce unpredictable gaps. Our algorithm takes an approach similar to [TopoJSON](https://github.com/topojson/topojson). It identifies the boundaries shared between polygons, simplifies those boundaries, then assigns the simplified boundaries back to the polygons. This results in simplified polygons that fit perfectly together without any gaps.

We also perform a cleanup step before converting to vectors that removes any isolated pixels of a particular value. This helps create a more visually cohesive albeit slightly less accurate output. You can specify the minimum size a collection of pixels must be to keep in the raster with `--min-blob-size`. Collections of pixels below this size will be stripped out and filled in with the pixels around them.

To speed up the computation, we first split the raster into tiles (whose size in pixels can be specified with `--tile-size` in the script), then process the tiles parallel. You can adjust the number of workers that are spawned with `--workers`.
