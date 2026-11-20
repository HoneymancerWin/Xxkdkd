#!/usr/bin/env bash
# Скачивает свободный шрифт Inter (лицензия SIL OFL) и создаёт для него Android.bp.
source "$(dirname "$0")/common.sh"

INTER_VERSION="${INTER_VERSION:-4.0}"
FONT_DIR="$REPO_ROOT/vendor/kimderheim/fonts"
WEIGHTS=(Regular Medium SemiBold Bold)

if [[ -f "$FONT_DIR/Android.bp" && -f "$FONT_DIR/InterVariable.ttf" ]]; then
    echo "Шрифт Inter уже скачан."
    exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "Скачиваю Inter $INTER_VERSION"
curl -fsSL "https://github.com/rsms/inter/releases/download/v$INTER_VERSION/Inter-$INTER_VERSION.zip" -o "$TMP/inter.zip"
unzip -q "$TMP/inter.zip" -d "$TMP/inter"

for w in "${WEIGHTS[@]}"; do
    f="$(find "$TMP/inter" -name "Inter-$w.ttf" | head -n1)"
    [[ -n "$f" ]] || die "В архиве нет Inter-$w.ttf"
    cp "$f" "$FONT_DIR/Inter-$w.ttf"
done
# Переменный шрифт — для часов экрана блокировки (анимация толщины)
cp "$(find "$TMP/inter" -name 'InterVariable.ttf' | head -n1)" "$FONT_DIR/InterVariable.ttf"
cp "$(find "$TMP/inter" -iname 'LICENSE*' | head -n1)" "$FONT_DIR/OFL.txt"

{
    echo "// Сгенерировано scripts/fetch-fonts.sh — не редактировать вручную."
    echo
    echo 'prebuilt_etc {'
    echo '    name: "kimderheim_fonts_customization.xml",'
    echo '    src: "fonts_customization.xml",'
    echo '    filename: "fonts_customization.xml",'
    echo '    product_specific: true,'
    echo '}'
    for f in "${WEIGHTS[@]/#/Inter-}" InterVariable; do
        echo
        echo 'prebuilt_font {'
        echo "    name: \"kimderheim_$f.ttf\","
        echo "    src: \"$f.ttf\","
        echo "    filename: \"$f.ttf\","
        echo '    product_specific: true,'
        echo '}'
    done
} > "$FONT_DIR/Android.bp"

say "Шрифт Inter готов"
