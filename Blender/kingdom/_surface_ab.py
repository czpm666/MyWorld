"""_surface_ab.py -- A/B harness for hd_surface.py (before / after weathering).

Builds the real castle through hd_castle's public API, renders it once with the
pristine medkit materials, applies `hd_surface.apply_weathering` to the very
same material dict, and renders the exact same camera again.

USAGE (headless):
    blender.exe --background --factory-startup --python _surface_ab.py
    blender.exe ... --python _surface_ab.py -- --quick        # 800x450 / 48 spp
    blender.exe ... --python _surface_ab.py -- --frame       # framing probe only
    blender.exe ... --python _surface_ab.py -- --closeup     # + a wall close-up

OUTPUT:
    <H.OUT_DIR>/surface_ab_before.png     1600x900, 128 spp
    <H.OUT_DIR>/surface_ab_after.png      same camera, weathered materials
    + surface_ab_closeup_before/after.png  (only with --closeup)
    + surface_ab_frame.png                 (only with --frame)

The before/after pair is the evidence file: identical geometry, identical
light, identical camera; only material nodes differ.
"""

import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bpy                                                    # noqa: E402
from mathutils import Vector                                  # noqa: E402

import hd_common as H                                         # noqa: E402
import medkit as K                                            # noqa: E402
import hd_surface as S                                        # noqa: E402

OUT = H.OUT_DIR

# one camera for both renders.  A high three-quarter from the city (+Y) side so
# the frame is masonry end to end: gatehouse, curtain wall, keep, roofs.
CAM_LOC = (84.0, 118.0, 44.0)
CAM_LOOK = (0.0, 0.0, 22.0)
CAM_LENS = 46.0

# close-up on the gatehouse drum tower: no orthographic trick, just 18 m away
CLOSE_LOC = (14.0, 66.0, 17.5)
CLOSE_LOOK = (6.5, 38.0, 13.5)
CLOSE_LENS = 62.0


# candidate framings used by --probe (loc, look, lens); the winner is copied
# into CAM_LOC / CAM_LOOK / CAM_LENS above
PROBE = [
    ((36.0, 111.7, 30.0), (0.0, 0.0, 19.0), 42.0),   # hd_castle's own cam_front
    ((84.0, 118.0, 44.0), (0.0, 0.0, 22.0), 46.0),   # front-right, high
    ((62.0, 128.0, 26.0), (0.0, 0.0, 20.0), 40.0),   # lower, wall-heavy
    ((104.0, 96.0, 38.0), (0.0, 0.0, 24.0), 50.0),   # more from +X side
]


def _argv():
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]
    return []


def _mat_list(MAT):
    seen = {}
    for key, mat in MAT.items():
        seen.setdefault(mat.name, []).append(key)
    for name in sorted(seen):
        mat = bpy.data.materials[name]
        nn = len(mat.node_tree.nodes) if mat.node_tree else 0
        print("  %-16s keys=%-28s nodes=%3d  wx=%s"
              % (name, ",".join(seen[name]), nn,
                 mat.get("_weathering_kind", "-")), flush=True)


def _floor_mat():
    """The diorama slab hd_castle.preview puts under the castle."""
    ob = H.diorama_floor(K.mat_flag("plateau", base="#7d7568", dark="#4a4438"),
                         320.0)
    return ob.data.materials[0] if ob.data.materials else None


def _stamp(path):
    """size + mtime of a source file, so a render can be traced to a revision."""
    try:
        st = os.stat(path)
        return "%s  %d bytes  %s" % (os.path.basename(path), st.st_size,
                                     time.strftime("%H:%M:%S",
                                                   time.localtime(st.st_mtime)))
    except OSError:
        return "%s (missing)" % path


def _auto_cam(lo, hi, pad=1.34, lens=45.0, dirn=(0.58, 1.0, 0.40)):
    """Three-quarter camera derived from a bbox - used for the fallback model."""
    ctr = (lo + hi) * 0.5
    size = hi - lo
    d = Vector(dirn).normalized()
    loc = ctr + d * (size.length * pad)
    look = Vector((ctr.x, ctr.y, ctr.z - size.z * 0.10))
    return tuple(loc), tuple(look), lens


def _build_castle():
    """hd_castle, or None when that module cannot build (it is under edit)."""
    import hd_castle as C
    print("[ab] source %s" % _stamp(C.__file__), flush=True)
    MAT = C.make_mats()
    # preview-only awning cloth (hd_castle.preview adds these the same way)
    MAT["cv_red"] = K.mat_cloth("canvas_red", "#8f3628")
    MAT["cv_gold"] = K.mat_cloth("canvas_gold", "#b1934f")
    MAT["cv_blue"] = K.mat_cloth("canvas_blue", "#3c5a70")
    rng = random.Random(11)
    parts = C.build(MAT, rng)
    return C, MAT, parts


def _build_market():
    """Fallback subject: the guild hall, which has a stable build(kind,MAT,rng)."""
    H._clear()
    import hd_market as MK
    print("[ab] source %s" % _stamp(MK.__file__), flush=True)
    MAT = MK.make_materials()
    parts = MK.build("guild_hall", MAT, random.Random(11))
    return MK, MAT, parts


