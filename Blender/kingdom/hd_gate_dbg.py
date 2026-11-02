"""Debug harness: build a single part of hd_gate and inspect / render it.

    blender -b --factory-startup --python hd_gate_dbg.py -- tower
    blender -b --factory-startup --python hd_gate_dbg.py -- barbican
    blender -b --factory-startup --python hd_gate_dbg.py -- gatehouse
"""
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import bpy

import hd_common as H
import hd_gate as G

OUT = r"E:\My World\Blender\renders\kingdom"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    what = argv[0] if argv else "tower"
    H._clear()
    MAT = G.materials()
    rng = random.Random(7)
    if what == "tower":
        parts = G.build_tower(MAT, rng, 1)
        cam_loc, look = (34.0, 40.0, 30.0), (14.2, 0.0, 16.0)
        lens = 45.0
    elif what == "barbican":
        parts = G.build_barbican(MAT, rng)
        cam_loc, look = (26.0, 52.0, 20.0), (0.0, 16.0, 8.0)
        lens = 40.0
    else:
        parts = G.build_gatehouse(MAT, rng)
        cam_loc, look = (0.0, 60.0, 22.0), (0.0, 6.0, 12.0)
        lens = 42.0
    n = 0
    for ob in G._flat(parts):
        if ob is None or ob.type != "MESH":
            continue
        ob.data.calc_loop_triangles()
        lo, hi = H.bbox([ob])
        print("%-18s tris=%-6d lo=(%6.2f,%6.2f,%6.2f) hi=(%6.2f,%6.2f,%6.2f)"
              % (ob.name[:18], len(ob.data.loop_triangles), lo[0], lo[1], lo[2],
                 hi[0], hi[1], hi[2]), flush=True)
        n += len(ob.data.loop_triangles)
    print("[dbg] %s parts=%d tris=%d" % (what, len(parts), n), flush=True)
    H.setup_world(sun_energy=4.2, sky="#9fc4e8", fill=0.0)
    H.setup_engine(samples=32, res=(900, 700), gpu=True)
    cam = H.camera("cam_dbg", cam_loc, look, lens)
    H.render_to(os.path.join(OUT, "hd_gate_dbg_%s.png" % what), cam)


if __name__ == "__main__":
    main()
