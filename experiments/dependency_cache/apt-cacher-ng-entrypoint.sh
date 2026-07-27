#!/bin/sh
set -eu

set -- -c /etc/apt-cacher-ng ForeGround=1 "$@"
if [ "${ENVSOLVE_CACHE_OFFLINE:-0}" = "1" ]; then
    set -- "$@" Offlinemode=1
fi
exec apt-cacher-ng "$@"
