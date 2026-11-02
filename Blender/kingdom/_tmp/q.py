import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")
rows=[]
for ob in bpy.data.objects:
    if ob.type!="MESH" or not ob.data or not ob.data.vertices: continue
    co=[ob.matrix_world @ v.co for v in ob.data.vertices]
    zs=[c.z for c in co]; x=sum(c.x for c in co)/len(co); y=sum(c.y for c in co)/len(co)
    if abs(x)<30 and -40<y<12 and max(zs)>8.0 and min(zs)<2.5: rows.append((round(max(zs),1),ob.name,len(co),round(x,1),round(y,1)))
rows.sort(reverse=True)
print("[q] %d"%len(rows))
for r in rows[:12]: print("[q] top=%.1f %-24s verts=%-6d at (%.1f, %.1f)"%r)
