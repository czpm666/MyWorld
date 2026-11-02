"""_surf_probe_wall.py -- fast, isolated look/measure loop for the stone recipe.

The full A/B harness needs 60 s of castle geometry before the first render, so
tuning a material through it costs ~2.5 min per idea.  This probe renders ONE
26 x 9.5 m ashlar wall (exactly the kind of `H.wall_course` core that carries
the real curtain walls) with hd_castle's own stone material, the same world and
the same fill light, at the same pixel density as the closeup (~27 px/m).

It renders:
    _surf_wall_before.png            pristine medkit stone
    _surf_wall_<tag>.png             one file per entry in VARIANTS

USAGE
    blender.exe --background --factory-startup --python _surf_probe_wall.py
    ... -- --res 800x450 --spp 40 --only v3,v4

Edit VARIANTS between runs: every entry is a dict of overrides on
hd_surface.RECIPES["stone"].
"""

import json
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy
import hd_common as H
import medkit as K
import hd_surface as S

OUT = H.OUT_DIR
WALL_W, WALL_H = 26.0, 9.5

# ---- what to try -----------------------------------------------------------
# defaults come from RECIPES["stone"]; each variant overrides a few keys
VARIANTS = {
    "cur": {},
    "no_cav": dict(cav=0.0),
    "no_zone": dict(zone=0.0),
    "no_patch": dict(patch=0.0),
    "no_course": dict(course=0.0),
    "no_joint": dict(joint=0.0, jmoss=0.0),
    "no_streak": dict(streak=0.0),
    "no_blk": dict(blk_amp=0.0),
    # the layers added in this round
    "no_bleach": dict(bleach=0.0),
    "no_jmoss": dict(jmoss=0.0),
    "no_drip": dict(drip=0.0),
    "no_foot": dict(foot=0.0),
    "no_splash": dict(splash=0.0),
    "no_moss": dict(moss=0.0),
}


def _argv():
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]
    return []


def build():
    H._clear()
    m = K.mat_stone("probe_stone")
    ob = H.box("probe_wall", H.Ts(0, 0, WALL_H * 0.5),
               (WALL_W, 0.62, WALL_H), m)
    # a ledge near the top: gives the drip/streak layers something to be
    # "under" and catches the sun the way a real string course does
    H.box("probe_ledge", H.Ts(0, 0.06, WALL_H - 1.05),
          (WALL_W, 0.86, 0.34), m, bev=0.02)
    H.diorama_floor(K.mat_flag("plateau", base="#7d7568", dark="#4a4438"), 120.0)
    H.setup_world()
    import hd_castle as C
    C.fill_light()
    cam = H.camera("cam_wall", (4.2, 33.0, 5.6), (0.0, 0.0, 4.4), lens=42.0)
    return ob, m, cam


def main():
    args = _argv()
    res = (800, 450)
    spp = 40
    only = None
    for i, a in enumerate(args):
        if a == "--res":
            res = tuple(int(v) for v in args[i + 1].split("x"))
        elif a == "--spp":
            spp = int(args[i + 1])
        elif a == "--only":
            only = set(args[i + 1].split(","))
    ob, mat, cam = build()
    H.setup_engine(samples=spp, res=res)
    H.render_to(os.path.join(OUT, "_surf_wall_before.png"), cam)

    base = dict(S.RECIPES["stone"])
    for tag, over in VARIANTS.items():
        if only and tag not in only:
            continue
        t0 = time.time()
        # fresh materials every time: medkit caches by name, so clear the cache
        # and let hd_castle rebuild its own dict (that is the authority on
        # which material is "stone")
        try:
            K._MAT_CACHE.clear()
        except Exception:
            pass
        import hd_castle as C
        MAT = C.make_mats()
        S.RECIPES["stone"] = dict(base, **over)
        S.apply_weathering({"stone": MAT["stone"]}, strength=1.0, seed=7)
        ob.data.materials[0] = MAT["stone"]
        for lg in ("probe_ledge",):
            lo = bpy.data.objects.get(lg)
            if lo is not None:
                lo.data.materials[0] = MAT["stone"]
        H.render_to(os.path.join(OUT, "_surf_wall_%s.png" % tag), cam)
        print("[wall] %s in %.1fs  over=%s"
              % (tag, time.time() - t0, json.dumps(over)), flush=True)


if __name__ == "__main__":
    main()
