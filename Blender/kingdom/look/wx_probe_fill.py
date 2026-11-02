"""Calibration sweep for `cfg["sky_fill"]` (the dome fill card above the town).

The question this answers with numbers instead of taste: how much shadow fill
does it take for the 52-degree gameplay frame to clear the brief's floor
(shadowed paving >= 35/255) without flattening a clear morning?

    python look/export_run.py wx_fill 900 LIGHT -- -b --factory-startup \
        --python look/wx_probe_fill.py
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
import hd_weather as W                                 # noqa: E402
import render as R                                     # noqa: E402
import weather_lab as WL                               # noqa: E402

OUT = r"E:\My World\Blender\renders\kingdom\look"
RES = (480, 270)
SAMPLES = 8
TOWN = None


def measure(path):
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        a = buf.reshape(h, w, 4)[::-1, :, :3]
    finally:
        bpy.data.images.remove(img)
    rgb = a * 255.0
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    hh = lum.shape[0]
    gnd = lum[int(hh * 0.45):]
    return dict(mean=round(float(lum.mean()), 1),
                p05=round(float(np.percentile(lum, 5)), 1),
                p50=round(float(np.percentile(lum, 50)), 1),
                p90=round(float(np.percentile(lum, 90)), 1),
                gnd_p10=round(float(np.percentile(gnd, 10)), 1),
                gnd_p25=round(float(np.percentile(gnd, 25)), 1),
                gnd_p50=round(float(np.percentile(gnd, 50)), 1),
                dead=round(float((lum < 8.0).mean()) * 100.0, 2),
                shadow=round(float((lum <= 0.30 * np.percentile(lum, 90)).mean())
                             * 100.0, 2))


def shot(state, fill, name, cam="accept", **over):
    sc = bpy.context.scene
    spec = WL._cam_specs()[cam]
    eye, look = spec["loc"], spec["look"]
    center = spec.get("center", (0.0, -30.0))
    R.wipe_rig()
    W.reset_materials()
    W.clear()
    R.build_rig("morning_town", 32.0, 112.0, haze=False,
                cam=(eye[0], eye[1]), sky="morning_town", ambient=0.38,
                exposure=-2.20)
    cfg = W.state(state, sky_fill=fill, **over)
    W.build(sc, cfg, center=center, radius=320.0, seed=9, eye=eye,
            ground_z=0.02, look=look)
    W.apply_atmos(sc, cfg, center=center, extent=1800.0)
    W.apply_materials(TOWN[1], cfg)
    sc.view_settings.exposure = -2.20
    camob = H.camera("sweep_cam", eye, look, lens=spec["lens"])
    path = os.path.join(OUT, "wx_fill_%s_%s_%02d.png"
                        % (state, name, int(round(fill * 100))))
    H.render_to(path, camob)
    st = measure(path)
    st.update(state=state, fill=fill, name=name, path=path)
    bpy.data.objects.remove(camob, do_unlink=True)
    print("[fill] %-6s %-5s fill=%.2f mean=%5.1f p50=%5.1f gnd_p10=%5.1f "
          "gnd_p25=%5.1f dead=%4.1f%%" % (state, name, fill, st["mean"], st["p50"],
                                           st["gnd_p10"], st["gnd_p25"], st["dead"]),
          flush=True)
    return st


def main():
    global TOWN
    TOWN = WL._town()
    R.setup_engine("eevee", samples=SAMPLES, res=RES)
    rows = []
    for fill in (0.0, 0.15, 0.30, 0.45):
        rows.append(shot("clear", fill, "accept"))
    for fill in (0.0, 0.17, 0.34, 0.50):
        rows.append(shot("rain", fill, "accept"))
    print("[fill] --- sweep ---", flush=True)
    for r in rows:
        print("[fill] %-6s fill=%.2f mean=%5.1f p05=%5.1f p50=%5.1f p90=%5.1f "
              "gnd_p10=%5.1f gnd_p25=%5.1f dead=%4.1f%%"
              % (r["state"], r["fill"], r["mean"], r["p05"], r["p50"], r["p90"],
                 r["gnd_p10"], r["gnd_p25"], r["dead"]), flush=True)
    with open(os.path.join(OUT, "_wx_fill_sweep.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    print("[fill] done", flush=True)


if __name__ == "__main__":
    main()
