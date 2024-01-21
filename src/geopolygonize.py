import click

from .geopolygonizer import GeoPolygonizer, GeoPolygonizerParams
from .utils.clean_exit import kill_self


@click.command(
    name="Geopolygonize",
    help="Convert a geographic raster input "
         "into an attractive gpkg file output."
)
@click.option(
    '--input-file',
    type=click.Path(file_okay=True, dir_okay=False),
    help="Input TIF file path",
    required=True,
)
@click.option(
    '--output-file',
    type=click.Path(file_okay=True, dir_okay=False),
    help="Output gpkg file path",
    required=True,
)
@click.option(
    '--label-name',
    default='label',
    type=str,
    help="The name of the attribute each pixel value represents.",
)
@click.option(
    '--pixel-size',
    default=0.0,
    type=float,
    help="Override on the size of each pixel in units of the "
         "input file's coordinate reference system.",
)
@click.option(
    "--simplification-pixel-window",
    default=1,
    type=float,
    help="The amount of simplification applied relative to the pixel size."
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
    default=1000,
    type=int,
    help="Tile size in pixels",
)
@click.option(
    '--debug',
    is_flag=True,
    help="enable debug mode"
)
def cli(
    input_file,
    output_file,
    pixel_size,
    simplification_pixel_window,
    smoothing_iterations,
    label_name,
    tile_size,
    debug,
):
    try:
        params = GeoPolygonizerParams(
            input_file=input_file,
            output_file=output_file,
            label_name=label_name,
            pixel_size=pixel_size,
            simplification_pixel_window=simplification_pixel_window,
            smoothing_iterations=smoothing_iterations,
            tile_size=tile_size,
            debug=debug,
        )
        GeoPolygonizer(params).geopolygonize()
    except Exception as e:
        print(f"geopolygonize encountered error: {e}")
        kill_self()


if __name__ == '__main__':
    cli()
