"""_surf_stats.py -- the numeric referee for hd_surface.py A/B renders.

Computes exactly the quantities the visual QC quotes, so a claim like "more
natural" can be replaced by a before -> after delta:

  * Rec.709 luma mean of the whole frame and of named regions
  * local-mean std at 8 / 16 / 32 / 64 px (the "per-block relief" proxy)
    and the CV ratio after/before at each window
  * greenness = G - (R+B)/2 in sRGB bytes, count of pixels above 8
  * the signed difference histogram (p01 / p50 / p99)
  * best off-position NCC for 96x96 tiles (tiling-repeat detector)

Regions are FRACTIONS of the frame, so the same preset works at 800x450 and
1600x900.  Two presets exist: "hero" (the 1600x900 A/B frame the QC used) and
"close" (the 800x450 closeup).

USAGE
    python _surf_stats.py BEFORE.png AFTER.png [--label NAME] [--preset hero|close]
    python _surf_stats.py ONE.png [--preset close]        # single-image report
"""

import argparse
import json
import os

import numpy as np
from PIL import Image

R709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)

# fractional boxes (x0, y0, x1, y1) in 0..1 of the frame
PRESETS = {
    "hero": {
        "sky":       (0.0125, 0.0111, 0.0688, 0.0778),
        "roof_blue": (0.3500, 0.0889, 0.4125, 0.1556),
        "roof_red":  (0.8688, 0.1667, 0.9375, 0.2389),
        "ground":    (0.4375, 0.9556, 0.5625, 0.9989),
        "tower":     (0.4000, 0.2667, 0.4375, 0.3333),
        "wallbase":  (0.3750, 0.9000, 0.5750, 0.9989),
        "wall":      (0.0600, 0.2200, 0.3400, 0.6200),
    },
    "close": {
        "sky":       (0.0000, 0.0000, 0.0700, 0.0800),
        "roof_blue": (0.3900, 0.1300, 0.4800, 0.2900),
        "roof_red":  (0.8000, 0.2400, 0.8700, 0.3300),
        "tower":     (0.3100, 0.4000, 0.4000, 0.5600),
        "wallbase":  (0.1500, 0.8800, 0.8500, 0.9900),
        "wall":      (0.1900, 0.6600, 0.3600, 0.8400),
        "gate":      (0.3800, 0.7500, 0.5600, 0.9000),
    },
}


def load(path):
    im = Image.open(path).convert("RGB")
    return np.asarray(im, dtype=np.float64)


def luma(rgb):
    return rgb @ R709


