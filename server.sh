#!/usr/bin/env bash
# Установка на VPS (Ubuntu/Debian): бот работает как служба 24/7.
# Повторный запуск обновляет код и перезапускает службу.
set -e
DIR=/opt/avito
BRANCH=ccr-84ad4696-6q8xkk
REPO=https://github.com/HoneymancerWin/Xxkdkd.git
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "==> Устанавливаю Python и git"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq python3 python3-venv git >/dev/null

echo "==> Скачиваю бота в $DIR"
if [ -d "$DIR/.git" ]; then
  $SUDO git -C "$DIR" pull -q
else
  $SUDO git clone -q -b "$BRANCH" "$REPO" "$DIR"
fi
$SUDO chown -R "$(id -u):$(id -g)" "$DIR"
cd "$DIR"

echo "==> Ставлю библиотеки"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

if [ ! -f config.yaml ]; then
  .venv/bin/python -m avito_monitor --setup < /dev/tty
fi

echo "==> Команда avito для управления"
$SUDO tee /usr/local/bin/avito.new >/dev/null <<'EOF'
#!/usr/bin/env bash
DIR=/opt/avito
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
case "$1" in
  logs)    $SUDO journalctl -u avito -f -n 50 -o cat ;;
  status)  $SUDO systemctl status avito --no-pager ;;
  restart) $SUDO systemctl restart avito && echo "Перезапущен" ;;
  stop)    $SUDO systemctl stop avito && echo "Остановлен" ;;
  start)   $SUDO systemctl start avito && echo "Запущен" ;;
  setup)   cd $DIR && .venv/bin/python -m avito_monitor --setup && $SUDO systemctl restart avito ;;
  edit)    ${EDITOR:-nano} $DIR/config.yaml && $SUDO systemctl restart avito ;;
  test)    cd $DIR && .venv/bin/python -m avito_monitor --test-telegram ;;
  proxy)   cd $DIR && .venv/bin/python -m avito_monitor.proxy_cmd avito "${2:-check}" && [ -n "$2" ] && [ "$2" != check ] && $SUDO systemctl restart avito ;;
  tgproxy) cd $DIR && .venv/bin/python -m avito_monitor.proxy_cmd telegram "${2:-check}" && [ -n "$2" ] && [ "$2" != check ] && $SUDO systemctl restart avito ;;
  update)  exec bash $DIR/server.sh ;;
  *) echo "avito logs | status | restart | stop | start | setup | edit | test | update | proxy <прокси|off> | tgproxy <прокси|off>" ;;
esac
EOF
$SUDO chmod +x /usr/local/bin/avito.new
$SUDO mv -f /usr/local/bin/avito.new /usr/local/bin/avito

echo "==> Служба"
$SUDO tee /etc/systemd/system/avito.service >/dev/null <<EOF
[Unit]
Description=Avito monitor
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m avito_monitor
Restart=always
RestartSec=30
User=$(id -un)
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
$SUDO systemctl daemon-reload
$SUDO systemctl enable -q avito
$SUDO systemctl restart avito

echo
echo "Готово! Бот работает и будет работать после перезагрузки сервера."
echo "  avito logs    — смотреть, что он делает (выход: Ctrl+C)"
echo "  avito edit    — поправить настройки"
echo "  avito setup   — настроить заново"
echo "  avito update  — обновить бота"
