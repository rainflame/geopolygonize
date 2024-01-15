import click

import geopandas as gpd
import rasterio

from visualization import get_show_config, show_polygons, show_raster


@click.command()
@click.option(
    '--tiffile',
    type=str,
    help='TIF file to view',
)
@click.option(
    '--gpkgfile',
    type=str,
    help='Geopackage to view',
)
@click.option(
    '--label-name',
    default="label",
    help='Name of the attribute storing the original pixel values',
)
def cli(tiffile, gpkgfile, label_name):
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

        show_polygons(polygons, labels)


if __name__ == '__main__':
    cli()
