#!/usr/bin/env bash

set -e
set -x

NAME=$1

source .venv/bin/activate
rm -f data/"$NAME".gpkg
python3 utilities/view.py --tiffile data/"$NAME".tif
python3 -m src.geopolygonize --input-file="data/$NAME.tif" --output-file="data/$NAME.gpkg" --tile-size=1000
python3 utilities/view.py --gpkgfile "data/$NAME.gpkg"
deactivate