def _blocks(gray, win):
    h, w = gray.shape
    ch = (w // win) * win
    cv = (h // win) * win
    if ch < win or cv < win:
        return None
    g = gray[:cv, :ch]
    return g.reshape(cv // win, win, ch // win, win).mean(axis=(1, 3))


def local_mean_std(gray, win):
    """std of the win x win block-mean image (low-frequency structure)."""
    b = _blocks(gray, win)
    return float("nan") if b is None else float(b.std())


def local_contrast(gray, win):
    """mean of the per-block std (high-frequency texture at that scale)."""
    h, w = gray.shape
    ch = (w // win) * win
    cv = (h // win) * win
    if ch < win or cv < win:
        return float("nan")
    g = gray[:cv, :ch].reshape(cv // win, win, ch // win, win)
    return float(g.std(axis=(1, 3)).mean())


def local_mean_cv(gray, win):
    s = local_mean_std(gray, win)
    m = gray.mean()
    return s / m if m else float("nan")


def masonry_mask(rgb):
    """Pixels that are masonry: not sky, not a roof tile, not a window hole.

    The full-frame 32 px local-mean std is dominated by architecture -- a block
    that straddles a window opening differs from one on a flat face by tens of
    levels no matter what the material does.  Restricting the statistic to the
    stone faces is the only way to ask "does the masonry itself now have
    per-block relief", which is what the QC review is actually about.
    """
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lm = luma(rgb)
    sky = (b - r > 6) & (lm > 105) & (b > 120)           # pale blue backdrop
    blue_tile = (b - r > 14) & (b > 34) & (lm < 120)
    red_tile = (r - b > 30) & (r > 55) & (lm < 150)
    hole = lm < 28                                        # deep shadow / glass
    return ~(sky | blue_tile | red_tile | hole)


def masked_lstd(gray, win, mask, min_frac=0.55):
    """std of win x win block means over the blocks that are mostly masonry."""
    h, w = gray.shape
    ch = (w // win) * win
    cv = (h // win) * win
    if ch < win or cv < win:
        return float("nan"), 0
    g = gray[:cv, :ch].reshape(cv // win, win, ch // win, win)
    m = mask[:cv, :ch].reshape(cv // win, win, ch // win, win)
    cnt = m.sum(axis=(1, 3))
    ok = cnt >= min_frac * win * win
    if ok.sum() < 8:
        return float("nan"), int(ok.sum())
    means = (g * m).sum(axis=(1, 3)) / np.maximum(cnt, 1)
    return float(means[ok].std()), int(ok.sum())


def greenness(rgb):
    """Greenness of the acceptance test: G - max(R, B), in sRGB bytes."""
    return rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])


def greenness_soft(rgb):
    """Looser variant G - (R+B)/2; kept for continuity with the old QC pass."""
    return rgb[:, :, 1] - 0.5 * (rgb[:, :, 0] + rgb[:, :, 2])


def _box(box, shape):
    h, w = shape[:2]
    x0, y0, x1, y1 = box
    return (max(0, int(x0 * w)), max(0, int(y0 * h)),
            min(w, int(x1 * w)), min(h, int(y1 * h)))


def region_mean(gray, box):
    x0, y0, x1, y1 = box
    return float(gray[y0:y1, x0:x1].mean())


def ncc_repeat(gray, tile=96, lo=96, hi=300, step=16, npat=8):
    """Best off-position NCC between a tile and shifted copies of itself."""
    h, w = gray.shape
    if h < tile + hi or w < tile + hi:
        return None
    ys = np.linspace(0, h - tile - hi, npat).astype(int)
    xs = np.linspace(0, w - tile - hi, npat).astype(int)
    best = -1.0
    for y0 in ys:
        for x0 in xs:
            a = gray[y0:y0 + tile, x0:x0 + tile]
            a = a - a.mean()
            na = np.sqrt((a * a).sum())
            if na < 1e-6:
                continue
            for dy in range(lo, hi + 1, step):
                for dx in range(lo, hi + 1, step):
                    if y0 + dy + tile > h or x0 + dx + tile > w:
                        continue
                    b = gray[y0 + dy:y0 + dy + tile, x0 + dx:x0 + dx + tile]
                    b = b - b.mean()
                    nb = np.sqrt((b * b).sum())
                    if nb < 1e-6:
                        continue
                    v = float((a * b).sum() / (na * nb))
                    if v > best:
                        best = v
    return best


def crop_block(gb, ga, box, label="crop"):
    """The QC numbers, measured on a stone-only crop instead of the frame."""
    x0, y0, x1, y1 = box
    b = gb[y0:y1, x0:x1]
    a = ga[y0:y1, x0:x1]
    print("  %s (%d,%d)-(%d,%d)  %dx%d px" % (label, x0, y0, x1, y1,
                                              x1 - x0, y1 - y0))
    print("    mean  %8.2f -> %8.2f  (%+.2f%%)   std %7.2f -> %7.2f (%+.1f%%)"
          % (b.mean(), a.mean(), 100.0 * (a.mean() / b.mean() - 1.0),
             b.std(), a.std(), 100.0 * (a.std() / b.std() - 1.0)))
    row = []
    for win in (8, 16, 32, 64):
        sb, sa = local_mean_std(b, win), local_mean_std(a, win)
        cb, ca = local_contrast(b, win), local_contrast(a, win)
        row.append((win, sb, sa, cb, ca))
    print("    %-6s %9s %9s %8s   %9s %9s"
          % ("win", "lstd_b", "lstd_a", "ratio", "lctr_b", "lctr_a"))
    for win, sb, sa, cb, ca in row:
        print("    %-6d %9.3f %9.3f %8.3f %+6.1f%%  %9.3f %9.3f %+6.1f%%"
              % (win, sb, sa, sa / sb, 100.0 * (sa / sb - 1.0), cb, ca,
                 100.0 * (ca / cb - 1.0)))


def save_zoom(before, after, box, out, zoom=3):
    """Side-by-side before|after crop, nearest-neighbour, for eyeballing."""
    x0, y0, x1, y1 = box
    ims = []
    for p in (before, after):
        im = Image.open(p).convert("RGB").crop((x0, y0, x1, y1))
        im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
        ims.append(im)
    w, h = ims[0].size
    canvas = Image.new("RGB", (w * 2 + 8, h), (255, 0, 255))
    canvas.paste(ims[0], (0, 0))
    canvas.paste(ims[1], (w + 8, 0))
    canvas.save(out)
    print("  zoom written -> %s  (%dx%d, x%d, left=before right=after)"
          % (out, canvas.width, canvas.height, zoom))


def report(path, preset="hero", label=""):
    rgb = load(path)
    g = luma(rgb)
    out = {
        "label": label or os.path.basename(path),
        "path": path,
        "size": list(rgb.shape[1::-1]),
        "mean": round(float(g.mean()), 2),
        "std": round(float(g.std()), 2),
        "green_px": int((greenness(rgb) > 8).sum()),
    }
    for win in (8, 16, 32, 64):
        out["lstd%d" % win] = round(local_mean_std(g, win), 3)
        out["cv%d" % win] = round(local_mean_cv(g, win), 4)
        out["lctr%d" % win] = round(local_contrast(g, win), 3)
    for k, box in PRESETS[preset].items():
        b = _box(box, rgb.shape)
        if b[2] <= b[0] or b[3] <= b[1]:
            continue
        out[k] = round(region_mean(g, b), 2)
    ncc = ncc_repeat(g)
    if ncc is not None:
        out["ncc_off"] = round(ncc, 3)
    return out


def compare(before, after, preset="hero", label="", cbox=None):
    rb = load(before)
    ra = load(after)
    if rb.shape != ra.shape:
        raise SystemExit("size mismatch: %s %s" % (rb.shape, ra.shape))
    gb, ga = luma(rb), luma(ra)
    d = ga - gb
    print("=" * 84)
    print("A/B  %s   (%dx%d, preset=%s)" % (label or "", rb.shape[1], rb.shape[0], preset))
    print("  before %-40s after %s" % (os.path.basename(before), os.path.basename(after)))
    print("  frame mean   %8.2f -> %8.2f  (%+.2f%%)"
          % (gb.mean(), ga.mean(), 100.0 * (ga.mean() / gb.mean() - 1.0)))
    print("  frame diff   p01 %+.2f  p50 %+.2f  p99 %+.2f  min %+.1f max %+.1f"
          % (np.percentile(d, 1), np.percentile(d, 50), np.percentile(d, 99), d.min(), d.max()))
    print("  frame std    %8.2f -> %8.2f  (%+.2f%%)"
          % (gb.std(), ga.std(), 100.0 * (ga.std() / gb.std() - 1.0)))
    gpb, gpa = (greenness(rb) > 8), (greenness(ra) > 8)
    hpb, hpa = (greenness_soft(rb) > 8), (greenness_soft(ra) > 8)
    print("  greenness>8  G-max(R,B) %6d -> %6d (x%.2f)   G-(R+B)/2 %6d -> %6d (x%.2f)"
          % (gpb.sum(), gpa.sum(), gpa.sum() / max(1, gpb.sum()),
             hpb.sum(), hpa.sum(), hpa.sum() / max(1, hpb.sum())))
    print("  %-6s %9s %9s %8s   %9s %9s" % ("win", "lstd_b", "lstd_a", "ratio",
                                            "lctr_b", "lctr_a"))
    for win in (8, 16, 32, 64):
        b = local_mean_std(gb, win)
        a = local_mean_std(ga, win)
        cb = local_contrast(gb, win)
        ca = local_contrast(ga, win)
        print("  %-6d %9.3f %9.3f %8.3f %+6.1f%%  %9.3f %9.3f  %+.1f%%"
              % (win, b, a, a / b, 100.0 * (a / b - 1.0), cb, ca,
                 100.0 * (ca / cb - 1.0)))
    # the same statistic restricted to masonry: this is the one that answers
    # "does the stone itself now read as blocks", the frame-wide number mostly
    # measures how much window there is
    mk = masonry_mask(rb)
    print("  %-6s %9s %9s %8s   %s"
          % ("win", "mstd_b", "mstd_a", "ratio", "blocks"))
    for win in (16, 32, 64):
        b, nbk = masked_lstd(gb, win, mk)
        a, _ = masked_lstd(ga, win, mk)
        if b == b and a == a:
            print("  %-6d %9.3f %9.3f %8.3f %+6.1f%%   %d masonry blocks"
                  % (win, b, a, a / b, 100.0 * (a / b - 1.0), nbk))
    print("  %-9s %8s %8s %8s %9s %9s" % ("region", "before", "after", "d%", "grn_b", "grn_a"))
    for k, box in PRESETS[preset].items():
        b = _box(box, rb.shape)
        if b[2] <= b[0] or b[3] <= b[1]:
            continue
        x0, y0, x1, y1 = b
        vb = region_mean(gb, b)
        va = region_mean(ga, b)
        n0 = int((greenness(rb[y0:y1, x0:x1]) > 8).sum())
        n1 = int((greenness(ra[y0:y1, x0:x1]) > 8).sum())
        print("  %-9s %8.2f %8.2f %+7.2f%% %9d %6d x%.2f"
              % (k, vb, va, 100.0 * (va / vb - 1.0) if vb else 0.0, n0, n1,
                 n1 / max(1, n0)))
    nb = ncc_repeat(gb)
    na = ncc_repeat(ga)
    if nb is not None:
        print("  NCC off-position best  %.3f -> %.3f  (repeat if >= 0.7)" % (nb, na))
    if cbox is not None:
        crop_block(gb, ga, cbox)
    print("=" * 84)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after", nargs="?")
    ap.add_argument("--label", default="")
    ap.add_argument("--preset", default="auto", choices=["auto", "hero", "close"])
    ap.add_argument("--crop", default="", help="x0,y0,x1,y1 in pixels")
    ap.add_argument("--zoom", default="", help="write side-by-side crop PNG here")
    ap.add_argument("--zoom-factor", type=int, default=3)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    preset = a.preset
    if preset == "auto":
        im = Image.open(a.before)
        preset = "hero" if im.size[0] >= 1200 else "close"
    box = None
    if a.crop:
        box = tuple(int(v) for v in a.crop.split(","))
        if len(box) != 4:
            raise SystemExit("--crop needs x0,y0,x1,y1")
    if a.after:
        compare(a.before, a.after, preset, a.label, box)
        if a.zoom:
            if box is None:
                raise SystemExit("--zoom needs --crop")
            save_zoom(a.before, a.after, box, a.zoom, a.zoom_factor)
        if a.json:
            with open(a.json, "w") as f:
                json.dump({"before": report(a.before, preset, "before"),
                           "after": report(a.after, preset, "after")}, f, indent=1)
    else:
        print(json.dumps(report(a.before, preset, a.label), indent=1))


if __name__ == "__main__":
    main()
