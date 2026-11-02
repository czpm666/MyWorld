"""_nature_test.py -- three-view previews and export checks for hd_nature.

Every asset gets a 3/4 view, a front view (looking along +Y at the -Y face)
and a high 3/4 view, rendered at 1400x900 with Cycles.  The images are meant
to be looked at, not just produced: the whole point of the round is to judge
the foliage silhouette, the rock facets and whether a grass tuft reads as a
hedgehog.

    blender -b --factory-startup --python _nature_test.py -- --tag r1
    blender -b --factory-startup --python _nature_test.py -- --assets oak,pine --samples 32 --tag probe
    blender -b --factory-startup --python _nature_test.py -- --stats
    blender -b --factory-startup --python _nature_test.py -- --verify
"""

import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hd_common as H
import hd_nature as N
import medkit as K
from medkit import T_at

OUT = N.RENDER_DIR

# camera: 50 mm on a 36 mm sensor, 1400x900 -> 39.6 deg horizontal, 26.1 vertical
_VFOV = 2.0 * math.atan((36.0 * 900.0 / 1400.0) * 0.5 / 50.0)


def _opts():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = {"assets": "all", "samples": 64, "res": "1400x900", "tag": "",
         "seed": None, "stats": False, "verify": False, "views": "abc",
         "lens": 50.0, "scale": 1.06}
    for a in argv:
        if a.startswith("--assets="):
            o["assets"] = a.split("=", 1)[1]
        elif a.startswith("--samples="):
            o["samples"] = int(a.split("=")[1])
        elif a.startswith("--res="):
            o["res"] = a.split("=")[1]
        elif a.startswith("--tag="):
            o["tag"] = a.split("=", 1)[1]
        elif a.startswith("--seed="):
            o["seed"] = int(a.split("=")[1])
        elif a.startswith("--views="):
            o["views"] = a.split("=")[1]
        elif a.startswith("--lens="):
            o["lens"] = float(a.split("=")[1])
        elif a.startswith("--scale="):
            o["scale"] = float(a.split("=")[1])
        elif a == "--stats":
            o["stats"] = True
        elif a == "--verify":
            o["verify"] = True
    return o


def _resolve(name):
    for k, fn in N.BUILDERS:
        if k == name:
            return k, fn
    raise KeyError(name)


def _ground(mat, size=400.0):
    K.box("ground", T_at(0, 0, -0.5), (size, size, 1.0), mat)


def _place(center, radius, az_deg, el_deg, lens=50.0, scale=1.06, dist_mul=None):
    """Camera at (az, el) on a sphere around center, framing `radius`."""
    vfov = 2.0 * math.atan((36.0 * 9.0 / 14.0) * 0.5 / lens)
    d = dist_mul if dist_mul else radius / math.sin(vfov * 0.5) * scale
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    loc = Vector((
        center.x + math.cos(el) * math.cos(az) * d,
        center.y + math.cos(el) * math.sin(az) * d,
        center.z + math.sin(el) * d,
    ))
    return loc, Vector(center)


VIEWS = [
    ("a", 38.0, 12.0),    # three-quarter
    ("b", -90.0, 5.0),    # front, looking along +Y
    ("c", -128.0, 44.0),  # high three-quarter, shows the ground contact
]


def render_asset(name, fn, o):
    key, _ = _resolve(name)
    N._new_scene()
    MAT = N.make_materials()
    parts = fn(seed=o["seed"] if o["seed"] is not None else N.SEED_BASE[key], MAT=MAT)
    _ground(MAT["earth"])
    lo, hi = H.bbox(parts)
    center = (lo + hi) * 0.5
    ext = hi - lo
    radius = max(0.35, 0.5 * math.sqrt(ext.x ** 2 + ext.y ** 2 + ext.z ** 2))
    st = N.stats(parts)

    H.setup_world(sun_energy=5.2, sky="#b6cfea", fill=2.2)
    H.setup_engine(samples=o["samples"], res=tuple(int(x) for x in o["res"].split("x")))
    os.makedirs(OUT, exist_ok=True)
    paths = []
    for tag, az, el in VIEWS:
        if tag not in o["views"]:
            continue
        loc, tgt = _place(center, radius, az, el, lens=o["lens"], scale=o["scale"])
        cam = H.camera("cam_" + tag, loc, tgt, lens=o["lens"])
        pre = ("%s_" % o["tag"]) if o["tag"] else ""
        p = os.path.join(OUT, "%snature_%s_%s.png" % (pre, key, tag))
        t0 = time.time()
        H.render_to(p, cam)
        print("[test] %s  %.1fs  tris=%d size=%s" %
              (p, time.time() - t0, st["tris"], st["size"]), flush=True)
        paths.append(p)
        bpy.data.objects.remove(cam, do_unlink=True)
    return st, paths


def verify(out_dir=None):
    """Re-import every exported FBX and check size / origin / tri count."""
    out_dir = out_dir or N.NATURE_DIR
    man = os.path.join(out_dir, "nature_manifest.json")
    with open(man, "r", encoding="utf-8") as fh:
        rows = json.load(fh)
    bad = 0
    for r in rows:
        p = os.path.join(out_dir, r["file"])
        N._new_scene()
        bpy.ops.import_scene.fbx(filepath=p)
        obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        lo, hi = H.bbox(obs)
        tris = H.tri_count(obs)
        size = (round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3))
        d = max(abs(size[i] - r["size"][i]) for i in range(3))
        zok = abs(lo.z) < 0.03
        triok = abs(tris - r["tris"]) <= max(4, r["tris"] * 0.02)
        flag = "OK " if (d < 0.02 and zok and triok) else "BAD"
        if flag == "BAD":
            bad += 1
        print("[verify] %s %-30s size=%s (d=%.4f) minz=%.4f tris=%d/%d objs=%d" %
              (flag, r["file"], size, d, lo.z, tris, r["tris"], len(obs)), flush=True)
    print("[verify] %d/%d files match the manifest" % (len(rows) - bad, len(rows)),
          flush=True)
    return bad


def main():
    o = _opts()
    if o["verify"]:
        verify()
        return
    names = [k for k, _ in N.BUILDERS] if o["assets"] == "all" else \
        [s.strip() for s in o["assets"].split(",") if s.strip()]
    rows = []
    t0 = time.time()
    for name in names:
        key, fn = _resolve(name)
        if o["stats"]:
            N._new_scene()
            MAT = N.make_materials()
            parts = fn(seed=o["seed"] if o["seed"] is not None else N.SEED_BASE[key],
                       MAT=MAT)
            st = N.stats(parts)
            print("[stats] %-14s tris=%5d size=%s min_z=%.4f" %
                  (key, st["tris"], st["size"], st["min_z"]), flush=True)
            rows.append(dict(asset=key, **st))
        else:
            st, paths = render_asset(name, fn, o)
            rows.append(dict(asset=key, paths=paths, **st))
    print("[test] done in %.1fs" % (time.time() - t0), flush=True)
    if not o["stats"]:
        p = os.path.join(OUT, "render_manifest_%s.json" % (o["tag"] or "final"))
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1)
        print("[test] wrote", p, flush=True)


if __name__ == "__main__":
    main()
