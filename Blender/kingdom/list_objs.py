import bpy, re, sys, os

path = r"E:\My World\Blender\renders\kingdom\capital_full.blend"
bpy.ops.wm.open_mainfile(filepath=path)

pats = re.compile(r"dock|boat|crane|barn|warehouse|hull|mast|quay|shed|silo", re.I)
rows = []
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    if pats.search(ob.name):
        bb = [ob.matrix_world @ v.co for v in ob.data.vertices[:0]]  # skip heavy
        rows.append((ob.name, len(ob.data.polygons), round(ob.location.x, 1), round(ob.location.y, 1), round(ob.location.z, 1)))

rows.sort()
print("[objs] matched = %d" % len(rows))
for r in rows:
    print("[objs] %-34s faces=%-6d loc=(%s, %s, %s)" % r)

# also: every object that is a lone roof high above ground in the suburbs
print("[objs] total mesh objects = %d" % len([o for o in bpy.data.objects if o.type == 'MESH']))
