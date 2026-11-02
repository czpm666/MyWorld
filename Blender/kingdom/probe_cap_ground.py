import bpy, math

path = r"E:\My World\Blender\renders\kingdom\capital_full.blend"
bpy.ops.wm.open_mainfile(filepath=path)

for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    n = ob.name.lower()
    if not (n.startswith("ground") or n.startswith("terrain") or n.startswith("ars_ground")):
        continue
    zs = []
    inner = []
    mw = ob.matrix_world
    for v in ob.data.vertices:
        p = mw @ v.co
        zs.append(p.z)
        if math.hypot(p.x, p.y) < 300.0:
            inner.append(p.z)
    zs.sort()
    inner.sort()
    print("[gnd] %s verts=%d  z: min=%.2f p50=%.2f max=%.2f" % (ob.name, len(zs), zs[0], zs[len(zs)//2], zs[-1]))
    if inner:
        print("[gnd]   inside r<300: n=%d min=%.2f p50=%.2f p95=%.2f max=%.2f" % (
            len(inner), inner[0], inner[len(inner)//2], inner[int(len(inner)*0.95)], inner[-1]))
