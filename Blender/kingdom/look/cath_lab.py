r"""cath_lab.py -- harness for the cathedral interior modules.

Runs INSIDE Blender:

    blender -b --factory-startup --python look\cath_lab.py -- --tag t1 \
        --res 480x270 --samples 8 --cams all

Features
--------
* imports a build module (default hd_cathedral_int) and calls build()
* prints a JSON stats block (objects, tris, bbox, build seconds, per-stage times)
* sets up a world + sun that can actually enter through the window openings
* optional local fog volume (hd_atmosphere.haze) for god rays
* optional half-section cut (crude: hides objects whose bbox lies in +x/+y)
* renders the module's CAMS plus a few lab-only cameras
* can dump the .blend

Everything is opt-in by flag so a failing stage does not kill the render.
"""
import argparse
import importlib
import json
import math
import os
import random
import sys
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_HERE, _KING, os.path.dirname(_KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                   # noqa: E402
from mathutils import Vector                                 # noqa: E402

import hd_common as H                                        # noqa: E402
import medkit as K                                           # noqa: E402

OUT = r"E:\My World\Blender\renders\kingdom\look"


# ---------------------------------------------------------------------------
def eprint(*a):
    print(*a, flush=True)


def parse():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="t")
    ap.add_argument("--module", default="hd_cathedral_int")
    ap.add_argument("--res", default="480x270")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--cams", default="all",
                    help="all | none | comma list of camera names")
    ap.add_argument("--lens", type=float, default=0.0, help="override lens")
    ap.add_argument("--sun", type=float, default=0.0,
                    help="sun energy; 0 = no sun")
    ap.add_argument("--sun-el", type=float, default=38.0)
    ap.add_argument("--sun-az", type=float, default=-118.0)
    ap.add_argument("--amb", type=float, default=0.35,
                    help="world background strength")
    ap.add_argument("--sky", default="#7f97b4")
    ap.add_argument("--fog", type=float, default=-1.0, help="fog density, <0 = off")
    ap.add_argument("--fog-h", type=float, default=26.0)
    ap.add_argument("--fog-ext", type=float, default=220.0)
    ap.add_argument("--section", default="", help="x | y | '' (half cut)")
    ap.add_argument("--nogodlights", action="store_true")
    ap.add_argument("--nocap", action="store_true")
    ap.add_argument("--save", default="")
    ap.add_argument("--dome", action="store_true", help="module supplied dome")
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--sune", type=float, default=-1.0, help="override the module sun energy")
    ap.add_argument("--dens", type=float, default=-1.0,
                    help="override the module haze density")
    ap.add_argument("--threads", type=int, default=0)
    return ap.parse_args(argv)


def tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    v = 0
    for ob in objs:
        if ob is None or ob.type != "MESH":
            continue
        obe = ob.evaluated_get(dg)
        try:
            me = obe.to_mesh()
        except Exception:
            continue
        if me is None:
            continue
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        v += len(me.vertices)
        obe.to_mesh_clear()
    return n, v