def main():
    args = _argv()
    quick = "--quick" in args
    frame = "--frame" in args
    closeup = "--closeup" in args
    wide = "--wide" in args
    probe = "--probe" in args

    samples = 24 if frame else (48 if quick else 128)
    res = (960, 540) if frame else ((800, 450) if quick else (1600, 900))
    if probe:
        samples, res = 12, (720, 405)

    t0 = time.time()
    H._clear()
    print("[ab] blender %s" % bpy.app.version_string, flush=True)

    mode = "castle"
    try:
        C, MAT, parts = _build_castle()
    except Exception as exc:
        print("[ab] hd_castle could not build (%s: %s)"
              % (type(exc).__name__, exc), flush=True)
        print("[ab] falling back to hd_market.build('guild_hall', ...)", flush=True)
        mode = "market"
        C, MAT, parts = _build_market()

    lo, hi = H.bbox(parts)
    print("[ab] %s: %d objects, bbox (%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f), %.1fs"
          % (mode, len(parts), lo.x, lo.y, lo.z, hi.x, hi.y, hi.z,
             time.time() - t0), flush=True)
    print("[ab] %d tris" % H.tri_count(parts), flush=True)

    floor = _floor_mat()
    H.setup_world()
    if mode == "castle":
        C.fill_light()
    else:
        H.setup_world(sun_energy=4.4, sky="#a8c8ea")
    H.setup_engine(samples=samples, res=res)

    if probe:
        for i, (loc, look, lens) in enumerate(PROBE):
            cam = H.camera("cam_probe%d" % i, loc, look, lens=lens)
            H.render_to(os.path.join(OUT, "surface_ab_probe%d.png" % i), cam)
            print("[ab] probe %d done" % i, flush=True)
        return

    if mode == "castle":
        # The model is rebuilt by another module while this runs, so every
        # camera is derived from the bbox.  The gate face sits at +Y.
        # main A/B shot: close enough that a 2 cm joint covers a pixel and the
        # surface layers actually resolve - this is the "near view looks new"
        # that the review complained about.  --wide adds the whole building.
        sc = (hi - lo).length / 153.0
        prim_look = (hi.x * 0.02, hi.y - 8.0, lo.z + 12.0)
        prim_loc = (hi.x * 0.30, hi.y + 32.0, lo.z + 15.0)
        cam_loc, cam_look, cam_lens = prim_loc, prim_look, 52.0
        wide_pos = _auto_cam(lo, hi, pad=1.26, lens=46.0,
                             dirn=(0.578, 0.812, 0.115))
        close_pos = ((hi.x * 0.16, hi.y + 46.0, lo.z + 13.0),
                     (0.0, hi.y - 5.0, lo.z + 12.0),
                     42.0)
    else:
        cam_loc, cam_look, cam_lens = _auto_cam(lo, hi, pad=1.30, lens=44.0,
                                                dirn=(0.55, 1.0, 0.34))
        wide_pos = _auto_cam(lo, hi, pad=2.02, lens=42.0,
                             dirn=(0.55, 1.0, 0.34))
        close_pos = _auto_cam(lo, hi, pad=1.05, lens=58.0,
                              dirn=(0.35, 1.0, 0.20))

    print("[ab] cam %s look %s lens %.0f | wide %s | close %s"
          % (tuple(round(v, 1) for v in cam_loc),
             tuple(round(v, 1) for v in cam_look), cam_lens,
             tuple(round(v, 1) for v in wide_pos[0]),
             tuple(round(v, 1) for v in close_pos[0])), flush=True)
    cam = H.camera("cam_ab", cam_loc, cam_look, lens=cam_lens)
    wcam = H.camera("cam_wide", wide_pos[0], wide_pos[1],
                    lens=wide_pos[2]) if wide else None
    ccam = H.camera("cam_close", close_pos[0], close_pos[1],
                    lens=close_pos[2]) if closeup else None

    if frame:
        H.render_to(os.path.join(OUT, "surface_ab_frame.png"), cam)
        if wcam is not None:
            H.render_to(os.path.join(OUT, "surface_ab_frame_wide.png"), wcam)
        if ccam is not None:
            H.render_to(os.path.join(OUT, "surface_ab_frame_close.png"), ccam)
        print("[ab] framing probe done", flush=True)
        return

    print("[ab] materials BEFORE:", flush=True)
    _mat_list(MAT)

    before = os.path.join(OUT, "surface_ab_before.png")
    after = os.path.join(OUT, "surface_ab_after.png")
    t1 = time.time()
    H.render_to(before, cam)
    if wcam is not None:
        H.render_to(os.path.join(OUT, "surface_ab_wide_before.png"), wcam)
    if ccam is not None:
        H.render_to(os.path.join(OUT, "surface_ab_closeup_before.png"), ccam)
    print("[ab] before rendered in %.1fs" % (time.time() - t1), flush=True)

    # ---- the only difference between the two frames -----------------------
    t2 = time.time()
    S.apply_weathering(MAT, strength=1.0, seed=7)
    # the diorama slab is not in MAT: age it explicitly so the castle does not
    # stand on a suspiciously clean ground plane
    if floor is not None:
        S.weather_material(floor, "ground", strength=1.0, seed=7)
        print("[surface] %-14s -> ground     (%s)"
              % (floor.name, floor.get("_weathering_kind", "-")), flush=True)
    print("[ab] weathering applied in %.2fs" % (time.time() - t2), flush=True)
    print("[ab] materials AFTER:", flush=True)
    _mat_list(MAT)

    t3 = time.time()
    H.render_to(after, cam)
    if wcam is not None:
        H.render_to(os.path.join(OUT, "surface_ab_wide_after.png"), wcam)
    if ccam is not None:
        H.render_to(os.path.join(OUT, "surface_ab_closeup_after.png"), ccam)
    print("[ab] after rendered in %.1fs" % (time.time() - t3), flush=True)

    print("[ab] done in %.1fs" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
