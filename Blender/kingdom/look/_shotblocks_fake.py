"""Synthetic block dump, so look/spots.py can be tested without blender.

Not a render input -- only used to prove the raster / clearance / ray-run
pipeline works and that the picks land in the gaps rather than inside a block.

    python look/_shotblocks_fake.py --out look/_shotblocks_fake.json
"""
import json
import os
import sys

W, D = 60.0, 40.0     # block size
SX, SY = 74.0, 54.0   # pitch, i.e. 14 m of street in both directions
R = 940.0


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shotblocks_fake.json")
    blocks = []
    y = -R
    row = 0
    while y < R:
        x = -R + (SX * 0.5 if row % 2 else 0.0)
        while x < R:
            cx, cy = x + W * 0.5, y + D * 0.5
            if (cx * cx + cy * cy) ** 0.5 < R:
                blocks.append({"name": "fake_%d_%d" % (row, len(blocks)),
                               "hull": [[x, y], [x + W, y], [x + W, y + D], [x, y + D]],
                               "z": 9.0 + (row % 3), "z0": 0.0, "nv": 4})
            x += SX
        y += SY
        row += 1
    stats = {"n": len(blocks), "z_p50": 10.0, "z_p90": 11.0, "z_p99": 11.0, "z_max": 11.0}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"blocks": blocks, "stats": stats}, fh)
    print("wrote %s with %d blocks" % (out, len(blocks)))


main()
