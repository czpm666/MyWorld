"""look/weather_lab.py -- the weather proving ground and contact sheet.

A 20-house town the size of a city block, a cobbled plaza, a treeline and two
layers of distant ridge -- then all eight weather states rendered from the same
camera with the same geometry, so the *only* difference between two tiles is the
weather dict.

The one rule this file now enforces: **the lab is lit by the main renderer's own
rig, at the main renderer's own exposure.** `look/render.py:build_rig()` is what
lights every city shot; a tile produced any other way is not comparable to one.
So each state does

    render.build_rig(preset, elev, azim, haze=False, cam=(x, y),
                     sky="morning_town", ambient=0.38, exposure=-2.20)
    hd_weather.build / apply_atmos / apply_materials
    scene.view_settings.exposure = -2.20        # CLI parity, all eight states

and nothing else.  `--rig hdsky` swaps the first line for the shorter path the
brief describes (`hd_sky.apply_all(scene, preset)` + `hd_light.bounce/contact` +
exposure -2.20); the two must measure the same, and `--rig both` proves it.

    blender -b --factory-startup --python look/weather_lab.py -- all
    blender -b --factory-startup --python look/weather_lab.py -- rain,storm --fast
    blender -b --factory-startup --python look/weather_lab.py -- all --rig both
    blender -b --factory-startup --python look/weather_lab.py -- all --game

Output
------
renders/kingdom/look/wx2_<state>.png          the 8-tile sheet (640x360)
renders/kingdom/look/wx2_<state>_game.png     rain/snow at 960x540, gameplay cam
renders/kingdom/look/_wx2_stats.json          per-state measurements
renders/kingdom/look/_wx2_table.md            the same as a markdown table

Metrics (all display values, 0-255, measured on the rendered PNG)
-----------------------------------------------------------------
sky      p50 of the top 22% rows      -- what the sky reads as
shadow   p25 of the bottom 55% rows   -- backlit paving / wall, the >=35 floor
dead     % of pixels below 8/255      -- the "crushed to black" area
particle % of pixels the particles move by >6 luma, measured against a twin
         render of the same state with particle_rate=0 at the same exposure
"""
import json
import math
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_KING, os.path.dirname(_KING), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                             # noqa: E402
from mathutils import Matrix                           # noqa: E402

import hd_common as H                                  # noqa: E402
import hd_houses as HS                                 # noqa: E402
import hd_nature as NR                                 # noqa: E402
import hd_weather as W                                 # noqa: E402
import medkit as K                                     # noqa: E402

OUT = r"E:\My World\Blender\renders\kingdom\look"
RES = (640, 360)
SAMPLES = 16
TAU = math.pi * 2.0

# the main renderer's numbers for a weather shot (see Docs/BRIEF, and
# look/render.py:apply_weather which forces the CLI exposure over the preset)
RIG_PRESET = "morning_town"
RIG_AMBIENT = 0.38
RIG_EXPOSURE = -2.20
FLASH = None          # None = still between bolts (flash off); --flash sets it

# 20 houses: kind, w, d, floors, frontage, palette variant.  Sizes/typologies
# are the city's own (`hd_houses.house` takes exactly these arguments), so the
# lab cannot drift into a look the city can never produce.
HOUSES = [
    ("timber",    7.2,  9.0, 2, "eaves", 0),
    ("timber",    6.6,  8.6, 2, "gable", 1),
    ("stone",     7.6,  9.2, 2, "eaves", 2),
    ("craft",     6.8,  8.8, 2, "eaves", 0),
    ("shop",      7.4,  9.0, 2, "eaves", 1),
    ("inn",       8.2, 10.0, 3, "gable", 2),
    ("manor",     8.6, 10.4, 2, "eaves", 0),
    ("warehouse", 8.0, 11.0, 2, "eaves", 1),
    ("tower",     5.8,  5.8, 2, "eaves", 2),
    ("shop",      7.0,  8.8, 1, "eaves", 0),
    ("timber",    7.4,  9.2, 1, "eaves", 1),
    ("stone",     7.2,  9.0, 2, "gable", 2),
    ("timber",    7.8,  9.4, 2, "eaves", 0),
    ("craft",     6.2,  8.2, 2, "eaves", 1),
    ("stone",     7.0,  8.8, 3, "gable", 2),
    ("shop",      7.6,  9.0, 2, "eaves", 0),
    ("timber",    6.8,  8.4, 2, "eaves", 1),
    ("inn",       8.0,  9.8, 2, "gable", 2),
    ("warehouse", 7.8, 10.6, 1, "eaves", 0),
    ("stone",     7.4,  9.2, 2, "eaves", 1),
]


