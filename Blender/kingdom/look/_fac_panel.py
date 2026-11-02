"""look/_fac_panel.py - build the 4-panel before/after facade comparison.

    E:\\GameProject\\Python313\\python.exe look\\_fac_panel.py

Takes the four full-resolution lab renders and lays them up as

        +------------------+------------------+
        |  BEFORE  52 deg  |  AFTER   52 deg  |
        +------------------+------------------+
        |  BEFORE  eye     |  AFTER   eye     |
        +------------------+------------------+

with a caption strip under each tile and one title bar.  Pure PIL, no Blender,
so it can run while another agent holds the render lock.
"""
import os

from PIL import Image, ImageDraw

OUT = r"E:\My World\Blender\renders\kingdom\look"
PANEL = os.path.join(OUT, "FAC_compare.png")

TILES = [
    ("fac_old_backs52.png", "BEFORE  -  52 deg, 34 m  (what the player sees over the roofs)"),
    ("fac_new_backs52.png", "AFTER   -  52 deg, 34 m"),
    ("fac_old_backs.png", "BEFORE  -  1.7 m eye height, 30 m from the backs"),
    ("fac_new_backs.png", "AFTER   -  1.7 m eye height, 30 m from the backs"),
]
BAR = 26
PAD = 6
TITLE = 44


def load(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        raise SystemExit("missing: %s" % p)
    im = Image.open(p).convert("RGB")
    print("[panel] %-22s %dx%d %d B" % (name, im.width, im.height,
                                        os.path.getsize(p)))
    return im


def main():
    ims = [load(t[0]) for t in TILES]
    # the four single tiles the brief asks for, under their FAC_* names
    for src, dst in (("fac_old_backs52.png", "FAC_before_52.png"),
                     ("fac_new_backs52.png", "FAC_after_52.png"),
                     ("fac_old_backs.png", "FAC_before_eye.png"),
                     ("fac_new_backs.png", "FAC_after_eye.png")):
        im = Image.open(os.path.join(OUT, src)).convert("RGB")
        im.save(os.path.join(OUT, dst))
        print("[panel] %s -> %s" % (src, dst))
    w, h = ims[0].size
    W = w * 2 + PAD * 3
    H = TITLE + (h + BAR + PAD) * 2 + PAD
    sheet = Image.new("RGB", (W, H), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    d.text((PAD + 2, 12), "ASLAR KINGDOM  -  HOUSE FACADES:  terrace flanks and "
                          "back walls, before / after", fill=(232, 228, 216))
    for i, (im, cap) in enumerate(zip(ims, [t[1] for t in TILES])):
        cx = PAD + (i % 2) * (w + PAD)
        cy = TITLE + PAD + (i // 2) * (h + BAR + PAD)
        sheet.paste(im, (cx, cy))
        d.rectangle([cx, cy + h, cx + w - 1, cy + h + BAR - 1], fill=(30, 30, 34))
        col = (214, 120, 96) if cap.startswith("BEFORE") else (150, 196, 140)
        d.text((cx + 6, cy + h + 7), cap, fill=col)
    sheet.save(PANEL)
    print("[panel] wrote %s  %dx%d  %d B" % (PANEL, W, H,
                                             os.path.getsize(PANEL)))


if __name__ == "__main__":
    main()
