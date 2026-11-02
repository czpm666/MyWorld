#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
export_lab.py -- build the export lab scene and (optionally) run the exporter
on it inside the same Blender process, so one lock acquisition covers both.

The scene is deliberately hostile to a naive exporter:

  * 200 box houses with BEVEL modifiers (join must apply modifiers first),
  * 1 castle landmark (unchunked FBX, many small objects),
  * a 300 m terrain grid, 90 k tris (chunked + collision),
  * 12 thin wall segments (name- and geometry-classified as walls),
  * 60 props (small objects, own chunks),
  * one 82 k-tri icosphere ("mega_chunk_test") that alone exceeds the chunk
    budget and must be bisected by the exporter's safety net.

USAGE

    blender -b --factory-startup --python look/export_lab.py -- \
        --blend "E:\My World\WorkQC\uexport\lab\lab.blend" \
        --export --out "E:\My World\WorkQC\uexport\lab\out" \
        --chunk-tris 50000 --lod --collision --materials both --axis-test "..."

Everything after --export is handed verbatim to export_unity.py.
"""
import bpy
import bmesh
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KINGDOM = os.path.dirname(HERE)
sys.path.insert(0, r"E:\My World\Blender")

import medkit as MK   # noqa: E402  (needs the path above)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def has(name):
    return name in argv


BLEND_OUT = arg("--blend", r"E:\My World\WorkQC\uexport\lab\lab.blend")
DO_EXPORT = has("--export")
RNG = random.Random(20261102)


def tri_count():
    n = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for p in o.data.polygons:
                n += max(0, len(p.vertices) - 2)
    return n


def add_box(name, cx, cy, z0, sx, sy, sz, mat, bevel=0.0, smooth=False):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, z0 + sz * 0.5))
    o = bpy.context.object
    o.name = name
    o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat is not None:
        o.data.materials.append(mat)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    if bevel:
        m = o.modifiers.new("bev", 'BEVEL')
        m.width = bevel
        m.segments = 1
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(35.0)
    return o


def add_gable(name, cx, cy, z0, sx, sy, sz, mat, bevel=0.0):
    """Triangular prism roof, ridge along X."""
    hx, hy = sx * 0.5, sy * 0.5
    verts = [(-hx, -hy, 0.0), (hx, -hy, 0.0), (hx, hy, 0.0), (-hx, hy, 0.0),
             (-hx, 0.0, sz), (hx, 0.0, sz)]
    faces = [(0, 1, 2, 3), (0, 1, 5, 4), (3, 2, 5, 4), (0, 3, 4), (1, 2, 5)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = (cx, cy, z0)
    bpy.context.scene.collection.objects.link(o)
    if mat is not None:
        me.materials.append(mat)
    if bevel:
        m = o.modifiers.new("bev", 'BEVEL')
        m.width = bevel
        m.segments = 1
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(35.0)
    return o


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0

    plaster = MK.mat_plaster("plaster")
    wood = MK.mat_wood("timber")
    tile = MK.mat_tile("roof_tile")
    stone = MK.mat_stone("stone")
    earth = MK.mat_earth("earth")
    cobble = MK.mat_cobble("cobble")

    # ---- 200 houses on a 14 x 15 grid, jittered, with pitched roofs
    n = 0
    for gy in range(15):
        for gx in range(14):
            if n >= 200:
                break
            cx = -91.0 + gx * 14.0 + RNG.uniform(-2.0, 2.0)
            cy = -91.0 + gy * 14.0 + RNG.uniform(-2.0, 2.0)
            w = RNG.uniform(6.0, 10.0)
            d = RNG.uniform(6.0, 9.0)
            h = RNG.uniform(3.6, 6.4)
            base = add_box("house_%03d_body" % n, cx, cy, 0.0, w, d, h, plaster, bevel=0.03)
            add_gable("house_%03d_roof" % n, cx, cy, h, w * 1.08, d * 1.08,
                      RNG.uniform(2.2, 3.4), tile, bevel=0.02)
            add_box("house_%03d_chimney" % n, cx + w * 0.3, cy + d * 0.25, h,
                    0.7, 0.7, 2.0, stone)
            # a doorway plate, so the houses are not bare boxes
            add_box("house_%03d_door" % n, cx, cy - d * 0.5 - 0.05, 0.0,
                    1.1, 0.12, 2.2, wood)
            base.data.materials.append(stone)
            n += 1

    # ---- castle landmark (must land in landmarks/castle.fbx, unchunked)
    add_box("castle_keep", 0.0, 0.0, 0.0, 26.0, 26.0, 20.0, stone, bevel=0.06)
    add_box("castle_keep_roof", 0.0, 0.0, 20.0, 28.0, 28.0, 4.0, tile, bevel=0.05)
    for i in range(4):
        a = math.radians(45 + 90 * i)
        tx, ty = 20.0 * math.cos(a), 20.0 * math.sin(a)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=4.2, depth=30.0,
                                           location=(tx, ty, 15.0))
        t = bpy.context.object
        t.name = "castle_tower_%d" % i
        t.data.materials.append(stone)
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=5.0, radius2=0.0,
                                       depth=9.0, location=(tx, ty, 34.5))
        c = bpy.context.object
        c.name = "castle_tower_roof_%d" % i
        c.data.materials.append(tile)
    for i in range(4):
        a = math.radians(45 + 90 * i)
        add_box("castle_curtain_%d" % i, 14.0 * math.cos(a), 14.0 * math.sin(a), 0.0,
                22.0, 1.4, 7.0, stone)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.35, depth=1.6,
                                       location=(18.0, 18.0, 22.0))
    fl = bpy.context.object
    fl.name = "castle_banner_pole"
    fl.data.materials.append(wood)

    # ---- terrain grid: 150 x 150 quads = 90 k tris
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=150, y_subdivisions=150, size=300.0)
    g = bpy.context.object
    g.name = "terrain_ground"
    g.data.materials.append(earth)
    # gentle roll so the chunks have a real silhouette
    for v in g.data.vertices:
        r = math.sqrt(v.co.x * v.co.x + v.co.y * v.co.y)
        v.co.z = 0.6 * math.sin(v.co.x * 0.05) * math.cos(v.co.y * 0.043) + \
            1.4 * max(0.0, 1.0 - r / 190.0)

    # ---- streets: a cross of cobbled plates (terrain category by name)
    add_box("road_east_west", 0.0, 42.0, 0.0, 240.0, 9.0, 0.25, cobble)
    add_box("road_north_south", -42.0, 0.0, 0.0, 9.0, 240.0, 0.25, cobble)

    # ---- 12 wall segments on a ring (thin, tall -> walls)
    for i in range(12):
        a0 = 2 * math.pi * i / 12.0
        a1 = 2 * math.pi * (i + 1) / 12.0
        am = 0.5 * (a0 + a1)
        R = 132.0
        mx, my = R * math.cos(am), R * math.sin(am)
        seglen = 2 * R * math.sin((a1 - a0) * 0.5) * 1.02
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(mx, my, 3.0))
        w = bpy.context.object
        w.name = "wall_seg_%02d" % i
        w.rotation_euler = (0.0, 0.0, am + math.pi * 0.5)
        w.scale = (1.0, seglen, 6.0)
        w.data.materials.append(stone)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # ---- 60 props
    for i in range(60):
        a = RNG.uniform(0, 2 * math.pi)
        r = RNG.uniform(20.0, 110.0)
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.45, depth=1.2,
                                           location=(r * math.cos(a), r * math.sin(a), 0.6))
        p = bpy.context.object
        p.name = "prop_barrel_%02d" % i
        p.data.materials.append(wood)
        for f in p.data.polygons:
            f.use_smooth = True

    # ---- one object that ALONE exceeds the chunk budget (~82k tris)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=7, radius=26.0,
                                         location=(120.0, 120.0, 26.0))
    mega = bpy.context.object
    mega.name = "mega_chunk_test"
    mega.data.materials.append(stone)
    bpy.ops.object.shade_smooth()

    # ---- an object with no useful name: geometry fallback must catch it
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.9,
                                        location=(-60.0, 60.0, 0.9))
    o = bpy.context.object
    o.name = "obj_90417"
    o.data.materials.append(stone)

    log_scene()


def log_scene():
    tris = tri_count()
    nobj = len([o for o in bpy.data.objects if o.type == 'MESH'])
    mods = len([o for o in bpy.data.objects if o.type == 'MESH' and o.modifiers])
    print("[LAB] objects=%d tris=%d modifiers=%d materials=%d"
          % (nobj, tris, mods, len(bpy.data.materials)))
    sys.stdout.flush()


def main():
    build()
    os.makedirs(os.path.dirname(BLEND_OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    print("[LAB] saved", BLEND_OUT, os.path.getsize(BLEND_OUT), "bytes")
    sys.stdout.flush()

    if not DO_EXPORT:
        return
    rest = argv[argv.index("--export") + 1:]
    path = os.path.join(KINGDOM, "export_unity.py")
    sys.argv = ["blender", "-b", BLEND_OUT, "--python", path, "--"] + rest
    print("[LAB] running exporter with:", " ".join(rest))
    sys.stdout.flush()
    g = {"__name__": "__main__", "__file__": path, "__package__": None}
    with open(path, "r", encoding="utf-8") as fh:
        code = fh.read()
    exec(compile(code, path, "exec"), g)


if __name__ == "__main__":
    main()
