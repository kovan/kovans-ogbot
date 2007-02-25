#!/bin/bash
# usage-message.sh

: ${1?"Usage: $0 VERSIONNUMBER"}

FILENAME=kovans-ogbot_$1.tar.gz

echo "Filename will be: $FILENAME"


tar czvf $FILENAME --exclude='*.svn' --exclude='*.pyc' --exclude='*~' --exclude='*.pyo' lib src languages runbot.* *.txt
googlecode-upload.py -s "Kovan's OGBot $1" -p kovans-ogbot -u jsceballos -l "Featured, Type-Source, OpSys-All" $FILENAME