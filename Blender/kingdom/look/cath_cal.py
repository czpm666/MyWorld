# -*- coding: utf-8 -*-
"""Light calibration: build once, then render the same view under a few
combinations of (sun energy, interior light multiplier, exposure)."""
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, os.path.dirname(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import hd_common as H
import medkit as K
import hd_cathedral_int as M

OUT = r"E:\My World\Blender\renders\kingdom\look"


def base_energies(lights):
    return [ob.data.energy for ob in lights]


def scale(lights, base, mult):
    for ob, e in zip(lights, base):
        ob.data.energy = e * mult


def add_sun(energy, angle_deg=1.4, color=(1.0, 0.96, 0.90)):
    li = bpy.data.lights.new("cal_sun", "SUN")
    li.energy = energy
    li.angle = angle_deg * 3.14159265 / 180.0
    li.color = color
    ob = bpy.data.objects.new("cal_sun", li)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = (-M.SUN_TO).to_track_quat("-Z", "Y").to_euler()
    return ob


def main():
    H._clear()
    K._MAT_CACHE.clear()
    t0 = time.time()
    parts = M.build()
    print("[cal] build %.1fs %d objs" % (time.time() - t0, len(parts)))
    lights = M.interior_lights(spec="shaft", air=False)
    bse = base_energies(lights)
    print("[cal] lights %d" % len(lights))

    H.setup_world(0.0, "#7f97b4", 0.35)
    H.setup_engine(samples=8, res=(480, 270), gpu=True)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy"
    except Exception:
        pass

    sun = add_sun(6.0)
    cam = H.camera("cal_nave", (0.0, -17.0, 1.72), (0.0, 20.0, 7.0), 20.0)
    cam2 = H.camera("cal_up", (0.0, -11.0, 1.72), (0.0, 1.5, 22.0), 15.0)

    runs = (
        ("a_s1_l1", 1.0, 1, 0.0, 0.0),
        ("b_s6_l0", 6.0, 0.0, 0.0, 0.0),
        ("c_s6_l1", 6.0, 1, 0.0, 0.0),
        ("d_s6_l4", 6.0, 4, 0.0, 0.0),
        ("e_s14_l4", 14.0, 4, 0.0, 0.0),
        ("f_s6_l4_x2", 6.0, 4, 2.0, 0.0),
    )
    for (tag, se, mult, expo, _) in runs:
        sun.data.energy = se
        scale(lights, bse, mult)
        sc.view_settings.exposure = expo
        for (nm, c) in (("nave", cam), ("up", cam2)):
            p = os.path.join(OUT, "CAL_%s_%s.png" % (tag, nm))
            H.render_to(p, c)
            print("[cal] %s" % p, flush=True)
    print("[cal] done")


main()
