import bpy

me = bpy.data.meshes.new("m1")
ob = bpy.data.objects.new("o1", me)
bpy.context.scene.collection.objects.link(ob)
print("before", len(bpy.data.objects), len(bpy.data.meshes))
try:
    bpy.data.batch_remove([ob, me])
    print("batch ok")
except Exception as e:
    print("exc", type(e).__name__, e)
print("after batch_remove", len(bpy.data.objects), len(bpy.data.meshes))

ob2 = bpy.data.objects.new("o2", bpy.data.meshes.new("m2"))
bpy.context.scene.collection.objects.link(ob2)
print("before2", len(bpy.data.objects), len(bpy.data.meshes))
try:
    bpy.data.batch_remove([ob2])
    bpy.data.batch_remove([ob2.data])
    print("batch2 ok")
except Exception as e:
    print("exc2", type(e).__name__, e)
print("after2", len(bpy.data.objects), len(bpy.data.meshes))
