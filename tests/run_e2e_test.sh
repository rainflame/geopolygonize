#!/usr/bin/env bash

set -e
set -x

NAME=$1

source .venv/bin/activate
rm -f "data/${NAME}_cleaned.tif"
rm -f "data/${NAME}.gpkg"
python3 utilities/view.py --tiffile "data/${NAME}.tif"
python3 -m src.clean --input-file="data/${NAME}.tif" --output-file="data/${NAME}_cleaned.tif"
#python3 utilities/downsample.py -i "data/${NAME}.tif" -o "data/${NAME}_reduced.tif" -r 0.125
python3 -m src.geopolygonize --input-file="data/${NAME}_cleaned.tif" --output-file="data/${NAME}.gpkg"
python3 utilities/view.py --gpkgfile "data/${NAME}.gpkg"
deactivate
