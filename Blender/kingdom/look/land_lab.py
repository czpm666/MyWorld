"""land_lab.py -- cold-start review rig for hd_landscape.

This does NOT open capital_v24.blend (860 MB / ~10 GB RAM; forbidden).  It
starts from Blender's factory scene, builds the landscape module on its own,
drops a crude *stand-in* city so the composition can be judged, and renders
review frames.

    blender -b --factory-startup -P look/land_lab.py -- \
        [--shots a_farm,a_wall] [--samples 8] [--res 480x270] [--seed 1337]

Renders land in renders/kingdom/look/.  The stand-in city is a flat disc, a
20-gon wall and a few hundred boxes -- it exists only to give the eye a scale
reference; the real city is wired in by capital.py:build().

Shot names
----------
  a_farm    aerial over the farm belt, 900 m up            (patchwork read)
  a_wide    high aerial, the whole basin + ridges          (macro read)
  a_near    lower aerial, 320 m, over the near band        (city edge read)
  a_wall    standing on the wall, looking out              (the parent's shot)
  a_field   eye level 1.72 m among the furrows             (furrow read)
  a_garden  eye level 1.72 m in the kitchen gardens        (near-band props)
  a_road    eye level on a gate road, cart ruts            (road read)
  a_mount   telephoto of the far ridges                    (mountain read)
  p_eye / p_pan / p_river / p_field / p_wide               (v23 names, kept)
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KROOT = os.path.dirname(HERE)
BROOT = os.path.dirname(KROOT)
for p in (KROOT, HERE, BROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy                                                       # noqa: E402

OUT = os.path.join(BROOT, "renders", "kingdom", "look")

SHOTS = {
    # ---------------- aerial, the "is it a patchwork quilt?" check ----------
    "a_farm": dict(loc=(980.0, 980.0, 860.0), look=(1480.0, 1480.0, 30.0),
                   lens=55.0, preset="morning_town", haze_extent=17000.0,
                   haze_mul=0.12),
    "a_wide": dict(loc=(760.0, -2700.0, 1450.0), look=(-60.0, 700.0, 320.0),
                   lens=30.0, preset="morning_town", haze_extent=19000.0,
                   haze_mul=0.15),
    "a_near": dict(loc=(44.0, 1520.0, 300.0), look=(-10.0, 1000.0, 4.0),
                   lens=42.0, preset="morning_town", haze_extent=17000.0,
                   haze_mul=0.11),
    # ---------------- from the wall, looking out ---------------------------
    "a_wall": dict(loc=None, look=(0.0, 0.0, 0.0), lens=40.0,
                   preset="morning_town", haze_extent=17000.0, haze_mul=0.11),
    # ---------------- ground level ----------------------------------------
    "a_field": dict(loc=None, look=(0.0, 0.0, 0.0), lens=40.0,
                    preset="morning_town", haze_extent=17000.0, haze_mul=0.09),
    "a_garden": dict(loc=None, look=(0.0, 0.0, 0.0), lens=40.0,
                     preset="morning_town", haze_extent=17000.0, haze_mul=0.09),
    "a_road": dict(loc=None, look=(0.0, 0.0, 0.0), lens=40.0,
                   preset="morning_town", haze_extent=17000.0, haze_mul=0.10),
    # ---------------- mountains -------------------------------------------
    "a_mount": dict(loc=(0.0, -2400.0, 260.0), look=(-300.0, 6200.0, 1500.0),
                    lens=90.0, preset="morning_town", haze_extent=20000.0,
                    haze_mul=0.13),
    # ---------------- v23 names, kept working ------------------------------
    "p_aerial": dict(loc=(700.0, -1240.0, 480.0), look=(0.0, 20.0, 15.0),
                     lens=50.0, preset="morning_town", haze_extent=17000.0,
                     haze_mul=0.13),
    "p_aerial2": dict(loc=(1020.0, -1980.0, 640.0), look=(-40.0, 220.0, 90.0),
                      lens=32.0, preset="morning_town", haze_extent=17000.0,
                      haze_mul=0.13),
    "p_eye": dict(loc=None, look=(0.0, 0.0, 26.0), lens=35.0,
                  preset="morning_town", haze_extent=17000.0, haze_mul=0.11),
    "p_pan": dict(loc=(-1560.0, -980.0, 260.0), look=(1200.0, 900.0, 420.0),
                  lens=30.0, preset="morning_town", haze_extent=17000.0,
                  haze_mul=0.13),
    "p_field": dict(loc=(1420.0, -860.0, 165.0), look=(2350.0, -1750.0, 120.0),
                    lens=45.0, preset="morning_town", haze_extent=17000.0,
                    haze_mul=0.11),
    "p_river": dict(loc=(-1230.0, -235.0, 96.0), look=(-1000.0, 0.0, 6.0),
                    lens=50.0, preset="morning_town", haze_extent=17000.0,
                    haze_mul=0.10),
    "p_wide": dict(loc=(420.0, -2700.0, 1150.0), look=(0.0, 600.0, 300.0),
                   lens=26.0, preset="morning_town", haze_extent=19000.0,
                   haze_mul=0.15),
    "p_top": dict(loc=(0.0, 0.0, 6200.0), look=(0.0, 40.0, 0.0), lens=28.0,
                  preset="morning_town", haze_extent=19000.0, haze_mul=0.05,
                  ortho=3600.0),
}

FLAGS = {}


def opts():
    o = {}
    a = sys.argv
    for i, s in enumerate(a):
        if s.startswith("--"):
            k = s[2:]
            if i + 1 < len(a) and not a[i + 1].startswith("--"):
                o[k] = a[i + 1]
            else:
                o[k] = True
    return o


# --------------------------------------------------------------------------- #
#  stand-in city
# --------------------------------------------------------------------------- #
def standin_city():
    """A cheap stand-in for the capital: flat disc, 20-gon wall, roof tops.
    Nothing here is a replacement for the real city -- it only gives the
    landscape something to sit around."""
    import hd_landscape as LAN
    rng = __import__("random").Random(7)

    def emit(name, V, F, key):
        if not F:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(V, [], F)
        me.update()
        ob = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(ob)
        me.materials.append(LAN._get_mat({}, key))
        return ob

    def box(V, F, x, y, z0, sx, sy, sz):
        k = len(V)
        for dz in (0.0, sz):
            for dx, dy in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
                V.append((x + dx, y + dy, z0 + dz))
        F.extend([(k, k + 3, k + 2, k + 1), (k + 4, k + 5, k + 6, k + 7),
                  (k, k + 1, k + 5, k + 4), (k + 1, k + 2, k + 6, k + 5),
                  (k + 2, k + 3, k + 7, k + 6), (k + 3, k, k + 4, k + 7)])

    R_OUT = float(getattr(LAN, "R_OUTER", 947.2))
    # the town floor comes from hd_landscape._town_floor(); a second disc here
    # only fights with it, so the stand-in starts at the wall.

    # wall: 20-gon ring
    V, F = [], []
    R, H = R_OUT, 13.0
    for i in range(20):
        a = 2.0 * math.pi * i / 20.0
        b = 2.0 * math.pi * (i + 1) / 20.0
        x0, y0 = R * math.cos(a), R * math.sin(a)
        x1, y1 = R * math.cos(b), R * math.sin(b)
        k = len(V)
        V.extend([(x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, H), (x0, y0, H)])
        F.append((k, k + 1, k + 2, k + 3))
        k = len(V)
        V.extend([(x0, y0, H), (x1, y1, H), (x1, y1, H + 0.9),
                  (x0, y0, H + 0.9)])
        F.append((k, k + 1, k + 2, k + 3))
    emit("standin_wall", V, F, "stone")

    # rooftops, in four loose quarters so it does not look like noise
    V, F = [], []
    for _i in range(900):
        a = rng.uniform(0.0, 2.0 * math.pi)
        r = R_OUT * math.sqrt(rng.uniform(0.0, 0.84))
        x, y = r * math.cos(a), r * math.sin(a)
        s = rng.uniform(2.6, 4.6)
        box(V, F, x, y, rng.uniform(2.4, 6.0), s, s, rng.uniform(1.6, 4.0))
    emit("standin_roofs", V, F, "roof")
    return None


# --------------------------------------------------------------------------- #
def _ground_eye(spot, back=0.0):
    """Resolve loc=None shots: stand 1.72 m above the built terrain."""
    import hd_landscape as LAN
    x, y, face = spot
    z = float(LAN.height(x, y))
    loc = (x, y, z + 1.72)
    fx = x + back * math.cos(face)
    fy = y + back * math.sin(face)
    return dict(loc=loc, look=(fx, fy, float(LAN.height(fx, fy)) + 1.35))


def resolve_shots(o):
    """Fill in the loc/look of the *derived* shots from the built terrain."""
    import hd_landscape as LAN
    import hd_landscape_near as NR
    R = float(getattr(LAN, "R_OUTER", 947.2))

    # --- on the wall, looking out over the near belt ------------------------
    # 24 m up (a corner turret) and a 170 m target: at anything flatter the
    # whole belt compresses into the bottom twenty pixels and the frame is one
    # enormous empty apron.
    w = R + 2.0
    z = float(LAN.height(0.0, w))
    SHOTS["a_wall"].update(loc=(0.0, w, max(z, 0.0) + 24.0),
                           look=(40.0, w + 170.0, 2.0), lens=38.0)

    # --- stand inside a real furrowed field --------------------------------
    fields = [f for f in getattr(LAN, "_FIELDS", [])
              if 1050.0 < f.r < 2100.0
              and getattr(f, "pitch", 0.0) > 1.2
              and f.w > 60.0 and f.d > 55.0]
    if fields:
        # a standing crop reads the furrows far better than bare plough, and a
        # bearing near 40 deg lets the sun rake across the ridges
        pref = {"wheat": 0.0, "rye": 0.03, "rapeseed": 0.05, "pasture": 0.08}
        fields.sort(key=lambda f: pref.get(f.crop, 0.6)
                    + abs(math.atan2(f.cy, f.cx) - 0.70) * 0.5
                    + 0.0004 * abs(f.r - 1450.0))
        f = fields[0]
        ca, sa = math.cos(f.ang), math.sin(f.ang)
        ru = (ca, sa)                       # across the ridges
        rv = (-sa, ca)                      # along the ridges
        px = f.cx - rv[0] * f.d * 0.40 - ru[0] * f.w * 0.28
        py = f.cy - rv[1] * f.d * 0.40 - ru[1] * f.w * 0.28
        lx = f.cx + rv[0] * f.d * 0.34 + ru[0] * f.w * 0.26
        ly = f.cy + rv[1] * f.d * 0.34 + ru[1] * f.w * 0.26
        SHOTS["a_field"].update(
            loc=(px, py, float(LAN.height(px, py)) + 1.72),
            look=(lx, ly, float(LAN.height(lx, ly)) + 1.30), lens=42.0)
        o["field_used"] = [round(f.cx, 1), round(f.cy, 1), f.crop,
                           round(f.pitch, 2)]

    # --- a kitchen garden at the wall foot --------------------------------
    gp = getattr(NR, "GARDEN_POS", [])
    if gp:
        gp = sorted(gp, key=lambda g: abs(math.atan2(g[1], g[0]) - 1.75))
        x, y, z, a = gp[0]
        ca, sa = math.cos(a), math.sin(a)
        px, py = x - ca * 9.0, y - sa * 9.0
        lx, ly = x + ca * 16.0, y + sa * 16.0
        SHOTS["a_garden"].update(
            loc=(px, py, float(LAN.height(px, py)) + 1.72),
            look=(lx, ly, float(LAN.height(lx, ly)) + 1.15), lens=36.0)

    # --- on the east highway, ground level, looking out --------------------
    P = np.asarray(LAN._spline(LAN.ROADS["east"], 12.0)[0])
    dd = np.hypot(P[:, 0], P[:, 1])
    k = int(np.argmin(np.abs(dd - (R + 190.0))))
    x, y = float(P[k, 0]), float(P[k, 1])
    x2, y2 = float(P[min(len(P) - 1, k + 26), 0]), float(P[min(len(P) - 1, k + 26), 1])
    SHOTS["a_road"].update(
        loc=(x, y, float(LAN.height(x, y)) + 1.72),
        look=(x2, y2, float(LAN.height(x2, y2)) + 1.05), lens=38.0)
    return o


# --------------------------------------------------------------------------- #
def shoot(name, spec, no_write=False):
    import render as RIG
    L = RIG.L
    RIG.wipe_rig()
    cam_ob = RIG.make_camera({"loc": spec["loc"], "look": spec["look"],
                              "lens": spec.get("lens", 35.0)})
    if spec.get("ortho"):
        cam_ob.data.type = "ORTHO"
        cam_ob.data.ortho_scale = spec["ortho"]
    cam_ob.data.clip_start = 0.4
    cam_ob.data.clip_end = 30000.0
    preset = spec.get("preset", "morning_town")
    pr = L.PRESETS[preset]
    c = cam_ob.location
    RIG.build_rig(preset,
                  spec.get("elev", pr["sun_elev_wide"]),
                  spec.get("azim", pr["sun_azim"]),
                  haze=not FLAGS.get("nohaze"),
                  haze_mul=spec.get("haze_mul", 1.0),
                  haze_extent=spec.get("haze_extent", 8000.0),
                  cam=(c.x, c.y),
                  sky=spec.get("sky", preset),
                  clouds=spec.get("clouds"))
    if "exposure" in spec:
        bpy.context.scene.view_settings.exposure = spec["exposure"]
    path = os.path.join(OUT, name + ".png")
    bpy.context.scene.render.filepath = path
    t0 = time.time()
    if not no_write:
        bpy.ops.render.render(write_still=True)
    return path, time.time() - t0


def main():
    o = opts()
    FLAGS.update(o)
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    import render as RIG
    import hd_landscape as LAN

    seed = int(o.get("seed", 1337))
    n = LAN.strip_old()
    print("[lab] stripped %d old objects" % n, flush=True)
    bopts = {}
    for k in ("rings", "fields", "woods", "town", "near", "marks"):
        if o.get("no_" + k):
            bopts[k] = False
    info = LAN.build({}, res=float(o.get("res_terrain", 20.0)), seed=seed,
                     **bopts)
    print("[lab-info] " + json.dumps({
        "count": info["count"], "faces": info["faces"],
        "tris": info["tris"], "verts": info["verts"],
        "seconds": round(info["seconds"], 2),
        "ram_mb": round(info["ram_mb"], 1),
        "peak_mb": round(info["peak_mb"], 1),
        "parts": {k: v for k, v in sorted(info.get("parts", {}).items())}}),
        flush=True)
    if not o.get("no_city"):
        standin_city()

    if o.get("bbox"):
        for ob in sorted(bpy.data.objects, key=lambda z: z.name):
            if ob.type != "MESH":
                continue
            vs = list(ob.data.vertices)
            if not vs:
                continue
            bad = 0
            for v in vs:
                if not (abs(v.co.x) < 1e6 and abs(v.co.y) < 1e6
                        and abs(v.co.z) < 1e6):
                    bad += 1
                elif v.co.x != v.co.x or v.co.z != v.co.z:
                    bad += 1
            co = [v.co for v in vs]
            ex = max(max(abs(v.x), abs(v.y)) for v in co)
            zn = min(v.z for v in co)
            zx = max(v.z for v in co)
            if bad or ex > 1500.0 or o.get("bbox") == "all":
                print("[bbox] %-22s v=%-7d f=%-7d r=%8.0f  z=%7.1f..%7.1f %s"
                      % (ob.name, len(vs), len(ob.data.polygons), ex, zn, zx,
                         ("BAD %d" % bad) if bad else ""), flush=True)

    resolve_shots(o)

    samples = int(o.get("samples", 8))
    res = [int(x) for x in str(o.get("res", "480x270")).split("x")]
    RIG.setup_engine("eevee", samples, res, vols=True)
    sc = bpy.context.scene
    try:
        sc.eevee.volumetric_end = 26000.0
    except Exception:                                            # noqa: BLE001
        pass

    want = str(o.get("shots", "a_farm,a_wall")).split(",")
    if o.get("cam") and o.get("look"):
        SHOTS["dbg"] = dict(
            loc=tuple(float(v) for v in str(o["cam"]).split(",")),
            look=tuple(float(v) for v in str(o["look"]).split(",")),
            lens=float(o.get("lens", 35.0)))
        want = ["dbg"]
    out = []
    for name in want:
        name = name.strip()
        if name not in SHOTS:
            print("[lab] no shot %r" % (name,), flush=True)
            continue
        p, sec = shoot(name, SHOTS[name], no_write=bool(o.get("no_write")))
        print("[lab] %-9s %5.1fs  %s" % (name, sec, p), flush=True)
        out.append({"shot": name, "path": p, "seconds": round(sec, 1)})
    print("[lab-result] " + json.dumps(out), flush=True)
    print("[lab] total %.1fs" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
