#!/usr/bin/env python3
"""Генерирует bootanimation.zip для KimderheimOS.

Белый логотип «K» в скруглённом контуре на чёрном фоне:
  part0 — плавное появление (один раз),
  part1 — мягкая пульсация (повторяется, пока система не загрузится).

Запуск:  python3 tools/generate_bootanimation.py
Нужен Pillow:  pip install pillow
"""
import io
import math
import os
import zipfile

from PIL import Image, ImageDraw

SIZE = 512        # кадр по центру экрана, остальное — чёрный фон
FPS = 30
SS = 4            # суперсэмплинг для гладких краёв
OUT = os.path.join(os.path.dirname(__file__), "..", "vendor", "kimderheim", "media",
                   "bootanimation.zip")


def rounded_square(draw, box, radius, width, fill):
    draw.rounded_rectangle(box, radius=radius, outline=fill, width=width)


def logo(brightness: float, scale: float) -> Image.Image:
    """Рисует логотип. brightness 0..1, scale — масштаб относительно базового."""
    s = SIZE * SS
    img = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(img)
    c = s / 2
    half = s * 0.26 * scale
    v = int(255 * brightness)

    # контур «скруглённый квадрат», как форма иконок
    rounded_square(d, (c - half, c - half, c + half, c + half),
                   radius=half * 0.45, width=max(1, int(s * 0.018 * scale)), fill=v)

    # буква K из трёх линий
    t = s * 0.045 * scale          # толщина
    k = half * 0.52                # половина высоты буквы
    x0 = c - k * 0.55              # вертикальная черта
    d.line((x0, c - k, x0, c + k), fill=v, width=int(t))
    d.line((x0 + t * 0.3, c + k * 0.05, c + k * 0.6, c - k), fill=v, width=int(t))
    d.line((x0 + k * 0.35, c - k * 0.12, c + k * 0.65, c + k), fill=v, width=int(t))

    return img.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB")


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def ease(x: float) -> float:
    return 1 - (1 - x) ** 3


def main() -> None:
    frames0, frames1 = [], []
    n0 = FPS                                   # 1 секунда появления
    for i in range(n0):
        p = ease(i / (n0 - 1))
        frames0.append(logo(p, 0.9 + 0.1 * p))
    n1 = FPS * 2                               # 2 секунды цикл пульсации
    for i in range(n1):
        p = 0.75 + 0.25 * (0.5 + 0.5 * math.cos(2 * math.pi * i / n1))
        frames1.append(logo(p, 1.0))

    desc = f"{SIZE} {SIZE} {FPS}\np 1 0 part0\np 0 0 part1\n"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Важно: архив должен быть БЕЗ сжатия (ZIP_STORED), иначе Android его не прочитает
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("desc.txt", desc)
        for name, frames in (("part0", frames0), ("part1", frames1)):
            for i, f in enumerate(frames):
                z.writestr(f"{name}/{i:04d}.png", png_bytes(f))
    print("Анимация сохранена:", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
