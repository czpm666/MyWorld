# -*- coding: utf-8 -*-
"""hd_nature smoke test: what do a tree and a bush actually cost?"""
import sys
import time

sys.path.insert(0, r"E:\My World\Blender")
sys.path.insert(0, r"E:\My World\Blender\kingdom")

import hd_common as H            # noqa: E402
import hd_nature as N            # noqa: E402

print("hd_nature", [n for n in dir(N) if not n.startswith("_")][:24], flush=True)

for fn in ("tree_oak", "bush", "tree_pine", "grass_tuft"):
    f = getattr(N, fn, None)
    if f is None:
        print(fn, "missing", flush=True)
        continue
    t0 = time.time()
    try:
        parts = f(seed=3)
    except Exception as exc:                        # noqa: BLE001
        print(fn, "FAILED", type(exc).__name__, exc, flush=True)
        continue
    parts = [p for p in parts if getattr(p, "type", None) == "MESH"]
    lo, hi = H.bbox(parts) if parts else ((0, 0, 0), (0, 0, 0))
    print("%-12s %5.2fs objs=%-4d tris=%-6d x %6.1f..%6.1f y %6.1f..%6.1f z %5.1f..%5.1f"
          % (fn, time.time() - t0, len(parts), H.tri_count(parts),
             lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]), flush=True)
