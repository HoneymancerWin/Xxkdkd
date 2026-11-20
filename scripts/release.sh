#!/usr/bin/env bash
# Подписывает сборку твоими ключами и создаёт factory-образ для прошивки.
# По мотивам https://grapheneos.org/build#generating-signed-factory-images-and-full-update-packages
source "$(dirname "$0")/common.sh"
need_device
[[ -e "$SRC_DIR/keys/$DEVICE" ]] || die "Нет ключей. Сначала запусти ./scripts/make-keys.sh"

android_env
do_lunch "$DEVICE-$RELEASE_CONFIG-$BUILD_VARIANT"

BUILD_NUMBER="$(cat out/soong/build_number.txt)"

say "Подписываю сборку $BUILD_NUMBER"
script/finalize.sh
script/generate-release.sh "$DEVICE" "$BUILD_NUMBER"

say "Готово. Factory-образ ищи в $SRC_DIR/releases/$BUILD_NUMBER/"
echo "Как прошить — docs/FLASHING.md"
