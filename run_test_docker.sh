#!/bin/env bash
set -e
# use "-t" argument for docker-compose only when we are on an interactive terminal
if [ -t 0 ]; then
    TTY_FLAG="-t"
else
    TTY_FLAG=""
fi
docker compose run -i $TTY_FLAG undistort /undistort/test.py -v -l -s
