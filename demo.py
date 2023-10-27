import glob
import multiprocessing as mp

from processing import process_tile, VectorizerParameters
from utils.tiler import Tiler, TilerParameters

parameters = VectorizerParameters(
    min_blob_size=30,
    meters_per_pixel=30,
)
tiler_parameters = TilerParameters(
    num_processes=mp.cpu_count(),
    tile_size=200,
)

if __name__ == '__main__':
    rz = Tiler(
        input_filepath=glob.glob('data/sources/*.tif')[0],
        output_filepath="data/outputs/vectors.shp",
        tiler_parameters=tiler_parameters,
        process_tile=process_tile,
        processer_parameters=parameters,
    )
    rz.process()