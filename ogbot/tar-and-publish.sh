#!/bin/sh

VERSION=$(cat src/version.txt)
FILENAME=kovans-ogbot_$VERSION.tar.gz

echo "Filename will be: $FILENAME"


tar czvf $FILENAME --exclude='*.svn' --exclude='*.pyc' --exclude='*~' --exclude='*.pyo' lib src languages runbot.* *.txt
./googlecode-upload.py -s "Kovan's OGBot $VERSION" -p kovans-ogbot -u jsceballos -l "Featured, Type-Source, OpSys-All" $FILENAME