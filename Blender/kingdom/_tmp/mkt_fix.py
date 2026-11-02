import bpy, sys, os
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import kcommon as KC

bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")

# what stands in the middle of the plaza and reaches above the arcade?
rows = []
for ob in bpy.data.objects:
    if ob.type != "MESH" or not ob.data or not ob.data.vertices:
        continue
    co = [ob.matrix_world @ v.co for v in ob.data.vertices]
    zs = [c.z for c in co]
    x = sum(c.x for c in co) / len(co)
    y = sum(c.y for c in co) / len(co)
    if abs(x) < 26 and 8 < y < 30 and min(zs) < 3.0 and max(zs) > 9.0:
        rows.append((round(max(zs), 1), ob.name, len(ob.data.polygons),
                     round(x, 1), round(y, 1)))
rows.sort(reverse=True)
print("[plaza] %d candidates" % len(rows), flush=True)
for r in rows[:14]:
    print("[plaza] top=%.1f %-26s faces=%-4d at (%.1f, %.1f)" % r, flush=True)

KC.clear_lights_cameras()
KC.setup_lighting()
KC.setup_render(w=1600, h=900, samples=32)
KC.setup_camera((0.0, -34.0, 11.0), (0.0, 18.0, 10.0), 30.0)
KC.render_to(os.path.join(r"E:\My World\Blender\renders\kingdom", "hd_market.png"))
print("MKT_DONE", flush=True)