def bbox(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        if ob is None or ob.type != "MESH":
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return [round(x, 2) for x in lo], [round(x, 2) for x in hi]


def clear_all():
    H._clear()
    try:
        K._MAT_CACHE.clear()
    except Exception:
        pass


def world_dim(sky, amb):
    w = bpy.data.worlds.new("lab_world")
    w.use_nodes = True
    bg = None
    for n in w.node_tree.nodes:
        if n.type == "BACKGROUND":
            bg = n
    bg.inputs[0].default_value = K.c(sky, 1.0)
    bg.inputs[1].default_value = amb
    bpy.context.scene.world = w


def sun_light(energy, el, az):
    d = bpy.data.lights.new("sun", "SUN")
    d.energy = energy
    d.angle = math.radians(0.7)
    d.color = (1.0, 0.93, 0.82)
    ob = bpy.data.objects.new("sun", d)
    bpy.context.scene.collection.objects.link(ob)
    # az measured from +Y, clockwise; el from horizon
    e = math.radians(el)
    a = math.radians(az)
    ob.rotation_euler = (math.pi * 0.5 - e, 0.0, a)
    return ob


def fog(dens, height, extent):
    import hd_atmosphere as A
    return A.haze("clear_morning", density=dens, height=height, extent=extent,
                  center=(0.0, 0.0), color=(1.0, 0.94, 0.86), aniso=0.55)


def cut(objs, axis):
    """Crude section: delete every object that sits wholly in the +axis half."""
    idx = {"x": 0, "y": 1}[axis]
    kept = []
    for ob in objs:
        if ob is None or ob.type != "MESH":
            kept.append(ob)
            continue
        mn, mx = bbox([ob])
        c = (mn[idx] + mx[idx]) * 0.5
        if c > 0.05:
            bpy.data.objects.remove(ob, do_unlink=True)
        else:
            kept.append(ob)
    return kept


def render(cam, path):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    eprint("[lab] %s  %.1fs" % (os.path.basename(path), time.time() - t0))
    return path


# ---------------------------------------------------------------------------
LAB_CAMS = {
    # name: (loc, look_at, lens)
    "door": ((0.0, -39.4, 1.72), (0.0, 12.0, 9.0), 20.0),
    "door_wide": ((0.0, -39.4, 1.72), (0.0, 14.0, 11.0), 15.0),
    "nave_up": ((0.0, -18.0, 1.72), (0.0, -8.0, 24.0), 15.0),
    "aisle": ((11.6, -14.0, 1.72), (11.6, 14.0, 8.0), 18.0),
    "altar": ((0.0, 8.0, 1.72), (0.0, 32.0, 6.0), 22.0),
    "rose_tr": ((20.0, 6.0, 3.0), (25.0, 6.0, 22.0), 20.0),
    "cross_up": ((0.0, 3.0, 1.72), (0.0, 7.0, 28.0), 14.0),
    "side_light": ((-9.0, -12.0, 1.72), (13.0, -20.0, 12.0), 24.0),
    "sec_x": ((46.0, -6.0, 12.0), (0.0, -6.0, 13.0), 34.0),
    "sec_y": ((0.0, -6.0, 12.0), (0.0, 60.0, 12.0), 34.0),
}


def main():
    a = parse()
    t_all = time.time()
    res = tuple(int(x) for x in a.res.lower().split("x"))
    os.makedirs(OUT, exist_ok=True)
    clear_all()

    mod = importlib.import_module(a.module)
    if hasattr(mod, "_MAT_CACHE"):
        try:
            K._MAT_CACHE.clear()
        except Exception:
            pass

    t0 = time.time()
    try:
        parts = mod.build()
    except TypeError:
        parts = mod.build({}, random.Random(7))
    t_build = time.time() - t0
    parts = [p for p in parts if p is not None]
    eprint("[lab] build %.1fs -> %d objects" % (t_build, len(parts)))

    ntri, nv = tri_count(parts)
    lo, hi = bbox(parts)
    eprint("[lab] tris=%d verts=%d bbox=%s..%s" % (ntri, nv, lo, hi))

    if a.section:
        parts = cut(parts, a.section)
        ntri2, _ = tri_count(parts)
        eprint("[lab] section %s -> %d tris" % (a.section, ntri2))

    world_dim(a.sky, a.amb)
    if a.sun > 0:
        sun_light(a.sun, a.sun_el, a.sun_az)

    if a.sune > 0 and hasattr(mod, "SUN_E"):
        mod.SUN_E = a.sune
    if hasattr(mod, "interior_lights") and not a.nogodlights:
        try:
            mod.interior_lights()
        except Exception:
            traceback.print_exc()
    if hasattr(mod, "_roof_cap") and not a.nocap:
        try:
            mod._roof_cap(mod._MAT)
        except Exception:
            traceback.print_exc()
    if a.fog >= 0:
        fog(a.fog, a.fog_h, a.fog_ext)
    if a.dens >= 0 and hasattr(mod, "atmosphere"):
        try:
            mod.atmosphere(density=a.dens)
        except Exception:
            traceback.print_exc()

    H.setup_engine(samples=a.samples, res=res, gpu=True)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy"
    except Exception:
        pass
    if a.exposure:
        sc.view_settings.exposure = a.exposure
    if a.threads:
        sc.render.threads_mode = "FIXED"
        sc.render.threads = a.threads

    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=a.save)
        eprint("[lab] saved", a.save)
    if a.cams != "none":
        want = None if a.cams == "all" else set(x.strip() for x in a.cams.split(","))
        cams = []
        if hasattr(mod, "CAMS"):
            for entry in mod.CAMS:
                name, loc, look = entry[0], entry[1], entry[2]
                lens = entry[3] if len(entry) > 3 else 20.0
                cams.append((name, loc, look, lens))
        for name, (loc, look, lens) in LAB_CAMS.items():
            if not hasattr(mod, "CAMS") or name not in [c[0] for c in cams]:
                cams.append((name, loc, look, lens))
        for (name, loc, look, lens) in cams:
            if want is not None and name not in want:
                continue
            cam = H.camera("lab_" + name, loc, look, a.lens or lens)
            render(cam, os.path.join(OUT, "L_%s_%s.png" % (a.tag, name)))

    summary = dict(module=a.module, tag=a.tag, objects=len(parts), tris=ntri,
                   verts=nv, bbox=[lo, hi], build_s=round(t_build, 1),
                   total_s=round(time.time() - t_all, 1),
                   res=list(res), samples=a.samples)
    eprint("[lab] SUMMARY " + json.dumps(summary))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
