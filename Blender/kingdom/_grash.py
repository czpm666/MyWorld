import sys, random
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import bpy, hd_common as H, hd_gate as G
H._clear()
M = G.make_materials()
rng = random.Random(7)
H.setup_world()
M2 = M
T = G.Ts(0, 0, 0)
o = G.ring_ashlar("probe_ash", T, 3.0, 1.0, 4.0, M["stone_warm"], M["stone_alt"], rng,
                  n=20, course=0.4, thick=0.05)
print("[probe] result type", type(o).__name__, "verts", len(o.data.vertices),
      "faces", len(o.data.polygons), "name", o.name)
print("[probe] scene mesh count", len([x for x in bpy.data.objects if x.type == "MESH"]))
for x in bpy.data.objects:
    if x.type == "MESH":
        print("   %-22s verts=%5d" % (x.name, len(x.data.vertices)))
obs = G.build(M, random.Random(20261030))
tw = bpy.data.objects.get("twL_ash")
print("[probe] twL_ash verts", len(tw.data.vertices) if tw else None)