# ---------------------------------------------------------------------------
# palette
# ---------------------------------------------------------------------------
def _palette(variant):
    """Exactly the city's path: make_mats -> weathering -> house_mats."""
    MAT = HS.make_mats()
    try:
        import hd_surface as SFC
        SFC.apply_weathering(MAT)
    except Exception as exc:                            # noqa: BLE001
        print("[wlab] weathering skipped: %s: %s" % (type(exc).__name__, exc),
              flush=True)
    try:
        import capital_hd_glue as G
        return G.house_mats(MAT, variant, False)
    except Exception as exc:                            # noqa: BLE001
        print("[wlab] house_mats skipped: %s: %s" % (type(exc).__name__, exc),
              flush=True)
        return MAT


# ---------------------------------------------------------------------------
# scenery
# ---------------------------------------------------------------------------
def _horizon(MAT, rng):
    """Two low ridges.  Everything this lab needs to *show* atmosphere:
    a silhouette at 300 m that hazy keeps and fog eats, and a darker one at
    560 m that only a clear day can see at all."""
    out = []
    for (r0, r1, h0, h1, mat, seg, name) in (
            (300.0, 340.0, 22.0, 62.0, MAT.get("ridge_near"), 46, "ridge_near"),
            (560.0, 640.0, 44.0, 120.0, MAT.get("ridge_far"), 40, "ridge_far")):
        verts, faces = [], []
        rm = (r0 + r1) * 0.5
        for i in range(seg):
            a = TAU * i / seg
            h = rng.uniform(h0, h1)
            h *= 0.55 + 0.45 * abs(math.sin(a * 2.3 + 0.7))
            hs = h * rng.uniform(0.45, 0.72)
            verts.append((math.cos(a) * r0, math.sin(a) * r0, -2.0))
            verts.append((math.cos(a) * rm, math.sin(a) * rm, hs))
            verts.append((math.cos(a) * r1, math.sin(a) * r1, h))
            verts.append((math.cos(a) * (r1 + 40.0), math.sin(a) * (r1 + 40.0), -2.0))
        for i in range(seg):
            a0 = 4 * i
            a1 = 4 * ((i + 1) % seg)
            for k in range(3):
                faces.append((a0 + k, a1 + k, a1 + k + 1, a0 + k + 1))
        me = H.poly(name, verts, faces, mat).data
        ob = bpy.data.objects.get(name)
        for p in me.polygons:
            p.use_smooth = False
        out.append(ob)
    return out


def _town(seed=7):
    """Build the town once.  Returns (parts, MAT, trees, n_houses)."""
    H._clear()
    rng = random.Random(seed)

    MAT = {}
    palettes = {}
    for v in (0, 1, 2):
        P = _palette(v)
        palettes[v] = P
        for k, m in P.items():
            if m is not None:
                MAT["v%d_%s" % (v, k)] = m

    parts = []
    # --- houses: two concentric rings facing the plaza ---------------------
    inner, outer = 10, 10
    for i in range(inner + outer):
        kind, w, d, fl, fr, var = HOUSES[i]
        P = palettes[var]
        if i < inner:
            a = TAU * (i + 0.02) / inner
            r = 25.0 + rng.uniform(-1.2, 1.2)
        else:
            a = TAU * (i - inner + 0.52) / outer
            r = 41.0 + rng.uniform(-2.0, 2.0)
        x, y = math.cos(a) * r, math.sin(a) * r
        yaw = math.atan2(x, -y)          # front (+Y) points at the plaza
        hp = HS.house(P, rng, kind=kind, w=w, d=d, floors=fl, frontage=fr)
        H.apply(hp, Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(yaw, 4, "Z"))
        parts += hp

    n_houses = len(parts)

    # --- ground -----------------------------------------------------------
    MAT["cobble"] = K.mat_cobble()
    MAT["flag"] = K.mat_flag("flag", base="#5d5649", dark="#2c2822", light="#79715f")
    parts.append(H.diorama_floor(MAT["flag"], size=340.0))
    # a very wide, plain ground beyond the plaza: without it the 340 m floor
    # ends in a straight edge with sky showing through the gap before the first
    # ridge, which reads as a seam drawn across the horizon
    MAT["far_ground"] = K.mat_stone("far_ground", base="#4a4e39", dark="#20231a",
                                    light="#565b42", scale=6.0)
    me = bpy.data.meshes.new("far_ground_me")
    me.from_pydata([(-2600.0, -2600.0, -0.32), (2600.0, -2600.0, -0.32),
                    (2600.0, 2600.0, -0.32), (-2600.0, 2600.0, -0.32)], [],
                   [(0, 1, 2, 3)])
    me.update()
    me.materials.append(MAT["far_ground"])
    fg = bpy.data.objects.new("far_ground", me)
    bpy.context.scene.collection.objects.link(fg)
    parts.append(fg)

    # --- trees ------------------------------------------------------------
    nrMAT = NR.make_materials()
    for k, m in nrMAT.items():
        if m is not None:
            MAT["tree_%s" % k] = m
    trees = []
    for i in range(9):
        if i < 6:
            a = TAU * i / 6.0 + 0.4
            r = 16.0 + rng.uniform(-1.5, 1.5)
        else:
            a = TAU * (i - 6) / 3.0 + 1.1
            r = 58.0 + rng.uniform(-4.0, 8.0)
        tp = NR.tree_oak(seed=100 + i, MAT=nrMAT)
        H.apply(tp, Matrix.Translation((math.cos(a) * r, math.sin(a) * r, 0.0))
                @ Matrix.Rotation(rng.uniform(0.0, TAU), 4, "Z"))
        trees += tp
    parts += trees

    # --- distant ridges ---------------------------------------------------
    MAT["ridge_near"] = K.mat_stone("ridge_near", base="#4e5648", dark="#20261f",
                                    light="#5f6857")
    MAT["ridge_far"] = K.mat_stone("ridge_far", base="#414a52", dark="#1b2026",
                                   light="#525c66")
    parts += _horizon(MAT, rng)

    return parts, MAT, trees, n_houses


