"""Probe the Blender 5.2 API surface we need for the look rig (defensive)."""
import bpy


def gp(owner, attr, label=None):
    try:
        print("  %-42s %r" % (label or attr, getattr(owner, attr)))
    except Exception as e:                                    # noqa: BLE001
        print("  %-42s <%s>" % (label or attr, e))


sc = bpy.context.scene

print("=== mist ===")
gp(sc.render, "use_mist")
w = sc.world or bpy.data.worlds.new("w")
gp(w, "mist_settings")
try:
    print("   mist:", [(a, getattr(w.mist_settings, a)) for a in ("start", "depth", "falloff")])
except Exception as e:                                         # noqa: BLE001
    print("   mist err", e)

print("=== view transforms / looks ===")
for vt in ("AgX", "Filmic", "Standard", "Khronos PBR Neutral"):
    try:
        sc.view_settings.view_transform = vt
        print("   ok", vt)
    except Exception:                                          # noqa: BLE001
        print("   no", vt)
sc.view_settings.view_transform = "AgX"
items = [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items]
print("   looks:", items)

print("=== compositor ===")
print("   has compositing_node_group:", hasattr(sc, "compositing_node_group"))
print("   use_nodes:", getattr(sc, "use_nodes", "n/a"))
print("   node_tree:", getattr(sc, "node_tree", "n/a"))
print("   render.use_compositing:", sc.render.use_compositing)
print("   render.use_sequencer:", sc.render.use_sequencer)
print("   compositor_device:", getattr(sc.render, "compositor_device", "n/a"))

print("=== passes ===")
vl = bpy.context.view_layer
for a in sorted(dir(vl)):
    if a.startswith("use_pass"):
        gp(vl, a)

print("=== engines ===")
print("  ", [i.identifier for i in sc.render.bl_rna.properties["engine"].enum_items])

print("=== cycles ===")
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.get_devices()
    print("   compute:", prefs.compute_device_type)
    print("   devices:", [(d.name, d.type, d.use) for d in prefs.devices])
except Exception as e:                                         # noqa: BLE001
    print("   err", e)

print("=== eevee more ===")
for a in ("use_bloom", "use_ssr", "use_gtao", "use_soft_shadows", "shadow_cube_size",
          "shadow_cascade_size", "use_shadow_high_bitdepth", "use_shadow_jitter",
          "volumetric_light_clamp", "use_volumetric_shadows", "light_threshold"):
    gp(sc.eevee, a)
