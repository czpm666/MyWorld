import sys, random
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import bpy, hd_common as H, hd_gate as G
H._clear()
M = G.make_materials()
obs = G.build(M, random.Random(20261030))
flat = G._flat(obs)
ret = set(o.name for o in flat)
import re
pat = re.compile(r"^(bt_as|cw_tas|twL_ash|twR_ash|gh_as|bb_fa|bb_sa|cw_as)")
rows = [(o.name, len(o.data.vertices), o.name in ret) for o in bpy.data.objects
        if o.type == "MESH" and pat.match(o.name)]
rows.sort()
for n, v, r in rows[:14]:
    print("[ash] %-22s verts=%6d in_build=%s" % (n, v, r))
print("[ash] objects matching:", len(rows), " min verts:", min(r[1] for r in rows))
print("[ash] scene meshes not returned =", len([o for o in bpy.data.objects
      if o.type == "MESH" and o.name not in ret]))
print("[ash] parts =", len(flat))
