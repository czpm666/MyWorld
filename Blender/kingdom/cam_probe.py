"""Render quick camera candidates from a saved variant .blend (no rebuild)."""
import os
import sys

import bpy

sys.path.insert(0, r"E:\My World\Blender")
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import build_farm as bf

RENDER_DIR = r"E:\My World\Blender\renders\kingdom"

CANDIDATES = [
    ("p5", (48.0, -126.0, 104.0), (0.0, -6.0, 2.0), 46.0),
    ("p7", (48.0, -124.0, 106.0), (0.0, -6.0, 2.0), 44.0),
    ("f1", (-30.0, -60.0, 13.0), (-34.0, -30.0, 0.5), 50.0),
    ("f2", (18.0, 6.0, 11.0), (32.0, 16.0, 0.4), 50.0),
    ("f3", (10.0, -34.0, 9.0), (-2.0, -24.0, 1.0), 50.0),
]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    key = argv[0] if argv else "farm_a"
    bpy.ops.wm.open_mainfile(filepath=os.path.join(bf.KING, key + ".blend"))
    sc = bpy.context.scene
    sc.render.resolution_x = 640
    sc.render.resolution_y = 360
    sc.render.resolution_percentage = 100
    try:
        sc.eevee.taa_render_samples = 24
    except Exception:
        pass
    for tag, loc, tgt, lens in CANDIDATES:
        bf.setup_camera(loc, tgt, lens)
        path = os.path.join(RENDER_DIR, "probe_%s_%s.png" % (key, tag))
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("PROBE", path)
    # also dump the scene bounds so framing can be computed, not guessed
    xs, ys, zs = [], [], []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.name == "ground":
            continue
        for v in o.bound_box:
            w = o.matrix_world @ __import__("mathutils").Vector(v)
            xs.append(w.x)
            ys.append(w.y)
            zs.append(w.z)
    print("BOUNDS x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f"
          % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))


if __name__ == "__main__":
    main()
