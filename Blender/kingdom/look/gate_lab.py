"""gate_lab.py -- the isolated stand for the gate v3 rebuild (GATE, 2026-11-02).

Nothing here touches a capital_*.blend: the scene is generated from hd_gate.py
into an empty file, saved as look/gate_lab.blend (<150 MB), and every render
opens only that.

    # build + verify + save the stand
    python look\\export_run.py gate_lab 900 LIGHT -- -b --factory-startup \
        --python look\\gate_lab.py -- --make

    # iterate (480x270, 8 samples) on the saved stand
    python look\\export_run.py gate_lab 900 LIGHT -- \
        -b look\\gate_lab.blend --python look\\gate_lab.py -- --res 480

    # the six delivery frames at 960x540
    python look\\export_run.py gate_lab 900 LIGHT -- \
        -b look\\gate_lab.blend --python look\\gate_lab.py -- --final

Modes: --make (build, verify, save), otherwise render from the loaded stand.
--rebuild forces a fresh build even when a stand is loaded.
"""
import math
import os
import random
import sys
import time

import bpy
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_KING, os.path.dirname(_KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hd_common as H                                            # noqa: E402
import hd_gate as G                                              # noqa: E402

LAB = os.path.join(_HERE, "gate_lab.blend")
OUT = os.path.join(r"E:\My World\Blender\renders\kingdom\look")
SEED = 20261102

# (name, camera location, look-at, lens) -- lens 38 gives the 30 deg vertical
# FOV of the game camera on a 16:9 frame, which is the read this landmark is
# judged by.
def game_cam(name, from_face, lens=38.0):
    """The real in-game rig: 34 m behind the player, 52 deg down, vFOV 30.

    At that pitch the frame's top edge is 37 deg below horizontal, so only
    ground within 14.6 m of the player is on screen.  Standing 4 m from the
    gate, the top of the frame is 8.0 m up the facade: the tunnel, the grille,
    the bridge and the plinths -- nothing above them -- is what a player reads.
    """
    d = 34.0
    pitch = math.radians(52.0)
    cam = Vector((0.0, G.G3["Y_OUT"] + from_face + d * math.cos(pitch),
                  d * math.sin(pitch)))
    tgt = cam + Vector((0.0, -math.cos(pitch), -math.sin(pitch))) * 30.0
    return H.camera(name, cam, tgt, lens)


SHOTS = [
    ("gc00",   None, None, None),                       # the money frame
    ("gc04",   None, None, None),
    ("portal", (0.0, 26.00, 2.00),  (0.0, 7.40, 4.60),  30.0),
    ("tower",  (16.50, 26.00, 1.70), (9.00, 4.00, 14.00), 28.0),
    ("walk",   (33.00, -0.40, 11.60), (12.00, -0.20, 9.60), 20.0),
    ("bastion", (44.00, 24.00, 5.00), (30.00, 6.00, 9.00), 45.0),
    ("grille", (1.60, 9.60, 1.50),  (0.00, G.G3["SILL_Y"], 0.75), 45.0),
    ("water",  (22.00, 22.00, 2.20), (10.50, 6.00, -0.30), 40.0),
    ("inside", (0.00, 12.50, 2.20),  (0.00, -9.00, 4.20), 26.0),
]
EXTRA = [
    ("top",    (58.00, 52.00, 72.00), (0.0, 4.00, 8.00), 50.0),
    ("road",   (0.0, 34.00, 1.70),  (0.0, 6.00, 7.00), 30.0),
]
# the face is (20.93 + P) from the camera, so the frame's top edge cuts the
# facade at 26.79 - 0.754*(20.93+P): 11.0 m at P=0, 8.0 m at P=4, and nothing
# at all beyond P=8.  The gate has to read inside that band.
GAME_DIST = {"gc00": 0.0, "gc04": 4.0}


def arg(name, default=None):
    av = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if name in av:
        i = av.index(name)
        if i + 1 < len(av) and not av[i + 1].startswith("--"):
            return av[i + 1]
        return True
    return default


# --------------------------------------------------------------------------
#  lights: the key comes from the moat side, because the gate faces +Y and a
#  back-lit elevation was exactly the "flat grey slab" the old build rendered.
# --------------------------------------------------------------------------
def sun(name, d, energy, color=(1.0, 1.0, 1.0), angle=6.0, shadow=True):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = energy
    ld.angle = math.radians(angle)
    ld.color = color
    if hasattr(ld, "use_shadow"):
        ld.use_shadow = shadow
    ob = bpy.data.objects.new(name, ld)
    bpy.context.collection.objects.link(ob)
    ob.rotation_euler = Vector(d).normalized().to_track_quat("Z", "Y").to_euler()
    return ob


def lights(P):
    H.setup_world(sun_energy=0.0, sky="#a8c6e4", fill=0.0)
    w = bpy.context.scene.world
    if w is not None and w.use_nodes:
        for node in w.node_tree.nodes:
            if node.type == "BACKGROUND":
                node.inputs[0].default_value = (0.52, 0.62, 0.76, 1.0)
                node.inputs[1].default_value = 0.55
    sun("key", (0.52, 0.76, 0.62), 4.4, (1.0, 0.97, 0.90), angle=4.0)
    sun("fill", (-0.30, -0.86, 0.30), 1.05, (0.70, 0.81, 1.0), shadow=False)
    sun("rim", (-0.86, 0.30, 0.44), 1.35, (0.88, 0.92, 1.0), shadow=False)
    # a warm bounce out of the passage, so the tunnel is not a black hole
    ld = bpy.data.lights.new("tunnel", "AREA")
    ld.energy = 90.0
    ld.size = 5.0
    ld.color = (1.0, 0.74, 0.46)
    ob = bpy.data.objects.new("tunnel", ld)
    ob.location = (0.0, -3.0, 3.4)
    ob.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    bpy.context.collection.objects.link(ob)


# --------------------------------------------------------------------------
#  build + verify
# --------------------------------------------------------------------------
def make():
    H._clear()
    t0 = time.time()
    MAT = G.materials()
    G.g3_weather(MAT)
    rng = random.Random(SEED)
    obs = G.build(MAT, rng)
    for ob in obs:
        if ob is not None and ob.type == "MESH":
            ob.data.calc_loop_triangles()
    tris = sum(len(ob.data.loop_triangles) for ob in obs
               if ob is not None and ob.type == "MESH")
    lo, hi = H.bbox(obs)
    print("[lab] parts=%d tris=%d  bbox lo=(%.2f,%.2f,%.2f) hi=(%.2f,%.2f,%.2f)"
          % (len(obs), tris, lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]), flush=True)
    print("[lab] built in %.1fs" % (time.time() - t0), flush=True)
    lights(MAT)
    verify(obs)
    city_check()
    bpy.ops.wm.save_as_mainfile(filepath=LAB)
    print("[lab] saved %s (%.1f MB)" % (LAB, os.path.getsize(LAB) / 1e6), flush=True)


