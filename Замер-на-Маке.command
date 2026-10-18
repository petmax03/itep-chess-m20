#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 benchmarks/depth_benchmark.py --workers 1
status=$?
printf '\nРезультаты находятся в benchmark-results/mac. Нажмите Enter.\n'
read -r answer
exit "$status"
