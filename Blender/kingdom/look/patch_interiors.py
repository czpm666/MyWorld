"""Add the throne hall and the cathedral nave to an already-built blend.

    blender -b <blend> --python look/patch_interiors.py -- --out <blend> [--castle] [--cathedral]

Opening the finished city costs ~20 s, while rebuilding it costs 13-25 minutes,
so the interiors are added as a post-pass whenever possible.  Both modules are
authored in their parent landmark's local frame and apply
Translation(origin, z) @ Rotation(rot) @ Scale(scale) themselves, which is the
same order hd_glue.place() uses -- so the parent's rot/scale carry over
unchanged.

Constants below mirror capital.py: CITY_SCALE=1.48 puts the castle rock at
(0, 303.4) with its cap at ROCK_TOP+0.45 = 18.45, and the castle itself is
drawn at scale 1.15 with yaw pi.
"""
import os
import sys
import time
import math

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
for _p in (os.path.dirname(KIND), KIND, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
import medkit as K  # noqa: E402

S = 1.48
CITY_SCALE = S
ROCK_C = (0.0, 205.0 * S)          # (0.0, 303.4)
ROCK_TOP = 18.0
CASTLE_Z = ROCK_TOP + 0.45         # 18.45
CASTLE_CS = 1.15
CATH_C = (-152.0 * S, 58.0 * S)    # (-224.96, 85.84)


def argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def arg(name, default=None):
    a = argv()
    if name in a:
        i = a.index(name)
        if i + 1 < len(a) and not a[i + 1].startswith("--"):
            return a[i + 1]
        return True
    return default


def log(*a):
    print("[interiors]", *a, flush=True)


def mat_dict():
    return {m.name: m for m in bpy.data.materials}


def castle(MAT):
    import hd_castle_int as CINT
    cx, cy = ROCK_C
    CS, yaw = CASTLE_CS, math.pi
    lx, ly, lz = 0.0, -21.0, 1.30
    c, s = math.cos(yaw), math.sin(yaw)
    ox = cx + CS * (lx * c - ly * s)
    oy = cy + CS * (lx * s + ly * c)
    oz = CASTLE_Z + CS * lz
    t0 = time.time()
    parts = CINT.build(K, MAT, origin=(ox, oy), rot=yaw, scale=CS, z=oz, seed=3)
    mesh = [o for o in parts if getattr(o, "type", "") == "MESH"]
    lights = [o for o in parts if getattr(o, "type", "") == "LIGHT"]
    faces = sum(len(o.data.polygons) for o in mesh)
    log("castle interior: %d meshes / %d lights / %d faces / %.1f s"
        % (len(mesh), len(lights), faces, time.time() - t0))
    return mesh + lights


def cathedral(MAT):
    import hd_cathedral_int as TINT
    cx, cy = CATH_C
    # hd_cathedral's local +Y is the west front; the interior's +Y points to the
    # apse (east), so the two are drawn with the same yaw (pi) as the parent.
    yaw = math.pi
    t0 = time.time()
    parts = TINT.build(K, MAT, origin=(cx, cy), rot=yaw, scale=1.0, seed=5)
    mesh = [o for o in parts if getattr(o, "type", "") == "MESH"]
    lights = [o for o in parts if getattr(o, "type", "") == "LIGHT"]
    faces = sum(len(o.data.polygons) for o in mesh)
    log("cathedral interior: %d meshes / %d lights / %d faces / %.1f s"
        % (len(mesh), len(lights), faces, time.time() - t0))
    return mesh + lights


def main():
    out = arg("--out")
    do_c = bool(arg("--castle", False))
    do_t = bool(arg("--cathedral", False))
    if not do_c and not do_t:
        do_c = do_t = True
    MAT = mat_dict()
    log("materials", len(MAT), "objects", len(bpy.data.objects))
    made = []
    if do_c:
        try:
            made += castle(MAT)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            log("CASTLE INTERIOR FAILED: %r" % (exc,))
    if do_t:
        try:
            made += cathedral(MAT)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            log("CATHEDRAL INTERIOR FAILED: %r" % (exc,))
    log("added %d objects; scene now %d" % (len(made), len(bpy.data.objects)))
    if out:
        bpy.ops.wm.save_as_mainfile(filepath=out)
        log("saved", out, os.path.getsize(out))


main()
