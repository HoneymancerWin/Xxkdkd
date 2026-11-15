#!/data/data/com.termux/files/usr/bin/bash
# Установка и запуск на Android (Termux). Повторный запуск просто стартует бота.
set -e
cd "$(dirname "$0")"
if ! python -c "import bs4, yaml, requests" 2>/dev/null; then
  pkg update -y
  pkg install -y python
  pip install beautifulsoup4 pyyaml requests
fi
[ -f config.yaml ] || python -m avito_monitor --setup
termux-wake-lock 2>/dev/null || true   # не даём Android усыпить бота
python -m avito_monitor
