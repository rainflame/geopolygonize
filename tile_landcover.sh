#!/bin/bash

mkdir -p data/output

echo -e "\nConverting to GeoJSON...\n"

ogr2ogr -f GeoJSONSeq data/temp/landcover.geojsons data/temp/combined.shp

echo -e "\nTiling dataset...\n"

tippecanoe -Z1 -z16 -P -o data/output/landcover.pmtiles --drop-densest-as-needed -l landcover data/temp/landcover.geojsons --force

echo -e "\n\nDone, created: \ndata/output/landcover.pmtiles\n"
