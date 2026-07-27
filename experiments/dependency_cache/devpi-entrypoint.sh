#!/bin/sh
set -eu

server_dir=/data
if [ ! -e "$server_dir/.nodeinfo" ]; then
    devpi-init --serverdir "$server_dir"
fi

if [ "${ENVSOLVE_CACHE_OFFLINE:-0}" = "1" ]; then
    exec devpi-server --offline-mode "$@"
fi
exec devpi-server "$@"
