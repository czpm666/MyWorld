"""What the crop palette comes out as once it is matched in luminance.

The near belt has to read as one landscape under one sun: a mosaic of hues, not
of brightnesses.  This prints the authored colour and the value the carpet will
actually hand the shader, so the mix can be judged without a render.

    python look/_land_pal.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import _land_stub

_land_stub.install()

import numpy as np

import hd_landscape as LS
import hd_landscape_fields as FLD


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1.0 / 2.4) - 0.055)


def main():
    print("%-9s %-9s %-18s %-18s %-18s %s"
          % ("crop", "hex", "linear", "matched", "sRGB of matched", "lum"))
    for k, v in FLD.CROPS.items():
        base = np.asarray(LS.rgb(v["col"]), dtype=np.float64)
        if not base.any():
            continue
        lum = base[0] * 0.30 + base[1] * 0.59 + base[2] * 0.11
        k2 = (0.16 / max(lum, 1e-4)) ** 0.45 * 0.85
        c = base * k2
        s = lin_to_srgb(c)
        print("%-9s %-9s (%5.3f %5.3f %5.3f) (%5.3f %5.3f %5.3f) "
              "(%5.3f %5.3f %5.3f) %.3f"
              % (k, v["col"],
                 base[0], base[1], base[2], c[0], c[1], c[2], s[0], s[1], s[2],
                 lum))


if __name__ == "__main__":
    main()
