"""Generuje grafiki zakreślenia dnia w kalendarzu (assets/cal_mark_ring.png i assets/cal_mark_fill.png).

Kształt pochodzi z obrazka (różowe odręczne kółko); używany jest tylko kształt, kolor to #fcb808.
Użycie: python tools/make_calendar_marks.py ŚCIEŻKA_DO_OBRAZKA.jpg
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

COLOR = (0xFC, 0xB8, 0x08)
WIDTH = 168  # px; w aplikacji wyświetlane ok. 3x mniejsze (ostre na ekranach HiDPI)
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def ring_alpha(src: Image.Image) -> Image.Image:
    """Maska obrysu: im bardziej piksel różowy (mniej zielonego), tym bardziej nieprzezroczysty."""
    green = src.convert("RGB").split()[1]
    return green.point(lambda g: max(0, min(255, round((255 - g) * 255 / (255 - 84)))))


def interior_mask(alpha: Image.Image) -> Image.Image:
    """Wnętrze zakreślenia: wszystko, do czego nie dociera tło z brzegu (obrys lekko pogrubiony, by domknąć szczeliny)."""
    solid = alpha.point(lambda a: 255 if a > 100 else 0).filter(ImageFilter.MaxFilter(9))
    outside = solid.convert("RGB")
    from PIL import ImageDraw

    ImageDraw.floodfill(outside, (0, 0), (255, 0, 0), thresh=10)
    reachable = outside.split()[0].point(lambda r: 255 if r > 200 else 0)
    green = outside.split()[1].point(lambda g: 255 if g < 50 else 0)
    outside_mask = ImageChops.multiply(reachable, green)
    return ImageChops.invert(outside_mask)


def colorize(alpha: Image.Image, box, size) -> Image.Image:
    alpha = alpha.crop(box).resize(size, Image.LANCZOS)
    img = Image.new("RGBA", size, COLOR + (0,))
    img.putalpha(alpha)
    return img


def main(path: str) -> None:
    src = Image.open(path)
    alpha = ring_alpha(src)
    inside = interior_mask(alpha)
    box = alpha.point(lambda a: 255 if a > 40 else 0).getbbox()
    width = box[2] - box[0]
    size = (WIDTH, round(WIDTH * (box[3] - box[1]) / width))
    ASSETS.mkdir(exist_ok=True)
    colorize(alpha, box, size).save(ASSETS / "cal_mark_ring.png")
    fill = ImageChops.lighter(alpha, inside.filter(ImageFilter.GaussianBlur(1.5)))
    colorize(fill, box, size).save(ASSETS / "cal_mark_fill.png")
    print("zapisano", size)


if __name__ == "__main__":
    main(sys.argv[1])
