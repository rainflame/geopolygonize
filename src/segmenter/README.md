# Segmenter

## Purpose

The `Segmenter` tool allows you to input a set of polygons,
perform some operation over their boundaries,
and retrieve the result of the operation such that the
polygons are returned in the same order as they were inputted and 
**wherever the input polygons share a boundary,
that boundary is preserved in the output**.

This is useful if you want to simplify or smooth the polygons and maintain
their cohesion. Your function will need to work over disjoint "segments"
of the polygon boundaries.

The function must respect the invariant that the start and end points of
each boundary-segment remain fixed after the operation.

## How to use

The following shows a scenario where you have a TIF file of geospatial data
representing elevation, and you want to output a nice-looking gpkg file
that shows tiers of elevation by every 1000 meters.

Read the TIF file.
```
with rasterio.open(elevation_tif_filepath) as src:
    data = src.read(1)
    transform = src.transform
```

Preprocess the data to bucket elevation in tiers of 1000 meters.
```
preprocessed_data = data // 1000 * 1000
```

Turn the raster into `Polygon`s.
```
shapes_gen = shapes(preprocessed_data, transform=transform)
polygons = [shape(s) for s, _v in shapes_gen]
elevation_tiers = [v for _s, v in shapes_gen]
```

Use the `Segmenter` to simplify and smoothen the boundaries of these tiers 
so that in the final gpkg file, they do not appear pixelated.
```
segmenter = Segmenter(polygons)
segmenter.run_per_segment(simplification_function)
segmenter.run_per_segment(smoothen_function)
modified_polygons = segmenter.get_result()
```

Output the result into a gpkg file.
```
gdf = gpd.GeoDataFrame(geometry=modified_polygons)
gdf['elevation_tier'] = elevation_tiers
gdf.to_file(elevation_gpkg_filepath)
```

## Method

The `Segmenter` returns the minimum set of mutually exclusive "segments" 
that in union are equal to the boundaries of the areas, hence its name.

It is possible to find this set in a more efficient way.
However, it's unclear if there is a significantly faster
way of doing this while also preserving information about _how_ the
segments compose the area boundaries.
