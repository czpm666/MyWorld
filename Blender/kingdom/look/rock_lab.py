r"""rock_lab.py -- iteration bench for hd_rock.py.  Own scene, own camera.

    blender -b --python look\rock_lab.py -- --site crag --shots hero,road,talus --res 480x270 --samples 8 --tag r01

Every shot is a camera + a look-at, nothing else; the material, the lighting and
the geometry are exactly what capital.py would get.
"""
import os
import sys
import math

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
KINGDOM = os.path.dirname(HERE)
BLENDER_DIR = os.path.dirname(KINGDOM)
for p in (KINGDOM, BLENDER_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import medkit as K
import hd_rock as HR

OUT = os.path.join(os.path.dirname(BLENDER_DIR), "renders", "kingdom", "look")
SHOTS = {
    # name: (camera xyz, target xyz, lens)
    # The crag is 126 m across and 18 m tall at (0, 303.4).  A camera above the
    # plateau only ever sees the plateau, so the hero shots sit *below* the rim:
    # that is the view a player gets anyway, and it is the only one where the
    # cliff face and the talus are more than a 20 px band.
    "hero":   ((0.0, 132.0, 28.0), (0.0, 292.0, 14.0), 40.0),
    "hero2":  ((-150.0, 108.0, 34.0), (0.0, 300.0, 15.0), 38.0),
    "wide":   ((-205.0, 96.0, 74.0), (0.0, 303.4, 10.0), 50.0),
    "face":   ((-4.0, 174.0, 24.0), (-2.0, 250.0, 12.0), 40.0),
    "face2":  ((58.0, 196.0, 20.0), (30.0, 262.0, 10.0), 40.0),
    "talus":  ((-112.0, 300.0, 8.0), (-80.0, 303.0, 2.0), 40.0),
    "talus2": ((96.0, 326.0, 7.0), (70.0, 300.0, 2.0), 35.0),
    "talus3": ((8.0, 196.0, 5.5), (0.0, 236.0, 6.0), 35.0),
    "east":   ((150.0, 258.0, 20.0), (78.0, 300.0, 11.0), 50.0),
    "wall":   ((92.0, 300.0, 12.0), (70.0, 300.0, 15.0), 42.0),
    "top":    ((6.0, 236.0, 96.0), (0.0, 298.0, 17.0), 55.0),
    "deck":   ((1.0, 118.0, 34.0), (0.0, 303.4, 14.0), 45.0),
    "north":  ((-18.0, 470.0, 40.0), (0.0, 310.0, 12.0), 45.0),
    "road":   ((88.0, 300.0, 10.0), (63.0, 300.0, 14.5), 38.0),
    "road2":  ((70.0, 268.0, 27.0), (52.0, 296.0, 14.0), 40.0),
    "road3":  ((-44.0, 206.0, 34.0), (-16.0, 250.0, 17.0), 42.0),
    "foot":   ((-104.0, 213.0, 16.0), (-58.0, 262.0, 6.0), 38.0),
    "rim":    ((-46.0, 244.0, 24.0), (-36.0, 286.0, 17.5), 45.0),
    "gate":   ((0.0, 200.0, 26.0), (0.0, 246.0, 19.0), 42.0),
    "game":   ((0.0, 258.0, 27.0), (0.0, 285.0, 12.0), 37.8),
    "cliff":  ((985.0, 1180.0, 26.0), (905.0, 1290.0, 4.0), 45.0),
    "cliff2": ((1190.0, 900.0, 16.0), (1290.0, 700.0, 3.0), 42.0),
    "cliffin": ((-620.0, -560.0, 30.0), (-690.0, -650.0, 6.0), 40.0),
}


def peak_mem():
    """Peak working set of this process, in MB.

    resource.getrusage().ru_maxrss is 0 on Windows, so ask psapi directly.  The
    brief makes memory the only real budget, so the report needs a number that
    came from the process, not from a guess.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        fn = None
        for mod, name in (("psapi", "GetProcessMemoryInfo"),
                          ("kernel32", "K32GetProcessMemoryInfo"),
                          ("psapi", "K32GetProcessMemoryInfo")):
            try:
                fn = getattr(getattr(ctypes.windll, mod), name)
                fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC),
                               wintypes.DWORD]
                fn.restype = wintypes.BOOL
                if fn(h, ctypes.byref(c), ctypes.sizeof(PMC)):
                    return c.PeakWorkingSetSize / 1048576.0
                print("[mem] %s.%s refused" % (mod, name))
            except Exception as exc:                             # noqa: BLE001
                print("[mem] %s.%s: %s" % (mod, name, exc))
        return -1.0
    except Exception as exc:                                     # noqa: BLE001
        print("[mem] unavailable:", exc)
        return -1.0


def opts():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    o = {"site": "crag", "shots": "hero", "res": "480x270", "samples": "8",
         "tag": "r00", "seed": "11", "style": "limestone", "nth": "1080",
         "castle": "1", "plants": "1", "preset": "morning_town",
         "drop": "17.6", "plain": "0", "height": "15",
         "sky": "morning_town", "elev": "48", "azim": "112",
         "ambient": "0.38", "exposure": "-2.20", "sky_strength": "1.0",
         "haze_mul": "0.45", "haze_extent": "2800"}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            k = a[2:].replace("-", "_")
            if "=" in k:
                k, v = k.split("=", 1)
                o[k] = v
            elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                o[k] = argv[i + 1]
                i += 1
            else:
                o[k] = "1"
        i += 1
    return o


def clean():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    for ma in list(bpy.data.materials):
        bpy.data.materials.remove(ma)


def setup(o):
    sc = bpy.context.scene
    w, h = [int(x) for x in o["res"].lower().split("x")]
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = int(o["samples"])
    try:
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    return sc


def mats():
    """Only what hd_rock borrows.  No capital import: keep the bench light."""
    M = {}
    M["leaf"] = K.mat_foliage("leaf", base="#4e6b33", light="#78954a", scale=0.9)
    M["leaf_dark"] = M["leaf"]
    M["wood"] = K.mat_wood("wood", base="#6a5237", light="#8a6b48")
    M["wood_dark"] = M["wood"]
    M["stone_warm"] = K.mat_stone("stone_warm", base="#c4b393", dark="#8a7c62",
                                  light="#dccdaf", scale=1.6)
    M["stone"] = M["stone_warm"]
    M["grass"] = K.mat_foliage("grass", base="#4f6b36", light="#6d8a44", scale=0.8)
    M["town_ground"] = K.mat_earth("town_ground", base="#8d8574", dark="#5c5749",
                                   scale=1.4)
    return M


def dump_mesh(name, cx, cy):
    """Ground truth on the built crag: radius profile, row spacing, boulders.

    The clay render showed a smooth dome where the code was supposed to have a
    nine-layer staircase, so measure the mesh instead of re-reading the code.
    For twelve z bands print the radius min/mean/max over the whole ring, and
    the angular wavelength of the radial variation (how many metres apart a
    wall step repeats), plus the count of isolated small objects.
    """
    import math
    ob = bpy.data.objects.get(name)
    if ob is None:
        print("[dump] no object %r (have %s)"
              % (name, sorted(o.name for o in bpy.data.objects
                              if o.type == "MESH")))
        return
    me = ob.data
    n = len(me.vertices)
    print("[dump] %s verts=%d polys=%d mats=%s"
          % (name, n, len(me.polygons),
             [m.name if m else "-" for m in me.materials]))
    zs = [v.co.z for v in me.vertices]
    print("[dump] z range %.2f .. %.2f" % (min(zs), max(zs)))
    bands = {}
    for v in me.vertices:
        k = int(math.floor(v.co.z / 1.5))
        r = math.hypot(v.co.x - cx, v.co.y - cy)
        a = bands.setdefault(k, [1e9, -1e9, 0.0, 0])
        a[0] = min(a[0], r)
        a[1] = max(a[1], r)
        a[2] += r
        a[3] += 1
    for k in sorted(bands):
        lo, hi, sm, cn = bands[k]
        step = (hi - lo) / max(1.0, cn / 96.0)
        print("[dump] z=%5.2f..%5.2f  r %6.2f..%6.2f mean %6.2f  n=%5d  "
              "radial spread/vert %.3f m"
              % (k * 1.5, (k + 1) * 1.5, lo, hi, sm / cn, cn, step))
    for on in ("rock_talus", "rock_cap_stones", "rock_plants", "rock_road",
               "rock_face"):
        o2 = bpy.data.objects.get(on)
        if o2 is None:
            continue
        vs = [v.co for v in o2.data.vertices]
        lo = [min(v[i] for v in vs) for i in range(3)]
        hi = [max(v[i] for v in vs) for i in range(3)]
        print("[dump] %-16s bbox (%.1f %.1f %.1f)..(%.1f %.1f %.1f) v=%d"
              % (on, lo[0], lo[1], lo[2], hi[0], hi[1], hi[2], len(vs)))
        # which material actually covers which heights: three earlier rounds
        # were spent guessing at this
        me2 = o2.data
        per = {}
        for p in me2.polygons:
            mi = p.material_index
            zm = sum(me2.vertices[v].co.z for v in p.vertices) / len(p.vertices)
            a = per.setdefault(mi, [0, 1e9, -1e9])
            a[0] += 1
            a[1] = min(a[1], zm)
            a[2] = max(a[2], zm)
        for mi in sorted(per):
            nm = me2.materials[mi].name if mi < len(me2.materials) else "?"
            c, z0, z1 = per[mi]
            print("[dump]   mat %-24s polys %6d  z %.2f .. %.2f"
                  % (nm, c, z0, z1))


def probe(sc, ob, name):
    """Name the surface a handful of rays land on.

    Guessing which object a pale slope belongs to cost more render cycles than
    this does: object, material, world z and |N.z| settle it outright.
    """
    from mathutils import Vector
    dg = bpy.context.evaluated_depsgraph_get()
    loc = ob.matrix_world.translation
    R = ob.matrix_world.to_quaternion()
    print("[probe] %s at (%.1f %.1f %.1f)" % (name, loc.x, loc.y, loc.z))
    for (px, py) in ((0.0, 0.0), (0.0, 0.55), (0.0, -0.55), (-0.55, 0.0),
                     (0.55, 0.0), (-0.6, -0.6)):
        d = R @ Vector((px, py, -1.0))
        ok, p, n, idx, hob, _m = sc.ray_cast(dg, loc, d.normalized(),
                                             distance=4000.0)
        if not ok:
            print("[probe]   %+.2f %+.2f  -> sky" % (px, py))
            continue
        mat = "?"
        vs = ""
        try:
            me = hob.data
            mat = me.materials[me.polygons[idx].material_index].name
            vs = " ".join("%.1f/%.1f/%.1f" % tuple(me.vertices[v].co)
                          for v in me.polygons[idx].vertices)
        except Exception:                                        # noqa: BLE001
            pass
        print("[probe]   %+.2f %+.2f  %-16s %-22s z=%6.2f nz=%5.2f dist=%6.1f"
              "  xyz=(%.1f %.1f %.1f) r=%.1f"
              % (px, py, hob.name, mat, p.z, abs(n.z), (p - loc).length,
                 p.x, p.y, p.z,
                 math.hypot(p.x - 0.0, p.y - 303.4)))
        if vs:
            print("[probe]        xy=(%.1f %.1f) quad %s" % (p.x, p.y, vs))


def cam(name, loc, tgt, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_start = 0.4
    cd.clip_end = 6000.0
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    v = (ob.location[0] - tgt[0], ob.location[1] - tgt[1], ob.location[2] - tgt[2])
    from mathutils import Vector
    ob.rotation_euler = Vector(v).to_track_quat("Z", "Y").to_euler()
    return ob


def ground(M, r=520.0):
    K.cyl("lab_ground", K.T_at(0.0, 303.4, -0.06), r, 0.12, M["grass"], seg=96)


def main():
    o = opts()
    clean()
    sc = setup(o)
    M = mats()
    t0 = __import__("time").time()
    site = o["site"]
    if site == "crag":
        ground(M)
        HR.build(K, M, seed=int(o["seed"]), style=o["style"],
                 nth=int(o["nth"]), drop=float(o["drop"]),
                 plants=bool(int(o["plants"])))
        if int(o["castle"]) and HR.build.LAST is not None:
            try:
                import capital_hd_glue as HG
                import random
                rng = random.Random(3)
                cz = 18.0 + 0.45
                objs = HG.castle(M, rng, 0.0, 303.4, math.pi, cz, 1.15)
                print("[lab] castle built: %d objs" % len(objs or []))
                CR = HR.build.LAST
                ramp = HG.wedge_ramp(HG.castle_mats(M), "lab_ramp", 0.0,
                                     y_top=303.4 - 47.6 * 1.15, z_top=cz + 2.55,
                                     y_bot=303.4 - 80.5, z_bot=0.0, w=11.5)
                print("[lab] ramp ok")
            except Exception as ex:
                print("[lab] castle skipped: %r" % (ex,))
    elif site == "cliff":
        K.cyl("lab_town", K.T_at(0.0, 0.0, -0.05), 947.2, 0.10, M["town_ground"],
              seg=200)
        K.cyl("lab_plain", K.T_at(0.0, 0.0, -0.42), 2100.0, 0.16, M["grass"],
              seg=200)
        HR.cliff_ring(K, M, seed=int(o["seed"]), style=o["style"],
                      nth=int(o["nth"]),
                      height=(6.0, float(o["height"])), verbose=True)
    elif site == "box":
        # nothing but a 12 m block on the ground: if this renders white too,
        # the crag geometry is not what broke the frame
        ground(M)
        K.box("lab_box", 12.0, 12.0, 12.0, M["stone"],
              T=K.T_at(0.0, 300.0, 6.0))
        K.cyl("lab_cyl", K.T_at(14.0, 300.0, 5.0), 2.4, 10.0, M["wood"])
    else:
        raise SystemExit("unknown site %r" % site)
    print("[lab] geometry %.2fs" % (__import__("time").time() - t0))
    if str(o.get("flatmat", "0")) not in ("0", "", "False"):
        # clay render: every material becomes 0.55 grey diffuse, so what is on
        # screen is geometry only.  Stops the argument about shading from being
        # an argument about shape.
        import bpy as _b
        clay = _b.data.materials.get("lab_clay")
        if clay is None:
            clay = _b.data.materials.new("lab_clay")
            clay.use_nodes = True
            bs = clay.node_tree.nodes.get("Principled BSDF")
            if bs is not None:
                bs.inputs["Base Color"].default_value = (0.42, 0.40, 0.36, 1.0)
                bs.inputs["Roughness"].default_value = 0.85
        for ob in _b.data.objects:
            if ob.type != "MESH" or ob.name.startswith("SKY_"):
                continue
            for sl in ob.material_slots:
                sl.material = clay
        print("[lab] clay materials ON")
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            print("[lab]   %-24s %7d v %7d f" % (ob.name, len(ob.data.vertices),
                                                 len(ob.data.polygons)))
    # light
    c = cam("driver", (0.0, 118.0, 62.0), (0.0, 303.4, 10.0), 62.0)
    sc.camera = c
    import hd_light as L
    r = L.apply(o["preset"], sc, cam=None, samples=int(o["samples"]),
                res=(sc.render.resolution_x, sc.render.resolution_y))
    print("[lab] light %r" % (r,))
    # --- replicate look/render.py:build_rig() so the lab frames are comparable
    # with the production V-log renders (same sky model, same ambient fill, same
    # exposure).  Without hd_sky's world the lab came out ~0.8 EV dark with a
    # flat constant above the horizon, which hid every ledge on the crag.
    elev = float(o["elev"])
    azim = float(o["azim"])
    L.sky(o["preset"], elev, azim)
    if o["sky"] != "0":
        try:
            import hd_sky as SKY
            SKY.world(sc, o["sky"], elevation=elev, azimuth=azim,
                      ambient=float(o["ambient"]), strength=float(o["sky_strength"]))
            print("[lab] hd_sky %s elev=%.0f azim=%.0f amb=%.2f"
                  % (o["sky"], elev, azim, float(o["ambient"])))
        except Exception as exc:                                # noqa: BLE001
            print("[lab] hd_sky skipped:", exc)
    L.sun(o["preset"], elev, azim)
    sc.view_settings.exposure = float(o["exposure"])
    print("[lab] exposure -> %.2f" % float(o["exposure"]))
    for fn, kw in (("bounce", {}), ("contact", {}),
                   ("haze", {"center": None, "mul": float(o["haze_mul"]),
                             "extent": float(o["haze_extent"])})):
        try:
            getattr(L, fn)(o["preset"], **kw)
        except Exception as exc:                                # noqa: BLE001
            print("[lab] %s skipped:" % fn, exc)
    try:
        L.post(o["preset"])
    except Exception as exc:                                    # noqa: BLE001
        print("[lab] post skipped:", exc)
    if str(o.get("nocomp", "0")) not in ("0", "", "False"):
        # bypass the compositor (glare/bloom) so a single NaN pixel cannot be
        # smeared over the whole frame
        sc.use_nodes = False
        print("[lab] compositor OFF")
    sc.view_settings.exposure = float(o["exposure"])
    if str(o.get("dump", "0")) not in ("0", "", "False"):
        dump_mesh("rock_face", 0.0, 303.4)
    names = [s.strip() for s in o["shots"].split(",") if s.strip()]
    os.makedirs(OUT, exist_ok=True)
    for nm in names:
        if nm not in SHOTS:
            print("[lab] no shot %r" % nm)
            continue
        loc, tgt, lens = SHOTS[nm]
        c.location = loc
        from mathutils import Vector
        c.data.lens = lens
        v = (loc[0] - tgt[0], loc[1] - tgt[1], loc[2] - tgt[2])
        c.rotation_euler = Vector(v).to_track_quat("Z", "Y").to_euler()
        p = os.path.join(OUT, "rock_%s_%s.png" % (o["tag"], nm))
        sc.render.filepath = p
        if str(o.get("probe", "0")) not in ("0", "", "False"):
            bpy.context.view_layer.update()
            probe(sc, c, nm)
        if str(o.get("sweep", "0")) not in ("0", "", "False"):
            # hd_sky was rewritten at 11:28 on 11-02 (emissive dome, gain 14x)
            # and every frame since is blown white.  Find the exposure that
            # lands the average where the old frames had it.
            for ev in (-2.2, -3.4, -4.6, -5.8, -7.0):
                sc.view_settings.exposure = ev
                sc.render.filepath = p.replace(".png", "_e%+.1f.png" % ev)
                t1 = __import__("time").time()
                bpy.ops.render.render(write_still=True)
                img = bpy.data.images.get("Render Result")
                mean = -1.0
                if img is not None and len(img.pixels):
                    px = img.pixels[:]
                    mean = sum(px[0::4]) / max(1, len(px) // 4)
                print("[lab] %-8s exp %+.1f %.1fs mean %.3f -> %s"
                      % (nm, ev, __import__("time").time() - t1, mean,
                         sc.render.filepath))
            sc.view_settings.exposure = float(o["exposure"])
            continue
        if str(o.get("engine", "eevee")) != "eevee":
            # EEVEE started writing flat white frames at 11:30 on 11-02, with
            # the result independent of exposure, camera and geometry.  Render
            # the same shot through the other engines to find out whether the
            # scene or the EEVEE backend is at fault.
            for eng in [e.strip() for e in o["engine"].split(",") if e.strip()]:
                if eng == "wb":
                    sc.render.engine = "BLENDER_WORKBENCH"
                    sh = sc.display.shading
                    sh.light = "STUDIO"
                    sh.color_type = "MATERIAL"
                    sh.show_shadows = True
                    sh.show_cavity = True
                elif eng == "cy":
                    sc.render.engine = "CYCLES"
                    sc.cycles.device = "CPU"
                    sc.cycles.samples = int(o["samples"])
                    sc.cycles.use_denoising = False
                    sc.cycles.max_bounces = 4
                sc.render.filepath = p.replace(".png", "_%s.png" % eng)
                t1 = __import__("time").time()
                bpy.ops.render.render(write_still=True)
                print("[lab] %-8s %-3s %.1fs -> %s"
                      % (nm, eng, __import__("time").time() - t1,
                         sc.render.filepath))
            continue
        t1 = __import__("time").time()
        bpy.ops.render.render(write_still=True)
        print("[lab] %-8s %.1fs -> %s" % (nm, __import__("time").time() - t1, p))
        try:
            img = bpy.data.images.get("Render Result")
            if img is not None and len(img.pixels):
                px = img.pixels[:]
                n = len(px) // 4
                m = [0.0, 0.0, 0.0]
                for c in range(3):
                    m[c] = sum(px[c::4]) / n
                print("[lab]   rgb mean %.3f %.3f %.3f  max %.2f"
                      % (m[0], m[1], m[2], max(px)))
        except Exception as exc:                                # noqa: BLE001
            print("[lab]   pixels? %s" % exc)
    if HR.build.LAST is not None and site == "crag":
        crag = HR.build.LAST
        print("[lab] report %r" % (crag.report(),))
        pm = peak_mem()
        print("[lab] peak working set %.0f MB" % pm)
        if pm < 0:
            print("[lab] peak working set unavailable")
        if str(o.get("rows", "0")) not in ("0", "", "False"):
            import math as _m
            for deg in (0.0, 90.0, 180.0, 270.0):
                th = _m.radians(deg)
                print("[rows] theta=%6.1f deck_z=%.2f tal_top=%.2f" % (
                    deg, crag.deck_z(th), crag.z_talus_top(th)))
                for k, row in enumerate(crag.rows_at(th)):
                    print("[rows]   %2d %-8s z=%7.3f off=%6.3f lay=%s" % (
                        (k,) + tuple(row[:3]) + (row[3],)))
    if str(o.get("hm", "0")) not in ("0", "", "False"):
        # what does the landscape height field actually do out at the town
        # edge?  the ring has to meet it, or it floats or gets eaten
        try:
            import hd_landscape as LS
            print("[hm] FLAT_IN=%r HALF=%r" % (getattr(LS, "FLAT_IN", None),
                                               getattr(LS, "HALF", None)))
            for deg in (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0):
                a = __import__("math").radians(deg)
                row = []
                for rr in (880.0, 920.0, 947.2, 970.0, 1000.0, 1007.0,
                           1030.0, 1060.0, 1120.0):
                    xs = [rr * __import__("math").cos(a)]
                    ys = [rr * __import__("math").sin(a)]
                    try:
                        zz = LS.heights(xs, ys)
                        row.append("%.0f:%.2f" % (rr, zz[0]))
                    except Exception as exc:                    # noqa: BLE001
                        row.append("%.0f:?%s" % (rr, exc))
                print("[hm] az=%3.0f " % deg + " ".join(row))
        except Exception as exc:                                # noqa: BLE001
            print("[hm] skipped:", exc)
    if str(o.get("check", "0")) not in ("0", "", "False"):
        # A single NaN in the frame is enough: the glare pass blurs it across
        # the whole image and every render comes out flat white.  So check the
        # geometry and the node defaults before blaming the renderer.
        import math as _m
        nbad = 0
        for ob in bpy.data.objects:
            if ob.type != "MESH":
                continue
            b = 0
            for v in ob.data.vertices:
                if not (_m.isfinite(v.co.x) and _m.isfinite(v.co.y)
                        and _m.isfinite(v.co.z)):
                    b += 1
            if b:
                print("[check] %-18s bad verts %d/%d" % (ob.name, b,
                                                         len(ob.data.vertices)))
                nbad += b
        for m in bpy.data.materials:
            if not m.use_nodes or m.node_tree is None:
                continue
            for nd in m.node_tree.nodes:
                for s in nd.inputs:
                    try:
                        dv = s.default_value
                    except AttributeError:
                        continue
                    vals = (dv,) if isinstance(dv, float) else (
                        tuple(dv)[:4] if hasattr(dv, "__len__") else (str(dv),))
                    for x in vals:
                        if isinstance(x, float) and not _m.isfinite(x):
                            print("[check] %s node %s socket %s = %r"
                                  % (m.name, nd.name, s.name, vals))
                            nbad += 1
        print("[check] non-finite total %d" % nbad)
    print("[lab] done")


main()
