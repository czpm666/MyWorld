r"""cath_ray.py -- beam / haze diagnosis sweep for hd_cathedral_int.

    blender -b --factory-startup --python look\cath_ray.py -- \
        --dens 0.004,0.010,0.016 --cams light,nave --fills 0 --samples 8

Builds ONCE, then for every haze density re-creates the volume and renders the
requested cameras, so a whole density sweep costs one build.
"""
import argparse
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_HERE, _KING, os.path.dirname(_KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                   # noqa: E402
from mathutils import Vector                                 # noqa: E402
import hd_common as H                                        # noqa: E402
import medkit as K                                           # noqa: E402
import hd_atmosphere as ATM                                  # noqa: E402

OUT = r"E:\My World\Blender\renders\kingdom\look"


def parse():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="ray")
    ap.add_argument("--module", default="hd_cathedral_int")
    ap.add_argument("--dens", default="0.004,0.010,0.016")
    ap.add_argument("--aniso", type=float, default=0.55)
    ap.add_argument("--cams", default="light,nave")
    ap.add_argument("--spec", default="shaft")
    ap.add_argument("--res", default="480x270")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--amb", type=float, default=0.25)
    ap.add_argument("--exp", type=float, default=0.0)
    ap.add_argument("--noemit", type=int, default=0)
    ap.add_argument("--dump", type=int, default=0)
    ap.add_argument("--sun", type=float, default=0.0)
    ap.add_argument("--probe", type=int, default=0)
    ap.add_argument("--hidegl", type=int, default=0)
    ap.add_argument("--free", default="")
    return ap.parse_args(argv)


def main():
    a = parse()
    w, h = [int(x) for x in a.res.lower().split("x")]
    H._clear()
    K._MAT_CACHE.clear()
    mod = __import__(a.module)
    t0 = time.time()
    parts = mod.build()
    print("[ray] build %.1fs %d objects" % (time.time() - t0, len(parts)),
          flush=True)

    H.setup_world(0.0, "#8fa6c4", a.amb)
    H.setup_engine(a.samples, (w, h), gpu=True)
    sc = bpy.context.scene
    try:
        sc.view_settings.look = "AgX - Punchy"
    except Exception:
        pass
    sc.view_settings.exposure = a.exp

    if a.noemit:
        n = 0
        for m in bpy.data.materials:
            if not m.use_nodes:
                continue
            for nd in m.node_tree.nodes:
                if nd.type == "BSDF_PRINCIPLED":
                    try:
                        nd.inputs["Emission Strength"].default_value = 0.0
                        n += 1
                    except Exception:
                        pass
        print("[ray] emission off on %d materials" % n, flush=True)
    if a.hidegl:
        n = 0
        for ob in bpy.data.objects:
            if ob.type == "MESH" and ("_gl" in ob.name or ob.name.endswith("_bk")):
                ob.hide_render = True
                n += 1
        print("[ray] hidden glazing %d" % n, flush=True)
    if a.sun:
        sd = bpy.data.lights.new("raysun", "SUN")
        sd.energy = a.sun
        sd.angle = math.radians(0.6)
        so = bpy.data.objects.new("raysun", sd)
        bpy.context.scene.collection.objects.link(so)
        so.rotation_euler = (-mod.SUN_TO).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        fw = so.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
        print("[ray] sun %.2f fwd=(%.2f,%.2f,%.2f) nlights=%d"
              % (a.sun, fw.x, fw.y, fw.z, len(bpy.data.lights)), flush=True)
    lights = mod.interior_lights(spec=a.spec, air=False)
    print("[ray] %s lights=%d" % (a.spec, len(lights)), flush=True)
    if a.probe:
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        st = mod.SUN_TO.normalized()
        rays = []
        for hz in (16.2, 17.6, 19.0):
            for yy in (-18.80, -18.00, -17.00):
                rays.append(("inX z=%.1f y=%.2f" % (hz, yy),
                             (20.0, yy, hz), Vector((-1.0, 0.0, 0.0))))
        for yy in (-18.80, -18.00, -17.00):
            rays.append(("sunz y=%.2f" % yy, (20.0, yy + 2.4, 22.4), st))
        for p0 in ((0.0, -20.0, 17.0), (0.0, -20.0, 12.0)):
            rays.append(("sun %s" % (p0,), p0, st))
        for nm, p0, st in rays:
            o = Vector(p0)
            names = []
            for _ in range(9):
                hit, loc, nrm, idx, ob, mat = bpy.context.scene.ray_cast(
                    dg, o, st)
                if not hit:
                    names.append("MISS")
                    break
                names.append("%s@%.1f(%.1f,%.1f,%.1f)"
                             % (ob.name, (loc - Vector(p0)).length,
                                loc.x, loc.y, loc.z))
                o = loc + st * 0.05
            print("[ray] probe %-18s -> %s" % (nm, " | ".join(names)),
                  flush=True)
        return
    if a.dump:
        bpy.context.view_layer.update()
        for ob in lights[:10]:
            li = ob.data
            fwd = ob.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
            print("[ray] %-14s loc=(%.2f,%.2f,%.2f) size=(%.2f,%.2f) e=%.0f "
                  "fwd=(%.2f,%.2f,%.2f) rot=(%.0f,%.0f,%.0f) col=%s"
                  % (ob.name, ob.location.x, ob.location.y, ob.location.z,
                     getattr(li, "size", 0), getattr(li, "size_y", 0),
                     li.energy, fwd.x, fwd.y, fwd.z,
                     math.degrees(ob.rotation_euler.x), math.degrees(ob.rotation_euler.y),
                     math.degrees(ob.rotation_euler.z),
                     tuple(round(c, 2) for c in li.color)), flush=True)
        for w in mod.WINDOWS[:8]:
            F, a0, a1, zsill, zspr, rise, th, seed = w
            print("[ray] win a=(%.2f,%.2f) z=(%.2f,%.2f,%.2f) th=%.2f "
                  "O=(%.2f,%.2f,%.2f) N=(%.2f,%.2f,%.2f)"
                  % (a0, a1, zsill, zspr, rise, th,
                     F.O.x, F.O.y, F.O.z, F.N.x, F.N.y, F.N.z), flush=True)
        if not a.cams.strip():
            print("[ray] dump only", flush=True)
            return
    cams = dict((c[0], c) for c in mod.CAMS)
    want = [c.strip() for c in a.cams.split(",") if c.strip()]

    if a.free:
        v = [float(t) for t in a.free.split(",")]
        cam = H.camera("cfree", (v[0], v[1], v[2]), (v[3], v[4], v[5]),
                       v[6] if len(v) > 6 else 28.0)
        p = os.path.join(OUT, "RAY_%s_free.png" % a.tag)
        H.render_to(p, cam)
        print("[ray] wrote %s" % os.path.basename(p), flush=True)
        return
    for d in [float(x) for x in a.dens.split(",")]:
        ATM.haze("fog", density=d, height=34.0, extent=210.0,
                 center=(0.0, 0.0), aniso=a.aniso)
        print("[ray] haze d=%.4f" % d, flush=True)
        for cn in want:
            if cn not in cams:
                continue
            c = cams[cn]
            cam = H.camera("c_%s" % cn, c[1], c[2], c[3] if len(c) > 3 else 20.0)
            p = os.path.join(OUT, "RAY_%s_d%03d_%s.png" % (a.tag, int(d * 1000), cn))
            t = time.time()
            H.render_to(p, cam)
            print("[ray] %s  %.1fs" % (os.path.basename(p), time.time() - t),
                  flush=True)
    print("[ray] done", flush=True)


main()