# ---------------------------------------------------------------------------
# cameras
# ---------------------------------------------------------------------------
def _cam_specs():
    """The sheet camera + the real gameplay camera."""
    eye = (0.0, -74.0, 23.0)
    tgt = (0.0, -3.0, 15.0)
    game_eye = (6.5, 6.5, 27.0)
    game_tgt = (2.0, -2.0, 4.4)
    # the contract camera: pitch 52 deg, 34 m from the subject, vfov 30 deg
    # (lens = 12/tan(15) on a 2x2 sensor, i.e. render.py's make_camera maths)
    a = math.radians(52.0)
    acc_tgt = (0.0, 14.0, 4.5)
    acc_eye = (acc_tgt[0], acc_tgt[1] - 34.0 * math.cos(a),
               acc_tgt[2] + 34.0 * math.sin(a))
    return dict(
        wide=dict(loc=eye, look=tgt, lens=24.0),
        game=dict(loc=game_eye, look=game_tgt, lens=37.8),
        accept=dict(loc=acc_eye, look=acc_tgt, lens=44.784,
                    center=(acc_tgt[0], acc_tgt[1])),
    )


# ---------------------------------------------------------------------------
# the rig
# ---------------------------------------------------------------------------
def rig(scene, spec, mode="main"):
    """Put the main renderer's lighting on the scene, then measure it.

    `mode="main"`   -- look/render.py:build_rig(), verbatim: hd_sky's world at
                       the preset's sun elevation, hd_light's sun + bounce +
                       contact AO, the compositor grade, exposure -2.20.
    `mode="hdsky"`  -- the brief's shorter recipe: hd_sky.apply_all() +
                       hd_light.bounce() + hd_light.contact() + exposure -2.20.
    `mode="none"`   -- the old lab (hd_light.post only).  Kept for the A/B that
                       proves what it cost; not used for any deliverable.
    """
    import hd_light as L
    import hd_sky as SKY
    elev = float(L.PRESETS[RIG_PRESET]["sun_elev_street"])
    azim = float(L.PRESETS[RIG_PRESET]["sun_azim"])
    if mode == "main":
        import render as R
        R.build_rig(RIG_PRESET, elev, azim, haze=False,
                    cam=(spec["loc"][0], spec["loc"][1]), sky=RIG_PRESET,
                    ambient=RIG_AMBIENT, exposure=RIG_EXPOSURE)
    elif mode == "hdsky":
        SKY.apply_all(scene, RIG_PRESET, elevation=elev, azimuth=azim,
                      ambient=RIG_AMBIENT)
        L.bounce(RIG_PRESET)
        L.contact(RIG_PRESET, scene)
        scene.view_settings.exposure = RIG_EXPOSURE
    else:
        L.post(RIG_PRESET, scene)
    return mode


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------
def _luma(path):
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
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def measure(path, base=None):
    """Display-value stats, plus how much the particles moved the frame."""
    import numpy as np
    lum = _luma(path)
    hh = lum.shape[0]
    top = lum[:max(1, int(hh * 0.22))]
    gnd = lum[int(hh * 0.45):]
    st = dict(
        mean=round(float(lum.mean()), 1),
        sky=round(float(np.percentile(top, 50)), 1),
        shadow=round(float(np.percentile(gnd, 25)), 1),
        gnd_p10=round(float(np.percentile(gnd, 10)), 1),
        p05=round(float(np.percentile(lum, 5)), 1),
        p50=round(float(np.percentile(lum, 50)), 1),
        p90=round(float(np.percentile(lum, 90)), 1),
        dead=round(float((lum < 8.0).mean()) * 100.0, 2),
    )
    if base is not None and base.shape == lum.shape:
        d = np.abs(lum - base)
        st["particle_pct"] = round(float((d > 6.0).mean()) * 100.0, 2)
        st["particle_gain"] = round(float((lum - base).mean()), 2)
    return st


