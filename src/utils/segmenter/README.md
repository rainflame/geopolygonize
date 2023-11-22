# Segmenter

## Purpose

You have data that represents something, e.g. elevation, snowfall,
about a region such that there are areas that have the same value
(maybe after preprocessing). You want to modify the boundaries
of these areas in some way, maybe to make them look nicer.

The `Segmenter` tool allows you to perform some operation over the boundaries,
e.g. simplification, smoothing, such that once you rebuild the areas,
you get a set of `Polygon`s and their corresponding values (labels)
that remain mutually exclusive; in other words, these `Polygon`s
do not intersect and do not have gaps between them. 

## How to use

Get the `data` and associated `transform`.
Name what the values in `data` represent via `label_name`.
```
with rasterio.open(input_tif_filepath) as src:
    data = src.read(1)
    transform = src.transform
    label_name = 'your_label'
```


Use the `Segmenter` to modify the boundaries of areas with the same value/label. 
```
segmenter = Segmenter(data, transform)
segmenter.run_per_segment(per_segment_function)
segmenter.rebuild()
polygons, labels = segmenter.get_result()
```

Output the result into a shapefile.
```
gdf = gpd.GeoDataFrame(geometry=polygons)
gdf[label_name] = labels
gdf.to_file(output_shp_filepath)
```

## Method

The `Segmenter` returns the minimum set of mutually exclusive "segments" 
that in union are equal to the boundaries of the areas.

It is possible to find this set in a more efficient way.
However, it's unclear if there is a significantly faster
way of doing this while also preserving information about _how_ the
segments compose the area boundaries.
