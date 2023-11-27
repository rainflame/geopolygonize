#!/bin/bash

set -e
set -x

source .venv/bin/activate
rm -f data/output.shp
python3 tests/view.py --tiffile data/input.tif
python3 -m src.geopolygonize --input-file="data/input.tif" --output-file="data/output.shp"
python3 tests/view.py --shapefile data/output.shp
deactivate
