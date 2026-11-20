#!/usr/bin/env bash
# Собирает KimderheimOS для устройства $DEVICE.
#
#   ./scripts/build.sh               — полная сборка
#   SKIP_ADEVTOOL=1 ./scripts/build.sh — повторная сборка без извлечения vendor-файлов
#
# Команды основаны на официальной инструкции https://grapheneos.org/build
# Если GrapheneOS поменяет процесс сборки — сверяйся с ней.
source "$(dirname "$0")/common.sh"
need_device
[[ -d "$SRC_DIR/.repo" ]] || die "Нет исходников в $SRC_DIR. Сначала запусти ./scripts/sync.sh"

# 1. Шрифты
"$REPO_ROOT/scripts/fetch-fonts.sh"

# 2. Копируем наш код в дерево исходников
say "Копирую vendor/kimderheim в дерево исходников"
mkdir -p "$SRC_DIR/vendor"
rsync -a --delete "$REPO_ROOT/vendor/kimderheim/" "$SRC_DIR/vendor/kimderheim/"

android_env

# 3. Извлечение закрытых файлов производителя (adevtool)
if [[ "${SKIP_ADEVTOOL:-0}" != "1" ]]; then
    say "adevtool: подготовка vendor-файлов для $DEVICE"
    yarnpkg install --cwd vendor/adevtool/
    do_lunch "sdk_phone64_x86_64-$RELEASE_CONFIG-$BUILD_VARIANT"
    m aapt2
    vendor/adevtool/bin/run generate-all -d "$DEVICE"
fi

# 4. Подключаем KimderheimOS к продукту устройства
TARGET="$DEVICE-$RELEASE_CONFIG-$BUILD_VARIANT"
do_lunch "$TARGET"

PRODUCT_MK="${PRODUCT_MK:-$(get_build_var INTERNAL_PRODUCT)}"
[[ -f "$PRODUCT_MK" ]] || die "Не нашёл makefile продукта ($PRODUCT_MK). Укажи вручную: PRODUCT_MK=путь/к/файлу.mk"

HOOK='$(call inherit-product, vendor/kimderheim/config/kimderheim.mk)'
if ! grep -qF "$HOOK" "$PRODUCT_MK"; then
    say "Подключаю kimderheim.mk к $PRODUCT_MK"
    printf '\n# KimderheimOS\n%s\n' "$HOOK" >> "$PRODUCT_MK"
fi
do_lunch "$TARGET"

# 5. Сборка
say "Сборка $TARGET (первый раз — несколько часов)"
m -j"$JOBS" vendorbootimage vendorkernelbootimage target-files-package

say "Сборка завершена. Дальше: ./scripts/release.sh"