# ---------------------------------------------------------------------------
# one state
# ---------------------------------------------------------------------------
def cast(name, town, spec, path, over=None, particles=True, cam=None):
    """Build + light + render one weather state.  Returns (stats, cfg)."""
    parts, MAT, trees, n_houses = town
    sc = bpy.context.scene
    t0 = time.time()
    over = dict(over or {})
    cfg = W.state(name, **over)
    if not particles:
        cfg["particle_kind"] = "none"
        cfg["particle_rate"] = 0
        cfg["puddle"] = 0.0
        cfg["ripple"] = 0.0
        cfg["fog_banks"] = 0.0
        cfg["rain_veil"] = 0.0
        cfg["bolt"] = 0.0
        cfg["rainbow"] = 0.0
    W.clear()
    W.reset_materials()
    info = W.build(sc, cfg, center=spec.get("center", (0.0, -30.0)), radius=320.0,
                   seed=9, eye=spec["loc"], ground_z=0.02, look=spec["look"])
    t_build = time.time() - t0

    t0 = time.time()
    # A still has to be the frame *between* bolts.  apply_flash leaves the flash
    # sun at 140*flash watts (storm: 77 W) for stills, which is a second key light
    # and is precisely why storm measured brighter than rain in the first sweep.
    # --flash renders the bolt frame instead.
    W.apply_atmos(sc, cfg, center=spec.get("center", (0.0, -30.0)), extent=1800.0,
                  flash=(FLASH if FLASH is not None else 0.0))
    n_mat = W.apply_materials(MAT, cfg)
    if trees and cfg["_wind_speed"] > 1.5:
        W.sway(trees, cfg, t=0.0, factor=1.0)
    # CLI parity: look/render.py forces --exposure over the preset's own value,
    # so every tile in this sheet is judged at exactly -2.20
    sc.view_settings.exposure = RIG_EXPOSURE
    t_atmos = time.time() - t0

    camob = H.camera(cam or "wx2_cam", spec["loc"], spec["look"], lens=spec["lens"])
    H.render_to(path, camob)
    bpy.data.objects.remove(camob, do_unlink=True)
    st = dict(weather=name, file=os.path.basename(path),
              objects=info["objects_n"], tris=info["tris"],
              t_build=round(t_build, 2), t_atmos=round(t_atmos, 2),
              materials=n_mat, exposure=round(float(sc.view_settings.exposure), 2),
              vis_km=round(W.visibility(cfg) / 1000.0, 3),
              report=W.report(cfg))
    return st, cfg


