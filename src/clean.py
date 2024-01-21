import click

from .cleaner import Cleaner, CleanerParams
from .utils.clean_exit import kill_self


@click.command(
    name="Clean",
    help="Cleaner preprocesses the input TIF file for geopolygonization."
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
    help="Output TIF file path",
    required=True,
)
@click.option(
    '--min-blob-size',
    default=30,
    type=int,
    help="The mininum number of pixels a blob can have and not be "
         "filtered out.",
)
@click.option(
    '--debug',
    is_flag=True,
    help="enable debug mode"
)
def cli(
    input_file,
    output_file,
    min_blob_size,
    debug,
):
    try:
        params = CleanerParams(
            input_file=input_file,
            output_file=output_file,
            min_blob_size=min_blob_size,
            debug=debug,
        )
        Cleaner(params).clean()
    except Exception as e:
        print(f"clean encountered error: {e}")
        kill_self()


if __name__ == '__main__':
    cli()
