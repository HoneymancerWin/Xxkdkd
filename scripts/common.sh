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

# --- Учёт наших изменений в коде GrapheneOS -------------------------------------
# Всё, что мы меняем в дереве исходников, записываем в журнал, чтобы sync.sh мог
# откатить это перед обновлением (иначе repo sync откажется обновлять проект).
MODLOG() { echo "$SRC_DIR/.kimderheim-modified"; }

record_mod() { # record_mod file <путь>  |  record_mod patch <каталог> <патч>
    grep -qxF "$*" "$(MODLOG)" 2>/dev/null || echo "$*" >> "$(MODLOG)"
}

# Применяет патч из patches/ к проекту исходников (если ещё не применён)
apply_patch() {
    local project="$1" patch="$REPO_ROOT/$2"
    local dir="$SRC_DIR/$project"
    if git -C "$dir" apply --reverse --check "$patch" 2>/dev/null; then
        echo "Патч $2 уже применён."
        return
    fi
    git -C "$dir" apply --3way "$patch" \
        || die "Патч $2 не применился: код GrapheneOS изменился. Отключи его в config.env или пришли ошибку."
    record_mod patch "$project" "$2"
    echo "Применён патч $2"
}

# Откатывает всё, что мы поменяли в исходниках (вызывается перед repo sync)
revert_mods() {
    local log; log="$(MODLOG)"
    [[ -f "$log" ]] || return 0
    local kind a b
    while read -r kind a b; do
        case "$kind" in
            file)  git -C "$(dirname "$a")" checkout -- "$(basename "$a")" 2>/dev/null || true ;;
            patch) git -C "$SRC_DIR/$a" apply --reverse --index "$REPO_ROOT/$b" 2>/dev/null \
                       || git -C "$SRC_DIR/$a" apply --reverse "$REPO_ROOT/$b" 2>/dev/null || true ;;
        esac
    done < "$log"
    rm -f "$log"
    echo "Наши изменения в исходниках откачены (будут применены заново при сборке)."
}
