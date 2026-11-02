"""Where does the landmark merge spend its time?"""
import os
import sys
import time

BL = r"E:\My World\Blender"
KING = os.path.join(BL, "kingdom")
for p in (KING, BL):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy
from mathutils import Vector

import capital_hd_glue as G

mat = bpy.data.materials.new("benchmat")


def make(n_obj, faces_each, name="part"):
    parts = []
    for i in range(n_obj):
        vs = [(i * 0.001, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0),
              (0.0, 1.0, 0.0)]
        fs = []
        for f in range(faces_each // 2):
            fs.append((0, 1, 2))
            fs.append((0, 2, 3))
        me = bpy.data.meshes.new(name)
        me.from_pydata(vs, [], fs)
        me.update()
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        parts.append(ob)
    return parts


for n, f in ((2000, 27), (13000, 8)):
    parts = make(n, f, "p%d" % n)
    print("[bench] created %d objs (scene %d)" % (n, len(bpy.data.objects)), flush=True)
    t0 = time.time()
    ob = G.merge_objects("merged_%d" % n, parts)
    print("[bench] merge %d objs -> %s in %.2f s (objects now %d)"
          % (n, ob.name if ob else None, time.time() - t0, len(bpy.data.objects)),
          flush=True)
