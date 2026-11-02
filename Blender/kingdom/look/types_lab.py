"""types_lab.py - lab scene and contact sheet for the six hd_types buildings.

    python look/export_run.py types_fast 900 LIGHT -- -b --python look/types_lab.py -- --fast
    python look/export_run.py types_final 1800 LIGHT -- -b --python look/types_lab.py

Everything is built into ONE scene, spaced along X at real size, so a single
Blender launch gives all six types and all their cameras.  Nothing is loaded
from disk: the scene is created from scratch, which is why this run can never
trip the >400 MB blend sentinel.

Per kind, three cameras:
    fit   the whole footprint, aerial at the game pitch (what the sheet uses)
    game  the real in-game camera: 34 m out, 52 deg pitch, 37.8 mm
    eye   1.72 m eye level, standing in front of the facade

Output (E:\\My World\\Blender\\renders\\kingdom\\look):
    types_<kind>_fit.png   960x540 (480x270 with --fast)
    types_<kind>_game.png  960x540
    types_<kind>_eye.png   only training_ground and barracks (960x540)
    TYPES_sheet.png        2 x 6 contact sheet: fit row over game row
"""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
for _p in (KING, os.path.dirname(KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                              # noqa: E402
import hd_common as H                                   # noqa: E402
import medkit as K                                      # noqa: E402
import hd_types as T                                    # noqa: E402

OUT = r"E:\My World\Blender\renders\kingdom\look"
RES = (960, 540)
SAMPLES = 24
LENS_PLAYER = 37.8
EYE_LENS = 24.0
EYE_KINDS = ("training_ground", "barracks")

#: the mill's whole point is the wheel, which lives on -X: the default +X
#: three-quarter view hid it behind the house
FIT_AZIM = {"mill": -36.0, "stable_yard": 22.0}


def _palette(variant=0):
    """The same material path the city uses: houses -> weathering -> glue."""
    import hd_houses as S
    MAT = S.make_mats()
    try:
        import hd_surface as SFC
        SFC.apply_weathering(MAT)
    except Exception as exc:
        print("[lab] weathering skipped: %r" % (exc,), flush=True)
    try:
        import capital_hd_glue as G
        MAT = G.house_mats(MAT, variant)
    except Exception as exc:
        print("[lab] house_mats skipped: %r" % (exc,), flush=True)
    return MAT


def _aim(target, dist, pitch_deg, azim_deg=0.0):
    """Camera on a sphere around `target`.

    azim 0 looks from +Y (the street side, which is what the city camera does);
    the fit shot uses ~30 deg so both the facade and one flank are visible - a
    pure +Y view of a 50 m roof tells you nothing about the building.
    """
    a = math.radians(pitch_deg)
    z = math.radians(azim_deg)
    h = dist * math.cos(a)
    return (target[0] + h * math.sin(z), target[1] + h * math.cos(z),
            target[2] + dist * math.sin(a))


def eval_tris(parts):
    """Honest count: modifiers applied through the depsgraph."""
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    return n


def build_all(only, seed=7):
    """Build every wanted type at real size in one row; returns [(kind, x, ...)]."""
    MAT = _palette(0)
    kinds = [k for k in T.ORDER if (not only or k in only)]
    rows = []
    cursor = 0.0
    plan = []
    for kind in kinds:
        w, d, h = T.FOOT[kind]
        plan.append((kind, cursor + w * 0.5, w, d, h))
        cursor += w + 12.0
    shift = -cursor * 0.5 + 6.0
    for (kind, x0, w, d, h) in plan:
        x0 += shift
        try:
            parts = T.build(kind, MAT, __import__("random").Random(seed + 11), x=x0,
                            y=0.0, rot=0.0)
        except Exception:
            print("[lab] !! %s failed to build" % kind, flush=True)
            traceback.print_exc()
            parts = []
        lo, hi = H.bbox(parts) if parts else (None, None)
        rows.append((kind, x0, w, d, h, parts,
                     (lo.copy(), hi.copy()) if parts else (None, None)))
        print("[lab] %-16s objs=%4d tris=%6d eval=%6d  w=%.1f d=%.1f h=%.1f"
              % (kind, len(parts), H.tri_count(parts), eval_tris(parts), w, d, h),
              flush=True)
        if parts:
            print("[lab]     bbox (%.1f, %.1f, %.1f) - (%.1f, %.1f, %.1f)"
                  % (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z), flush=True)
    return MAT, rows


def cameras(kind, x0, w, d, h):
    """fit / game / eye camera rigs for one type."""
    mid = (x0, 0.0, h * 0.42)
    fit_d = max(28.0, 1.80 * max(w, d))
    game = _aim((x0, 0.0, min(h * 0.5, 4.2)), 34.0, 52.0)
    return [
        ("fit", _aim(mid, fit_d, 40.0, FIT_AZIM.get(kind, 30.0)), mid, LENS_PLAYER),
        ("game", game, (x0, 0.0, min(h * 0.5, 4.2)), LENS_PLAYER),
        ("eye", (x0 + w * 0.30, -(d * 0.5 + 11.0), 1.72),
         (x0 - w * 0.10, 0.0, 3.1), EYE_LENS),
    ]


def render_all(rows, fast, only):
    os.makedirs(OUT, exist_ok=True)
    shots_wanted = ("fit", "game") if fast else ("fit", "game", "eye")
    made = []
    for (kind, x0, w, d, h, parts, bb) in rows:
        if not parts:
            continue
        for (tag, loc, tgt, lens) in cameras(kind, x0, w, d, h):
            if tag not in shots_wanted:
                continue
            if tag == "eye" and kind not in EYE_KINDS and not fast:
                continue
            cam = H.camera("cam_%s_%s" % (kind, tag), loc, tgt, lens=lens)
            path = os.path.join(OUT, "types_%s_%s.png" % (kind, tag))
            H.render_to(path, cam)
            bpy.data.objects.remove(cam, do_unlink=True)
            made.append((kind, tag, path))
            print("[lab] wrote %s" % path, flush=True)
    return made


def contact_sheet(made, cols, rows_n, path, cell=(480, 270)):
    """2 x 6 sheet; cell (row, col) = row0 fit / row1 game.  numpy, no PIL."""
    import numpy as np
    grid = {}
    for (kind, tag, p) in made:
        grid[(tag, kind)] = p
    order = [r[0] for r in laid_out_order(made)]
    W, Hh = cell[0] * cols, cell[1] * rows_n
    canvas = np.zeros((Hh, W, 4), dtype=np.float32)
    canvas[..., 3] = 1.0
    placed = 0
    rowof = {"fit": 0, "game": 1}
    for col, kind in enumerate(order):
        for tag, r in rowof.items():
            p = grid.get((tag, kind))
            if not p or not os.path.exists(p):
                continue
            img = bpy.data.images.load(p)
            iw, ih = img.size
            px = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
            ys = (np.arange(cell[1]) * ih // cell[1]).clip(0, ih - 1)
            xs = (np.arange(cell[0]) * iw // cell[0]).clip(0, iw - 1)
            small = px[ys][:, xs]
            y0 = Hh - (r + 1) * cell[1]
            canvas[y0:y0 + cell[1], col * cell[0]:(col + 1) * cell[0]] = small
            bpy.data.images.remove(img)
            placed += 1
    img = bpy.data.images.new("types_sheet", W, Hh, alpha=True, float_buffer=False)
    try:
        img.pixels.foreach_set(canvas.ravel())
    except Exception:
        img.pixels = canvas.ravel().tolist()
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("[lab] sheet %s  %dx%d  cells=%d" % (path, W, Hh, placed), flush=True)


def laid_out_order(made):
    seen = []
    for (kind, tag, p) in made:
        if kind not in [s[0] for s in seen]:
            seen.append((kind, tag, p))
    return seen


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    global RES, SAMPLES
    fast = "--fast" in argv
    if fast:
        RES = (480, 270)
        SAMPLES = 8

    H._clear()
    MAT, rows = build_all(only, 7)
    H.diorama_floor(MAT["stone"], 340.0)

    sc = bpy.context.scene
    import hd_light as L
    import hd_sky as SKY
    L.apply("morning_town", sc, samples=SAMPLES, res=RES)
    SKY.world(sc, "morning_town", ambient=0.38)
    try:
        sc.view_settings.exposure = -2.20
    except Exception:
        pass
    print("[lab] res=%s samples=%s" % (RES, SAMPLES), flush=True)

    made = render_all(rows, fast, only)
    if not fast and len(made) >= 6:
        contact_sheet(made, 6, 2, os.path.join(OUT, "TYPES_sheet.png"))
    print("[lab] done: %d images" % len(made), flush=True)


if __name__ == "__main__":
    main()
