#!/bin/bash
# Создать релиз v1.0 на GitHub (после того как папка уже выложена кнопкой «Выложить-на-GitHub»).
cd "$(dirname "$0")" || exit 1
fail() { printf '\n\033[31m%s\033[0m\n\n' "$*"; read -r -p "Нажми Enter, чтобы закрыть. "; exit 1; }
command -v gh >/dev/null 2>&1 || fail "Нет gh — сначала запусти «Выложить-на-GitHub.command»."
git remote get-url origin >/dev/null 2>&1 || fail "Папка ещё не выложена — сначала «Выложить-на-GitHub.command»."
git add -A && { git diff --cached --quiet || git commit -q -m "release v1.0"; }
git push -q origin main || fail "Отправка не удалась."
if ! git rev-parse v1.0 >/dev/null 2>&1; then
    git tag -a v1.0 -m "v1.0 — первый публичный выпуск (реконструкция v19.1)" && git push -q origin v1.0 || fail "Тег не отправлен."
fi
if gh release view v1.0 >/dev/null 2>&1; then
    echo "Релиз v1.0 уже существует."
else
    ZIP="../itep-chess-m20-v1.0.zip"
    rm -f "$ZIP"; (cd .. && zip -qr "itep-chess-m20-v1.0.zip" "$(basename "$PWD")" -x "*/.git/*" "*/engine/*.so" "*/engine/*.dylib" "*/__pycache__/*" "*/game.json" "*/benchmark-results/*")
    gh release create v1.0 "$ZIP" --title "v1.0 — первый публичный выпуск" --notes-file RELEASE_NOTES.md || fail "Релиз не создан."
fi
echo; gh release view v1.0 --web >/dev/null 2>&1 || true
read -r -p "Готово. Нажми Enter, чтобы закрыть. "
