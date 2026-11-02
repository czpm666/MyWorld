import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_v23.blend")
print("== MATERIALS ==")
for m in sorted(bpy.data.materials, key=lambda m: m.name):
    print("  %-28s users=%d" % (m.name, m.users))
