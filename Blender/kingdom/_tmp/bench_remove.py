"""Which removal primitive is fast at 13 k objects with mesh data?"""
import bpy
import time

mat = bpy.data.materials.new("benchmat")
N = 13000


def make(n_obj, name="part"):
    parts = []
    coll = bpy.context.scene.collection
    for i in range(n_obj):
        vs = [(i * 0.001, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0),
              (0.0, 1.0, 0.0)]
        fs = [(0, 1, 2), (0, 2, 3)] * 4
        me = bpy.data.meshes.new(name)
        me.from_pydata(vs, [], fs)
        me.update()
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        parts.append(ob)
    return parts


def t(fn, label):
    t0 = time.time()
    fn()
    print("[r] %-28s %6.2f s  objects=%d meshes=%d"
          % (label, time.time() - t0, len(bpy.data.objects), len(bpy.data.meshes)),
          flush=True)


# A: unlink everything, then remove objects one by one, then meshes
parts = make(N)
meshes = [p.data for p in parts]


def a():
    coll = bpy.context.scene.collection
    for p in parts:
        coll.objects.unlink(p)
    for p in parts:
        bpy.data.objects.remove(p)
    for m in meshes:
        bpy.data.meshes.remove(m)


t(a, "A unlink+remove+remove")

# B: meshes first, then objects
parts = make(N)
meshes = [p.data for p in parts]


def b():
    for m in meshes:
        bpy.data.meshes.remove(m)
    for p in parts:
        bpy.data.objects.remove(p, do_unlink=True)


t(b, "B meshes then objects")

# C: batch_remove in chunks of 500
parts = make(N)


def c():
    buf = []
    for p in parts:
        buf.append(p)
        buf.append(p.data)
        if len(buf) >= 1000:
            bpy.data.batch_remove(buf)
            buf = []
    if buf:
        bpy.data.batch_remove(buf)


t(c, "C batch_remove chunks")
