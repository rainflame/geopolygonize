import click

import geopandas as gpd
import rasterio

from visualization import (
    get_show_config,
    save_polygons,
    show_polygons,
    show_raster
)


@click.command('view the geometry of a file')
@click.option(
    '-t',
    '--tiffile',
    type=str,
    help='TIF file to view',
)
@click.option(
    '-g',
    '--gpkgfile',
    type=str,
    help='Geopackage to view',
)
@click.option(
    '-l',
    '--label-name',
    default="label",
    help='Name of the attribute storing the original pixel values',
)
@click.option(
    '-o',
    '--output-image-path',
    default=None,
    help='IMG path to save image to. Only applies to gpkg files.',
)
@click.option(
    '--dpi',
    default=324,
    help='DPI of the image to be saved.',
)

def cli(tiffile, gpkgfile, label_name, output_image_path, dpi):
    if tiffile is not None:
        with rasterio.open(tiffile) as src:
            data = src.read(1)
            cmap, min_value, max_value = get_show_config(data)
            show_raster(data, cmap, min_value, max_value)
    elif gpkgfile is not None:
        gdf = gpd.read_file(gpkgfile)

        polygons = []
        labels = []
        for shape, label in zip(gdf.geometry, gdf[label_name]):
            if shape.geom_type == "MultiPolygon":
                shapes = shape.geoms
                polygons.extend(shapes)
                labels.extend([label] * len(shapes))
            else:
                polygons.append(shape)
                labels.append(label)

        if output_image_path is None:
            show_polygons(polygons, labels=labels)
        else:
            save_polygons(output_image_path, polygons, dpi=dpi, labels=labels)


if __name__ == '__main__':
    cli()