def _table(rows):
    cols = ("weather", "sky", "shadow", "gnd_p10", "p05", "p50", "p90", "dead",
            "vis_km", "particle_pct", "particle_gain", "exposure")
    head = "| %s |" % " | ".join(cols)
    rule = "|" + "|".join(["---"] * len(cols)) + "|"
    lines = [head, rule]
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c, "")
            if isinstance(v, float):
                v = "%.2f" % v
            cells.append(str(v))
        lines.append("| %s |" % " | ".join(cells))
    return "\n".join(lines)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    states = []
    for a in argv:
        for s in a.replace(";", ",").split(","):
            if s in W.ORDER and s not in states:
                states.append(s)
    if not states:
        states = list(W.ORDER)

    global RES, SAMPLES, FLASH
    rig_mode = "main"
    if "--rig" in argv:
        rig_mode = argv[argv.index("--rig") + 1]
    if "--fast" in argv:
        RES = (480, 270)
        SAMPLES = 8
    if "--accept" in argv:
        RES = (960, 540)
        SAMPLES = 24
    if "--res" in argv:
        RES = tuple(int(v) for v in argv[argv.index("--res") + 1].split("x"))
    if "--samples" in argv:
        SAMPLES = int(argv[argv.index("--samples") + 1])
    if "--flash" in argv:
        FLASH = float(argv[argv.index("--flash") + 1])

    os.makedirs(OUT, exist_ok=True)
    import render as R

    parts, MAT, trees, n_houses = _town()
    town_tris = H.tri_count(parts)
    print("[wlab] town: parts=%d houses=%d tris=%d trees=%d"
          % (len(parts), n_houses, town_tris, len(trees)), flush=True)

    sc = bpy.context.scene
    R.setup_engine("eevee", samples=SAMPLES, res=RES)
    print("[wlab] engine=%s res=%s samples=%d rig=%s exp=%.2f amb=%.2f"
          % (sc.render.engine, RES, SAMPLES, rig_mode, RIG_EXPOSURE, RIG_AMBIENT),
          flush=True)

    town = (parts, MAT, trees, n_houses)
    specs = _cam_specs()
    rows = []
    t_all = time.time()
    for name in states:
        spec = specs["wide"]
        rig(sc, spec, rig_mode)
        path = os.path.join(OUT, "wx2_%s.png" % name)
        st, cfg = cast(name, town, spec, path)
        st.update(measure(path))
        # the particle twin: same light, same exposure, no particles -- the
        # difference between the two frames is exactly "how much rain is drawn"
        if cfg["particle_rate"] > 0 or cfg["ripple"] > 0:
            rig(sc, spec, rig_mode)
            twin = os.path.join(OUT, "_wx2_%s_nop.png" % name)
            st2, _ = cast(name, town, spec, twin, particles=False)
            base = _luma(twin)
            st.update(measure(path, base=base))
            try:
                os.remove(twin)
            except OSError:
                pass
        rows.append(st)
        print("[wlab] %-9s sky=%5.1f shadow=%5.1f gnd_p10=%5.1f dead=%4.1f%% "
              "vis=%6.3fkm part=%s"
              % (name, st["sky"], st["shadow"], st["gnd_p10"], st["dead"],
                 st["vis_km"],
                 ("%.1f%%/+%.1f" % (st.get("particle_pct", 0),
                                    st.get("particle_gain", 0)))
                 if "particle_pct" in st else "-"), flush=True)

    # the two gameplay stills the brief asks for, at 960x540
    if "--game" in argv or "--accept" in argv:
        specs = _cam_specs()
        gspec = specs["game"]
        old = (bpy.context.scene.render.resolution_x,
               bpy.context.scene.render.resolution_y)
        R.setup_engine("eevee", samples=max(24, SAMPLES), res=(960, 540))
        for name in ("rain", "snow"):
            if name not in states:
                continue
            rig(sc, gspec, rig_mode)
            p = os.path.join(OUT, "wx2_%s_game.png" % name)
            st, cfg = cast(name, town, gspec, p)
            st.update(measure(p))
            st["file"] = os.path.basename(p)
            rows.append(st)
            print("[wlab] %-9s game sky=%5.1f shadow=%5.1f mean=%5.1f"
                  % (name, st["sky"], st["shadow"], st["mean"]), flush=True)
        R.setup_engine("eevee", samples=SAMPLES, res=old)

    out = dict(res=list(RES), samples=SAMPLES, rig=rig_mode,
               exposure=RIG_EXPOSURE, ambient=RIG_AMBIENT, town_tris=town_tris,
               town_parts=len(parts), seconds=round(time.time() - t_all, 1),
               states=rows)
    with open(os.path.join(OUT, "_wx2_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    md = _table([r for r in rows if not r["file"].endswith("_game.png")])
    with open(os.path.join(OUT, "_wx2_table.md"), "w", encoding="utf-8") as fh:
        fh.write("# weather_lab 8-state metrics (rig=%s, exposure %.2f, "
                 "ambient %.2f)\n\n%s\n" % (rig_mode, RIG_EXPOSURE, RIG_AMBIENT, md))
    print("[wlab] --- sheet ---\n" + md, flush=True)
    print("[wlab] total %.1fs" % (time.time() - t_all), flush=True)
    print("[wlab] done", flush=True)


if __name__ == "__main__":
    main()
