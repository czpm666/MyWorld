import bpy, sys, os
for name in ("streets_bed", "streets_gutter", "ground_town", "ground_outer"):
    ob = bpy.data.objects.get(name)
    if not ob:
        print("[n] MISSING", name, flush=True)
        continue
    me = ob.data
    nz = [round(p.normal.z, 3) for p in me.polygons[:6]]
    allz = [v.co.z for v in me.vertices]
    print("[n] %-14s faces=%d  normal.z first=%s  z %.3f..%.3f  mats=%s" % (
        name, len(me.polygons), nz, min(allz), max(allz), [m.name for m in me.materials][:3]), flush=True)
    up = sum(1 for p in me.polygons if p.normal.z > 0.5)
    dn = sum(1 for p in me.polygons if p.normal.z < -0.5)
    print("[n]    up-faces=%d  down-faces=%d" % (up, dn), flush=True)
print("N_DONE", flush=True)
