#!/bin/bash
# Одна кнопка: выложить эту папку на GitHub (первый раз — создать репозиторий,
# в следующие разы — отправить изменения). Запускать двойным щелчком на Mac.
# Имя репозитория можно поменять здесь:
REPO="itep-chess-m20"
DESC="ITEP chess program (Moscow, 1966) running again on an M-20 emulator — реконструкция шахматной программы ИТЭФ для М-20"

cd "$(dirname "$0")" || exit 1

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n\n' "$*"; read -r -p "Нажми Enter, чтобы закрыть. "; exit 1; }

say "1/5  Проверяю git и GitHub CLI"
if ! command -v git >/dev/null 2>&1; then
    xcode-select --install >/dev/null 2>&1
    fail "Нет git. macOS сейчас предложит установить Command Line Tools — согласись, дождись конца установки и запусти этот файл снова."
fi
if ! command -v gh >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        say "Ставлю GitHub CLI (gh) через Homebrew — это один раз"
        brew install gh || fail "Не удалось установить gh через Homebrew."
    else
        fail "Нет GitHub CLI (gh) и нет Homebrew. Скачай установщик gh для macOS: https://cli.github.com — поставь и запусти этот файл снова."
    fi
fi

say "2/5  Вход в GitHub"
if ! gh auth status >/dev/null 2>&1; then
    echo "Сейчас откроется браузер: подтверди там код, который покажет терминал."
    gh auth login --hostname github.com --git-protocol https --web || fail "Вход в GitHub не выполнен."
fi
gh auth setup-git >/dev/null 2>&1 || true
LOGIN=$(gh api user -q .login 2>/dev/null) || fail "Не удалось узнать имя пользователя GitHub."
USERID=$(gh api user -q .id 2>/dev/null)
if [ -z "$(git config --global user.name 2>/dev/null)" ]; then git config --global user.name "$LOGIN"; fi
if [ -z "$(git config --global user.email 2>/dev/null)" ]; then git config --global user.email "${USERID}+${LOGIN}@users.noreply.github.com"; fi
echo "Аккаунт: $LOGIN"

say "3/5  Готовлю репозиторий"
# адрес репозитория в CITATION.cff — под реальный логин
if [ -f CITATION.cff ]; then
    sed -i '' "s#https://github.com/[^/\"]*/itep-chess-m20#https://github.com/${LOGIN}/${REPO}#" CITATION.cff 2>/dev/null || true
fi
if [ ! -d .git ]; then
    git init -q -b main 2>/dev/null || { git init -q && git checkout -q -b main; }
fi
git add -A
if ! git diff --cached --quiet; then
    git commit -q -m "ITEP chess program (M-20, 1966): reconstruction $(cat VERSION 2>/dev/null)" || fail "Коммит не удался."
    echo "Изменения записаны."
else
    echo "Новых изменений нет."
fi

say "4/5  Отправляю на GitHub"
if git remote get-url origin >/dev/null 2>&1; then
    git push -u origin main || fail "Отправка не удалась. Проверь интернет (GitHub может требовать VPN) и запусти снова."
else
    gh repo create "$REPO" --public --source=. --remote=origin --push --description "$DESC" \
        || fail "Не удалось создать репозиторий. Если имя занято — поменяй REPO в начале этого файла и запусти снова."
fi

say "5/5  Готово"
URL="https://github.com/${LOGIN}/${REPO}"
echo "$URL"
open "$URL" >/dev/null 2>&1 || true
echo
read -r -p "Нажми Enter, чтобы закрыть. "
