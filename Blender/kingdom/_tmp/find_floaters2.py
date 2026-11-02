import bpy

bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")

rows = []
for ob in bpy.data.objects:
    if ob.type != "MESH" or not ob.data:
        continue
    if len(ob.data.vertices) > 400:
        continue
    co = [ob.matrix_world @ v.co for v in ob.data.vertices]
    if not co:
        continue
    zmin = min(v.z for v in co)
    xs = [v.x for v in co]
    ys = [v.y for v in co]
    size = max(max(xs) - min(xs), max(ys) - min(ys))
    if zmin > 3.0 and size < 4.0:
        rows.append((round(zmin, 1), ob.name, len(ob.data.polygons), round(size, 1),
                     round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)))

rows.sort(reverse=True)
print("[hi] %d small objects above z=3" % len(rows), flush=True)
for r in rows[:20]:
    print("[hi] z=%.1f %-26s faces=%-4d size=%.1f at (%.1f, %.1f)" % r, flush=True)
