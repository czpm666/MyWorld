import bpy
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\kingdom\port_a.blend")
for name in ("port_a_ground","port_a_quay"):
    ob=bpy.data.objects[name]; mw=ob.matrix_world
    vs=[mw @ v.co for v in ob.data.vertices]
    print("%s bbox x %.2f..%.2f y %.2f..%.2f z %.3f..%.3f" % (name,
        min(v.x for v in vs),max(v.x for v in vs),min(v.y for v in vs),max(v.y for v in vs),
        min(v.z for v in vs),max(v.z for v in vs)))
# water faces specifically
ob=bpy.data.objects["port_a_quay"]; me=ob.data; mw=ob.matrix_world
mi=[i for i,m in enumerate(me.materials) if m and m.name=="water_port"]
zs=[];ys=[];xs=[]
for p in me.polygons:
    if p.material_index in mi:
        for vi in p.vertices:
            v=mw @ me.vertices[vi].co; zs.append(v.z); ys.append(v.y); xs.append(v.x)
print("water_port faces: x %.2f..%.2f y %.2f..%.2f z %.3f..%.3f" % (min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)))
print("DIAGDONE")
