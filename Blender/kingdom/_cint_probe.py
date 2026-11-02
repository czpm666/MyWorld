"""_cint_probe.py - one-shot API probe for the throne hall build (throwaway)."""
import bpy
import sys

print("BLENDER", bpy.app.version_string, flush=True)

m = bpy.data.materials.new("probe")
m.use_nodes = True
b = None
for n in m.node_tree.nodes:
    if n.type == "BSDF_PRINCIPLED":
        b = n
print("PRINCIPLED_INPUTS:", flush=True)
for i in b.inputs:
    print("   ", repr(i.name), i.type, flush=True)

# light types
for t in ("SUN", "AREA", "POINT", "SPOT"):
    try:
        ld = bpy.data.lights.new("l_" + t, t)
        print("LIGHT", t, "ok", flush=True)
    except Exception as e:
        print("LIGHT", t, "FAIL", e, flush=True)

sc = bpy.context.scene
print("ENGINES:", [e.identifier for e in
                   bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items], flush=True)
print("cycles", hasattr(sc, "cycles"), flush=True)
if hasattr(sc, "cycles"):
    for k in ("volume_step_rate", "volume_max_steps", "volume_bounces",
              "use_denoising", "denoiser", "samples", "use_adaptive_sampling",
              "adaptive_threshold", "max_bounces", "transparent_max_bounces",
              "caustics_reflective", "sample_clamp_indirect", "use_light_tree"):
        print("  cycles.%s = %r" % (k, getattr(sc.cycles, k, "<missing>")), flush=True)
print("view_transform", sc.view_settings.view_transform, flush=True)
print("LOOKS", [e.identifier for e in
                bpy.types.ColorManagedViewSettings.bl_rna.properties["look"].enum_items][:12],
      flush=True)
# compositor node availability
print("has compositing_node_group", hasattr(sc, "compositing_node_group"), flush=True)
print("use_nodes", getattr(sc, "use_nodes", "<missing>"), flush=True)
print("PROBE_DONE", flush=True)