def _mesh_objs(prefix):
    return [o for o in bpy.data.objects
            if o.type == "MESH" and o.name.startswith(prefix)]


def _cast(origin, direction, dist=1000.0):
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    try:
        return sc.ray_cast(dg, Vector(origin), Vector(direction), distance=dist)
    except TypeError:
        return sc.ray_cast(Vector(origin), Vector(direction), distance=dist)


def _zmin(obs):
    return min((ob.matrix_world @ v.co).z for ob in obs for v in ob.data.vertices)


def city_check():
    """The city does not hand hd_gate this module's palette, and never will.

    capital.py passes hd_glue.hd_materials(MAT): capital's own key names.  So
    build_gatehouse(MAT, rng) has to survive a dict that has neither `void` nor
    `sill` nor `moss` in it -- `_g3_P` fills those -- and must return a flat
    list of MESH objects with no exception, because hd_glue.guard() would
    silently drop the entire gate.
    """
    keys = ("stone", "stone_warm", "stone_dark", "stone_pale", "iron",
            "iron_dark", "wood", "wood_dark", "tile", "slate", "gold",
            "plaster", "banner_red", "banner_blue", "water", "cobble",
            "glow", "glass", "ground", "grass", "earth")
    MAT = {k: bpy.data.materials.new("citytest_" + k) for k in keys}
    n0 = len(bpy.data.objects)
    try:
        obs = G.build_gatehouse(MAT, random.Random(7))
        obs = [o for o in obs if o is not None]
        tris = sum(len(o.data.polygons) for o in obs if o.type == "MESH")
        ok = bool(obs) and all(o.type == "MESH" for o in obs)
        print("[check] capital-shaped MAT -> %d objects, %d faces, %s"
              % (len(obs), tris, "OK" if ok else "PROBLEM"), flush=True)
        if not ok:
            print("[check] PROBLEM: build_gatehouse returned non-mesh objects")
        for o in obs:
            bpy.data.objects.remove(o, do_unlink=True)
    except Exception as exc:                                    # noqa: BLE001
        print("[check] PROBLEM: build_gatehouse raised %s: %s"
              % (type(exc).__name__, exc), flush=True)
        for o in list(bpy.data.objects)[n0:]:
            bpy.data.objects.remove(o, do_unlink=True)


