# Geopolygonize

Convert geographic rasters into simplified polygons. Given an input raster file, this tool produces a shapefile representation of the raster that simplifies out pixelation. It also maintains shapes' relations to one another such that the output is guaranteed to have no gaps.

#### Algorithm

Most existing methods for polygon simplification such as the [Douglas–Peucker simplification algorithm](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) or [concave hulls](http://lin-ear-th-inking.blogspot.com/2022/04/outer-and-inner-concave-polygon-hulls.html) operate on a single polygon at a time. This presents a problem when run on a collection of polygons that fit together perfectly–simplifying each polygon separately will introduce unpredictable gaps. Our algorithm takes an approach similar to [TopoJSON](https://github.com/topojson/topojson). It identifies the boundaries shared between polygons, simplifies those boundaries, then assigns the simplified boundaries back to the polygons. This results in simplified polygons that fit perfectly together without any gaps.

## Install

```
pip install geopolygonize
```

## Quickstart

To convert a raster to simplified polygons, run:

```
geopolygonize --input-file="data/input.tif" --output-file="data/output.shp"
```

## CLI Options

### `--min-blob-size`

Optional raster preprocessing step to remove pixels that are not connected to neighboring pixels with the same value. This value dictates the minimum number of pixels of the same value each must be connected to in order to be kept. Pixels in blobs smaller than this value will be removed and filled with the most common pixel value surrounding it.

### `--tile-size`

The polygonization process can be run in parallel to speed up the computation. To prepare to process in parallel, the raster is cut into square tiles of this number of pixels.

### `--meters-per-pixel`

Specify the pixel size in meters. This is used for determining a sensible simplification tolerance.

### `--simplification-pixel-window`

The amount of simplification applied relative to the pixel size. The higher the number, the more simplified the output. For example, with a pixel size of 30 meters and a simplification pixel window of 2, the output polygons will be simplified by 60 meters.

### `--smoothing-iterations`

The number of iterations of smoothing to run on the output polygons. We use [Chaikin's corner cutting algorithm](http://graphics.cs.ucdavis.edu/education/CAGDNotes/Chaikins-Algorithm.pdf) for smoothing.

### `--workers`

Number of workers that should be spawned to process tiles in parallel.

## Development

Install the requirements:

```
pip install -r requirements.txt
```

Then run the CLI:

```
python -m src.geopolygonize --input-file...
```

Find test raster inputs [here](https://drive.google.com/drive/folders/1KiEPwjg9zhowBJEODQTJJ44VPrPkXC3_?usp=drive_link).

\# TODO: API docs
