"""look/_fac2_cmp.py - glue the before/after pairs of FACADE round 2.

The before images come from `look/facade_lab.py` run with the PRE-EDIT
`hd_houses.py` (tag fac2a), the after images from the same lab, same seeds,
same light and same cameras run against the edited file (tag fac2b).  Both are
480x270, so nothing is resampled: each panel is dropped in at its native size
and the canvas is padded, which keeps the comparison honest.

    python look/_fac2_cmp.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = r"E:\My World\Blender\renders\kingdom\look"
PANEL = (480, 270)
CANVAS = (960, 540)
BG = (16, 16, 18)
FG = (232, 226, 210)
DIM = (150, 145, 132)

PAIRS = [
    ("fac2_cmp_game.png", "fac2_before_game.png", "fac2_after_game.png",
     "GAME CAMERA 52 deg / 34 m - the frame the city render gets wrong",
     "front row of a terrace, flank running off the right of frame"),
    ("fac2_cmp_ends.png", "fac2_before_ends.png", "fac2_after_ends.png",
     "1.72 m EYE, 16 m OUT - the party-wall flank face on",
     "stone coursing, windows, shutters, quoins, chimney breast"),
]


def _font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf", "arial.ttf",
                 "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _panel(path):
    if not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGB")
    if img.size != PANEL:
        img = img.resize(PANEL, Image.LANCZOS)
    return img


def main():
    f_big = _font(17)
    f_small = _font(13)
    for (dst, a, b, title, sub) in PAIRS:
        left, right = _panel(os.path.join(OUT, a)), _panel(os.path.join(OUT, b))
        if left is None or right is None:
            print("[cmp] missing source for %s" % dst, flush=True)
            continue
        cv = Image.new("RGB", CANVAS, BG)
        cv.paste(left, (0, 150))
        cv.paste(right, (480, 150))
        d = ImageDraw.Draw(cv)
        d.text((16, 14), title, font=f_big, fill=FG)
        d.text((16, 36), sub, font=f_small, fill=DIM)
        for x, lab, col in ((0, "BEFORE  (pre-edit hd_houses.py)", (226, 120, 96)),
                            (480, "AFTER  (round 2)", (140, 208, 156))):
            d.rectangle([x, 150, x + 479, 150 + 269], outline=(58, 58, 62))
            d.rectangle([x + 241, 122, x + 479, 148], fill=BG)
            d.text((x + 249, 126), lab, font=f_small, fill=col)
        d.text((16, 430), "same lab scene, same seeds, same light, same cameras",
               font=f_small, fill=DIM)
        d.text((16, 448), "panels are native 480x270 - no resampling",
               font=f_small, fill=DIM)
        d.text((16, 512), "FACADE round 2  -  E:\\My World\\Blender\\kingdom",
               font=f_small, fill=(96, 94, 88))
        p = os.path.join(OUT, dst)
        cv.save(p)
        print("[cmp] %s  %dx%d" % (p, CANVAS[0], CANVAS[1]), flush=True)


if __name__ == "__main__":
    main()
