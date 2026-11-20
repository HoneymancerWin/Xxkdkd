#!/usr/bin/env python3
"""Генерирует обои KimderheimOS по умолчанию: мягкий размытый градиент.

Запуск:  python3 tools/generate_wallpaper.py
Нужен Pillow:  pip install pillow
"""
import os
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 1440, 3200          # покрывает экраны всех современных Pixel
SCALE = 4                  # рисуем в 4 раза меньше, потом увеличиваем (быстро и гладко)
OUT = os.path.join(os.path.dirname(__file__), "..", "vendor", "kimderheim", "overlay",
                   "frameworks", "base", "core", "res", "res", "drawable-nodpi",
                   "default_wallpaper.png")

# Палитра: глубокий синий -> индиго -> розовый -> оранжевый
BACKGROUND = (12, 18, 54)
BLOBS = [
    # (x, y, радиус) в долях от размера, цвет
    ((0.15, 0.20, 0.55), (0, 110, 255)),
    ((0.90, 0.35, 0.50), (120, 70, 255)),
    ((0.30, 0.65, 0.55), (255, 60, 140)),
    ((0.85, 0.85, 0.45), (255, 150, 60)),
    ((0.50, 0.45, 0.30), (90, 200, 255)),
]


def main() -> None:
    random.seed(42)
    w, h = W // SCALE, H // SCALE
    img = Image.new("RGB", (w, h), BACKGROUND)
    for (fx, fy, fr), color in BLOBS:
        layer = Image.new("RGB", (w, h), (0, 0, 0))
        mask = Image.new("L", (w, h), 0)
        r = fr * w
        cx, cy = fx * w, fy * h
        ImageDraw.Draw(mask).ellipse((cx - r, cy - r * 1.3, cx + r, cy + r * 1.3), fill=200)
        layer.paste(color, mask=mask)
        mask = mask.filter(ImageFilter.GaussianBlur(w * 0.18))
        img = Image.composite(layer, img, mask)
    img = img.filter(ImageFilter.GaussianBlur(w * 0.05))
    img = img.resize((W, H), Image.BICUBIC)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, optimize=True)
    print("Обои сохранены:", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
