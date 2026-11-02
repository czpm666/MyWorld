"""Side-by-side before/after sheet for the user report.

    python look/_ba.py aerial
    python look/_ba.py street
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

LOOK = r"E:\My World\Blender\renders\kingdom\look"

PAIRS = {
    "aerial": ("f1_aerial.png", "C1_aerial.png", "before: 2 900 houses", "after: 12 215 houses"),
    "street": ("f1_game5.png", "C1_game4.png", "before: flat salmon roof", "after: pantiles + dormers"),
}


def font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        for base in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    pass
    return ImageFont.load_default()


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "aerial"
    a, b, la, lb = PAIRS[which]
    ia = Image.open(os.path.join(LOOK, a)).convert("RGB")
    ib = Image.open(os.path.join(LOOK, b)).convert("RGB")
    W, H = 960, 540
    ia = ia.resize((W, H), Image.LANCZOS)
    ib = ib.resize((W, H), Image.LANCZOS)
    pad, top = 12, 46
    sheet = Image.new("RGB", (W * 2 + pad * 3, H + top + pad), (18, 18, 20))
    sheet.paste(ia, (pad, top))
    sheet.paste(ib, (pad * 2 + W, top))
    d = ImageDraw.Draw(sheet)
    f = font(26)
    d.text((pad + 8, 10), la, font=f, fill=(214, 214, 220))
    d.text((pad * 2 + W + 8, 10), lb, font=f, fill=(255, 226, 170))
    out = os.path.join(LOOK, "_ba_%s.png" % which)
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
