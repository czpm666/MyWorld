import bpy
from mathutils import Vector

path = r"E:\My World\Blender\renders\kingdom\capital_full.blend"
bpy.ops.wm.open_mainfile(filepath=path)

# Castle keep area in Blender coords: castle at (0, 205) roughly, keep tower above z~30
rows = []
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    mw = ob.matrix_world
    pts = [mw @ v.co for v in ob.data.vertices]
    if not pts:
        continue
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    cx = sum(xs)/len(xs); cy = sum(ys)/len(ys)
    if abs(cx) > 120 or cy < 120 or cy > 300:
        continue
    dx = max(xs)-min(xs); dy = max(ys)-min(ys); dz = max(zs)-min(zs)
    if dz > 25.0:
        rows.append((dz, ob.name, dx, dy, dz, max(zs)))
rows.sort(reverse=True)
for r in rows[:16]:
    print("[keep] %-26s dx=%6.2f dy=%6.2f dz=%6.2f top=%6.2f  flat=%s"
          % (r[1], r[2], r[3], r[4], r[5], "YES" if min(r[2], r[3]) < 0.6 else "no"))
print("[keep] candidates =", len(rows))
