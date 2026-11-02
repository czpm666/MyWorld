import bpy, sys, os
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import kcommon as KC
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")
hid=0
for ob in bpy.data.objects:
    if ob.type=="MESH" and ob.name.startswith("gh_as"):
        ob.hide_render=True; hid+=1
print("[hide]", hid)
KC.clear_lights_cameras(); KC.setup_lighting(); KC.setup_render(w=1600,h=900,samples=24)
KC.setup_camera((0.0,-34.0,11.0),(0.0,18.0,10.0),30.0)
KC.render_to(r"E:\My World\Blender\renders\kingdom\_test_mkt_nogh.png")
print("HIDE_DONE")
