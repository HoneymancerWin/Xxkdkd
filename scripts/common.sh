#!/usr/bin/env bash
# Общие функции и загрузка настроек. Подключается остальными скриптами.
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$REPO_ROOT/config.env" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/config.env"
fi

SRC_DIR="${SRC_DIR:-$HOME/kimderheim-src}"
KEYS_DIR="${KEYS_DIR:-$HOME/kimderheim-keys}"
JOBS="${JOBS:-$(nproc)}"
# Релизная конфигурация GrapheneOS ("cur" = текущая). Сверяй с grapheneos.org/build
RELEASE_CONFIG="${RELEASE_CONFIG:-cur}"
BUILD_VARIANT="${BUILD_VARIANT:-user}"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mОшибка: %s\033[0m\n' "$*" >&2; exit 1; }

need_device() {
    [[ -n "$DEVICE" ]] || die "Не задано DEVICE (кодовое имя Pixel). Заполни config.env — см. docs/BUILD.md"
}

# envsetup.sh и lunch не рассчитаны на 'set -e', поэтому временно его снимаем
android_env() {
    cd "$SRC_DIR"
    set +e
    # shellcheck disable=SC1091
    source build/envsetup.sh >/dev/null
    set -e
}

do_lunch() {
    set +e
    lunch "$1"
    local rc=$?
    set -e
    [[ $rc -eq 0 ]] || die "lunch $1 не сработал"
}
