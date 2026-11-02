"""Find any horizontal face acting as a raised platform/riser above grade.

Scans every mesh object in the open .blend for near-horizontal faces with meaningful
area whose height sits between 0.20 and 0.70 m, and reports the material + object.
Also reports every material's flat base colour so a brown '#624A35' offender is
identifiable even if it is not a horizontal face.
"""
import bpy
import os
import sys
from mathutils import Vector

arg = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "port_a"
BLEND = os.path.join(r"E:\My World\Blender\kingdom", arg + ".blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("=== horizontal faces 0.20 <= z <= 0.70 (area >= 0.4 m2) ===")
hits = 0
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    mw = ob.matrix_world
    me = ob.data
    mats = [m.name if m else "<none>" for m in me.materials]
    counts = {}
    for p in me.polygons:
        n = (mw.to_3x3() @ p.normal).normalized()
        if abs(n.z) < 0.80:
            continue
        c = mw @ p.center
        if not (0.20 <= c.z <= 0.70):
            continue
        a = p.area
        if a < 0.4:
            continue
        key = (mats[p.material_index] if p.material_index < len(mats) else "?", round(c.z, 2))
        e = counts.setdefault(key, [0, 0.0, 1e9, -1e9])
        e[0] += 1
        e[1] += a
        e[2] = min(e[2], c.z)
        e[3] = max(e[3], c.z)
    for (mn, _), (n, a, z0, z1) in sorted(counts.items(), key=lambda kv: -kv[1][1]):
        print("  %-22s %-18s faces=%-5d area=%7.1f m2  z %.3f..%.3f" % (ob.name, mn, n, a, z0, z1))
        hits += 1
if not hits:
    print("  none")

print("=== material flat base colours (Principled default, for '#624A35' hunting) ===")
for m in sorted(bpy.data.materials, key=lambda x: x.name):
    if not m.use_nodes:
        continue
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        continue
    col = bsdf.inputs["Base Color"].default_value
    hexs = "#%02x%02x%02x" % (
        max(0, min(255, int(col[0] ** (1 / 2.2) * 255))),
        max(0, min(255, int(col[1] ** (1 / 2.2) * 255))),
        max(0, min(255, int(col[2] ** (1 / 2.2) * 255))),
    )
    users = [o.name for o in bpy.data.objects if o.type == "MESH" and m.name in [x.name if x else "" for x in o.data.materials]]
    print("  %-22s %s  linked=%s  users=%s" % (m.name, hexs, bsdf.inputs["Base Color"].is_linked, ",".join(users)))
print("DIAGDONE", arg)
