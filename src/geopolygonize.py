import os
import glob
import click
import multiprocessing
import warnings
import tempfile
import shutil

import rasterio

from .processing import process_tile, GeoPolygonizerParameters
from .utils.tiler import Tiler, TilerParameters

warnings.filterwarnings("ignore", category=RuntimeWarning)

EPSILON = 1.0e-10


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
    help="The amount of simplification applied relative to the pixel size. "
         "The higher the number, the more simplified the output. "
         "For example, with a pixel size of 30 meters and a simplification "
         "of 2, the output will be simplified by 60 meters.",
)
@click.option(
    "--smoothing-iterations",
    default=0,
    help="The number of iterations of smoothing to run on the "
         "output polygons.",
)
@click.option(
    '--tile-size',
    default=200,
    help="Tile size in pixels",
)
@click.option(
    '--label-name',
    default='label',
    help="The name of the attribute to store the original "
         "pixel value in the output.",
)
@click.option(
    '--workers',
    default=multiprocessing.cpu_count(),
    help="Number of processes to spawn to process tiles in parallel."
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
    inputs = glob.glob(input_file)
    if len(inputs) >= 1:
        input_file = inputs[0]
    else:
        raise ValueError(f'Input file does not exist: {input_file}')

    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        raise ValueError(f'Output directory does not exist: {output_dir}')

    with rasterio.open(input_file) as src:
        data = src.read(1)
        meta = src.meta
        crs = meta['crs']
        transform = src.transform
        res = src.res

    endx = data.shape[0]
    endy = data.shape[1]

    if pixel_size == 0:
        # assume pixel is square
        assert abs(res[0] - res[1]) < EPSILON
        pixel_size = abs(res[0])
        if pixel_size == 0:
            raise RuntimeError(
                "Cannot infer pixel size from input file. "
                "Please input it manually using `--pixel-size`."
            )

    try:
        parameters = GeoPolygonizerParameters(
            data=data,
            meta=meta,
            crs=crs,
            transform=transform,
            label_name=label_name,
            min_blob_size=min_blob_size,
            pixel_size=pixel_size,
            simplification_pixel_window=simplification_pixel_window,
            smoothing_iterations=smoothing_iterations,
        )

        temp_dir = tempfile.mkdtemp()
        tiler_parameters = TilerParameters(
            endx=endx,
            endy=endy,
            tile_size=tile_size,
            num_processes=workers,
            temp_dir=temp_dir,
        )
        rz = Tiler(
            tiler_parameters=tiler_parameters,
            process_tile=process_tile,
            processer_parameters=parameters,
        )
        gdf = rz.process()
        gdf.to_file(output_file)

    except Exception as e:
        raise e
    finally:
        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    cli()
