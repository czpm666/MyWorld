import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")
rows=[]
for ob in bpy.data.objects:
    if ob.type!="MESH" or not ob.data or len(ob.data.vertices)>500: continue
    co=[ob.matrix_world @ v.co for v in ob.data.vertices]
    if not co: continue
    zmin=min(v.z for v in co); cx=sum(v.x for v in co)/len(co); cy=sum(v.y for v in co)/len(co)
    if zmin>4.0 and abs(cx-12)<28 and abs(cy-18)<32: rows.append((round(zmin,1),ob.name,len(ob.data.polygons),round(cx,1),round(cy,1)))
rows.sort(reverse=True)
print("[p] %d"%len(rows))
for r in rows[:15]: print("[p] z=%.1f %-24s faces=%-4d at (%.1f, %.1f)"%r)
