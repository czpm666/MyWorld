"""Inventory: which materials actually cover the city, and what the ground is."""
import bpy
import collections

mats = collections.defaultdict(lambda: [0, 0])     # name -> [objects, faces]
pref = collections.defaultdict(lambda: [0, 0])
ground = []
BIG = []

for ob in bpy.data.objects:
    if ob.type != "MESH" or not ob.data.materials:
        continue
    me = ob.data
    nf = len(me.polygons)
    names = [m.name if m else "<none>" for m in me.materials]
    # per material index face count
    per = collections.Counter(p.material_index for p in me.polygons)
    for idx, cnt in per.items():
        nm = names[idx] if idx < len(names) else "<oob>"
        mats[nm][0] += 1
        mats[nm][1] += cnt
        pref[nm.split(".")[0]][0] += 1
        pref[nm.split(".")[0]][1] += cnt
    low = ob.name.lower()
    if any(k in low for k in ("ground", "street", "road", "plaza", "cobble", "pave",
                              "yard", "field", "grass", "dirt", "earth", "terrain")):
        ground.append((nf, ob.name, tuple(round(v, 1) for v in ob.dimensions), names))
    BIG.append((nf, ob.name, names[:4]))

print("=== materials by face count (prefix grouped) ===")
for nm, (objs, faces) in sorted(pref.items(), key=lambda kv: -kv[1][1])[:26]:
    print("  %-22s objs=%-7d faces=%d" % (nm, objs, faces))

print("=== full material names, top 30 ===")
for nm, (objs, faces) in sorted(mats.items(), key=lambda kv: -kv[1][1])[:30]:
    print("  %-28s objs=%-7d faces=%d" % (nm, objs, faces))

print("=== ground-ish objects (top 30 by faces) ===")
ground.sort(reverse=True)
for nf, name, dim, names in ground[:30]:
    print("  %-26s f=%-7d dim=%-22s %s" % (name, nf, dim, names))

print("=== biggest objects ===")
BIG.sort(reverse=True)
for nf, name, names in BIG[:18]:
    print("  %-26s f=%-7d %s" % (name, nf, names))

print("=== z extents of ground objects ===")
zs = []
for nf, name, dim, names in ground[:40]:
    ob = bpy.data.objects.get(name)
    if ob:
        zs.append((name, round(ob.location.z, 3),
                   round(min((ob.matrix_world @ v.co).z for v in ob.data.vertices), 3)
                   if len(ob.data.vertices) < 200000 else None))
for z in zs[:20]:
    print("  ", z)
