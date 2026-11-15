#!/data/data/com.termux/files/usr/bin/bash
# Установка на Android (Termux): бот работает в фоне.
# Повторный запуск обновляет установку и перезапускает бота.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
cd "$DIR"

if ! python -c "import bs4, yaml, requests" 2>/dev/null; then
  echo "==> Устанавливаю Python и библиотеки (пару минут)"
  pkg update -y
  pkg install -y python
  pip install beautifulsoup4 pyyaml requests
fi

[ -f config.yaml ] || python -m avito_monitor --setup

# Цикл, который держит бота живым: упал — через 30 с снова запустится.
cat > "$DIR/run_loop.sh" <<EOF
#!$PREFIX/bin/bash
cd "$DIR"
trap 'kill \$child 2>/dev/null; rm -f avito.pid; exit 0' TERM INT
while true; do
  if [ -f avito.log ] && [ \$(wc -c < avito.log) -gt 5000000 ]; then
    tail -n 2000 avito.log > avito.log.tmp && mv avito.log.tmp avito.log
  fi
  python -m avito_monitor >> avito.log 2>&1 &
  child=\$!
  wait \$child
  echo "\$(date '+%H:%M:%S') бот остановился, перезапуск через 30 с" >> avito.log
  sleep 30
done
EOF
chmod +x "$DIR/run_loop.sh"

cat > "$PREFIX/bin/avito" <<EOF
#!$PREFIX/bin/bash
DIR="$DIR"
cd "\$DIR"
running() { [ -f avito.pid ] && kill -0 \$(cat avito.pid) 2>/dev/null; }
case "\$1" in
  start)
    if running; then echo "Уже работает"; exit 0; fi
    termux-wake-lock 2>/dev/null || true
    nohup ./run_loop.sh >/dev/null 2>&1 &
    echo \$! > avito.pid
    echo "Бот запущен в фоне. Логи: avito logs" ;;
  stop)
    if running; then kill \$(cat avito.pid); rm -f avito.pid; echo "Остановлен"; else echo "Не запущен"; fi
    termux-wake-unlock 2>/dev/null || true ;;
  restart) "\$0" stop >/dev/null; sleep 1; "\$0" start ;;
  status)  if running; then echo "Работает"; tail -n 5 avito.log 2>/dev/null; else echo "Не запущен"; fi ;;
  logs)    tail -n 50 -f avito.log ;;
  edit)    nano config.yaml && "\$0" restart ;;
  setup)   python -m avito_monitor --setup && "\$0" restart ;;
  test)    python -m avito_monitor --test-telegram ;;
  update)  git pull -q && bash termux.sh ;;
  *) echo "avito start | stop | restart | status | logs | edit | setup | test | update" ;;
esac
EOF
chmod +x "$PREFIX/bin/avito"

# Автозапуск после перезагрузки телефона (нужно приложение Termux:Boot).
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/avito.sh" <<EOF
#!$PREFIX/bin/bash
termux-wake-lock
$PREFIX/bin/avito start
EOF
chmod +x "$HOME/.termux/boot/avito.sh"

avito restart
echo
echo "Готово! Бот работает в фоне. Termux можно свернуть (но не закрывать через «Exit»)."
echo "  avito logs   — что делает бот (выход: Ctrl+C, бот продолжит работать)"
echo "  avito stop   — остановить,  avito start — запустить"
echo "  avito edit   — настройки,   avito update — обновить"
