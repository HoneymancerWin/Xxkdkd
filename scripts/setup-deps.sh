#!/usr/bin/env bash
# Устанавливает зависимости для сборки (Ubuntu / Debian).
source "$(dirname "$0")/common.sh"

say "Устанавливаю пакеты (нужен sudo)"
sudo apt-get update
sudo apt-get install -y \
    git git-lfs gnupg curl rsync zip unzip openssl openssh-client \
    python3 python3-pip python3-pil python-is-python3 \
    nodejs yarnpkg build-essential fontconfig libncurses-dev

if ! command -v repo >/dev/null; then
    say "Устанавливаю утилиту repo"
    mkdir -p "$HOME/.local/bin"
    curl -fsSL https://storage.googleapis.com/git-repo-downloads/repo -o "$HOME/.local/bin/repo"
    chmod +x "$HOME/.local/bin/repo"
    echo 'Добавь в ~/.bashrc:  export PATH="$HOME/.local/bin:$PATH"'
fi

if [[ -z "$(git config --global user.name)" ]]; then
    echo "Для repo нужно имя и почта git:"
    echo '  git config --global user.name  "Твоё имя"'
    echo '  git config --global user.email "почта@example.com"'
fi

say "Готово"
