#!/usr/bin/env bash
# Создаёт ТВОИ ключи подписи для $DEVICE. Запускается один раз на устройство.
#
# ВАЖНО:
#  - Ключи никому не передавай и не загружай в git/облако.
#  - Сделай резервную копию $KEYS_DIR. Потеряешь ключи — не сможешь выпускать
#    обновления для уже прошитых телефонов.
#  - Скрипт спросит пароль для каждого ключа (можно оставить пустым, но лучше задать).
#
# По мотивам https://grapheneos.org/build#generating-release-signing-keys
source "$(dirname "$0")/common.sh"
need_device
[[ -d "$SRC_DIR/development" ]] || die "Нет исходников в $SRC_DIR"

DEST="$KEYS_DIR/$DEVICE"
[[ -e "$DEST" ]] && die "Ключи для $DEVICE уже есть в $DEST — не перезаписываю."
mkdir -p "$DEST"
cd "$DEST"

CN="KimderheimOS"
for k in releasekey platform shared media networkstack sdk_sandbox bluetooth; do
    say "Ключ $k"
    "$SRC_DIR/development/tools/make_key" "$k" "/CN=$CN/" || true   # make_key выходит с кодом 1 даже при успехе
    [[ -f "$k.pk8" ]] || die "Не удалось создать ключ $k"
done

say "Ключ Verified Boot (AVB)"
openssl genrsa 4096 | openssl pkcs8 -topk8 -scrypt -out avb.pem
"$SRC_DIR/external/avb/avbtool.py" extract_public_key --key avb.pem --output avb_pkmd.bin

say "Ключ подписи factory-образов"
ssh-keygen -t ed25519 -f id_ed25519

# Скрипты GrapheneOS ищут ключи в $SRC_DIR/keys/<устройство>
mkdir -p "$SRC_DIR/keys"
ln -sfn "$DEST" "$SRC_DIR/keys/$DEVICE"

say "Ключи созданы в $DEST. СДЕЛАЙ РЕЗЕРВНУЮ КОПИЮ!"
