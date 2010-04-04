#!/bin/sh
folder=`dirname "$0"`
cd "$folder"
clear
python -O src/OGBot.py $*
