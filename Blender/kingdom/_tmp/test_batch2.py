import time

import bpy

N = 10000
ids = []
t0 = time.time()
for i in range(N):
    me = bpy.data.meshes.new("m")
    ob = bpy.data.objects.new("o", me)
    bpy.context.scene.collection.objects.link(ob)
    ids.append(ob)
    ids.append(me)
print("[t] created %d in %.1f s, objects=%d" % (N, time.time() - t0, len(bpy.data.objects)))

t0 = time.time()
bpy.data.batch_remove(ids)
print("[t] batch_remove %.1f s, objects=%d meshes=%d"
      % (time.time() - t0, len(bpy.data.objects), len(bpy.data.meshes)))

# second style: unlink + purge
ids = []
for i in range(N):
    me = bpy.data.meshes.new("n")
    ob = bpy.data.objects.new("p", me)
    bpy.context.scene.collection.objects.link(ob)
    ids.append(ob)
t0 = time.time()
for ob in ids:
    for c in ob.users_collection:
        c.objects.unlink(ob)
print("[t] unlink %.1f s" % (time.time() - t0,))
t0 = time.time()
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
print("[t] purge %.1f s, objects=%d meshes=%d"
      % (time.time() - t0, len(bpy.data.objects), len(bpy.data.meshes)))
