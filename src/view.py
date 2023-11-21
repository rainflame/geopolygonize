import click

import geopandas as gpd

from .utils.visualization import show_polygons


@click.command()
@click.option(
    '--file',
    default="data/temp/combined.shp",
    type=str,
    help='Shapefile to view',
)
@click.option(
    '--label-name',
    default="label",
    help='Name of the attribute storing the original pixel values',
)
def cli(file, label_name):
    gdf = gpd.read_file(file)

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
