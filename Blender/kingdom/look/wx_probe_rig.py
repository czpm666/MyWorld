"""Probe: how far is the weather lab's light rig from the main render's?

The complaint is that `WX_accept_clear/rain.png` are ~2 stops darker than a
`look/render.py` shot of the same city.  Two candidate causes:

  A. the lab never calls the main rig at all -- it only calls `hd_light.post()`
     once and lets `hd_weather.apply_atmos()` drive sky/sun/exposure, so it
     misses everything `render.build_rig()` does before the weather is applied;
  B. the scene content (a paving-dominated 52 deg frame) is simply darker than
     a roof-dominated city shot, and the ~2 stops are a framing illusion.

This probe renders the *same lab town, same camera, same state* twice: once
through the current lab path, once through `render.build_rig()` verbatim (the
main renderer's own function), and prints the measured luminance of both.

    python look/export_run.py wx_probe 900 LIGHT -- -b --factory-startup \
        --python look/wx_probe_rig.py
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_KING, os.path.dirname(_KING), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                              # noqa: E402

import hd_common as H                                  # noqa: E402
import hd_light as L                                   # noqa: E402
import hd_weather as W                                 # noqa: E402
import render as R                                     # noqa: E402
import weather_lab as WL                               # noqa: E402

OUT = r"E:\My World\Blender\renders\kingdom\look"
RES = (480, 270)
SAMPLES = 8


def _lin(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def measure(path):
    """Luminance percentiles + the linear mean (for a stop comparison)."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        a = buf.reshape(h, w, 4)[::-1, :, :3]          # blender is bottom-up
    finally:
        bpy.data.images.remove(img)
    rgb = a * 255.0
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    p = [float(np.percentile(lum, q)) for q in (5, 10, 25, 50, 75, 90, 95)]
    mean = float(lum.mean())
    lin = np.vectorize(_lin)(rgb).mean()
    hh = lum.shape[0]
    top = lum[:int(hh * 0.25)]
    bot = lum[int(hh * 0.40):]
    return dict(
        path=path, w=w, h=h, mean=round(mean, 1),
        linmean=round(float(lin), 5),
        p05=round(p[0], 1), p10=round(p[1], 1), p25=round(p[2], 1),
        p50=round(p[3], 1), p75=round(p[4], 1), p90=round(p[5], 1),
        p95=round(p[6], 1),
        sky_p50=round(float(np.percentile(top, 50)), 1),
        ground_p10=round(float(np.percentile(bot, 10)), 1),
        ground_p50=round(float(np.percentile(bot, 50)), 1),
        dead=round(float((lum < 8.0).mean()) * 100.0, 2),
        shadow=round(float((lum <= 0.30 * p[5]).mean()) * 100.0, 2),
    )


def shot(cam_spec, name, mode, state, elev=32.0):
    """One render: `mode` = 'lab' (current weather_lab) or 'main' (build_rig)."""
    sc = bpy.context.scene
    R.wipe_rig()
    W.reset_materials()
    W.clear()
    eye = cam_spec["loc"]
    look = cam_spec["look"]
    center = cam_spec.get("center", (0.0, -30.0))
    cfg = W.state(state)
    if mode == "lab":
        # exactly what weather_lab.py does today
        L.post("morning_town", sc)
        W.build(sc, cfg, center=center, radius=320.0, seed=9, eye=eye,
                ground_z=0.02, look=look)
        W.apply_atmos(sc, cfg, center=center, extent=1800.0)
        W.apply_materials(TOWN[1], cfg)
    else:
        # exactly what look/render.py does for a --weather shot
        R.build_rig("morning_town", elev, 112.0, haze=False, cam=(eye[0], eye[1]),
                    sky="morning_town", ambient=0.38, exposure=-2.20)
        W.build(sc, cfg, center=center, radius=320.0, seed=9, eye=eye,
                ground_z=0.02, look=look)
        W.apply_atmos(sc, cfg, center=center, extent=1800.0)
        W.apply_materials(TOWN[1], cfg)
        sc.view_settings.exposure = -2.20
    cam = H.camera("probe_cam", eye, look, lens=cam_spec["lens"])
    path = os.path.join(OUT, "wx_probe_%s_%s_%s.png" % (mode, state, name))
    H.render_to(path, cam)
    st = measure(path)
    st["mode"] = mode
    st["state"] = state
    st["exposure"] = round(float(sc.view_settings.exposure), 3)
    bpy.data.objects.remove(cam, do_unlink=True)
    print("[probe] %-5s %-6s mean=%5.1f p50=%5.1f p90=%5.1f dead=%4.1f%% exp=%+.2f"
          % (mode, state, st["mean"], st["p50"], st["p90"], st["dead"],
             st["exposure"]), flush=True)
    return st


TOWN = None


def main():
    global TOWN
    TOWN = WL._town()
    print("[probe] town parts=%d tris=%d" % (len(TOWN[0]), H.tri_count(TOWN[0])),
          flush=True)
    R.setup_engine("eevee", samples=SAMPLES, res=RES)
    spec = WL._cam_specs()
    rows = []
    # the acceptance camera: the 52 deg gameplay framing, no sky in frame
    for state in ("clear", "rain"):
        rows.append(shot(spec["accept"], "accept", "lab", state))
        rows.append(shot(spec["accept"], "accept", "main", state))
    # the sheet camera: sky in the top fifth, so "sky display value" is real
    for mode in ("lab", "main"):
        rows.append(shot(spec["wide"], "wide", mode, "clear"))
    print("[probe] --- summary ---", flush=True)
    by = {}
    for r in rows:
        by[(r["state"], r["mode"], r["path"].rsplit("_", 2)[-2])] = r
    for r in rows:
        print("[probe] %-6s %-5s mean=%5.1f lin=%7.5f p05=%5.1f p50=%5.1f "
              "sky_p50=%5.1f gnd_p10=%5.1f" % (r["state"], r["mode"], r["mean"],
                                               r["linmean"], r["p05"], r["p50"],
                                               r["sky_p50"], r["ground_p10"]),
              flush=True)
    for state in ("clear", "rain"):
        a = [r for r in rows if r["state"] == state and r["mode"] == "lab"][0]
        b = [r for r in rows if r["state"] == state and r["mode"] == "main"][0]
        import math
        d = 20.0 * math.log10(max(1e-9, b["linmean"]) / max(1e-9, a["linmean"]))
        print("[probe] %-6s main/lab = %+.2f stops (linear mean %.5f -> %.5f)"
              % (state, d, a["linmean"], b["linmean"]), flush=True)
    with open(os.path.join(OUT, "_wx_probe_rig.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    print("[probe] done", flush=True)


if __name__ == "__main__":
    main()
