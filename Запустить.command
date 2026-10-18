#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 play.py
status=$?
if [ "$status" -ne 0 ]; then
  printf '\nНажмите Enter, чтобы закрыть окно.\n'
  read -r answer
fi
exit "$status"
