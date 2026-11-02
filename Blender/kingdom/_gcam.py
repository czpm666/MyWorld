"""Debug cameras for the gate's portcullis junction.

    blender -b --factory-startup --python _gcam.py
Writes dbg_*.png into renders\\kingdom\\_qa.
"""
import os
import random
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_gate as G                                            # noqa: E402
import hd_common as H                                          # noqa: E402

OUT = os.path.join(G.OUT_DIR, "_qa")
os.makedirs(OUT, exist_ok=True)

H._clear()
MAT = G.materials()
rng = random.Random(20261030)
G.build(MAT, rng)
G._context(MAT, rng)
H.setup_world(sun_energy=4.2, sky="#9fc4e8", fill=0.0)
G._lights(MAT)
H.setup_engine(samples=24, res=(1000, 700), gpu=True)

SHOTS = [
    ("pc_front", (0.0, 20.0, 4.20), (0.0, 5.45, 6.90), 26.0),
    ("pc_up", (0.0, 12.0, 6.30), (0.0, 5.40, 7.15), 22.0),
    ("pc_side", (3.60, 9.60, 4.60), (0.0, 5.45, 6.80), 30.0),
]
for name, loc, look, lens in SHOTS:
    cam = H.camera("cam_" + name, loc, look, lens)
    H.render_to(os.path.join(OUT, "dbg_%s.png" % name), cam)
    print("[gcam] wrote %s" % name, flush=True)
