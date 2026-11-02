"""_surf_ablate_castle.py -- per-layer ablation of hd_surface on the REAL castle.

The wall probe (`_surf_probe_wall.py`) is cheap and flat, so its ablation table
answers "what does this layer do on a featureless face".  This script answers
the question that actually matters: what does each layer cost in exposure and
buy in local contrast on the 18 000-object gatehouse, where every corbel and
reveal is real geometry.

It builds the castle once, renders the pristine closeup once, then for every
variant copies the PRISTINE materials (never a weathered one), applies
`hd_surface.weather_material` with one recipe key overridden, points every
material slot at the copy and renders the same camera again.  One Blender
launch, one Cycles kernel compile, N+1 renders.

USAGE
    blender.exe --background --factory-startup --python _surf_ablate_castle.py
    ... -- --only cur,no_shelter --spp 24 --res 800x450
    python _surf_ablate_castle.py --report     # read the PNGs, print the table
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# the render directory hd_common uses; recomputed here so --report works from
# plain python too (no bpy import on that path)
OUT = os.path.join(os.path.dirname(_HERE), "renders", "kingdom")

# one entry per layer: the recipe keys that switch it off
VARIANTS = [
    ("cur", {}),
    ("no_shelter", {"shelter": 0.0}),
    ("no_cav", {"cav": 0.0}),
    ("no_blk", {"blk_amp": 0.0}),
    ("no_bleach", {"bleach": 0.0}),
    ("no_zone", {"zone": 0.0}),
    ("no_patch", {"patch": 0.0}),
    ("no_drip", {"drip": 0.0}),
    ("no_foot", {"foot": 0.0}),
    # not a layer: a deliberate over-drive of the three block-scale layers, to
    # find the ceiling of the 32 px metric before the image turns into a quilt
    ("x_extreme", {"blk_amp": 1.0, "patch": 1.7, "phase": 2.2, "zone": 1.1}),
]

CROP = (240, 120, 420, 300)


def _argv():
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]
    return sys.argv[1:]


def _arg(args, name, default):
    if name in args:
        return args[args.index(name) + 1]
    return default


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def _report(paths):
    import numpy as np
    import _surf_stats as ST

    def one(path, box):
        g = ST.load(path)
        if box is not None:
            x0, y0, x1, y1 = box
            g = g[y0:y1, x0:x1]
        lm = ST.luma(g)
        blocks = ST._blocks(lm, 32)
        lstd = float(blocks.std()) if blocks is not None else 0.0
        return float(lm.mean()), float(lm.std()), lstd, int((ST.greenness(g) > 8).sum())

    print("=" * 78)
    print("castle ablation -- frame and stone crop")
    print("  %-12s %8s %8s %8s %8s | %8s %8s %8s"
          % ("variant", "mean", "sigma", "gmax8", "lstd32", "cropmean", "cropsig", "crop32"))
    base = None
    for tag, path in paths:
        if not os.path.exists(path):
            print("  %-12s (missing)" % tag)
            continue
        m, s, l, gr = one(path, None)
        cm, cs, cl, cgr = one(path, CROP)
        if base is None:
            base = (m, s, l, gr, cm, cs, cl, cgr)
        print("  %-12s %8.2f %8.2f %8d %8.2f | %8.2f %8.2f %8.2f"
              % (tag, m, s, gr, l, cm, cs, cl))
    if base is not None:
        m0, s0, l0, g0, cm0, cs0, cl0, cg0 = base
        print("-" * 78)
        print("  %-12s %8s %8s %8s %8s | %8s %8s %8s"
              % ("delta vs pristine", "dmean", "dsig", "dgreen", "lstd32", "",
                 "cropd%", "crop32"))
        for tag, path in paths:
            if not os.path.exists(path):
                continue
            m, s, l, gr = one(path, None)
            cm, cs, cl, cgr = one(path, CROP)
            print("  %-12s %+8.2f %+8.2f %+8d %8.3f | %+8.1f%% %8.3f"
                  % (tag, m - m0, s - s0, gr - g0, l / l0 if l0 else 0,
                     100.0 * (cm / cm0 - 1.0) if cm0 else 0.0,
                     cl / cl0 if cl0 else 0))
    print("=" * 78)


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def main():
    args = _argv()
    if args and args[0] == "--report":
        _report([("pristine", os.path.join(OUT, "_surf_cab_pristine.png"))]
                + [(t, os.path.join(OUT, "_surf_cab_%s.png" % t))
                   for t, _ in VARIANTS])
        return

    import bpy
    import hd_common as H
    import hd_surface as S
    import _surface_ab as AB

    only = _arg(args, "--only", "")
    pick = set(x for x in only.split(",") if x)
    spp = int(_arg(args, "--spp", "48"))
    res = _arg(args, "--res", "800x450")
    res = tuple(int(v) for v in res.lower().split("x"))

    t0 = time.time()
    H._clear()
    print("[cab] blender %s" % bpy.app.version_string, flush=True)
    C, MAT, parts = AB._build_castle()
    lo, hi = H.bbox(parts)
    print("[cab] castle %d objects, bbox %.1f..%.1f z, %.1fs"
          % (len(parts), lo.z, hi.z, time.time() - t0), flush=True)
    H.setup_world()
    C.fill_light()
    H.setup_engine(samples=spp, res=res)

    # exactly the closeup camera used by _surface_ab.py
    close_pos = ((hi.x * 0.16, hi.y + 46.0, lo.z + 13.0),
                 (0.0, hi.y - 5.0, lo.z + 12.0),
                 42.0)
    cam = H.camera("cam_cab", close_pos[0], close_pos[1], lens=close_pos[2])

    pristine = os.path.join(OUT, "_surf_cab_pristine.png")
    H.render_to(pristine, cam)
    print("[cab] pristine in %.1fs" % (time.time() - t0), flush=True)

    # untouched copies of every material, so a variant never inherits nodes
    orig = {}
    for key, mat in MAT.items():
        c = mat.copy()
        c.name = mat.name + "__p"
        c["_wx_base"] = mat.name
        if c.node_tree is mat.node_tree:
            print("[cab] WARNING material copy shares a node tree", flush=True)
        orig[key] = c

    objs = list(bpy.data.objects)
    print("[cab] %d objects to re-point" % len(objs), flush=True)

    for tag, over in VARIANTS:
        if tag != "cur" and pick and tag not in pick:
            continue
        if tag == "cur" and pick and "cur" not in pick:
            continue
        t1 = time.time()
        by_base = {}
        for key, src in orig.items():
            v = src.copy()
            v.name = "%s__%s" % (src["_wx_base"], tag)
            v["_wx_base"] = src["_wx_base"]
            by_base[src["_wx_base"]] = v
        # apply with the variant's overrides, one kind at a time
        patched = {}
        for key, v in by_base.items():
            kind = S.resolve_kind(key)
            if kind is None:
                continue
            if kind not in patched:
                patched[kind] = dict(S.RECIPES.get(kind, {}))
                S.RECIPES.setdefault(kind, {}).update(over)
            S.weather_material(v, kind, strength=1.0, seed=7)
        for kind, back in patched.items():
            S.RECIPES[kind] = back
        n = 0
        for ob in objs:
            for slot in ob.material_slots:
                m = slot.material
                if m is None:
                    continue
                tgt = by_base.get(m.get("_wx_base") or m.name)
                if tgt is not None and tgt is not m:
                    slot.material = tgt
                    n += 1
        bpy.context.view_layer.update()
        H.render_to(os.path.join(OUT, "_surf_cab_%s.png" % tag), cam)
        print("[cab] %s in %.1fs (%d slots)" % (tag, time.time() - t1, n),
              flush=True)

    print("[cab] done in %.1fs" % (time.time() - t0), flush=True)
    _report([("pristine", pristine)]
            + [(t, os.path.join(OUT, "_surf_cab_%s.png" % t)) for t, _ in VARIANTS])


if __name__ == "__main__":
    main()
