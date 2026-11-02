"""Isolate the haze: same view with and without the volume."""
import os
import random
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.dirname(HERE), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import hd_common as H            # noqa: E402
import hd_cathedral_int as M     # noqa: E402

H._clear()
H.mat_cleanup = None
parts = M.build()
print("[vol] objects %d" % len(parts), flush=True)
H.setup_world(0.05, "#7f97b4", 0.35)
H.setup_engine(samples=24, res=(320, 180), gpu=True)
M.interior_lights(air=False)
cams = {}
for nm, loc, look, lens in M.CAMS:
    if nm in ("nave", "light", "nave_up"):
        cams[nm] = H.camera("c_" + nm, loc, look, lens)
for tag, dens in (("nohaze", 0.0), ("haze", 0.011)):
    if dens > 0.0:
        M.atmosphere(density=dens)
    for nm, cam in cams.items():
        p = os.path.join(H.OUT_DIR, "VOL_%s_%s.png" % (tag, nm))
        H.render_to(p, cam)
        print("[vol] %s" % p, flush=True)
print("[vol] DONE", flush=True)
