# -*- coding: utf-8 -*-
"""Which hd_nature seeds are safe?  Some blow up (3.6 GB and no end)."""
import sys
import time

sys.path.insert(0, r"E:\My World\Blender")
sys.path.insert(0, r"E:\My World\Blender\kingdom")

import hd_common as H            # noqa: E402
import hd_nature as N            # noqa: E402

ok = {}
for fn in ("tree_pine", "bush", "grass_tuft"):
    f = getattr(N, fn)
    good = []
    for seed in range(1, 25):
        t0 = time.time()
        try:
            parts = f(seed)
        except Exception:                       # noqa: BLE001
            continue
        dt = time.time() - t0
        parts = [p for p in parts if getattr(p, "type", None) == "MESH"]
        n = H.tri_count(parts)
        if dt < 1.5 and n < 40000:
            good.append(seed)
        print("%-10s seed %2d  %5.2fs  %6d tris" % (fn, seed, dt, n), flush=True)
    ok[fn] = good
    print(fn, "good seeds", good, flush=True)
print("SUMMARY", ok, flush=True)
