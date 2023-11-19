import os
import glob
import click
import multiprocessing
import warnings
import tempfile
import shutil

from .processing import process_tile, VectorizerParameters
from .utils.tiler import Tiler, TilerParameters

warnings.filterwarnings("ignore", category=RuntimeWarning)


@click.command(
    name="Geopolygonize",
    help="Convert a geographic raster file into simplified polygons"
)
@click.option(
    '--input-file',
    type=click.Path(file_okay=True, dir_okay=False),
    help='Input tif file',
    required=True,
)
@click.option(
    '--output-file',
    type=click.Path(file_okay=True, dir_okay=False),
    help='Output shapefile',
    required=True,
)
@click.option(
    '--min-blob-size',
    default=30,
    help='The minimum number of pixels with the same value. ' + \
    'Blobs smaller than this will be filtered out and replaced'
)
@click.option(
    '--meters-per-pixel',
    default=30,
    help='The pixel size in meters',
)
@click.option(
    '--tile-size',
    default=200,
    help='Tile size in pixels',
)
@click.option(
    '--workers',
    default=multiprocessing.cpu_count(),
    help='Number of processes to spawn to process tiles in parallel'
)
@click.option(
    '--debug',
    is_flag=True, help='Debug mode',
)
def cli(
    input_file,
    output_file,
    min_blob_size,
    meters_per_pixel,
    workers,
    tile_size,
    debug,
):
    inputs = glob.glob(input_file)
    if len(inputs) >= 1:
        input_file = inputs[0]
    else:
        raise ValueError(f'Input file does not exist: {input_file}')

    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        raise ValueError(f'Output directory does not exist: {output_dir}')
    
    # create a temp dir that we can destroy when done
    temp_dir = tempfile.mkdtemp()

    parameters = VectorizerParameters(
        min_blob_size=min_blob_size,
        meters_per_pixel=meters_per_pixel,
    )
    tiler_parameters = TilerParameters(
        num_processes=workers,
        tile_size=tile_size,
        temp_dir=temp_dir,
        debug=debug,
    )
    rz = Tiler(
        input_filepath=input_file,
        output_filepath=output_file,
        tiler_parameters=tiler_parameters,
        process_tile=process_tile,
        processer_parameters=parameters,
    )
    rz.process()

    shutil.rmtree(temp_dir)


if __name__ == '__main__':
    cli()
