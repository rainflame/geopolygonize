import click
import rasterio
import numpy as np
from scipy import stats

from tqdm import tqdm


@click.command("fill in pixel values with the average of the surrounding pixels")
@click.option(
    "-i",
    "--input-path",
    required=True,
    type=str,
    help="TIF input file path",
)
@click.option(
    "-o",
    "--output-path",
    required=True,
    type=str,
    help="TIF output file path",
)
@click.option(
    "--filter-values",
    default=0,
    type=str,
    help="Comma separated list of values to filter out",
)
def cli(
    input_path,
    output_path,
    filter_values,
):

    filter_values = list(map(int, filter_values.split(",")))

    with rasterio.open(input_path) as src:
        # assuming data is in the first band
        band1 = src.read(1)
        rows, cols = band1.shape
        modified_band = band1.copy()

        for row in tqdm(range(rows)):
            for column in range(cols):
                if band1[row, column] in filter_values:

                    window_size = 2
                    mode = None

                    while mode is None:
                        window = band1[
                            max(0, row - window_size) : min(
                                rows, row + window_size + 1
                            ),
                            max(0, column - window_size) : min(
                                cols, column + window_size + 1
                            ),
                        ]

                        # remove the filter values from the window
                        for filter_value in filter_values:
                            window = window[window != filter_value]

                        mode_val = stats.mode(window, axis=None, keepdims=True)

                        if mode_val.count[0] > 0:
                            mode = mode_val.mode[0]

                        # increase the window size until a mode value is found
                        window_size += 2

                    modified_band[row, column] = mode

        with rasterio.open(output_path, "w", **src.profile) as dst:
            dst.write(modified_band, 1)


if __name__ == "__main__":
    cli()
