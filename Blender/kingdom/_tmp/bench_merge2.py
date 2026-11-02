"""Phase timings inside a big merge."""
import bmesh
import bpy
import time

mat = bpy.data.materials.new("benchmat")


def make(n_obj, faces_each, name="part"):
    parts = []
    for i in range(n_obj):
        vs = [(i * 0.001, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0),
              (0.0, 1.0, 0.0)]
        fs = [(0, 1, 2), (0, 2, 3)] * (faces_each // 2)
        me = bpy.data.meshes.new(name)
        me.from_pydata(vs, [], fs)
        me.update()
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        parts.append(ob)
    return parts


N = 13000
parts = make(N, 8)
print("[b] created %d (scene %d)" % (N, len(bpy.data.objects)), flush=True)

bm = bmesh.new()
t0 = time.time()
for p in parts:
    me = p.data
    for poly in me.polygons:
        poly.material_index = 0
    bm.from_mesh(me)
t1 = time.time()
print("[b] from_mesh loop %.2f s" % (t1 - t0,), flush=True)

new = bpy.data.meshes.new("m")
bm.to_mesh(new)
bm.free()
t2 = time.time()
print("[b] to_mesh %.2f s" % (t2 - t1,), flush=True)

ids = []
for p in parts:
    ids.append(p)
    ids.append(p.data)
t3 = time.time()
bpy.data.batch_remove(ids)
t4 = time.time()
print("[b] batch_remove %.2f s (objects now %d)" % (t4 - t3, len(bpy.data.objects)),
      flush=True)
