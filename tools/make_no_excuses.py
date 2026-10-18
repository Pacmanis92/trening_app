"""Jednorazowy generator assets/no_excuses.png (wymaga Pillow i czcionki Ink Free; nie jest zależnością aplikacji)."""
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\Inkfree.ttf"
YELLOW = (252, 184, 8, 255)
ANGLE = 8  # stopnie, obrót przeciwnie do ruchu wskazówek zegara (prawy koniec wyżej)
BOLD = 3  # obrys pogrubiający

def line(text: str, size: int) -> Image.Image:
    font = ImageFont.truetype(FONT, size)
    img = Image.new("RGBA", (size * len(text), int(size * 1.6)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((20, 10), text, font=font, fill=YELLOW, stroke_width=BOLD, stroke_fill=YELLOW)
    return img.crop(img.getbbox())

no, ex = line("NO", 190), line("EXCUSES", 190)
ex_w = ex.width
no = no.resize((int(no.width * 0.8), int(no.height * 0.8)), Image.LANCZOS)
canvas = Image.new("RGBA", (ex_w + 60, no.height + ex.height + 20), (0, 0, 0, 0))
canvas.alpha_composite(no, (20, 0))
canvas.alpha_composite(ex, (30, no.height + 10))
out = canvas.rotate(ANGLE, resample=Image.BICUBIC, expand=True)
out = out.crop(out.getbbox())
out.save("assets/no_excuses.png")
print(out.size)
