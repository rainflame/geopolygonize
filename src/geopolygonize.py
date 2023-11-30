import click

from .geopolygonizer import GeoPolygonizer


@click.command(
    name="Geopolygonize",
    help="Convert a geographic raster file into simplified polygons",
)
@click.option(
    '--input-file',
    type=click.Path(file_okay=True, dir_okay=False),
    help="Input tif file",
    required=True,
)
@click.option(
    '--output-file',
    type=click.Path(file_okay=True, dir_okay=False),
    help="Output shapefile",
    required=True,
)
@click.option(
    '--min-blob-size',
    default=30,
    type=int,
    help="The minimum number of pixels with the same value. "
         "Blobs smaller than this will be filtered out and replaced.",
)
@click.option(
    '--pixel-size',
    default=0.0,
    type=float,
    help="Override the size of the pixels in units of the "
         "input file's coordinate reference system.",
)
@click.option(
    "--simplification-pixel-window",
    default=1,
    type=float,
    help="The amount of simplification applied relative to the pixel size. "
         "The higher the number, the more simplified the output. "
         "For example, with a pixel size of 30 meters and a simplification "
         "of 2, the output will be simplified by 60 meters.",
)
@click.option(
    "--smoothing-iterations",
    default=0,
    type=int,
    help="The number of iterations of smoothing to run on the "
         "output polygons.",
)
@click.option(
    '--tile-size',
    default=200,
    type=int,
    help="Tile size in pixels",
)
@click.option(
    '--label-name',
    default='label',
    type=str,
    help="The name of the attribute to store the original "
         "pixel value in the output.",
)
@click.option(
    '--workers',
    default=0,  # standard for use all cpus
    type=int,
    help="Number of processes to spawn to process tiles in parallel. "
         "Use 0 if you want to use all available CPUs."
)
def cli(
    input_file,
    output_file,
    min_blob_size,
    pixel_size,
    simplification_pixel_window,
    smoothing_iterations,
    label_name,
    workers,
    tile_size,
):
    geopolygonizer = GeoPolygonizer(
        input_file=input_file,
        output_file=output_file,
        min_blob_size=min_blob_size,
        pixel_size=pixel_size,
        simplification_pixel_window=simplification_pixel_window,
        smoothing_iterations=smoothing_iterations,
        label_name=label_name,
        workers=workers,
        tile_size=tile_size,
    )
    geopolygonizer.run()


if __name__ == '__main__':
    cli()
