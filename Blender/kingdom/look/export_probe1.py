"""Probe 1 - what does this Blender's FBX exporter / bake stack actually expose?

Run: blender -b --factory-startup --python look/export_probe1.py
Everything printed here is measured, not assumed.
"""
import bpy, sys, os, time, json
print("=" * 70)
print("BLENDER", bpy.app.version_string, "pid", os.getpid())
print("=" * 70)

# ---- numpy
try:
    import numpy as np
    print("numpy", np.__version__)
except Exception as e:
    print("NO NUMPY", e)

# ---- FBX exporter operator
rna = bpy.ops.export_scene.fbx.get_rna_type()
print("\n--- export_scene.fbx properties (%d) ---" % len(rna.properties))
for p in rna.properties:
    if p.identifier == "rna_type":
        continue
    default = getattr(p, "default", None)
    try:
        default = repr(default)
    except Exception:
        default = "<unrepr>"
    extra = ""
    if p.type == "ENUM":
        extra = " items=" + ",".join(i.identifier for i in p.enum_items)
    print("  %-28s %-8s default=%-24s%s" % (p.identifier, p.type, default, extra))

# ---- units on startup
sc = bpy.context.scene
print("\nunits:", sc.unit_settings.system, "scale_length", sc.unit_settings.scale_length,
      "length_unit", sc.unit_settings.length_unit)

# ---- bake support
print("\nbake ops:", hasattr(bpy.ops.object, "bake"))
print("cycles addon:", "cycles" in bpy.context.preferences.addons)
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    print("cycles compute devices:", [(d.name, d.type, d.use) for d in prefs.get_devices()[0][:4]])
    print("cycles device:", prefs.compute_device_type)
except Exception as e:
    print("cycles prefs err", e)

# ---- colour attributes / UV ops
me = bpy.data.meshes.new("t")
print("mesh has color_attributes:", hasattr(me, "color_attributes"))
print("uv ops:", [o for o in dir(bpy.ops.uv) if "proj" in o or "smart" in o])

# ---- images: can we save 2k png fast?
img = bpy.data.images.new("probe", 2048, 2048, alpha=False)
t0 = time.time()
img.filepath_raw = os.path.join(os.environ.get("TEMP", "."), "probe_2k.png")
img.file_format = "PNG"
img.save()
print("saved 2048 png in %.2fs -> %s bytes" % (time.time() - t0, os.path.getsize(img.filepath_raw)))

# ---- gltf exporter presence (fallback path)
print("gltf op:", hasattr(bpy.ops.export_scene, "gltf"))

# ---- modifiers available for LOD / collision
print("modifier types:", [i.identifier for i in bpy.types.Modifier.bl_rna.properties["type"].enum_items])
print("DONE")
