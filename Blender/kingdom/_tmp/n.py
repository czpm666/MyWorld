import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")
obs=list(bpy.data.objects)
for i,ob in enumerate(obs):
    if ob.name=="gh_asps1":
        print("[n] idx", i, "of", len(obs))
        for j in range(max(0,i-4), min(len(obs), i+5)):
            o=obs[j]; print("   ", j, o.name, o.type, [round(v,1) for v in o.matrix_world.translation])
        break
