"""Isolate the black-sky wide shot: same bench, three ways.

    python look\\_wide_diag.py

Writes `_diag_nopost.png`, `_diag_post_noap.png` and `_diag_post_ap.png`.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)


def inside():
    import sky_lab
    for tag, ap in (("nopost", None), ("post_noap", False), ("post_ap", True)):
        sc, cfg = sky_lab.wide_bench("morning_town", ap=ap)
        out = os.path.join(sky_lab.OUT, "_diag_%s.png" % tag)
        sky_lab._render(sc, out)
        print("[diag] %-10s sky=%s ground=%s" % (
            tag, sky_lab._px(out, [(0.5, 0.95)])[0][0],
            sky_lab._px(out, [(0.5, 0.10)])[0][0]))
    return 0


if __name__ == "__main__":
    sys.exit(inside())
