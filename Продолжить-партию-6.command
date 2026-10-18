#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 play.py --pgn examples/itef-game-6.pgn --side black --depth 3 --budget 20000000000
status=$?
if [ "$status" -ne 0 ]; then
    printf '\nНажмите Enter, чтобы закрыть окно.\n'
    read -r answer
fi
exit "$status"
