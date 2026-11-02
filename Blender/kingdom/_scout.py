"""_scout.py - find camera positions that are actually in open air.

    blender -b capital_full.blend -P _scout.py -- check            (rays only)
    blender -b capital_full.blend -P _scout.py -- shot <name> [w h spp]
    blender -b capital_full.blend -P _scout.py -- grid             (all, 400x225)
"""
import os
import sys
import json
import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
import numpy as np
from mathutils import Vector

OUT = r"E:\My World\Blender\renders\kingdom"
LAYOUT = os.path.join(HERE, "layout.json")


def cam_at(loc, look, lens):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("SC")
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_start = 0.05
    cd.clip_end = 9000.0
    co = bpy.data.objects.new("SC", cd)
    sc.collection.objects.link(co)
    co.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    bpy.context.view_layer.update()
    return co


def clearance(co, nx=11, ny=6, maxd=4000.0):
    """Fraction of frustum rays that hit something closer than 2 m, and the min
    hit distance -- a camera with near_frac > 0.15 is inside a wall."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    mw = co.matrix_world
    lens = co.data.lens
    sw = co.data.sensor_width
    half = (sw / 2.0) / lens
    aspect = sc.render.resolution_y / float(sc.render.resolution_x)
    near = 0
    hits = 0
    dmin = 1e9
    for iy in range(ny):
        for ix in range(nx):
            u = ((ix + 0.5) / nx * 2.0 - 1.0) * half
            v = ((iy + 0.5) / ny * 2.0 - 1.0) * half * aspect
            dirw = (mw.to_3x3() @ Vector((u, v, -1.0))).normalized()
            origin = mw.translation + dirw * 0.06
            ok, loc, nor, idx, ob, mat = sc.ray_cast(dg, origin, dirw, distance=maxd)
            if ok:
                hits += 1
                dd = (loc - mw.translation).length
                dmin = min(dmin, dd)
                if dd < 2.0:
                    near += 1
    n = nx * ny
    return near / float(n), (dmin if hits else maxd), hits / float(n)


# candidate cameras: name -> (loc, look, lens, kind)
CAND = {
    "gate_avenue": [
        ((8.0, 600.0, 1.70), (0.0, 400.0, 14.0), 35.0),
        ((14.0, 588.0, 1.70), (0.0, 380.0, 16.0), 35.0),
        ((2.0, 560.0, 1.70), (0.0, 300.0, 20.0), 35.0),
        ((-6.0, 604.0, 1.70), (0.0, 420.0, 12.0), 32.0),
    ],
    "main_street": [
        ((30.0, 120.0, 1.70), (-10.0, 140.0, 6.0), 28.0),
        ((120.0, 30.0, 1.70), (100.0, 130.0, 8.0), 28.0),
        ((-60.0, 90.0, 1.70), (-90.0, 160.0, 8.0), 28.0),
        ((80.0, -40.0, 1.70), (60.0, 60.0, 8.0), 28.0),
    ],
    "market_square": [
        ((9.2, 20.0, 8.0), (9.2, 92.0, 6.0), 35.0),
        ((9.2, 10.0, 12.0), (9.2, 90.0, 4.0), 35.0),
        ((9.2, 30.0, 6.0), (9.2, 95.0, 8.0), 35.0),
    ],
    "overview_34": [
        ((700.0, -1240.0, 480.0), (0.0, 20.0, 15.0), 50.0),
        ((820.0, -1050.0, 520.0), (0.0, 40.0, 10.0), 50.0),
    ],
    "castle_close": [
        ((60.0, 320.0, 40.0), (0.0, 232.0, 34.0), 50.0),
        ((90.0, 300.0, 55.0), (0.0, 228.0, 30.0), 50.0),
        ((0.0, 340.0, 30.0), (0.0, 228.0, 34.0), 50.0),
    ],
    "cathedral_plaza": [
        ((-30.0, -60.0, 14.0), (-148.0, 34.0, 34.0), 28.0),
        ((10.0, -80.0, 18.0), (-148.0, 34.0, 34.0), 28.0),
        ((-60.0, -30.0, 10.0), (-148.0, 34.0, 40.0), 24.0),
    ],
}


def check():
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    for name, cands in CAND.items():
        for i, (loc, look, lens) in enumerate(cands):
            co = cam_at(loc, look, lens)
            nf, dmin, frac = clearance(co)
            flag = "OK " if nf < 0.12 and dmin > 2.0 else "BAD"
            print("SCOUT %-16s #%d %-16s near=%.2f dmin=%7.1f hit=%.2f %s"
                  % (name, i, str(tuple(round(v) for v in loc)), nf, dmin, frac, flag),
                  flush=True)
            bpy.data.objects.remove(co, do_unlink=True)


def shoot(name, idx, res, spp, tag=None):
    import hd_light as L
    sc = bpy.context.scene
    loc, look, lens = CAND[name][idx]
    L.apply("morning_town", None, 32.0, 112.0)
    co = cam_at(loc, look, lens)
    sc.camera = co
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    sc.cycles.samples = spp
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    p = os.path.join(OUT, "_sc_%s_%d.png" % (name, idx))
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)[:, :, :3]
    bpy.data.images.remove(img)
    print("SCOUTSHOT %s #%d mean=%.4f max=%.4f -> %s"
          % (name, idx, float(a.mean()), float(a.max()), p), flush=True)


def main():
    a = sys.argv
    args = a[a.index("--") + 1:] if "--" in a else ["check"]
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 400, 225
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in ("OPTIX", "CUDA")
    except Exception:  # noqa: BLE001
        pass
    if args[0] == "check":
        check()
    elif args[0] == "shot":
        shoot(args[1], int(args[2]), (400, 225), 16)
    elif args[0] == "grid":
        for name in CAND:
            for i in range(len(CAND[name])):
                shoot(name, i, (400, 225), 16)


main()
