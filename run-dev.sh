#!/usr/bin/env bash
# Запуск ТЕСТОВОГО бота (dev-профиль) для отладки локального стека сайта.
# Конфиг: configuration/conf.dev.env (создаётся из conf.dev.env.example), данные: storage-dev/.
# Продовый conf.env и storage/ не трогаются.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

ENV_FILE=configuration/conf.dev.env
if [[ ! -f $ENV_FILE ]]; then
    cp configuration/conf.dev.env.example "$ENV_FILE"
    echo "Создан $ENV_FILE — впишите TOKEN тестового бота и запустите снова." >&2
    exit 1
fi
if grep -q '^TOKEN=PASTE_DEV_BOT_TOKEN_HERE' "$ENV_FILE" || ! grep -qE '^TOKEN=[0-9]+:' "$ENV_FILE"; then
    echo "В $ENV_FILE не задан TOKEN тестового бота (строка вида TOKEN=123456789:AA...)." >&2
    exit 1
fi

PY=python3
[[ -x .venv/bin/python ]] && PY=.venv/bin/python
[[ -x venv/bin/python ]] && PY=venv/bin/python

export ANSWERBOT_ENV=dev ANSWERBOT_ENV_FILE=$ENV_FILE STORAGE_DIR=$PWD/storage-dev LOG_DIR=$PWD/loginning/log-dev
mkdir -p storage-dev loginning/log-dev
exec "$PY" main.py
