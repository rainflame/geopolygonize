import os
import click
import multiprocessing

from processing import process_tile, VectorizerParameters
from utils.tiler import Tiler, TilerParameters

@click.command()
@click.option('--input-file', required=True, help='Input tiff file')
@click.option('--output-file', required=True, help='Output shapefile')
@click.option('--min-blob-size', default=30, help='The minimum number of pixels with the same value. Blobs smaller than this will be filtered out and replaced.')
@click.option('--meters-per-pixel', default=30, help='The pixel size in meters')
@click.option('--workers', default=multiprocessing.cpu_count(), help='Number of processes to spawn')
@click.option('--tile-size', default=200, help='Tile size in pixels to cut the input file into')
def cli(
    input_filepath,
    output_filepath,
    min_blob_size,
    meters_per_pixel,
    workers,
    tile_size,
):
    
    # if there's a data/temp directory, delete it and start over
    if os.path.exists('data/temp'):
        os.system('rm -rf data/temp')
    os.makedirs('data/temp', exist_ok=True)

    if not os.path.exists(input_filepath):
        raise ValueError(f'Input file does not exist: {input_filepath}')

    output_dir = os.path.dirname(output_filepath)
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
    )
    rz = Tiler(
        input_filepath=input_filepath,
        output_filepath=output_filepath,
        tiler_parameters=tiler_parameters,
        process_tile=process_tile,
        processer_parameters=parameters,
    )
    rz.process()


if __name__ == '__main__':
    cli()