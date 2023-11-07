import click
import glob
import os
import pandas as pd
import fiona
import json

from tqdm import tqdm


@click.command()
@click.option(
    '--input-file',
    default="data/temp/landcover.geojsons",
    help='Vectorized landcover geojson file'
)
@click.option(
    '--values-file',
    default="data/sources/values.csv",
    help='Values CSV file',
)
@click.option(
    '--output-file',
    default="data/output/classes.json",
    help='Output JSON file',
)
def cli(input_file, values_file, output_file):
    inputs = glob.glob(input_file)
    if len(inputs) >= 1:
        input_file = inputs[0]
    else:
        raise ValueError(f'Input file does not exist: {input_file}')
    pass

    values = glob.glob(values_file)
    if len(values) >= 1:
        values_file = values[0]
    else:
        raise ValueError(f'Values file does not exist: {values_file}')

    # verify the path ot the output file exists, if not create it
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # read the values file
    df = pd.read_csv(values_file)

    label_lookup = {}

    print("Loading geojson file...")
    with fiona.open(input_file, 'r') as f:

        print("Creating label lookup...")
        for feature in tqdm(f):
            # get the feature's label from properties
            label = feature.properties['label']
            value = df[df['VALUE'] == int(label)].iloc[0]
            label_lookup[label] = {
                'name': value['EVT_NAME'],
                'class': value['EVT_CLASS'],
                'subclass': value['EVT_SBCLS'],
                'color': "#bbd1b8"  # setting a default color
            }

    print("Writing output file...")
    with open(output_file, 'w') as f:
        f.write(json.dumps(label_lookup, indent=4))


if __name__ == '__main__':
    cli()
