"""Open the saved v22 city, report what is actually in it, and time one frame."""
import bpy
import os
import sys
import time

BLEND = r"E:\My World\Blender\renders\kingdom\capital_full.blend"

t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND)
print("[probe] open %.1fs" % (time.time() - t0), flush=True)

sc = bpy.context.scene
obs = list(bpy.data.objects)
types = {}
for o in obs:
    types[o.type] = types.get(o.type, 0) + 1
print("[probe] objects", len(obs), types, flush=True)

meshes = [o for o in obs if o.type == "MESH"]
tot_v = sum(len(o.data.vertices) for o in meshes)
tot_f = sum(len(o.data.polygons) for o in meshes)
print("[probe] verts %d  faces %d" % (tot_v, tot_f), flush=True)

print("[probe] materials", len(bpy.data.materials), flush=True)
print("[probe] lights", [o.name for o in obs if o.type == "LIGHT"], flush=True)
print("[probe] cameras", [o.name for o in obs if o.type == "CAMERA"], flush=True)

# biggest objects
ms = sorted(meshes, key=lambda o: -len(o.data.polygons))[:10]
for o in ms:
    print("[probe] big", o.name, len(o.data.polygons), flush=True)

# world
w = sc.world
print("[probe] world", w.name if w else None, "use_nodes", w.use_nodes if w else None, flush=True)
if w and w.use_nodes:
    for n in w.node_tree.nodes:
        print("[probe] wn", n.type, n.name, flush=True)

# engine / color management
print("[probe] engine", sc.render.engine, "res", sc.render.resolution_x, sc.render.resolution_y, flush=True)
print("[probe] view_transform", sc.view_settings.view_transform, "look", sc.view_settings.look,
      "exposure", sc.view_settings.exposure, flush=True)
print("[probe] eevee", [(a, getattr(sc.eevee, a)) for a in dir(sc.eevee)
                        if a in ("taa_render_samples", "use_raytracing", "use_shadows",
                                 "use_gtao", "gtao_distance", "volumetric_tile_size",
                                 "volumetric_samples", "use_volumetric_lights")], flush=True)
print("[probe] render props", [(a, getattr(sc.render, a)) for a in
                               ("use_motion_blur", "film_transparent", "use_freestyle")], flush=True)

# a few material base colors to see the palette
import collections
cols = []
for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            c = n.inputs["Base Color"].default_value
            cols.append((m.name, round(c[0], 3), round(c[1], 3), round(c[2], 3)))
            break
print("[probe] mat_count_with_bsdf", len(cols), flush=True)
for row in cols[:60]:
    print("[probe] mat", row, flush=True)

# render test
from mathutils import Vector
cd = bpy.data.cameras.new("probe_cam")
cd.lens = 45
cd.clip_end = 6000
co = bpy.data.objects.new("probe_cam", cd)
sc.collection.objects.link(co)
co.location = Vector((0, -1250, 620))
d = Vector((0, 0, 20)) - co.location
co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
sc.camera = co

sd = bpy.data.lights.new("probe_sun", "SUN")
sd.energy = 4.5
sd.angle = 0.02
suno = bpy.data.objects.new("probe_sun", sd)
sc.collection.objects.link(suno)
suno.rotation_euler = (0.58, 0, 0.6)

sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.render.filepath = r"E:\My World\Blender\renders\kingdom\_w2_probe.png"

t1 = time.time()
bpy.ops.render.render(write_still=True)
print("[probe] render %.1fs" % (time.time() - t1), flush=True)
print("PROBE_DONE", flush=True)
