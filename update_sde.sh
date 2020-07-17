#!/bin/bash

remote_file="https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2"
local_file="/home/kbeck/projects/thingenv/evething/db/sqlite-latest.sqlite.bz2"

modified=$(curl --silent --head $remote_file |
           awk -F: '/^Last-Modified/ { print $2 }')
remote_ctime=$(date --date="$modified" +%s)
force="$1"

if [ -e $local_file ]; then
    local_ctime=$(stat -c %z "$local_file")
    local_ctime=$(date --date="$local_ctime" +%s)
else
    local_ctime=false
fi

if [ $local_ctime = false ] || [ $local_ctime -lt $remote_ctime ]; then
    cd /home/kbeck/projects/thingenv/evething
    curl -sS $remote_file > $local_file
    FILESIZE=$(stat -c%s "$local_file")

    if [ $FILESIZE -gt 78643200 ]; then
        bzip2 -dk -f $local_file
        source ../bin/activate
        python import.py

        exit 0
    else
        rm "$local_file"
    fi
fi

if [ "$force" ==  "--force" ]; then
    source ../bin/activate
    python import.py
fi
