"""Verify contact.montage() puts the pictures in the order it was given.

    blender -b --factory-startup --python look/_shotmontage_test.py

`montage()` copies Blender images row by row, and Blender's pixel buffer is
bottom-up, so the obvious loop silently produces a vertically flipped sheet --
which is exactly the kind of bug that ships, because a contact sheet of a city
looks plausible either way.  This test tiles six known-different frames from
`renders/kingdom/look` and checks the result numerically: the mean colour of
each cell must match the mean colour of the source it came from.  It prints a
per-cell error and exits non-zero if any cell is out of place.

Run it in a light lock slot: it never opens a city blend.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy                                                    # noqa: E402
import numpy as np                                            # noqa: E402

LOOK = os.path.join(os.path.dirname(os.path.dirname(HERE)), "renders",
                    "kingdom", "look")
NAMES = ["V24_aerial.png", "V24_castle.png", "V24_cathedral.png",
         "V24_gate.png", "V24_overview.png", "V24_plaza.png"]
COLS = 3
OUT = os.path.join(LOOK, "_montage_test.png")


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return px


def main():
    paths = [os.path.join(LOOK, n) for n in NAMES]
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        print("[mt] missing sources: %s" % missing)
        return 2
    src = [load(p) for p in paths]
    means = [tuple(float(x) for x in s[:, :, :3].reshape(-1, 3).mean(0))
             for s in src]
    print("[mt] sources: %d at %dx%d" % (len(src), src[0].shape[1],
                                         src[0].shape[0]))
    for n, m in zip(NAMES, means):
        print("[mt]   %-22s mean rgb %.3f %.3f %.3f" % ((n,) + m))

    import contact
    contact.montage(paths, OUT, COLS)
    sheet = load(OUT)
    h, w = sheet.shape[0], sheet.shape[1]
    ch, cw = h // 2, w // COLS
    print("[mt] sheet %dx%d -> cells %dx%d" % (w, h, cw, ch))
    bad = 0
    for i, m in enumerate(means):
        r, c = divmod(i, COLS)
        y0 = (2 - 1 - r) * ch          # sheet pixels are bottom-up
        cell = sheet[y0:y0 + ch, c * cw:(c + 1) * cw, :3].reshape(-1, 3)
        got = tuple(float(x) for x in cell.mean(0))
        err = max(abs(a - b) for a, b in zip(got, m))
        ok = err < 0.02
        bad += 0 if ok else 1
        print("[mt] cell %d row %d col %d: want %.3f %.3f %.3f  got %.3f %.3f "
              "%.3f  err %.4f  %s" % ((i, r, c) + m + got + (err,
                                                            "ok" if ok else
                                                            "MISPLACED")))
    print("[mt] %s (%d/%d cells misplaced)"
          % ("PASS" if not bad else "FAIL", bad, len(means)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
