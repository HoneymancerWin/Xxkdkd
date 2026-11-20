#!/usr/bin/env bash
# Запускает тесты логики лаунчера на обычной Java (Android не нужен).
set -e
cd "$(dirname "$0")/.."
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
javac -encoding UTF-8 -d "$OUT" src/os/kimderheim/launcher/LayoutModel.java test/os/kimderheim/launcher/LayoutModelTest.java
java -Dstdout.encoding=UTF-8 -cp "$OUT" os.kimderheim.launcher.LayoutModelTest
