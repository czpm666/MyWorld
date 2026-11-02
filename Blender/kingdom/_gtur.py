import sys, random
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import bpy, hd_common as H, hd_gate as G
H._clear()
M = G.make_materials()
obs = G.build(M, random.Random(20261030))
flat = G._flat(obs)
ret = set(o.name for o in flat)
for pref in ("cw_tas", "cw_t", "bt_as", "twL_ash"):
    sel = [o for o in bpy.data.objects if o.name.startswith(pref)]
    print("[turret] %-8s objects=%d returned=%d" % (pref, len(sel),
          len([o for o in sel if o.name in ret])))
    for o in sel[:6]:
        print("   %-18s verts=%5d in_build=%s" % (o.name, len(o.data.vertices),
                                                  o.name in ret))
