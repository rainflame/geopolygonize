import click
import glob
import os
import sys
from tqdm import tqdm
from pathlib import Path

import dask.dataframe as dd
import dask_geopandas as dgpd
import geopandas as gpd

curr_file_dir = os.path.dirname(__file__)

root_path = os.path.abspath(
    os.path.join(curr_file_dir, "..")
)
sys.path.append(root_path)
from src.utils.io import to_file

_CHUNKSIZE = int(1e4)


@click.command('combine a set of gpkg files into one')
@click.option(
    '-i',
    '--input-path',
    required=True,
    type=str,
    help='directory path with gpkg files to combine',
)
@click.option(
    '-o',
    '--output-path',
    required=True,
    type=str,
    help='TIF output file path',
)
@click.option(
    '-l',
    '--label-name',
    default="label",
    help='Name of attribute to combine polygons over',
)
def cli(
    input_path,
    output_path,
    label_name,
):
    union_dgdf = dgpd.from_geopandas(
        gpd.GeoDataFrame(),
        chunksize=_CHUNKSIZE
    )
    for filepath in tqdm(
        glob.glob(f"{input_path}/*.gpkg"),
        desc="Adding gpkg files",
    ):
        gdf = gpd.read_file(filepath)
        dgdf = dgpd.from_geopandas(gdf, npartitions=1)
        union_dgdf = dd.concat([union_dgdf, dgdf])

    # Dask recommends using split_out = 1
    # to use sort=True, which allows for determinism,
    # and because split_out > 1  may not work
    # with newer versions of Dask.
    # However, this will require all the data
    # to fit on the memory, which is not always possible.
    # Unfortunately, the lack of determinism
    # means that sometimes the dissolve outputs
    # a suboptimal join of the polygons.
    # This should be remedied with a rerun on the
    # same tile directory.
    #
    # https://dask-geopandas.readthedocs.io/en/stable/guide/dissolve.html
    num_rows = len(union_dgdf.index)
    partitions = num_rows // _CHUNKSIZE + 1
    print(
        f"# ROWS: {num_rows}"
        f"\tCHUNKSIZE: {_CHUNKSIZE}"
        f"\t# PARTITIONS: {partitions}"
    )
    union_dgdf = union_dgdf.dissolve(
        label_name,
        split_out=partitions
        #sort=True,
    )
    to_file(union_dgdf, output_path)


if __name__ == '__main__':
    cli()

