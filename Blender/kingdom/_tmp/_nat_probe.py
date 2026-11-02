import bpy, sys, time, math
print("VER", bpy.app.version_string)
print("has fbx op", hasattr(bpy.ops.export_scene, "fbx"))
try:
    print("use_nodes attr", hasattr(bpy.types.Material, "use_nodes"))
except Exception as e:
    print("use_nodes err", e)
m = bpy.data.materials.new("probe")
try:
    m.use_nodes = True
    print("use_nodes set ok", m.use_nodes)
except Exception as e:
    print("use_nodes set FAIL", e)
bsdf = [n.type for n in m.node_tree.nodes] if m.node_tree else None
print("nodes", bsdf)
if m.node_tree:
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            print("inputs", [i.name for i in n.inputs])
print("render engines", [e.bl_idname if hasattr(e, "bl_idname") else e for e in bpy.types.RenderEngine.__subclasses__()][:5])
sc = bpy.context.scene
try:
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    print("devices", [(d.name, d.type, d.use) for d in prefs.devices])
except Exception as e:
    print("GPU err", e)
print("rt", [e for e in dir(bpy.app) if "build" in e])
