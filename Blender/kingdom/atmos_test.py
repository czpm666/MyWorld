"""atmos_test.py - apply the atmosphere to the saved capital, render, and grade itself.

    blender -b "E:/My World/Blender/renders/kingdom/capital_full.blend" \
        --python atmos_test.py -- --preset golden_hour --shot ars_overview

    # every preset, full key-art res, with the pass/fail table
    blender -b capital_full.blend --python atmos_test.py -- --preset all --samples 192

    # converge exposure for every preset (cheap renders, prints a paste-ready block)
    blender -b capital_full.blend --python atmos_test.py -- --preset all --autocal

Self-check thresholds (all measured on the written PNG, display space 0..255):
    overexposed  pixels >= 250 must be < 2 %      (was 42.8 % in the v2 golden_hour)
    city band    std of luminance >= 18          (was 2.63)
    horizon      frame top-edge elevation > 0 deg (was -7.97, i.e. no horizon at all)
    sky gradient brighter toward the horizon     (v2 darkened toward it)
    stripes      no vertical high-pass spikes in the sky band (the default-Streaks glare)
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy
import hd_atmosphere as A

# framing: pitch must stay under the half vertical FOV or the horizon leaves the frame.
# 34 mm / z330 gave pitch 24.55 deg vs half-FOV 16.58 -> 7.97 deg of frame above nothing.
# 28 mm / z138 gives pitch 10.05 vs 19.88 -> horizon at 24.7 % of the frame.
SHOTS = {
    "ars_overview": dict(loc=(430.0, -560.0, 138.0), look=(0.0, 20.0, 10.0), lens=32.0),
    "ars_street": dict(loc=(0.0, -168.0, 1.75), look=(0.0, -262.0, 2.6), lens=26.0),
    "ars_plaza": dict(loc=(36.0, -34.0, 6.2), look=(0.0, 20.0, 7.5), lens=34.0),
    "ars_castle": dict(loc=(150.0, -60.0, 120.0), look=(-10.0, 190.0, 40.0), lens=40.0),
    "ars_gate": dict(loc=(10.0, -390.0, 12.0), look=(0.0, -300.0, 12.0), lens=42.0),
    "ars_harbour": dict(loc=(-40.0, -250.0, 26.0), look=(10.0, -350.0, 2.0), lens=40.0),
}

OUT_DIR = "E:/My World/Blender/renders/kingdom"

CHECK = dict(over_max=2.0, city_sigma_min=18.0, stripe_max=25.0,
             skyinv_max=14.0, dwb_min=6.0)


def arg(name, default=None):
    if "--" not in sys.argv:
        return default
    a = sys.argv[sys.argv.index("--") + 1:]
    if name in a:
        i = a.index(name)
        if i + 1 < len(a):
            return a[i + 1]
    return default


def flag(name):
    return "--" in sys.argv and name in sys.argv[sys.argv.index("--") + 1:]


def measure(path):
    """Load the written PNG as raw display values (no sRGB->linear decode)."""
    import numpy as np
    im = bpy.data.images.load(path, check_existing=False)
    try:
        im.colorspace_settings.name = "Non-Color"
    except Exception:                                             # noqa: BLE001
        pass
    w, h = im.size
    px = np.array(im.pixels[:], dtype="f4")
    a = px.reshape(h, w, 4)[::-1, :, :3] * 255.0          # row 0 = top of frame
    bpy.data.images.remove(im)
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    return a, lum


def evaluate(path, cam, name):
    import numpy as np
    a, lum = measure(path)
    h, w = lum.shape
    geo = A.horizon_row(cam, w, h)
    hy = geo["row"]

    over = float((lum >= 250.0).mean() * 100.0)
    clip = float((lum >= 254.5).mean() * 100.0)

    r0 = int(min(max(hy + 0.04 * h, 0), h - 8))
    r1 = int(0.95 * h)
    city = lum[r0:r1, :] if r1 > r0 + 4 else lum[int(0.5 * h):int(0.95 * h), :]
    city_sigma = float(city.std())
    city_mean = float(city.mean())

    sky_r1 = int(max(min(hy - 2, h - 2), 12))
    sky = lum[0:sky_r1, :]
    sky_mean = float(sky.mean()) if sky.size else 0.0
    sky_sigma = float(sky.std()) if sky.size else 0.0
    # gradient: compare the row just above the horizon with the top row
    top = float(lum[max(0, min(4, h - 1)), :].mean())
    near_h = float(lum[max(0, sky_r1 - 6), :].mean()) if sky_r1 > 8 else top
    d_lum = near_h - top
    near_wb = float((a[max(0, sky_r1 - 6), :, 0] - a[max(0, sky_r1 - 6), :, 2]).mean()) \
        if sky_r1 > 8 else 0.0
    top_wb = float((a[max(0, min(4, h - 1)), :, 0] - a[max(0, min(4, h - 1)), :, 2]).mean())
    d_wb = near_wb - top_wb
    # vertical-stripe detector on the sky band
    if sky.shape[0] > 2 and sky.shape[1] > 8:
        hp = sky[:, 1:-1] - 0.5 * (sky[:, :-2] + sky[:, 2:])
        stripe = float(np.percentile(np.abs(hp), 99.9))
    else:
        stripe = 0.0

    fails = []
    if over >= CHECK["over_max"]:
        fails.append("over%.2f" % over)
    if city_sigma < CHECK["city_sigma_min"]:
        fails.append("sigma%.1f" % city_sigma)
    if geo["top_deg"] <= 0.0:
        fails.append("nohorizon%.1f" % geo["top_deg"])
    if d_lum <= -CHECK["skyinv_max"]:
        fails.append("skyinv%.1f" % d_lum)
    if d_wb < CHECK["dwb_min"]:
        fails.append("skycold%.1f" % d_wb)
    if stripe > CHECK["stripe_max"]:
        fails.append("stripe%.1f" % stripe)

    return dict(name=name, mean=float(lum.mean()), over=over, clip=clip,
                city_sigma=city_sigma, city_mean=city_mean, sky_mean=sky_mean,
                sky_sigma=sky_sigma, horizon_y=hy, horizon_pct=100.0 * hy / h,
                top_deg=geo["top_deg"], pitch=geo["pitch"], dlum=d_lum, dwb=d_wb,
                stripe=stripe, ok=not fails, fails=fails, w=w, h=h)


def row_str(r):
    return ("  %-13s mean%6.1f  over%5.2f%%  clip%5.2f%%  city%5.1f/mean%6.1f  "
            "sky%6.1f sd%5.1f  hor%5.1f(%4.1f%%)  top%+6.2f  dLum%+6.1f  dWB%+5.1f  str%5.1f  %s"
            % (r["name"], r["mean"], r["over"], r["clip"], r["city_sigma"], r["city_mean"],
               r["sky_mean"], r["sky_sigma"], r["horizon_y"], r["horizon_pct"],
               r["top_deg"], r["dlum"], r["dwb"], r["stripe"],
               "PASS" if r["ok"] else "FAIL " + ",".join(r["fails"])))


def shoot(preset, shot, samples, res, out, cpu=False, quiet=False):
    A.LOG = not quiet
    A.apply(preset, samples=samples, res=res, gpu=not cpu)
    s = SHOTS.get(shot, SHOTS["ars_overview"])
    A.render(out, s["loc"], s["look"], lens=s["lens"])
    cam = bpy.data.objects.get("BeautyCam")
    A.LOG = True
    return evaluate(out, cam, preset)


def autocal(preset, shot, targets=6, cpu=False):
    """Bisect the exposure key until the frame lands at the target brightness."""
    import math
    tel = A.PRESETS[preset]
    tmp = os.path.join(os.environ.get("TEMP", "."), "atmos_cal.png")
    best = None
    for it in range(targets):
        r = shoot(preset, shot, 48, (480, 270), tmp, cpu=cpu, quiet=True)
        err = math.log2(118.0 / max(1.0, r["mean"])) if r["mean"] > 1e-6 else 1.0
        if err > -0.06 and err < 0.10 and r["over"] < 1.2:
            best = r
            break
        tel["exposure"] = round(tel["exposure"] + max(-0.55, min(0.55, err * 0.8)), 3)
        best = r
    print("  CAL %-13s exposure=%+.3f  mean=%.1f over=%.2f%% city_sd=%.1f %s"
          % (preset, tel["exposure"], best["mean"], best["over"], best["city_sigma"],
             "PASS" if best["ok"] else "FAIL " + ",".join(best["fails"])), flush=True)
    return tel["exposure"]


def main():
    preset = arg("--preset", "golden_hour")
    shot = arg("--shot", "ars_overview")
    samples = int(arg("--samples", "192"))
    res = (int(arg("--w", "1600")), int(arg("--h", "900")))
    cpu = flag("--cpu")
    do_cal = flag("--autocal")

    names = list(A.PRESETS.keys()) if preset == "all" else [preset]

    if do_cal:
        print("[test] autocal on %d preset(s)" % len(names), flush=True)
        conv = {}
        for n in names:
            conv[n] = autocal(n, shot, cpu=cpu)
        print("[test] paste-ready:\n" + "\n".join(
            '    "%s": %+.2f,' % (k, v) for k, v in conv.items()), flush=True)
        return

    results = []
    for n in names:
        # The "_chk_" prefix is deliberate: these are 480x270 self-check frames,
        # never the delivered key art.  Without it the default name collides with
        # the real render (atmos_<shot>_<preset>.png) and silently overwrites it,
        # which makes it impossible to tell "which picture goes with which model"
        # by mtime afterwards.
        out = arg("--out") if (arg("--out") and len(names) == 1) else \
            os.path.join(OUT_DIR, "_chk_atmos_%s_%s.png" % (shot, n))
        r = shoot(n, shot, samples, res, out, cpu=cpu, quiet=len(names) > 1)
        results.append(r)
        print("[test] wrote %s" % out, flush=True)
        print(row_str(r), flush=True)

    if len(results) > 1:
        print("\n[test] ---- summary ----", flush=True)
        for r in results:
            print(row_str(r), flush=True)
    nfail = sum(0 if r["ok"] else 1 for r in results)
    print("[atmos] selfcheck %s  (%d/%d pass)" %
          ("PASS" if nfail == 0 else "FAIL", len(results) - nfail, len(results)), flush=True)
    if nfail:
        sys.exit(1)


if __name__ == "__main__":
    main()
