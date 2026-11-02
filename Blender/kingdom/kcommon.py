"""Shared render / export helpers for the Asura Kingdom builds (headless safe)."""
import os
import math

import bpy
from mathutils import Vector, Euler


# ---------------------------------------------------------------- lighting
def clear_lights_cameras():
    for ob in [o for o in bpy.data.objects if o.type in ("LIGHT", "CAMERA")]:
        bpy.data.objects.remove(ob, do_unlink=True)


def setup_lighting(sun_energy=3.4, elev=50.0, azim=34.0):
    sc = bpy.context.scene
    sd = bpy.data.lights.new("sun", "SUN")
    sd.energy = sun_energy
    sd.angle = math.radians(4.0)
    sd.color = (1.0, 0.94, 0.83)
    so = bpy.data.objects.new("sun", sd)
    sc.collection.objects.link(so)
    so.rotation_euler = Euler((math.radians(elev), 0, math.radians(azim)), "XYZ")

    wd = sc.world
    if wd is None:
        wd = bpy.data.worlds.new("World")
        sc.world = wd
    wd.use_nodes = True
    nt = wd.node_tree
    bg = nt.nodes.get("Background")
    if bg is None:
        bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.44, 0.58, 0.76, 1.0)
    bg.inputs[1].default_value = 0.85

    # fill so the shadow side is readable
    ad = bpy.data.lights.new("fill", "AREA")
    ad.energy = 900.0
    ad.size = 120.0
    ao = bpy.data.objects.new("fill", ad)
    sc.collection.objects.link(ao)
    ao.location = (-160.0, -140.0, 180.0)
    ao.rotation_euler = Euler((math.radians(52), 0, math.radians(-42)), "XYZ")


def setup_render(w=1600, h=900, samples=48):
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    for attr, val in (("taa_render_samples", samples), ("use_raytracing", True),
                      ("use_shadows", True), ("shadow_ray_count", 2),
                      ("shadow_step_count", 6)):
        try:
            setattr(sc.eevee, attr, val)
        except (AttributeError, TypeError):
            pass
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    return sc


def setup_camera(loc, look_at, lens=50.0):
    sc = bpy.context.scene
    for ob in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(ob, do_unlink=True)
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.clip_start = 0.5
    cd.clip_end = 6000.0
    co = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(co)
    co.location = Vector(loc)
    d = Vector(look_at) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    return co


def render_to(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


# ---------------------------------------------------------------- export
def join_parts(parts, name):
    """Select `parts`, convert modifiers, join into one mesh, apply transforms."""
    parts = [p for p in parts if p is not None and p.name in bpy.data.objects]
    if not parts:
        return None
    for ob in bpy.data.objects:
        ob.select_set(False)
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.convert(target="MESH")
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = name
    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except RuntimeError as exc:
        print("[export] transform_apply skipped for %s: %s" % (merged.name, exc))
    return merged


def export_group(parts, path, name):
    """Merge `parts` into a single mesh object and export it as one FBX."""
    merged = join_parts(parts, name)
    if merged is None:
        raise RuntimeError("nothing to export for " + path)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    for ob in bpy.data.objects:
        ob.select_set(False)
    merged.select_set(True)
    bpy.context.view_layer.objects.active = merged
    kw = dict(filepath=path, use_selection=True, object_types={"MESH"},
              global_scale=1.0, apply_unit_scale=True, use_mesh_modifiers=True,
              axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE",
              path_mode="AUTO", embed_textures=False,
              bake_space_transform=False)
    try:
        bpy.ops.export_scene.fbx(**kw)
    except TypeError:
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True,
                                 global_scale=1.0, apply_unit_scale=True,
                                 use_mesh_modifiers=True,
                                 axis_forward="-Z", axis_up="Y")
    return path
