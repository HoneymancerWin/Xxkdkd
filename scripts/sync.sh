#!/usr/bin/env bash
# Скачивает исходники GrapheneOS нужной версии (~150+ ГБ, надолго).
source "$(dirname "$0")/common.sh"

[[ -n "$GOS_TAG" ]] || die "Не задано GOS_TAG (тег релиза GrapheneOS). Заполни config.env"

mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

say "repo init: GrapheneOS $GOS_TAG"
repo init -u https://github.com/GrapheneOS/platform_manifest.git -b "refs/tags/$GOS_TAG"

# GrapheneOS подписывает теги — проверка подлинности манифеста
# (инструкция по импорту ключа: https://grapheneos.org/build#downloading-source-code)
if ! (cd .repo/manifests && git verify-tag "$(git describe --tags)" 2>/dev/null); then
    echo "ВНИМАНИЕ: подпись тега не проверена (не импортирован ключ GrapheneOS?)."
fi

say "repo sync (это может занять несколько часов)"
repo sync -c -j"$JOBS" --force-sync

say "Исходники в $SRC_DIR"
