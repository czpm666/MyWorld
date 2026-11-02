"""temp render / probe harness for hd_cathedral_int.py  (Blender, -b)

blender -b --factory-startup --python rr.py -- mode=render cams=rose samples=48
       mode=leak        -> ray-cast sky-leak census (no preview roof cap)
       mode=render      -> the module's own CAMS
       mode=cam         -> one custom camera via loc/look/lens
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
for p in (KING, os.path.dirname(KING)):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy                                                  # noqa: E402
from mathutils import Vector                                # noqa: E402
import hd_common as H                                       # noqa: E402
import hd_cathedral_int as C                                # noqa: E402

OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)


def opts():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = {}
    flat = []
    for tok in a:
        flat.extend(tok.split())
    last = None
    for tok in flat:
        if "=" in tok:
            k, v = tok.split("=", 1)
            o[k] = v
            last = k
        elif last is not None:
            o[last] = o[last] + " " + tok
    return o


def build(cap=True, samples=48, res=(900, 506), hide="", sky="#8ba6c6", sun=2.4):
    H._clear()
    try:
        import medkit as K
        K._MAT_CACHE.clear()
    except Exception:
        pass
    M = C._ensure({})
    C.build(M, __import__("random").Random(11))
    H.diorama_floor(M["floor"], 420.0)
    H.setup_world(sun_energy=sun, sky=sky, fill=0.0)
    H.setup_engine(samples=samples, res=res, gpu=True)
    if cap:
        C._roof_cap(M)
    C.interior_lights()
    if hide:
        pre = [t for t in hide.split(",") if t]
        n = 0
        for ob in list(bpy.data.objects):
            if any(ob.name.startswith(p) for p in pre):
                ob.hide_render = True
                n += 1
        print("[rr] hidden %d objects for %s" % (n, pre), flush=True)
    return M


def do_render(o):
    samples = int(o.get("samples", 48))
    res = (int(o.get("rx", 900)), int(o.get("ry", 506)))
    build(cap=o.get("cap", "1") == "1", samples=samples, res=res,
          hide=o.get("hide", ""), sky=o.get("sky", "#8ba6c6"),
          sun=float(o.get("sun", 2.4)))
    outdir = o.get("outdir") or H.OUT_DIR
    os.makedirs(outdir, exist_ok=True)
    cams = o.get("cams", "entry,mid,choir,vault,rose,cross").split(",")
    t0 = time.time()
    for (name, loc, look, lens) in C.CAMS:
        if name not in cams:
            continue
        cam = H.camera("ci_cam_" + name, loc, look, lens)
        p = os.path.join(outdir, "ci_%s.png" % name)
        H.render_to(p, cam)
        print("[rr] %s %.1fs" % (p, time.time() - t0), flush=True)


def do_cam(o):
    samples = int(o.get("samples", 48))
    res = (int(o.get("rx", 900)), int(o.get("ry", 506)))
    build(cap=o.get("cap", "1") == "1", samples=samples, res=res)
    loc = tuple(float(v) for v in o.get("loc", "0,-24,1.7").split(","))
    look = tuple(float(v) for v in o.get("look", "0,-41,25.4").split(","))
    lens = float(o.get("lens", 20.0))
    cam = H.camera("ci_cam_custom", loc, look, lens)
    p = os.path.join(o.get("outdir") or H.OUT_DIR, o.get("name", "ci_custom") + ".png")
    H.render_to(p, cam)


def do_leak(o):
    """Ray-cast census: from inside the building, how many directions escape?"""
    build(cap=o.get("cap", "0") == "1", samples=1, res=(64, 36))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    # hide the preview roof cap so we test the interior's own closure
    for ob in list(bpy.data.objects):
        if ob.name.startswith("ci_cap"):
            ob.hide_viewport = True
            ob.hide_render = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    pts = []
    for yy in o.get("ys", "-36,-28,-20,-12,-4,4,10,20,28").split(","):
        for xx in o.get("xs", "-10,0,10").split(","):
            for zz in o.get("zs", "1.7,8.0,20.0,27.0").split(","):
                pts.append(Vector((float(xx), float(yy), float(zz))))
    nd = int(o.get("ndirs", 900))
    escapes = []
    for p in pts:
        for i in range(nd):
            # spherical fibonacci
            ga = math.pi * (3.0 - math.sqrt(5.0))
            z = 1.0 - 2.0 * (i + 0.5) / nd
            r = math.sqrt(max(0.0, 1.0 - z * z))
            d = Vector((math.cos(ga * i) * r, math.sin(ga * i) * r, z))
            hit, loc, nrm, idx, ob, mat = sc.ray_cast(dg, p, d, distance=300.0)
            if not hit:
                escapes.append((tuple(round(v, 2) for v in p),
                                tuple(round(v, 3) for v in d)))
    print("[leak] origins=%d dirs=%d escapes=%d" % (len(pts), nd, len(escapes)),
          flush=True)
    # summarize escape directions in azimuth/elevation buckets
    buckets = {}
    for (p, d) in escapes:
        el = math.degrees(math.asin(max(-1.0, min(1.0, d[2]))))
        az = math.degrees(math.atan2(d[1], d[0]))
        key = (int(round(az / 30.0)) * 30, int(round(el / 10.0)) * 10)
        buckets[key] = buckets.get(key, 0) + 1
    for k in sorted(buckets, key=lambda k: -buckets[k])[:40]:
        print("   az=%+4d el=%+3d  n=%d" % (k[0], k[1], buckets[k]))
    print("[leak] total=%d of %d" % (len(escapes), len(pts) * nd), flush=True)


def do_ray(o):
    """Cast a ray from a named camera through a pixel and list every surface hit."""
    name = o.get("cam", "entry")
    W = int(o.get("rx", 900))
    Hh = int(o.get("ry", 506))
    build(cap=o.get("cap", "0") == "1", samples=1, res=(64, 36))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tgt = None
    for (nm, loc, look, lens) in C.CAMS:
        if nm == name:
            tgt = (loc, look, lens)
    loc, look, lens = tgt
    cam = H.camera("ci_cam_" + name, loc, look, lens)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()   # must be re-fetched after any change
    MW = cam.matrix_world
    R = MW.to_3x3()
    eye = MW.translation
    tanx = 18.0 / cam.data.lens
    tany = tanx * Hh / W
    spec = o.get("pix") or o.get("px", "450")
    for tok in spec.split("|"):
        pxs = [float(v) for v in tok.split(",")]
        if o.get("pix"):
            pairs = [(pxs[0], pxs[1])] if len(pxs) >= 2 else []
        else:
            pairs = [(px, pxs[0]) for px in pxs[1:]]
        for px, py in pairs:
            ndx = (px / W) * 2.0 - 1.0
            ndy = 1.0 - (py / Hh) * 2.0
            d = (R @ Vector((ndx * tanx, ndy * tany, -1.0))).normalized()
            print("[ray] cam=%s px=%.0f py=%.0f" % (name, px, py))
            p = eye.copy()
            for i in range(14):
                hit, hp, nrm, idx, ob, mat = sc_cast(dg, p, d)
                if not hit:
                    print("   %2d ESCAPE at (%.2f, %.2f, %.2f)"
                          % (i, p.x, p.y, p.z))
                    break
                mn = "-"
                try:
                    if ob.data.materials and mat is not None:
                        mn = ob.data.materials[int(mat)].name
                except Exception:
                    pass
                print("   %2d %-18s (%.2f, %.2f, %.2f) n=(%.2f,%.2f,%.2f) mat=%s" %
                      (i, ob.name, hp.x, hp.y, hp.z,
                       nrm.x, nrm.y, nrm.z, mn))
                p = hp.copy()


def sc_cast(dg, p, d):
    return bpy.context.scene.ray_cast(dg, p + d * 0.002, d, distance=400.0)


def do_seg(o):
    """Cast a single straight segment between two world points, list hits."""
    build(cap=o.get("cap", "0") == "1", samples=1, res=(64, 36))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    a = Vector([float(v) for v in o.get("from", "0,0,0").split(",")])
    b = Vector([float(v) for v in o.get("to", "0,0,10").split(",")])
    d = (b - a)
    L = d.length
    d = d.normalized()
    print("[seg] %.2f m from (%.2f,%.2f,%.2f) to (%.2f,%.2f,%.2f)"
          % (L, a.x, a.y, a.z, b.x, b.y, b.z), flush=True)
    p = a.copy()
    t = 0.0
    for i in range(20):
        hit, hp, nrm, idx, ob, mat = bpy.context.scene.ray_cast(
            dg, p + d * 0.002, d, distance=400.0)
        if not hit:
            print("   %2d CLEAR to end" % i, flush=True)
            break
        t = (hp - a).length
        if t > L + 1e-3:
            print("   %2d CLEAR to end (next hit %.2f m away)" % (i, t), flush=True)
            break
        print("   %2d t=%.3f m  %-18s (%.2f, %.2f, %.2f) n=(%.2f,%.2f,%.2f)"
              % (i, t, ob.name, hp.x, hp.y, hp.z, nrm.x, nrm.y, nrm.z), flush=True)
        p = hp.copy()
        if t >= L:
            break


if __name__ == "__main__":
    o = opts()
    mode = o.get("mode", "render")
    t0 = time.time()
    if mode == "leak":
        do_leak(o)
    elif mode == "ray":
        do_ray(o)
    elif mode == "seg":
        do_seg(o)
    elif mode == "cam":
        do_cam(o)
    else:
        do_render(o)
    print("[rr] mode=%s done %.1fs" % (mode, time.time() - t0), flush=True)
