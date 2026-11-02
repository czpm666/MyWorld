import bpy, sys
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\kingdom\port_a.blend")
def s(v):
    v=max(0.0,min(1.0,v)); return int(v**(1/2.2)*255+0.5)
for m in sorted(bpy.data.materials, key=lambda x:x.name):
    b=next((n for n in m.node_tree.nodes if n.type=="BSDF_PRINCIPLED"), None)
    if not b: continue
    c=b.inputs["Base Color"].default_value
    d=m.diffuse_color
    print("MAT %-20s bsdf=#%02x%02x%02x linked=%-5s diff=#%02x%02x%02x" % (m.name, s(c[0]),s(c[1]),s(c[2]), b.inputs["Base Color"].is_linked, s(d[0]),s(d[1]),s(d[2])))
