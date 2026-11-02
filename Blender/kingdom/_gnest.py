"""Where could "48 orphan parts" have come from?

Counts the objects in build()'s return, the nested lists inside it, and how many
objects each nested list holds, then reports objects whose world bbox is nowhere
near the asset.
"""
import sys
import random

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import bpy
import hd_common as H
import hd_gate as G

H._clear()
M = G.make_materials()
rng = random.Random(20261030)
obs = G.build(M, rng)

lists = [o for o in obs if isinstance(o, (list, tuple))]
inner = sum(len(o) for o in lists)
flat = G._flat(obs)
print("[nest] top-level entries   = %d" % len(obs))
print("[nest] nested list entries = %d" % len(lists))
print("[nest] objects inside them = %d" % inner)
print("[nest] flattened objects   = %d" % len(flat))
print("[nest] difference          = %d" % (len(flat) - len(obs)))
for o in lists:
    print("[nest]   %s -> %d obj %s" % (o[0].name if o else "-", len(o),
                                       getattr(o[0], "name", "?")))

scene = [o for o in bpy.data.objects if o.type == "MESH"]
returned = set(o.name for o in flat)
extra = [o for o in scene if o.name not in returned]
print("[nest] meshes in scene not in build() = %d" % len(extra))
far = []
for o in flat:
    c = sum((o.matrix_world @ v.co for v in o.data.vertices),
            __import__("mathutils").Vector()) / max(len(o.data.vertices), 1)
    if c.length < 1.0:
        far.append((o.name, tuple(round(v, 2) for v in c)))
print("[nest] returned objects whose centroid is within 1 m of origin = %d" % len(far))
for n, c in far[:10]:
    print("[nest]   %s %s" % (n, c))
