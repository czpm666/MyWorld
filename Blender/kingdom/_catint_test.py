"""_catint_test.py --- 大教堂室内自评：构建 / 三角统计 / 净空 / 渲染

用法（在 E:\\My World 下）：
    blender.exe -b --python Blender\\kingdom\\_catint_test.py -- build
    blender.exe -b --python Blender\\kingdom\\_catint_test.py -- render 128 1600 900 entry,mid
    blender.exe -b --python Blender\\kingdom\\_catint_test.py -- all 128 1600 900
"""

import os
import sys
import time

KING = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KING)
sys.path.insert(0, os.path.dirname(KING))

import bpy                                                     # noqa: E402
import hd_common as H                                          # noqa: E402
import hd_cathedral_int as CI                                  # noqa: E402

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
MODE = argv[0] if argv else "build"
SAMPLES = int(argv[1]) if len(argv) > 1 else 128
RES = (int(argv[2]), int(argv[3])) if len(argv) > 3 else (1600, 900)
ONLY = argv[4].split(",") if len(argv) > 4 and argv[4] else None


def scene_stats(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    raw = 0
    ev = 0
    lo = [1e9, 1e9, 1e9]
    hi = [-1e9, -1e9, -1e9]
    for ob in objs:
        if ob.type != "MESH":
            continue
        me = ob.data
        raw += sum(max(0, len(p.vertices) - 2) for p in me.polygons)
        obe = ob.evaluated_get(dg)
        me2 = obe.to_mesh()
        ev += sum(max(0, len(p.vertices) - 2) for p in me2.polygons)
        for v in me2.vertices:
            w = obe.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
        obe.to_mesh_clear()
    return raw, ev, lo, hi


def report(objs):
    raw, ev, lo, hi = scene_stats(objs)
    print("=" * 66)
    print("[ci] objects      : %d" % len(objs))
    print("[ci] tris (mesh)  : %d" % raw)
    print("[ci] tris (eval)  : %d" % ev)
    print("[ci] bbox lo      : %.3f %.3f %.3f" % tuple(lo))
    print("[ci] bbox hi      : %.3f %.3f %.3f" % tuple(hi))
    print("[ci] size (x,y,z) : %.3f %.3f %.3f" % (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
    print("[ci] footprint    : %s  height %.2f" % (CI.footprint(), CI.height()))
    print("=" * 66)


def find_outliers(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    bad = []
    for ob in objs:
        if ob.type != "MESH":
            continue
        obe = ob.evaluated_get(dg)
        me = obe.to_mesh()
        lo = [1e9] * 3
        hi = [-1e9] * 3
        for v in me.vertices:
            w = obe.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
        obe.to_mesh_clear()
        if (lo[2] < -0.35 or hi[2] > 40.2 or lo[0] < -25.2 or hi[0] > 25.3
                or lo[1] < -42.1 or hi[1] > 36.0):
            bad.append((ob.name, lo, hi))
    bad.sort(key=lambda t: -t[2][2])
    print("[ci] outliers: %d" % len(bad))
    for (n, lo, hi) in bad[:40]:
        print("   %-22s lo %7.2f %7.2f %7.2f   hi %7.2f %7.2f %7.2f" % (n, *lo, *hi))


DBG = [
    ("cler", (-1.0, -16.0, 9.0), (8.3, -7.5, 25.0), 28.0),
    ("rose", (0.0, -18.0, 4.0), (0.0, -41.0, 25.4), 24.0),
    ("trif", (0.0, -12.0, 13.0), (8.4, -10.0, 17.5), 35.0),
    ("up", (0.0, -20.0, 1.7), (0.0, -2.0, 34.0), 20.0),
    ("lantern", (0.0, -2.0, 1.7), (0.0, 7.5, 30.0), 18.0),
    ("win", (4.6, -7.59, 23.4), (8.45, -7.59, 23.4), 30.0),
    ("apse", (0.0, 20.0, 2.0), (0.0, 34.0, 19.0), 26.0),
]


def hit(objs, p):
    dg = bpy.context.evaluated_depsgraph_get()
    print("[ci] objects containing %s:" % (p,))
    for ob in objs:
        if ob.type != "MESH":
            continue
        obe = ob.evaluated_get(dg)
        me = obe.to_mesh()
        lo = [1e9] * 3
        hi = [-1e9] * 3
        for v in me.vertices:
            w = obe.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
        obe.to_mesh_clear()
        if all(lo[i] <= p[i] <= hi[i] for i in range(3)):
            print("   %-20s lo %7.2f %7.2f %7.2f  hi %7.2f %7.2f %7.2f" % (ob.name, *lo, *hi))


def probe(cam_loc, targets):
    from mathutils import Vector
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    print("[ci] probe from %s" % (cam_loc,))
    for t in targets:
        d = (Vector(t) - Vector(cam_loc))
        L = d.length
        d.normalize()
        ok, loc, nor, idx, ob, mat = sc.ray_cast(dg, Vector(cam_loc), d)
        if ok:
            print("   -> %-18s dist %6.2f at %6.2f %6.2f %6.2f"
                  % (ob.name, (loc - Vector(cam_loc)).length, loc.x, loc.y, loc.z))
        else:
            print("   -> (miss) toward %s" % (t,))


def listing():
    """CI_LIST='glass_*,cloth_*:4' 列出材质前缀命中且 z 高度 > 4 m 的对象。"""
    spec = os.environ.get("CI_LIST", "")
    if ":" in spec:
        pats, hmin = spec.split(":")
        hmin = float(hmin)
    else:
        pats, hmin = spec, 0.0
    pats = [p for p in pats.split(",") if p]
    print("[ci] listing pats=%s hmin=%.1f" % (pats, hmin))
    if pats and pats[0] == "*":
        names = sorted({ob.data.materials[0].name.split(".")[0] for ob in bpy.data.objects
                        if ob.type == "MESH" and ob.data.materials})
        print("[ci] MATS", names)
        return
    byname = pats and pats[0].startswith("=")
    if byname:
        pats = [p.lstrip("=") for p in pats]
    for ob in bpy.data.objects:
        if ob.type != "MESH" or not ob.data.materials:
            continue
        mn = ob.data.materials[0].name.split(".")[0]
        if byname:
            if not any(ob.name.startswith(p) for p in pats):
                continue
        elif not any(mn.startswith(p) for p in pats):
            continue
        z0 = min(v.co.z for v in ob.data.vertices)
        z1 = max(v.co.z for v in ob.data.vertices)
        if z1 - z0 < hmin:
            continue
        x1 = max(v.co.x for v in ob.data.vertices)
        y0 = min(v.co.y for v in ob.data.vertices)
        y1 = max(v.co.y for v in ob.data.vertices)
        print("   %-22s %-12s z %6.2f..%6.2f  x1 %6.2f y %6.2f..%6.2f"
              % (ob.name, mn, z0, z1, x1, y0, y1))


def mat_card(M):
    """材质测试卡：6 块玻璃 + 石墙 + 木 + 金，正面直射，看真实颜色。"""
    from medkit import T_at as Ts
    keys = ["glass_blue", "glass_red", "glass_gold", "glass_green", "glass_rose",
            "stone", "wood", "gold"]
    for i, k in enumerate(keys):
        ob = bpy.data.meshes.new("mc_" + k)
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(ob)
        bm.free()
        o = bpy.data.objects.new("mc_" + k, ob)
        bpy.context.scene.collection.objects.link(o)
        o.location = (-3.5 + i * 1.0, 6.0, 1.6)
        o.scale = (0.45, 0.2, 0.45)
        ob.materials.append(M[k])
    # 背景墙
    ob = bpy.data.meshes.new("mc_wall")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(ob)
    bm.free()
    o = bpy.data.objects.new("mc_wall", ob)
    bpy.context.scene.collection.objects.link(o)
    o.location = (0.0, 9.0, 2.0)
    o.scale = (12.0, 0.2, 6.0)
    ob.materials.append(M["stone_dark"])
    H.setup_world(sun_energy=3.0, sky="#8ba6c6", fill=0.0)
    H.setup_engine(samples=SAMPLES, res=RES, gpu=True)
    cam = H.camera("ci_cam_mat", (0.0, 0.0, 1.6), (0.0, 6.0, 1.6), 35.0)
    p = os.path.join(H.OUT_DIR, "dbg_mat.png")
    H.render_to(p, cam)
    print("[ci] wrote", p)


def main():
    t0 = time.time()
    H._clear()
    try:
        import medkit as K
        K._MAT_CACHE.clear()
    except Exception:
        pass
    M = CI._ensure({})
    if MODE == "mat":
        mat_card(M)
        print("[ci] total %.1fs" % (time.time() - t0))
        return
    objs = CI.build(M, None)
    report(objs)
    find_outliers(objs)
    if os.environ.get("CI_HIT"):
        p = tuple(float(v) for v in os.environ["CI_HIT"].split(","))
        hit(objs, p)
    if os.environ.get("CI_PROBE"):
        v = [float(x) for x in os.environ["CI_PROBE"].split(";")[0].split(",")]
        tg = []
        for s in os.environ["CI_PROBE"].split(";")[1:]:
            tg.append(tuple(float(x) for x in s.split(",")))
        probe(tuple(v), tg)
    if os.environ.get("CI_LIST"):
        listing()
    print("[ci] build time %.1fs" % (time.time() - t0))
    if MODE in ("render", "all"):
        paths = CI.preview(samples=SAMPLES, res=RES, only=ONLY)
        for p in paths:
            print("[ci] wrote", p)
        objs2 = [o for o in bpy.data.objects if o.type == "MESH"]
        report(objs2)
    if MODE == "debug":
        H.diorama_floor(M["floor"], 420.0)
        H.setup_world(sun_energy=2.4, sky="#8ba6c6", fill=0.0)
        H.setup_engine(samples=SAMPLES, res=RES, gpu=True)
        CI._roof_cap(M)
        CI.interior_lights()
        if not os.path.isdir(H.OUT_DIR):
            os.makedirs(H.OUT_DIR, exist_ok=True)
        for (name, loc, look, lens) in DBG:
            if ONLY and name not in ONLY:
                continue
            cam = H.camera("ci_cam_" + name, loc, look, lens)
            p = os.path.join(H.OUT_DIR, "dbg_%s.png" % name)
            H.render_to(p, cam)
            print("[ci] wrote", p)
    print("[ci] total %.1fs" % (time.time() - t0))


main()
