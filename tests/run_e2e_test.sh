#!/bin/bash

set -e
set -x

NAME="tiny"

source .venv/bin/activate

rm -f data/$NAME.shp
python3 tests/view.py --tiffile data/$NAME.tif
python3 -m src.geopolygonize --input-file="data/$NAME.tif" --output-file="data/$NAME.shp"
python3 tests/view.py --shapefile data/$NAME.shp
deactivate
