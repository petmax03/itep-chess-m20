#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ "${1:-}" = "--uci" ]; then
    shift
    exec python3 uci.py "$@"
fi
if [ "${1:-}" = "--benchmark" ]; then
    shift
    exec python3 benchmarks/depth_benchmark.py "$@"
fi
exec python3 play.py "$@"
