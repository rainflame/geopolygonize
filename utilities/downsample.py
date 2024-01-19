import click

import rasterio
from rasterio.enums import Resampling


@click.command('reduce resolution of the TIF file')
@click.option(
    '-i',
    '--input-path',
    required=True,
    type=str,
    help='TIF input file path',
)
@click.option(
    '-o',
    '--output-path',
    required=True,
    type=str,
    help='TIF output file path',
)
@click.option(
    '-r',
    '--resolution',
    default=1.0,
    help='Float in range (0.0, 1.0] to reduce resolution of TIF to.',
)
def cli(
    input_path,
    output_path,
    resolution,
):
    with rasterio.open(input_path) as src:
        new_height = int(src.height * resolution)
        new_width = int(src.width * resolution)

        data = src.read(
            out_shape=(src.count, new_height, new_width),
            resampling=Resampling.mode # select pixel that appears most often
        )

        transform = src.transform * src.transform.scale(
            (src.width / new_width),
            (src.height / new_height),
        )

        profile = src.profile.copy()
        profile.update({
            'transform': transform,
            'height': new_height,
            'width': new_width
        })

        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(data)


if __name__ == '__main__':
    cli()
