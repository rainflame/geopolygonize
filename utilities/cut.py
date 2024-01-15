import click

import rasterio


@click.command('cut a region of a TIF file into a new TIF file')
@click.option(
    '-i',
    '--input-path',
    required=True,
    type=str,
    help='TIF file path to cut',
)
@click.option(
    '-o',
    '--output-path',
    required=True,
    type=str,
    help='TIF output file path',
)
@click.option(
    '-c',
    '--start-col',
    required=True,
    type=int,
    help='Column index to start the cut region',
)
@click.option(
    '-r',
    '--start-row',
    required=True,
    type=int,
    help='Row index to start the cut region',
)
@click.option(
    '-w',
    '--width',
    required=True,
    type=int,
    help='Width of the cut region',
)
@click.option(
    '-h',
    '--height',
    required=True,
    type=int,
    help='Height of the cut region',
)
def cli(
    input_path,
    output_path,
    start_col,
    start_row,
    width,
    height,
):
    with rasterio.open(input_path) as src:
        window = rasterio.windows.Window(start_col, start_row, width, height)
        data = src.read(window=window)

        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update({
            'transform': transform,
            'height': height,
            'width': width
        })

        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(data)


if __name__ == '__main__':
    cli()

