import sys, os, time
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_layout as L

for rings, court, bma in ((2, 5.0, 15500.0), (2, 6.0, 19000.0), (2, 5.5, 22000.0),
                          (3, 6.0, 26000.0)):
    specs = L.capital_layout_specs(outer=True, density=1.0)
    for name, sp in specs:
        sp["rings"] = rings
        sp["courtyard"] = court
        if name == "core":
            sp["block_min_area"] = bma
    t0 = time.time()
    res = L.layout_city(specs)
    st = res["stats"]
    print("rings=%d court=%.1f bma=%6.0f -> blocks %2d sub %3d build %4d (h %4d / s %3d)"
          " cov %.1f%% %.1fs"
          % (rings, court, bma, st["blocks"], st["sub_blocks"], st["buildings"],
             st["houses"], st["shops"], 100.0 * st["build_m2"] / st["area_m2"],
             time.time() - t0), flush=True)
    print("   kinds:", dict(sorted(st["kinds"].items(), key=lambda kv: -kv[1])), flush=True)