def verify(obs):
    """The three P0 tests, measured on geometry, never on a screenshot."""
    bugs = []
    Gc = G.G3

    # --- P0-2: the grille lands on the stone sill -------------------------
    pc = _mesh_objs("g3_pc")
    sill = [o for o in bpy.data.objects if o.name == "g3_sill"]
    if pc and sill:
        zb = _zmin(pc)
        top = max((o.matrix_world @ v.co).z for o in sill for v in o.data.vertices)
        gap = zb - top
        print("[check] portcullis lowest point z=%.4f  sill top z=%.4f  gap=%+.4f m"
              % (zb, top, gap), flush=True)
        if gap > 0.02 or gap < -0.06:
            bugs.append("portcullis gap %.3f m" % gap)
    else:
        bugs.append("portcullis or sill missing (pc=%d sill=%d)" % (len(pc), len(sill)))

    # --- P0-1: the water is cut round the plinths, and the drums are closed
    water = _mesh_objs("g3_water")
    if not water:
        bugs.append("no water mesh")
    else:
        keep = G.gate_keepout()
        worst = 1e9
        for o in water:
            for v in o.data.vertices:
                w = o.matrix_world @ v.co
                if abs(w.z - Gc["WATER_Z"]) > 1e-4:
                    bugs.append("water vertex off the water plane: z=%.3f" % w.z)
                    break
                for (kx, ky, kr) in keep:
                    d = math.hypot(w.x - kx, w.y - ky)
                    worst = min(worst, d - (kr - 0.60))
        intru = max(0.0, -worst) if worst < 1e9 else 0.0
        print("[check] water: nearest vertex-to-keepout margin %+.3f m "
              "(a grid cell may intrude 0.57 m; the wet shelf covers it)"
              % (worst if worst < 1e9 else 0.0), flush=True)
        if worst < 1e9 and worst < -0.02:
            bugs.append("water inside the plinth keep-out by %.2f m" % intru)

    for (kx, ky, kr) in G.gate_keepout():
        # the top must be a deck, not an open pool
        hit, loc, nor, idx, ob, mx = _cast((kx, ky, 60.0), (0.0, 0.0, -1.0), 80.0)
        zt = loc.z if hit else -99.0
        print("[check] drum (%+.1f,%.1f) top ray -> %s z=%.2f"
              % (kx, ky, (ob.name if hit else "MISS"), zt), flush=True)
        if not hit or zt < Gc["TOW_PAR"] - 0.30:
            bugs.append("drum top open at (%+.1f,%.1f): first hit z=%.2f"
                        % (kx, ky, zt))
        # the base must be closed under the bed, or the moat shows inside it
        hit, loc, nor, idx, ob, mx = _cast((kx, ky, Gc["BED_Z"] - 1.60),
                                           (0.0, 0.0, 1.0), 20.0)
        zb2 = loc.z if hit else -99.0
        print("[check] drum (%+.1f,%.1f) under-bed ray -> %s z=%.2f"
              % (kx, ky, (ob.name if hit else "MISS"), zb2), flush=True)
        if not hit or zb2 > Gc["BED_Z"] + 0.10:
            bugs.append("drum base open at (%+.1f,%.1f): first hit z=%.2f"
                        % (kx, ky, zb2))

    # --- the passage has to be deep enough to read as a tunnel ------------
    depth = Gc["Y_OUT"] - Gc["Y_IN"]
    print("[check] passage clear width %.2f m, depth %.2f m, crown %.2f m"
          % (2.0 * Gc["R_PASS"], depth, Gc["Z_SPRING"] + Gc["R_PASS"]), flush=True)
    if depth < 12.0:
        bugs.append("passage only %.1f m deep" % depth)
    # ...and it has to be a hole.  A ray down the centre from the road must get
    # past the facade plane (Y_OUT); if it stops there, the arch is sealed.
    hit, loc, nor, idx, ob, mx = _cast((0.0, 30.0, 3.20), (0.0, -1.0, 0.0), 60.0)
    print("[check] centreline ray from the road -> %s at y=%+.2f (facade %+.2f)"
          % ((ob.name if hit else "MISS"), loc.y if hit else 0.0, Gc["Y_OUT"]),
          flush=True)
    if not hit or loc.y > Gc["Y_OUT"] - 0.35:
        bugs.append("passage sealed at the facade (first hit y=%+.2f)"
                    % (loc.y if hit else 0.0))

    # --- the curtain runs must butt the gate, not run through it ----------
    intr = []
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.name.startswith("g3_curt"):
            continue
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            if abs(w.x) < Gc["CURT_X1"] - 1.0 and abs(w.y) < 12.0:
                intr.append(o.name)
                break
    print("[check] curtain meshes inside the gate footprint: %d %s"
          % (len(intr), intr[:4]), flush=True)
    if intr:
        bugs.append("curtain crosses the gate: %s" % intr[:3])

    # --- nothing may sink under the moat bed ------------------------------
    lowest = min(_zmin([o]) for o in obs if o.type == "MESH")
    print("[check] lowest geometry z=%.2f (bed %.2f)" % (lowest, Gc["BED_Z"]),
          flush=True)
    if lowest < Gc["BED_Z"] - 0.90:
        bugs.append("geometry %.2f m under the bed" % (lowest - Gc["BED_Z"]))

    if bugs:
        print("[check] *** %d PROBLEM(S) ***" % len(bugs), flush=True)
        for b in bugs:
            print("[check]   - %s" % b, flush=True)
    else:
        print("[check] all P0 measurements pass", flush=True)
    return bugs


# --------------------------------------------------------------------------
#  render
# --------------------------------------------------------------------------
def render(final=False, res=None, only=None):
    if not any(o.type == "MESH" for o in bpy.data.objects):
        make()
    if res is None:
        res = (960, 540) if final else (480, 270)
    samples = 32 if final else 8
    H.setup_engine(samples=samples, res=res, gpu=True)
    shots = SHOTS if final else (SHOTS + EXTRA)
    t0 = time.time()
    for name, loc, look, lens in shots:
        if only and name not in only:
            continue
        if name in GAME_DIST:
            cam = game_cam("cam_" + name, GAME_DIST[name])
        else:
            cam = H.camera("cam_" + name, loc, look, lens)
        path = os.path.join(OUT, "gate2_%s.png" % name)
        H.render_to(path, cam)
        print("[lab] wrote %s  (%.0fs)" % (path, time.time() - t0), flush=True)


def main():
    if arg("--make") or arg("--rebuild"):
        make()
        if arg("--make"):
            return 0
    render(final=bool(arg("--final")), only=arg("--only"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
