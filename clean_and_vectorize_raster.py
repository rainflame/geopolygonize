import os
import glob
import click
import multiprocessing
import warnings

from processing import process_tile, VectorizerParameters
from utils.tiler import Tiler, TilerParameters

warnings.filterwarnings("ignore", category=RuntimeWarning) 

@click.command()
@click.option('--input-file', required=True, help='Input tiff file')
@click.option('--output-file', required=True, help='Output shapefile')
@click.option('--min-blob-size', default=30, help='The minimum number of pixels with the same value. Blobs smaller than this will be filtered out and replaced.')
@click.option('--meters-per-pixel', default=30, help='The pixel size in meters')
@click.option('--tile-size', default=200, help='Tile size in pixels')
@click.option('--workers', default=multiprocessing.cpu_count(), help='Number of processes to spawn to process tiles in parallel')
@click.option('--debug', is_flag=True, help='Debug mode')
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
    
    # if there's a data/temp directory, delete it and start over
    if os.path.exists('data/temp'):
        os.system('rm -rf data/temp')
    os.makedirs('data/temp', exist_ok=True)

    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        raise ValueError(f'Output directory does not exist: {output_dir}')

    parameters = VectorizerParameters(
        min_blob_size=min_blob_size,
        meters_per_pixel=meters_per_pixel,
    )
    tiler_parameters = TilerParameters(
        num_processes=workers,
        tile_size=tile_size,
        temp_dir='data/temp',
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


if __name__ == '__main__':
    cli()