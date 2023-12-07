#!/usr/bin/env bash

set -e
set -x

NAME=$1

source .venv/bin/activate
rm -f data/"$NAME".gpkg
python3 tests/view.py --tiffile data/"$NAME".tif
python3 -m src.geopolygonize --input-file="data/$NAME.tif" --output-file="data/$NAME.gpkg"
python3 tests/view.py --gpkgfile "data/$NAME.gpkg"
deactivate
