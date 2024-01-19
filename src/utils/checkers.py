import glob
import os


def check_and_retrieve_input_path(
    input_file: str,
) -> str:
    inputs = glob.glob(input_file)
    if len(inputs) < 1:
        raise ValueError(f'Input file does not exist: {input_file}')
    return inputs[0]


def check_output_path(
    output_file: str,
):
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        raise ValueError(f'Output directory does not exist: {output_dir}')


def check_is_positive(
    field_name: str,
    field_value: float,  # encompasses int
) -> None:
    if field_value <= 0:
        raise ValueError(f'Value for `{field_name}` must be positive.')


def check_is_non_negative(
    field_name: str,
    field_value: float,  # encompasses int
) -> None:
    if field_value < 0:
        raise ValueError(f'Value for `{field_name}` must be non-negative.')
