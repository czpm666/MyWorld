# -*- coding: utf-8 -*-
"""Farm-village archetype builder (Asura Kingdom / Mushoku Tensei).

Three variants, same palette, different footprints:
  farm_a  crossroads crossroads -- lanes form a T, houses in two rows either side
  farm_b  linear street -- one long street with a green and a well at its heart
  farm_c  fork -- the road splits around a triangular island with the well

Run headless:
  blender -b --factory-startup --python build_farm.py -- --variant farm_a
"""
import bpy
import os
import sys
import math
import json
import random

HERE = r"E:\My World\Blender"
KING = os.path.join(HERE, "kingdom")
for _p in (HERE, KING):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import medkit
import medbuild
import farm_kit as fk
from medkit import T_at, box, cyl, cone, sphere
from farm_kit import (M, Assemblies, farmhouse, barn, windmill, well,
                      notice_board, shrine, banner, haystack, scarecrow,
                      woodpile, fence_run, gate, lantern_post, cart_ruts,
                      crop_ridge, field_block, wheat_field, veg_rows,
                      lane_strip, apron, path_to_door, tufts, simple_tree,
                      ground_plate)

EXPORT_DIR = os.path.join(HERE, "export", "kingdom", "farm")
RENDER_DIR = os.path.join(HERE, "renders", "kingdom")
TAU = math.pi * 2.0


# ---------------------------------------------------------------- geometry utils
def slab_between(name, p0, p1, w, mat=None, z=0.0):
    """Solid slab from p0 to p1 (world xy), width w, top at z, 2 m deep."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ang = math.atan2(-dx, dy)
    T = T_at((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5, 0.0, rz=ang)
    return box(name, T @ T_at(0, 0, z - 1.0), (w, L, 2.0), mat or M["road"])


def road_ribbon(name, pts, w, mat=None, z=-0.002, wob=0.22, seed=0):
    """One continuous road surface along a polyline, with a 2 m buried skirt.

    Per-segment slabs left wedge overlaps at every bend; because the joined mesh
    is flat-shaded the overlap showed as a lighter band down the lane. The skirt
    keeps the plate from reading as a sheet floating over the Unity terrain.
    """
    r = random.Random(seed)
    n = len(pts)
    depth = 2.0
    norms = []
    for i in range(n):
        if i == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        elif i == n - 1:
            dx, dy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
        else:
            ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
            bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
            la = math.hypot(ax, ay) or 1.0
            lb = math.hypot(bx, by) or 1.0
            dx, dy = ax / la + bx / lb, ay / la + by / lb
        L = math.hypot(dx, dy) or 1.0
        norms.append((-dy / L, dx / L))
    verts, faces = [], []
    zt, zb = z, z - depth
    for i, (p, nv) in enumerate(zip(pts, norms)):
        hl = w * 0.5 + r.uniform(-wob, wob)
        hr = w * 0.5 + r.uniform(-wob, wob)
        verts.append((p[0] + nv[0] * hl, p[1] + nv[1] * hl, zt))
        verts.append((p[0] - nv[0] * hr, p[1] - nv[1] * hr, zt))
    m = 2 * n
    for i in range(n):
        x0, y0, _ = verts[2 * i]
        x1, y1, _ = verts[2 * i + 1]
        verts.append((x0, y0, zb))
        verts.append((x1, y1, zb))
    for i in range(n - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 2))
        faces.append((a + 1, a + 3, a + 2))
    # skirt: two side walls plus end caps; normals are recalculated below
    for i in range(n - 1):
        for vi in (0, 1):
            p, q = 2 * i + vi, 2 * (i + 1) + vi
            pb, qb = m + 2 * i + vi, m + 2 * (i + 1) + vi
            faces.append((p, pb, q))
            faces.append((pb, qb, q))
    for i in (0, n - 1):
        a, b = 2 * i, 2 * i + 1
        ab, bb = m + 2 * i, m + 2 * i + 1
        faces.append((a, ab, b))
        faces.append((ab, bb, b))
    ob = medkit.mesh_obj(name, verts, faces, smooth=False)
    medkit.assign(ob, mat or M["road"])
    fix_normals(ob)
    return ob


def fix_normals(ob):
    """Recalculate outward normals on a closed solid built by hand."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def apron_cluster(key, cx, cy, w, d, seed=0, n=4, mat=None):
    """Overlapping jittered cobble patches: a square slab reads as tarmac."""
    r = random.Random(seed)
    # a solid base under the jitter: without it the gaps between patches show
    # the core plate or the render ground, which read as green blotches
    parts = [apron("%s_base" % key, T_at(cx, cy, 0), w * 0.94, d * 0.94,
                   mat=mat, z=0.0008)]
    for i in range(n):
        ang = r.uniform(-0.20, 0.20)
        ww = w * r.uniform(0.70, 1.0)
        dd = d * r.uniform(0.70, 1.0)
        ox = r.uniform(-0.13, 0.13) * w
        oy = r.uniform(-0.13, 0.13) * d
        parts.append(apron("%s_%d" % (key, i),
                           T_at(cx + ox, cy + oy, 0, rz=ang),
                           ww, dd, mat=mat, z=0.0014 + i * 0.00045))
    return parts


def verge_quads(key, p0, p1, w, seed=0, mat=None, tight=0.06, loose=0.42,
                skip=None):
    """Ragged earth/gravel strips hugging both sides of a lane segment.

    A decal-straight road edge is the giveaway that the lane is a quad; these
    jittered patches break the silhouette without another texture.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 0.5:
        return []
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    r = random.Random(seed)
    out = []
    for side in (-1, 1):
        t = 0.0
        while t < 0.99:
            ln = r.uniform(0.10, 0.30)
            t1 = min(1.0, t + ln)
            if t1 - t < 0.04:
                break
            off = w * 0.5 + r.uniform(tight, loose)
            wd = r.uniform(0.30, 0.85)
            cx = 0.5 * (t + t1)
            ax = p0[0] + dx * t + nx * side * (off + wd * 0.4)
            ay = p0[1] + dy * t + ny * side * (off + wd * 0.4)
            bx = p0[0] + dx * t1 + nx * side * (off + wd * 0.4)
            by = p0[1] + dy * t1 + ny * side * (off + wd * 0.4)
            if skip:
                mx, my = 0.5 * (ax + bx), 0.5 * (ay + by)
                if any(math.hypot(mx - sx, my - sy) < sr for sx, sy, sr in skip):
                    t = t1 + r.uniform(0.0, 0.05)
                    continue
            out.append(slab_between("%s_v%d%d" % (key, side, int(cx * 97)),
                                    (ax, ay), (bx, by), wd,
                                    mat or M["earth"], z=0.001))
            t = t1 + r.uniform(0.0, 0.05)
    return out


def boundary_ditch(A, key, x0, x1, y0, y1, w=1.4, seed=5):
    """Shallow ditch + spoil bank ringing the map so the lawn stops being infinite.

    Each side is broken into jittered spans so the perimeter does not read as a
    ruler-straight picture frame around the village.
    """
    r = random.Random(seed)
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    for i, (a, b) in enumerate((
            ((x0, y0), (x1, y0)), ((x0, y1), (x1, y1)),
            ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)))):
        horiz = abs(b[0] - a[0]) > abs(b[1] - a[1])
        n = 3
        pts = []
        for j in range(n + 1):
            t = j / n
            px = a[0] + (b[0] - a[0]) * t
            py = a[1] + (b[1] - a[1]) * t
            if 0 < j < n:
                if horiz:
                    py += r.uniform(-0.9, 0.9)
                else:
                    px += r.uniform(-0.9, 0.9)
            pts.append((px, py))
        for j in range(n):
            p, q = pts[j], pts[j + 1]
            k = "%s_%d_%d" % (key, i, j)
            A.add(k, slab_between(k, p, q, w, M["earth"], z=0.0))
            dx, dy = q[0] - p[0], q[1] - p[1]
            L = math.hypot(dx, dy)
            ang = math.atan2(-dx, dy)
            # spoil bank on the inner side of the ditch
            mx, my = 0.5 * (p[0] + q[0]), 0.5 * (p[1] + q[1])
            to_c = math.hypot(cx - mx, cy - my) or 1.0
            ox, oy = (cx - mx) / to_c, (cy - my) / to_c
            T = T_at(mx + ox * (w * 0.5 + 0.5), my + oy * (w * 0.5 + 0.5), 0,
                     rz=ang)
            A.add(k + "_b", box(k + "_b", T @ T_at(0, 0, 0.11),
                                (0.85, L * 1.02, 0.22), M["pasture"], bev=0.10))


def lane_road(A, key, pts, w, seed=0, ruts=True, skip=None):
    """One assembly group per lane: a single mitred ribbon plus ragged verges.

    Per-segment slabs used to overlap at every bend and, because the material
    is fed TexCoord.Object, each object sampled a different patch of noise 闁?the
    lane read as banded tarmac. One continuous mesh fixes both.
    """
    parts = [road_ribbon(key + "_rb", pts, w, M["road"], z=-0.002,
                         wob=w * 0.06, seed=seed)]
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        seg = "%s_s%d" % (key, i)
        parts += verge_quads(seg + "_v", p0, p1, w, seed * 31 + i, skip=skip,
                             tight=-0.34, loose=-0.12)
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if ruts and L > 11.0:
            ang = math.atan2(-dx, dy)
            T = T_at((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5, 0, rz=ang)
            parts += cart_ruts(seg + "_r", T, L - 1.5)
    A.add(key, parts)


def cottage(A, key, x, y, rz, seed, **kw):
    kw.setdefault("W", 6.2)
    kw.setdefault("D", 5.0)
    kw.setdefault("nF", 1)
    kw.setdefault("FH", 2.9)
    A.add(key, farmhouse(key, T_at(x, y, 0, rz=rz), rng=random.Random(seed), **kw))


def cottage_along(A, key, p0, p1, t, side, seed, lane_w=6.0, verge=3.0, **kw):
    """Place a cottage beside a lane p0->p1 at parameter t.

    side = +1 -> left of travel direction, -1 -> right.
    Front face looks at the lane.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    px, py = p0[0] + dx * t, p0[1] + dy * t
    nx, ny = (-uy, ux) if side > 0 else (uy, -ux)
    D = kw.get("D", 5.0)
    d = lane_w * 0.5 + verge + D * 0.5
    cx, cy = px + nx * d, py + ny * d
    rz = math.atan2(ny, nx) - math.pi * 0.5
    cottage(A, key, cx, cy, rz, seed, **kw)
    # doorstep path from the lane edge to the door
    s = lane_w * 0.5
    slab_between(key + "_path", (px + nx * s, py + ny * s),
                 (cx + nx * (D * 0.5 + 0.1), cy + ny * (D * 0.5 + 0.1)), 1.3)
    return cx, cy, rz, (nx, ny)


def tree_at(A, key, x, y, h, seed, species="broad"):
    """Broadleaf tree: cheap trunk + lobes, every third a full medbuild hero.

    medbuild.tree() is ~2.3k faces; twenty of them would eat a third of the
    budget, and at map scale the cheap three-lobe tree reads the same.
    """
    rng = random.Random(seed)
    T = T_at(x, y, 0, rz=rng.uniform(0, TAU))
    if seed % 3 == 0:
        from mathutils import Matrix
        A.add(key, medbuild.tree(key, T @ Matrix.Scale(h / 3.6, 4), h=3.6,
                                 rng=rng, species=species,
                                 leaf_mat=M["leaf"] if seed % 2 else M["leaf2"]))
    else:
        A.add(key, simple_tree(key, T, h=h, rng=rng, seg=9))


def bush_at(A, key, x, y, r, seed):
    rng = random.Random(seed)
    A.add(key, medbuild.bush(key, T_at(x, y, 0, rz=rng.uniform(0, TAU)), r=r, rng=rng))


def hedge_row(A, key, p0, p1, seed, step=1.62, r=0.78):
    """A clipped hedge: continuous green body plus a ragged bush top, so it
    reads as a wall of foliage instead of a row of beads."""
    rng = random.Random(seed)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ang = math.atan2(dy, dx)
    hh = r * 1.12
    A.add(key + "_body", box(
        key + "_body",
        T_at((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5, hh * 0.5 - 0.03,
             rz=ang),
        (L, r * 1.45, hh), M["leaf"], bev=0.12))
    n = max(2, int(L / (r * 1.45)))
    for i in range(n):
        t = (i + 0.5) / n
        x = p0[0] + dx * t + rng.uniform(-0.18, 0.18)
        y = p0[1] + dy * t + rng.uniform(-0.18, 0.18)
        bush_at(A, "%s_b%d" % (key, i), x, y, r * rng.uniform(0.88, 1.12),
                seed * 7 + i)


def orchard(A, key, x, y, nx, ny, dx, dy, seed, h0=5.0, h1=6.6):
    rng = random.Random(seed)
    for i in range(nx):
        for j in range(ny):
            tree_at(A, "%s_t%d%d" % (key, i, j),
                    x + i * dx + rng.uniform(-0.45, 0.45),
                    y + j * dy + rng.uniform(-0.45, 0.45),
                    rng.uniform(h0, h1), seed * 13 + i * 7 + j * 3)


def prop_cluster(A, key, x, y, seed, barrels=0, crates=0, sacks=0):
    rng = random.Random(seed)
    parts = []
    for i in range(barrels):
        a = rng.uniform(0, TAU)
        rr = 0.0 if i == 0 else rng.uniform(0.55, 1.05)
        parts += medbuild.barrel("%s_bar%d" % (key, i),
                                 T_at(x + math.cos(a) * rr, y + math.sin(a) * rr, 0,
                                      rz=rng.uniform(0, TAU)),
                                 r=rng.uniform(0.27, 0.32), h=rng.uniform(0.78, 0.86), rng=rng)
    for i in range(crates):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(0.9, 1.5)
        s = rng.uniform(0.55, 0.72)
        parts += medbuild.crate("%s_cr%d" % (key, i),
                                T_at(x + math.cos(a) * rr, y + math.sin(a) * rr, s * 0.5,
                                     rz=rng.uniform(0, TAU)), s=s, rng=rng)
    for i in range(sacks):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(0.4, 0.9)
        parts += medbuild.sack("%s_sk%d" % (key, i),
                               T_at(x + math.cos(a) * rr, y + math.sin(a) * rr, 0,
                                    rz=rng.uniform(0, TAU)),
                               r=rng.uniform(0.22, 0.27), rng=rng)
    A.add(key, parts)


def paddock(A, key, x, y, w, d, seed, rot=0.0, hay=1, fence_sides=3):
    """Fenced grass paddock with a haystack: fills the gaps between buildings
    so the village reads as worked land rather than a lawn."""
    rng = random.Random(seed)
    T = T_at(x, y, 0, rz=rot)
    if fence_sides >= 1:
        A.add(key + "_f1", fence_run(key + "_f1", T @ T_at(0, -d * 0.5, 0), w))
    if fence_sides >= 2:
        A.add(key + "_f2", fence_run(key + "_f2",
                                     T @ T_at(-w * 0.5, 0, 0, rz=math.pi * 0.5), d))
    if fence_sides >= 3:
        A.add(key + "_f3", fence_run(key + "_f3",
                                     T @ T_at(w * 0.5, 0, 0, rz=math.pi * 0.5), d))
    if fence_sides >= 4:
        A.add(key + "_f4", fence_run(key + "_f4", T @ T_at(0, d * 0.5, 0), w))
    for i in range(hay):
        A.add(key + "_hay%d" % i, haystack(
            key + "_hay%d" % i,
            T @ T_at(rng.uniform(-w * 0.22, w * 0.22),
                     rng.uniform(-d * 0.22, d * 0.22), 0,
                     rz=rng.uniform(0, TAU)),
            r=rng.uniform(1.25, 1.5), h=rng.uniform(1.9, 2.2), rng=rng))
    A.add(key + "_trough", trough(key + "_trough",
                                  T @ T_at(w * 0.28, d * 0.22, 0,
                                           rz=rng.uniform(0, TAU))))


def garden(A, key, x, y, w, d, seed, rot=0.0):
    """Kitchen plot behind a cottage: soil, cabbage rows, two fence sides."""
    rng = random.Random(seed)
    T = T_at(x, y, 0, rz=rot)
    A.add(key + "_soil", apron(key + "_soil", T, w, d, mat=M["earth"], z=0.0))
    A.add(key + "_crop", veg_rows(key + "_crop", T, w - 0.8, d - 0.8,
                                  M["crop_cabbage"], M["crop_green"], rng=rng,
                                  spacing=0.82, furrows=False))
    A.add(key + "_f1", fence_run(key + "_f1", T @ T_at(0, -d * 0.5, 0), w - 0.3))
    A.add(key + "_f2", fence_run(key + "_f2",
                                 T @ T_at(-w * 0.5, 0, 0, rz=math.pi * 0.5), d - 0.3))


def trough(name, T, L=2.2, Wd=0.55, H=0.46):
    out = []
    out.append(box(name + "_t", T @ T_at(0, 0, H * 0.5), (L, Wd, H),
                   M["stone_step"], bev=0.02))
    out.append(box(name + "_w", T @ T_at(0, 0, H - 0.03), (L - 0.22, Wd - 0.22, 0.03),
                   M["water"]))
    out.append(box(name + "_s1", T @ T_at(-L * 0.3, 0, 0.04), (0.24, Wd + 0.14, 0.08),
                   M["stone_step"]))
    out.append(box(name + "_s2", T @ T_at(L * 0.3, 0, 0.04), (0.24, Wd + 0.14, 0.08),
                   M["stone_step"]))
    return out


# ---------------------------------------------------------------- scene / render
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = "AgX"
    except Exception:
        pass
    for look in ("AgX - Medium High Contrast", "Medium High Contrast",
                 "AgX - Base Contrast", "None"):
        try:
            sc.view_settings.look = look
            break
        except Exception:
            continue
    sc.view_settings.exposure = 0.05
    ee = sc.eevee
    for attr, val in (("taa_render_samples", 96), ("use_raytracing", True),
                      ("use_shadows", True), ("shadow_ray_count", 2),
                      ("shadow_step_count", 8)):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass

    w = sc.world
    if w is None:
        w = bpy.data.worlds.new("VillageWorld")
        sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.40, 0.55, 0.80, 1.0)
    bg.inputs["Strength"].default_value = 0.90
    nt.links.new(bg.outputs[0], out.inputs["Surface"])


def clear_lights_cameras():
    for ob in list(bpy.data.objects):
        if ob.type in {"LIGHT", "CAMERA"}:
            bpy.data.objects.remove(ob, do_unlink=True)


def add_lights(sun_rot=(50.0, 0.0, 34.0), sun_e=3.4):
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = sun_e
    ld.angle = math.radians(1.3)
    ld.color = (1.0, 0.95, 0.85)
    ob = bpy.data.objects.new("Sun", ld)
    bpy.context.collection.objects.link(ob)
    ob.rotation_euler = [math.radians(a) for a in sun_rot]

    fd = bpy.data.lights.new("Fill", type="AREA")
    fd.energy = 1150.0
    fd.size = 34.0
    fd.color = (0.72, 0.84, 1.0)
    f = bpy.data.objects.new("Fill", fd)
    bpy.context.collection.objects.link(f)
    f.location = (-26.0, 30.0, 26.0)
    from mathutils import Vector
    v = Vector((0.0, 0.0, 0.0)) - Vector((-26.0, 30.0, 26.0))
    f.rotation_euler = v.to_track_quat("-Z", "Y").to_euler()


def setup_camera(loc, target, lens=40.0):
    from mathutils import Vector
    for ob in list(bpy.data.objects):
        if ob.type == "CAMERA":
            bpy.data.objects.remove(ob, do_unlink=True)
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cd.clip_start = 0.5
    cd.clip_end = 900.0
    ob = bpy.data.objects.new("Cam", cd)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def ground_mat():
    m = bpy.data.materials.new("village_ground")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = None
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            bsdf = n
    bsdf.inputs["Roughness"].default_value = 0.92
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (0.0, 0.0, 0.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

    # Broad dry/rough patches first: a uniform green plane reads as a lawn that
    # the village was dropped onto, which is the exact note from last round.
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 0.045
    n1.inputs["Detail"].default_value = 2.2
    n1.inputs["Roughness"].default_value = 0.55
    nt.links.new(mp.outputs["Vector"], n1.inputs["Vector"])

    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 3.4
    n2.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs["Vector"], n2.inputs["Vector"])

    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position = 0.30
    els[0].color = medkit.c("#465a28")
    e = els.new(0.50)
    e.color = medkit.c("#63733a")
    e = els.new(0.64)
    e.color = medkit.c("#7d7c46")
    e = els.new(0.80)
    e.color = medkit.c("#93875a")
    nt.links.new(n1.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], bsdf.inputs["Base Color"])

    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 0.5
    mix.inputs["Color1"].default_value = (1, 1, 1, 1)
    nt.links.new(r.outputs["Color"], mix.inputs["Color1"])
    nt.links.new(n2.outputs["Fac"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = 0.06
    b.inputs["Distance"].default_value = 0.12
    nt.links.new(n2.outputs["Fac"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def add_ground(size=200.0):
    h = size * 0.5
    me = bpy.data.meshes.new("ground")
    me.from_pydata([(-h, -h, -0.012), (h, -h, -0.012), (h, h, -0.012), (-h, h, -0.012)],
                   [], [(0, 1, 2, 3)])
    me.update()
    ob = bpy.data.objects.new("ground", me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(ground_mat())
    return ob


def render_to(path, samples=None):
    sc = bpy.context.scene
    if samples:
        try:
            sc.eevee.taa_render_samples = samples
        except Exception:
            pass
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDER", path)


# ---------------------------------------------------------------- export / stats
def scene_stats(objs):
    tris = 0
    mn = [1e9] * 3
    mx = [-1e9] * 3
    for ob in objs:
        me = ob.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        mw = ob.matrix_world
        for v in me.vertices:
            co = mw @ v.co
            for i in range(3):
                if co[i] < mn[i]:
                    mn[i] = co[i]
                if co[i] > mx[i]:
                    mx[i] = co[i]
    mats = set()
    for ob in objs:
        for ms in ob.material_slots:
            if ms.material:
                mats.add(ms.material.name)
    return dict(objects=len(objs), tris=tris, materials=len(mats),
                bbox=[round(mn[0], 2), round(mx[0], 2), round(mn[1], 2),
                      round(mx[1], 2), round(mn[2], 2), round(mx[2], 2)],
                mat_names=sorted(mats))


def join_groups(A, tag):
    joined = []
    for key, objs in A.groups:
        objs = [o for o in objs if o is not None and o.name in bpy.data.objects]
        if not objs:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        bpy.ops.object.convert(target="MESH")
        ob = bpy.context.view_layer.objects.active
        ob.name = "%s_%s" % (tag, key)
        ob.data.name = ob.name
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        joined.append(ob)
    return joined


def export_fbx(path):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    kw = dict(filepath=path, use_selection=True, object_types={"MESH"},
              global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
              axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True,
              mesh_smooth_type="FACE", path_mode="AUTO", embed_textures=False,
              bake_space_transform=False)
    bpy.ops.export_scene.fbx(**kw)


# ---------------------------------------------------------------- low-level kit
# Layout bookkeeping, so every build prints a numeric self check.
CK = {"houses": [], "walls": [], "soft": [], "hard": [], "streets": [],
      "paths": [], "info": {}}


def ck_clear():
    for k in CK:
        CK[k].clear()


def poly_plate(name, pts, mat=None, top=0.0, depth=2.0):
    """One closed, self-shaded ground slab under an arbitrary polygon.

    The village floor is a single plate so the Unity terrain never shows through
    between the buildings; it drops `depth` below grade so no edge floats.
    """
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    verts = [(cx, cy, top)]
    verts += [(p[0], p[1], top) for p in pts]
    verts += [(p[0], p[1], top - depth) for p in pts]
    faces = []
    for i in range(n):
        a, b = 1 + i, 1 + (i + 1) % n
        faces.append((0, a, b))
    for i in range(n):
        a, b = 1 + i, 1 + (i + 1) % n
        d, c = 1 + n + i, 1 + n + (i + 1) % n
        faces.append((a, b, c, d))
    faces.append(tuple(1 + n + i for i in range(n - 1, -1, -1)))
    ob = medkit.mesh_obj(name, verts, faces, smooth=False)
    medkit.assign(ob, mat or M["road"])
    fix_normals(ob)
    return ob


def pad(name, x, y, w, d, top, mat=None, rot=0.0):
    """Rectangular terrace slab: top face at z=top, 2 m of skirt below grade."""
    return box(name, T_at(x, y, top - 1.0, rz=rot), (w, d, 2.0), mat or M["earth"])


def _run_T(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    return (math.atan2(-dx, dy), math.hypot(dx, dy),
            ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5))


def wall_between(A, key, p0, p1, h=0.56, t=0.38, mat=None, cap=True, group=None):
    """Low stone wall along p0->p1 with a lighter coping course."""
    ang, L, mid = _run_T(p0, p1)
    if L < 0.5:
        return None
    mat = mat or M["stone"]
    parts = [box(key + "_b", T_at(mid[0], mid[1], h * 0.5, rz=ang),
                 (t, L, h), mat, bev=0.0)]
    if cap:
        parts.append(box(key + "_c", T_at(mid[0], mid[1], h + 0.045, rz=ang),
                         (t + 0.11, L + 0.07, 0.09), M["stone_step"], bev=0.0))
    A.add(group or key, parts)
    CK["walls"].append(("stone", p0, p1))
    return parts


def wall_run(A, key, pts, h=0.56, t=0.38, mat=None, cap=True):
    """One object, many segments: a continuous village-edge or plot wall."""
    for i in range(len(pts) - 1):
        wall_between(A, "%s_%d" % (key, i), pts[i], pts[i + 1],
                     h=h, t=t, mat=mat, cap=cap, group=key)


def corner_posts(A, key, pts, h, t, skip_ends=True):
    """Quoin blocks at every polyline corner so a bend opens no notch."""
    parts = []
    lo, hi = (1, len(pts) - 1) if skip_ends else (0, len(pts))
    for i in range(lo, hi):
        px, py = pts[i]
        w = t * 1.30
        parts.append(box("%s_q%d" % (key, i), T_at(px, py, (h + 0.14) * 0.5),
                         (w, w, h + 0.14), M["stone"], bev=0.0))
        parts.append(box("%s_qc%d" % (key, i), T_at(px, py, h + 0.185),
                         (w + 0.12, w + 0.12, 0.10), M["stone_step"], bev=0.0))
    if parts:
        A.add(key, parts)


def retwall(A, key, pts, top, t=0.36, mat=None, cap=0.10):
    """Stone retaining wall holding a raised terrace: z = 0 .. top+cap."""
    parts = []
    h = top + cap
    for i in range(len(pts) - 1):
        ang, L, mid = _run_T(pts[i], pts[i + 1])
        if L < 0.2:
            continue
        parts.append(box("%s_%d" % (key, i), T_at(mid[0], mid[1], h * 0.5, rz=ang),
                         (t, L + t * 0.5, h), mat or M["stone_step"], bev=0.0))
        parts.append(box("%s_c%d" % (key, i),
                         T_at(mid[0], mid[1], h + 0.045, rz=ang),
                         (t + 0.10, L + t * 0.5 + 0.06, 0.09),
                         M["stone"], bev=0.0))
        CK["walls"].append(("stone", pts[i], pts[i + 1]))
    A.add(key, parts)


def stairs(A, key, ex, ey, dx, dy, w, high, rise=0.18, run=0.34, mat=None):
    """Stone steps from grade up to `high`, starting at (ex,ey) along (dx,dy)."""
    n = max(1, int(round(high / rise)))
    rz = math.atan2(-dx, dy)
    parts = []
    for i in range(n):
        top = high - (i + 1) * rise
        if top < 0.03:
            continue
        parts.append(box("%s_%d" % (key, i),
                         T_at(ex, ey, top * 0.5, rz=rz) @ T_at(0, run * (i + 0.5), 0),
                         (w, run + 0.05, top), mat or M["stone_step"], bev=0.0))
    A.add(key, parts)
    px, py = -dy, dx
    CK["walls"].append(("steps", (ex - px * w * 0.5, ey - py * w * 0.5),
                        (ex + px * w * 0.5, ey + py * w * 0.5)))


def kerb(A, key, pts, z=0.11, t=0.30, mat=None):
    parts = []
    for i in range(len(pts) - 1):
        ang, L, mid = _run_T(pts[i], pts[i + 1])
        parts.append(box("%s_%d" % (key, i), T_at(mid[0], mid[1], z * 0.5, rz=ang),
                         (t, L, z), mat or M["stone_step"], bev=0.0))
    A.add(key, parts)


def paved_square(A, key, cx, cy, w, d, rot=0.0):
    """Cobbled square with a stone kerb, a flag centre and an earth shoulder."""
    A.add(key + "_shoulder", apron(key + "_shoulder", T_at(cx, cy, 0, rz=rot),
                                   w + 0.7, d + 0.7, mat=M["earth"], z=0.0012))
    A.add(key + "_cobble", apron(key + "_cobble", T_at(cx, cy, 0, rz=rot),
                                 w, d, mat=M["cobble"], z=0.0035))
    hw, hd = w * 0.5, d * 0.5
    kerb(A, key + "_kerb", [(cx - hw, cy - hd), (cx + hw, cy - hd),
                            (cx + hw, cy + hd), (cx - hw, cy + hd),
                            (cx - hw, cy - hd)], mat=M["stone"])
    CK["hard"].append((cx, cy, w + 0.7, d + 0.7, rot))


def hedge(A, key, p0, p1, seed=0, r=0.72):
    """Clipped hedge: one green body + bushes, all in a single export object."""
    rng = random.Random(seed)
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if L < 0.8:
        return
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    hh = r * 1.30
    A.add(key, [box(key + "_b",
                    T_at((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5,
                         hh * 0.5 - 0.04, rz=ang),
                    (L, r * 1.55, hh), M["leaf"], bev=0.10)])
    n = max(2, int(L / (r * 2.1)))
    for i in range(n):
        t = (i + 0.5) / n
        A.add(key, medbuild.bush(key + "_s%d" % i,
                                 T_at(p0[0] + (p1[0] - p0[0]) * t,
                                      p0[1] + (p1[1] - p0[1]) * t, 0,
                                      rz=rng.uniform(0, TAU)),
                                 r=r * rng.uniform(0.86, 1.12), rng=rng))
    CK["walls"].append(("hedge", p0, p1))


def front(A, key, ex, ey, fx, fy, seed, setback=0.65, W=5.8, D=5.0,
          path_w=1.30, nF=1, **kw):
    """House whose facade faces (fx,fy), `setback` behind the point (ex,ey).

    (ex,ey) is the point on the road edge its door opens onto, so the facade
    line is the road line: 0.3-1.2 m of threshold, never a lawn.
    """
    rz = math.atan2(-fx, fy)
    cx = ex - fx * (setback + D * 0.5)
    cy = ey - fy * (setback + D * 0.5)
    cottage(A, key, cx, cy, rz, seed, W=W, D=D, nF=nF, **kw)
    if path_w:
        CK["paths"].append(slab_between(
            key + "_path",
            (cx + fx * (D * 0.5 + 0.05), cy + fy * (D * 0.5 + 0.05)),
            (ex, ey), path_w, M["cobble"], z=0.006))
    walk = apron(key + "_walk",
                 T_at(cx + fx * (D * 0.5 + setback * 0.5),
                      cy + fy * (D * 0.5 + setback * 0.5), 0, rz=rz),
                 W * 0.94, setback + 0.10, mat=M["cobble"], z=0.0042)
    A.add(key, walk)
    h = dict(c=(cx, cy), rz=rz, W=W, D=D, f=(fx, fy), e=(ex, ey), key=key,
             setback=setback, nF=nF)
    CK["houses"].append(h)
    return h


def _front_corners(h):
    f, c, W, D = h["f"], h["c"], h["W"], h["D"]
    t = (-f[1], f[0])
    return [(c[0] + f[0] * D * 0.5 + s * t[0] * W * 0.5,
             c[1] + f[1] * D * 0.5 + s * t[1] * W * 0.5) for s in (-1, 1)]


def _house_poly(h):
    f, c, W, D = h["f"], h["c"], h["W"], h["D"]
    t = (-f[1], f[0])
    return [(c[0] + f[0] * D * 0.5 * sy + t[0] * W * 0.5 * sx,
             c[1] + f[1] * D * 0.5 * sy + t[1] * W * 0.5 * sx)
            for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1))]


def _pt_seg_d(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - dx * t, py - ay - dy * t)


def _poly_dist(A_, B_):
    best = 1e9
    for p in A_:
        for i in range(len(B_)):
            best = min(best, _pt_seg_d(p, B_[i], B_[(i + 1) % len(B_)]))
    for p in B_:
        for i in range(len(A_)):
            best = min(best, _pt_seg_d(p, A_[i], A_[(i + 1) % len(A_)]))
    return best


def link(A, key, a, b, h=0.54, style="stone"):
    """Close the gap between two neighbouring house fronts (the street wall)."""
    best = None
    for pa in _front_corners(a):
        for pb in _front_corners(b):
            d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
            if best is None or d < best[0]:
                best = (d, pa, pb)
    d, pa, pb = best
    if d > 4.2:
        return None
    if style == "hedge":
        return hedge(A, key, pa, pb, seed=len(CK["walls"]) + 7, r=0.62)
    if style == "fence":
        return fence_between(A, key, pa, pb)
    return wall_between(A, key, pa, pb, h=h)


def add_street(pts, half):
    for i in range(len(pts) - 1):
        CK["streets"].append((pts[i], pts[i + 1], half))


def fence_between(A, key, p0, p1, gap=0.0, gate_=False):
    """Fence from p0 to p1; with `gap` it leaves a gateway in the middle.

    fence_run()/gate() lay their length along local X, while _run_T() returns the
    angle that lays a box's local *Y* along the run -- feeding that angle to a
    fence rotated every fence 90 degrees off its plot edge.
    """
    ang, L, mid = _run_T(p0, p1)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    if L < 0.6:
        return
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    if gap <= 0.2 or L <= gap + 1.4:
        A.add(key, fence_run(key + "_f", T_at(mid[0], mid[1], 0, rz=ang), L))
        CK["walls"].append(("fence", p0, p1))
        return
    seg = (L - gap) * 0.5
    off = (L + gap) * 0.25
    for s in (-1, 1):
        c = (mid[0] + ux * s * off, mid[1] + uy * s * off)
        A.add(key, fence_run("%s_%d" % (key, s),
                             T_at(c[0], c[1], 0, rz=ang), seg))
        CK["walls"].append(("fence", (c[0] - ux * seg * 0.5, c[1] - uy * seg * 0.5),
                            (c[0] + ux * seg * 0.5, c[1] + uy * seg * 0.5)))
    A.add(key + "_gate", gate(key + "_gate", T_at(mid[0], mid[1], 0, rz=ang),
                              w=gap))
    CK["walls"].append(("gate", (mid[0] - ux * gap * 0.5, mid[1] - uy * gap * 0.5),
                        (mid[0] + ux * gap * 0.5, mid[1] + uy * gap * 0.5)))


def enclosure(A, key, x, y, w, d, gap=2.9, gate_side="s", kind="fence"):
    """Fence or wall the four edges of a plot, leaving one gateway."""
    hw, hd = w * 0.5, d * 0.5
    corners = dict(sw=(x - hw, y - hd), se=(x + hw, y - hd),
                   ne=(x + hw, y + hd), nw=(x - hw, y + hd))
    sides = dict(s=(corners["sw"], corners["se"]), e=(corners["se"], corners["ne"]),
                 n=(corners["ne"], corners["nw"]), w=(corners["nw"], corners["sw"]))
    for s, (p0, p1) in sides.items():
        g = gap if s == gate_side else 0.0
        if kind == "wall":
            wall_between(A, "%s_%s" % (key, s), p0, p1, h=0.52,
                         group=key + "_w")
            if g:
                A.add(key + "_gate", gate(key + "_gate",
                                          T_at((p0[0] + p1[0]) * 0.5,
                                               (p0[1] + p1[1]) * 0.5, 0,
                                               rz=_run_T(p0, p1)[0]), w=g))
        else:
            fence_between(A, key + "_" + s, p0, p1, gap=g)


def grass_patch(A, key, x, y, w, d, rot=0.0, seed=0, tuft=True, n=None):
    """Enclosed pasture: a green patch that is *not* open village lawn."""
    A.add(key, ground_plate(key, T_at(x, y, 0, rz=rot), w, d, M["pasture"],
                            top=0.004, depth=1.4))
    CK["soft"].append((x, y, w, d, rot))
    if tuft:
        r = random.Random(seed)
        n = n or max(3, int(w * d / 8.0))
        pts = [(x + r.uniform(-w * 0.44, w * 0.44),
                y + r.uniform(-d * 0.44, d * 0.44), 0.012) for _ in range(n)]
        A.add(key + "_t", tufts(key + "_t", T_at(x, y, 0), pts,
                                r=0.12, h=0.34, mat=M["crop_green"], rng=r))


def pasture_plot(A, key, x, y, w, d, seed=0, gate_side="s", tuft=True):
    grass_patch(A, key, x, y, w, d, seed=seed, tuft=tuft)
    enclosure(A, key + "_p", x, y, w, d, gap=2.9, gate_side=gate_side)


def yard_plot(A, key, x, y, w, d, seed=0, gate_side="s"):
    A.add(key + "_earth", apron(key + "_earth", T_at(x, y, 0), w, d,
                                mat=M["earth"], z=0.0025))
    enclosure(A, key + "_y", x, y, w, d, gap=3.0, gate_side=gate_side)
    CK["hard"].append((x, y, w, d, 0.0))


def field_plot(A, key, cx, cy, w, d, open_side="s", seed=0, crop="wheat",
               rot=0.0):
    """Three-sided crop field; the open side faces the lane it belongs to."""
    r = random.Random(seed)
    T = T_at(cx, cy, 0, rz=rot)
    A.add(key + "_soil", apron(key + "_soil", T, w, d, mat=M["earth"], z=0.002))
    iw, id_ = w - 2.2, d - 2.2
    if crop == "veggie":
        A.add(key + "_crop", veg_rows(key + "_crop", T, iw, id_,
                                      M["crop_cabbage"], M["crop_green"],
                                      rng=r, spacing=0.95))
    else:
        A.add(key + "_crop", wheat_field(key + "_crop", T, iw, id_, rng=r))
    hw, hd = w * 0.5, d * 0.5
    sides = dict(s=((cx - hw, cy - hd), (cx + hw, cy - hd)),
                 e=((cx + hw, cy - hd), (cx + hw, cy + hd)),
                 n=((cx + hw, cy + hd), (cx - hw, cy + hd)),
                 w=((cx - hw, cy + hd), (cx - hw, cy - hd)))
    for s, (p0, p1) in sides.items():
        if s == open_side:
            continue
        fence_between(A, key + "_f" + s, p0, p1)
    CK["hard"].append((cx, cy, w, d, rot))


def kitchen_garden(A, key, x, y, w, d, seed=0, gate_side="s"):
    r = random.Random(seed)
    A.add(key + "_earth", apron(key + "_earth", T_at(x, y, 0), w, d,
                                mat=M["earth"], z=0.0025))
    A.add(key + "_crop", veg_rows(key + "_crop", T_at(x, y, 0), w - 2.0, d - 2.0,
                                  M["crop_cabbage"], M["crop_green"], rng=r,
                                  spacing=0.9))
    enclosure(A, key + "_g", x, y, w, d, gap=2.9, gate_side=gate_side)
    CK["hard"].append((x, y, w, d, 0.0))


def orchard(A, key, x, y, w, d, seed=0, n=(3, 2), gate_side="s"):
    """Gridded orchard inside a fence: the pattern rule for trees."""
    r = random.Random(seed)
    A.add(key + "_soil", apron(key + "_soil", T_at(x, y, 0), w, d,
                               mat=M["pasture"], z=0.003))
    CK["soft"].append((x, y, w, d, 0.0))
    nx, ny = n
    for i in range(nx):
        for j in range(ny):
            px = x - w * 0.5 + w * (i + 0.5) / nx
            py = y - d * 0.5 + d * (j + 0.5) / ny
            A.add(key, simple_tree("%s_%d%d" % (key, i, j),
                                   T_at(px + r.uniform(-0.2, 0.2),
                                        py + r.uniform(-0.2, 0.2), 0,
                                        rz=r.uniform(0, TAU)),
                                   h=r.uniform(4.2, 5.2), rng=r,
                                   leaf=M["leaf2"], leaf2=M["leaf"]))
    enclosure(A, key + "_o", x, y, w, d, gap=2.4, gate_side=gate_side)


def village_gate(A, key, cx, cy, w=5.4, h=3.55):
    """Twin stone piers, a tall lintel, a tiled cap: the village door.

    Clear opening is measured, not guessed: piers are 0.72 wide and the beam
    underside sits exactly at `h`, so clear_w = w - 0.72 and clear_h = h.
    """
    pw = 0.72
    parts = []
    for s in (-1, 1):
        px = cx + s * w * 0.5
        parts.append(box("%s_p%d" % (key, s), T_at(px, cy, h * 0.5),
                         (pw, pw + 0.12, h), M["stone"], bev=0.02))
        parts.append(box("%s_b%d" % (key, s), T_at(px, cy, 0.17),
                         (pw + 0.18, pw + 0.30, 0.34), M["stone_step"],
                         bev=0.02))
        parts.append(box("%s_c%d" % (key, s), T_at(px, cy, h + 0.09),
                         (pw + 0.20, pw + 0.30, 0.18), M["stone_step"],
                         bev=0.02))
        parts.append(sphere("%s_f%d" % (key, s), T_at(px, cy, h + 0.30),
                            0.17, M["iron"], seg=8, ring=6))
    # lintel: its underside is exactly at h, so nothing can clip the player
    parts.append(box(key + "_lintel", T_at(cx, cy, h + 0.17),
                     (w + 1.15, 0.30, 0.34), M["wood_frame"], bev=0.01))
    parts.append(box(key + "_sign", T_at(cx, cy - 0.20, h + 0.16),
                     (1.70, 0.10, 0.44), M["wood_board"], bev=0.012))
    parts.append(box(key + "_cap", T_at(cx, cy, h + 0.44),
                     (w + 1.35, 0.64, 0.14), M["tile"][1], bev=0.01))
    parts.append(box(key + "_ridge", T_at(cx, cy, h + 0.60),
                     (w + 1.10, 0.30, 0.22), M["tile"][1], bev=0.01))
    A.add(key, parts)
    print("GATECHECK " + json.dumps(dict(w=w, clear_w=round(w - pw, 2),
                                         clear_h=round(float(h), 2))))
    CK["walls"].append(("stone", (cx - w * 0.5, cy), (cx - w * 0.5, cy)))
    CK["walls"].append(("stone", (cx + w * 0.5, cy), (cx + w * 0.5, cy)))


def clash_report():
    hs = CK["houses"]
    gaps = []
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            gaps.append((_poly_dist(_house_poly(hs[i]), _house_poly(hs[j])),
                         hs[i]["key"], hs[j]["key"]))
    gaps.sort()
    rmax = 0.0
    for h in hs:
        for p in _house_poly(h):
            rmax = max(rmax, math.hypot(p[0], p[1]))
    return gaps, rmax, [h["setback"] for h in hs]


def isolated_runs():
    """Every wall/fence run must end on a building, another run, or a road."""
    out = []
    runs = CK["walls"]
    for idx, (kind, p0, p1) in enumerate(runs):
        for end in (p0, p1):
            best = 9e9
            for jdx, (kind2, q0, q1) in enumerate(runs):
                if jdx == idx:
                    continue
                best = min(best, math.hypot(end[0] - q0[0], end[1] - q1[1]),
                           math.hypot(end[0] - q1[0], end[1] - q1[1]),
                           _pt_seg_d(end, q0, q1))
            for h in CK["houses"]:
                best = min(best, _poly_dist([end], _house_poly(h)))
            for s in CK["streets"]:
                best = min(best, max(0.0, _pt_seg_d(end, s[0], s[1]) - s[2]))
            if best > 0.55:
                out.append([kind, round(end[0], 1), round(end[1], 1),
                            round(best, 2)])
    return out


def _in_rect(px, py, q):
    dx, dy = px - q[0], py - q[1]
    c, s = math.cos(-q[4]), math.sin(-q[4])
    lx, ly = dx * c - dy * s, dx * s + dy * c
    return abs(lx) <= q[2] * 0.5 and abs(ly) <= q[3] * 0.5


def free_spots(n, seed, x0, x1, y0, y1, clear=0.45, tries=6000):
    """Random points that keep clear of every paved rect and house footprint."""
    r = random.Random(seed)
    out, t = [], 0
    while len(out) < n and t < tries:
        t += 1
        px, py = r.uniform(x0, x1), r.uniform(y0, y1)
        ok = True
        for q in CK["hard"]:
            if _in_rect(px, py, (q[0], q[1], q[2] + clear * 2.0,
                                 q[3] + clear * 2.0, q[4])):
                ok = False
                break
        if ok:
            for h in CK["houses"]:
                if _in_rect(px, py, (h["c"][0], h["c"][1], h["W"] + 2.4,
                                     h["D"] + 2.4, -h["rz"])):
                    ok = False
                    break
        if ok:
            out.append((px, py, 0.004))
    return out


def layout_check(key):
    r = random.Random(4)
    n = 600
    hard = 0
    for _ in range(n):
        a = r.uniform(0, TAU)
        rr = 14.0 * math.sqrt(r.random())
        px, py = math.cos(a) * rr, math.sin(a) * rr
        for h in CK["houses"]:
            if _in_rect(px, py, (h["c"][0], h["c"][1], h["W"], h["D"], -h["rz"])):
                hard += 1
                break
        else:
            for q in CK["hard"]:
                if _in_rect(px, py, q):
                    hard += 1
                    break
    gaps, rmax, setb = clash_report()
    info = dict(variant=key, hard=round(hard / float(n), 3),
                core_r=round(rmax, 2),
                gap_min=round(gaps[0][0], 2) if gaps else None,
                gap_pair=list(gaps[0][1:]) if gaps else None,
                setback=[round(min(setb), 2), round(max(setb), 2)],
                runs=len(CK["walls"]), isolated=isolated_runs())
    print("LAYOUTCHECK " + json.dumps(info))
    return info


# ------------------------------------------------------------------ farm_a
def layout_a(A):
    """Crossroads market village: gate lane -> cross lane + square -> mill."""
    ck_clear()
    SW = 4.9
    XW = 4.4
    core = [(-13.5, -24.5), (-6.6, -29.0), (8.0, -29.0), (17.5, -21.5),
            (22.5, -10.5), (23.0, 2.0), (20.0, 13.0), (12.0, 23.0),
            (2.0, 26.5), (-9.0, 24.5), (-18.0, 17.0), (-22.0, 6.0),
            (-20.5, -8.0), (-16.5, -17.0)]
    A.add("core", poly_plate("core", core, M["pasture"], top=0.0))
    # The floor is pasture on purpose: the village sits on grass, and only the
    # lanes / square / plots are hard. An earth disc under everything read as a
    # mud pancake with a hard edge against the terrain.

    arrive = [(0.0, -44.6), (0.5, -39.0), (-0.3, -33.0), (0.3, -30.2)]
    lane_road(A, "lane_arrive", arrive, SW, seed=11, ruts=True)
    add_street(arrive, SW * 0.5)
    # material changes from dirt to stone exactly at the gate (LA 1.10)
    street = [(0.3, -30.2), (0.3, -26.0), (0.0, -19.0), (0.2, -13.5),
              (0.0, -11.2)]
    A.add("street", road_ribbon("street", street, SW, M["cobble"], z=0.0035,
                                wob=SW * 0.05, seed=17))
    add_street(street, SW * 0.5)
    CK["hard"].append((0.1, -20.7, 5.4, 19.0, 0.0))
    cross = [(-23.0, -9.3), (-14.0, -9.0), (-6.0, -9.2), (0.0, -9.0),
             (7.0, -9.2), (15.0, -8.9), (23.0, -9.3)]
    A.add("lane_cross", road_ribbon("lane_cross", cross, XW, M["cobble"],
                                    z=0.0030, wob=XW * 0.05, seed=12))
    add_street(cross, XW * 0.5)
    CK["hard"].append((0.0, -9.1, 46.0, XW, 0.0))
    north = [(0.0, 6.6), (0.0, 10.0), (0.0, 14.2)]
    A.add("lane_north", road_ribbon("lane_north", north, SW, M["cobble"],
                                    z=0.0030, wob=SW * 0.05, seed=13))
    add_street(north, SW * 0.5)

    # ---- arrival corridor: soil shoulders so no lawn shows beside the lane
    # ---- the gate sits *in* the village wall, not 11 m out in the field ----
    village_gate(A, "gate", 0.2, -29.4, w=5.4, h=3.55)
    A.add("gate_apron", apron_cluster("gate_apron", 0.0, -33.2, 9.2, 7.0,
                                      seed=21, n=5, mat=M["cobble"]))
    CK["hard"].append((0.0, -33.2, 9.2, 7.0, 0.0))
    tree_at(A, "avenue_w", -3.9, -30.7, 8.4, 51, "broad")
    tree_at(A, "avenue_e", 4.2, -30.7, 8.6, 52, "broad")
    A.add("junction", apron_cluster("junction", -0.1, -9.1, 13.0, 8.4,
                                    seed=22, n=5, mat=M["cobble"]))

    # ---- the square ------------------------------------------------------
    paved_square(A, "plaza", 0.0, 0.4, 12.6, 12.4, rot=0.012)
    A.add("forecourt", apron_cluster("forecourt", 0.0, 12.4, 9.4, 5.0,
                                     seed=23, n=4, mat=M["cobble"]))
    A.add("north_pass", apron("north_pass", T_at(0.0, 8.25, 0), 7.2, 3.6,
                              mat=M["cobble"], z=0.0038))
    CK["hard"].append((0.0, 12.4, 9.6, 5.2, 0.0))
    CK["hard"].append((0.0, 8.25, 7.4, 3.8, 0.0))

    # ---- mill terrace (level +0.90) --------------------------------------
    A.add("mill_pad", pad("mill_pad", 0.0, 19.9, 13.0, 8.6, 0.90, M["earth"]))
    retwall(A, "mill_wall_sl", [(-6.5, 15.6), (-1.9, 15.6)], 0.90)
    retwall(A, "mill_wall_sr", [(1.9, 15.6), (6.5, 15.6)], 0.90)
    wall_run(A, "mill_wall_w", [(-6.5, 24.2), (-6.5, 15.6)])
    wall_run(A, "mill_wall_e", [(6.5, 15.6), (6.5, 24.2)])
    wall_run(A, "mill_wall_n", [(-6.5, 24.2), (6.5, 24.2)])
    stairs(A, "mill_steps", 0.0, 15.55, 0.0, -1.0, 3.3, 0.90)
    # sail tips at 11.0 m, 8.7 m across: a village mill, not a cathedral
    A.add("mill", windmill("mill", T_at(0.0, 20.4, 0.90, rz=math.pi),
                           tower_h=5.6, r_base=2.05, r_top=1.50, sail_len=4.20))
    A.add("mill_shed_w", fk.shed("mill_shed_w",
                                 T_at(-4.9, 21.4, 0.90, rz=math.pi * 0.5),
                                 w=3.6, d=2.5, h=2.3))
    A.add("mill_shed_e", fk.shed("mill_shed_e",
                                 T_at(4.9, 20.2, 0.90, rz=-math.pi * 0.5),
                                 w=3.6, d=2.5, h=2.3))
    prop_cluster(A, "mill_props", 3.4, 17.2, 41, barrels=2, crates=1, sacks=2)

    # ---- arrival street --------------------------------------------------
    w1 = front(A, "house_w_1", -2.45, -14.8, 1, 0, 101, W=5.8, D=5.0,
               pi=0, ti=1, si=1, win_front=1, firewood=False)
    w2 = front(A, "house_w_2", -2.45, -21.6, 1, 0, 102, W=6.0, D=5.2,
               pi=3, ti=2, si=3, win_front=1, firewood=False)
    e1 = front(A, "house_e_1", 2.45, -14.7, -1, 0, 103, W=5.6, D=4.9,
               pi=2, ti=0, si=0, win_side=0, win_front=1, firewood=False)
    e2 = front(A, "house_e_2", 2.45, -21.6, -1, 0, 104, W=6.2, D=5.1,
               pi=5, ti=2, si=1, ridge_along_front=False, win_front=1,
               firewood=False)
    link(A, "w_1_2", w1, w2)
    link(A, "e_1_2", e1, e2)

    # ---- the square frontage ---------------------------------------------
    pw1 = front(A, "plaza_w_1", -6.3, -3.0, 1, 0, 105, W=5.4, D=5.0,
                pi=1, ti=1, si=3, firewood=False)
    pw2 = front(A, "plaza_w_2", -6.3, 3.2, 1, 0, 106, W=5.6, D=5.0,
                pi=4, ti=0, si=0, firewood=False)
    pe1 = front(A, "plaza_e_1", 6.3, -2.6, -1, 0, 107, W=5.4, D=5.0,
                pi=2, ti=1, si=1, firewood=False)
    inn = front(A, "inn", 6.3, 3.9, -1, 0, 108, W=6.4, D=5.6,
                pi=0, ti=2, si=1, nF=2)
    link(A, "pw_1_2", pw1, pw2)
    link(A, "pe_1_inn", pe1, inn, style="hedge")

    # ---- north: miller's house, walled yard, arch over the mill lane -----
    front(A, "miller", -2.45, 11.4, 1, 0, 109, W=5.2, D=4.8,
          pi=5, ti=0, si=3, win_side=0, win_front=1, firewood=False)
    village_gate(A, "arch", 0.0, 8.1, w=5.7, h=3.10)
    wall_run(A, "arch_wall_w", [(-2.85, 8.1), (-4.6, 8.1), (-4.6, 11.4),
                                (-3.4, 11.4)])
    wall_run(A, "arch_wall_e", [(2.85, 8.1), (3.3, 8.1)])
    A.add("yard_e_floor", apron("yard_e_floor", T_at(6.4, 10.8, 0, rz=0.02),
                                6.6, 6.2, mat=M["earth"], z=0.0022))
    A.add("yard_e_shed", fk.shed("yard_e_shed",
                                 T_at(7.6, 11.8, 0, rz=-math.pi * 0.5),
                                 w=3.6, d=2.5, h=2.35))
    A.add("yard_e_wood", woodpile("yard_e_wood", T_at(4.9, 9.2, 0, rz=0.1),
                                  w=2.2, rows=4))
    A.add("yard_e_laundry", fk.laundry("yard_e_laundry",
                                       T_at(6.8, 8.6, 0, rz=math.pi * 0.5),
                                       L=3.2))
    wall_run(A, "yard_e_w", [(3.3, 7.6), (3.3, 10.3), (3.3, 12.1), (3.3, 14.0)])
    wall_run(A, "yard_e_n", [(3.3, 14.0), (9.9, 14.0)])
    wall_run(A, "yard_e_e", [(9.9, 14.0), (9.9, 7.6)])
    wall_run(A, "yard_e_s", [(9.9, 7.6), (3.3, 7.6)])
    A.add("yard_e_gate", gate("yard_e_gate", T_at(3.3, 11.2, 0, rz=math.pi * 0.5),
                              w=3.5))

    # ---- barn + its yard on the cross lane -------------------------------
    A.add("barn", barn("barn", T_at(-15.8, -1.6, 0, rz=math.pi),
                       W=10.5, D=7.2, ti=1))
    A.add("barn_yard", apron("barn_yard", T_at(-15.6, -6.8, 0, rz=0.03),
                             11.0, 3.4, mat=M["earth"], z=0.0022))
    A.add("barn_cart", medbuild.cart("barn_cart", T_at(-11.8, -6.4, 0, rz=1.9),
                                     rng=random.Random(9)))
    prop_cluster(A, "barn_props", -19.2, -6.6, 43, barrels=2, crates=2, sacks=1)
    A.add("barn_hay", haystack("barn_hay", T_at(-22.6, -4.4, 0),
                               r=1.5, h=2.1, rng=random.Random(21)))
    wall_run(A, "barn_wall", [(-21.05, -5.2), (-23.4, -5.2), (-23.4, -6.9)])

    # ---- square furniture ------------------------------------------------
    A.add("well", well("well", T_at(-2.6, 2.6, 0, rz=0.3)))
    A.add("shrine", shrine("shrine", T_at(-4.9, 8.7, 0, rz=0.55)))
    A.add("notice", notice_board("notice", T_at(4.2, -4.2, 0, rz=-1.4)))
    A.add("banner", banner("banner", T_at(2.7, 6.1, 0), h=5.2))
    A.add("stall_a", fk.stall("stall_a", T_at(-4.4, 4.6, 0, rz=0.05),
                              w=2.9, d=2.1))
    A.add("stall_b", fk.stall("stall_b", T_at(4.6, 0.7, 0, rz=-math.pi * 0.5),
                              w=2.9, d=2.1))
    A.add("bench_sq", fk.bench("bench_sq", T_at(-0.7, 5.0, 0, rz=0.1)))
    prop_cluster(A, "sq_props", -5.0, -3.9, 51, barrels=2, crates=1, sacks=1)
    A.add("lanterns", fk.lantern_post("lan1", T_at(-2.9, -6.4, 0)))
    # stone kerb bollards instead of crop cones: this is paving, not a field
    A.add("bollards", fk.bollard("bol_1", T_at(-5.55, -3.4, 0)) +
                       fk.bollard("bol_2", T_at(-5.55, 2.3, 0)) +
                       fk.bollard("bol_3", T_at(5.55, -2.7, 0)) +
                       fk.bollard("bol_4", T_at(5.55, 4.4, 0)))
    A.add("hitch", fk.hitch_post("hitch_1", T_at(5.9, -5.1, 0,
                                                 rz=-math.pi * 0.5)))
    prop_cluster(A, "sq_props2", 1.4, -4.4, 57, barrels=1, crates=2, sacks=1)
    A.add("bench_sq2", fk.bench("bench_sq2", T_at(2.2, 3.0, 0, rz=-1.5)))

    # ---- village edge: one closed wall ring, ends buried in the gate piers -
    ring = [(2.9, -29.4), (8.0, -29.0), (17.5, -21.5), (22.5, -10.5), (23.0, 2.0),
            (20.0, 13.0), (12.0, 23.0), (2.0, 26.5), (-9.0, 24.5), (-18.0, 17.0),
            (-22.0, 6.0), (-20.5, -8.0), (-16.5, -17.0), (-13.5, -24.5),
            (-6.6, -29.0), (-2.5, -29.4)]
    wall_run(A, "edge", ring, h=1.30, t=0.52)
    corner_posts(A, "edge", ring, 1.30, 0.52)

    # ---- plots in the ring band -----------------------------------------
    kitchen_garden(A, "g_w", -9.4, -22.6, 6.4, 4.6, 71, gate_side="n")
    yard_plot(A, "p_w", -12.4, -17.0, 5.8, 5.0, seed=33, gate_side="e")
    A.add("p_w_hay", haystack("p_w_hay", T_at(-13.6, -18.2, 0), r=1.25,
                              h=1.9, rng=random.Random(26)))
    orchard(A, "orchard_nw", -15.4, 12.0, 8.6, 8.4, seed=61, n=(2, 2),
            gate_side="e")
    kitchen_garden(A, "g_e", 10.0, -18.4, 5.8, 4.8, 72, gate_side="n")
    pasture_plot(A, "p_e", 15.6, -3.6, 6.0, 7.0, seed=34, gate_side="w")
    yard_plot(A, "y_e", 17.0, 6.6, 7.4, 8.4, seed=35, gate_side="w")
    A.add("y_e_hay", haystack("y_e_hay", T_at(16.0, 8.4, 0), r=1.35, h=2.0,
                              rng=random.Random(24)))
    A.add("y_e_trough", trough("y_e_trough", T_at(18.4, 4.8, 0, rz=0.3)))
    pasture_plot(A, "p_ne", 8.6, 18.0, 6.0, 6.4, seed=36, gate_side="s")
    A.add("p_ne_trough", trough("p_ne_trough", T_at(8.2, 18.6, 0, rz=-0.4)))

    # ---- back trees ------------------------------------------------------
    tree_at(A, "poplar_1", -8.2, 20.2, 10.6, 303, "poplar")
    tree_at(A, "tree_back1", 7.6, -9.8, 9.0, 154, "broad")
    tree_at(A, "tree_back2", 8.8, 16.4, 8.4, 155, "broad")
    tree_at(A, "tree_back3", -11.2, -11.2, 8.6, 156, "broad")
    hedge(A, "hedge_nw", (-4.9, 10.6), (-11.1, 13.6), 61, r=0.55)

    # ---- fields: hard against the outside of the village wall, flanking ---
    # the gate corridor, so "field -> gate -> street -> square" is one line
    field_plot(A, "field_wheat", -11.5, -36.0, 13.8, 13.4, open_side="e",
               seed=81)
    field_plot(A, "field_veg", 11.0, -36.0, 12.8, 13.4, open_side="w", seed=82,
               crop="veggie")
    fence_between(A, "wheat_wall", (-4.6, -42.7), (-4.6, -29.2), gap=3.0)
    fence_between(A, "veg_wall", (4.6, -42.7), (4.6, -29.2), gap=3.0)

    rt = random.Random(19)
    core_t = free_spots(26, 19, -20.0, 20.0, -26.0, 24.0)
    A.add("core_tufts", tufts("core_tufts", T_at(0, 0, 0), core_t, r=0.13,
                              h=0.30, mat=M["crop_green"], rng=rt))
    rt = random.Random(29)
    core_t = free_spots(22, 29, -15.0, 15.0, -25.0, 20.0)
    A.add("core_tufts", tufts("core_tufts", T_at(0, 0, 0), core_t, r=0.13,
                              h=0.30, mat=M["crop_green"], rng=rt))
    rt = random.Random(31)
    core_t = free_spots(24, 31, -16.0, 16.0, -24.0, 20.0)
    A.add("core_tufts", tufts("core_tufts", T_at(0, 0, 0), core_t, r=0.13,
                              h=0.30, mat=M["crop_green"], rng=rt))
    A.add("paths", CK["paths"])

# ------------------------------------------------------------------ farm_b
def layout_b(A):
    """Long street village: one lane, a fenced green on the east, mill head."""
    ck_clear()
    SW = 4.9
    core = [(-14.0, -24.0), (-7.2, -29.0), (7.0, -29.0), (17.5, -22.0),
            (21.5, -11.0), (22.0, 0.0), (18.5, 11.0), (12.0, 19.0),
            (3.0, 23.5), (-6.0, 23.0), (-14.0, 17.5), (-18.0, 6.0),
            (-17.5, -10.0), (-15.5, -18.0)]
    A.add("core", poly_plate("core", core, M["pasture"], top=0.0))

    arrive = [(0.0, -44.6), (0.4, -39.0), (-0.4, -33.0), (0.3, -29.0)]
    lane_road(A, "lane_arrive", arrive, SW, seed=11, ruts=True)
    add_street(arrive, SW * 0.5)
    # inside the wall the lane is stone, not dirt (matches farm_a / farm_c)
    main = [(0.3, -29.0), (0.2, -24.0), (0.0, -17.0), (0.2, -9.0), (0.0, 0.0),
            (0.2, 7.0), (0.1, 15.0)]
    A.add("street", road_ribbon("street", main, SW, M["cobble"], z=0.0035,
                                wob=SW * 0.05, seed=17))
    add_street(main, SW * 0.5)
    A.add("verge_w", apron("verge_w", T_at(-4.7, -35.0, 0), 4.6, 18.6,
                           mat=M["earth"], z=0.0009))
    A.add("verge_e", apron("verge_e", T_at(5.2, -35.0, 0), 5.4, 18.6,
                           mat=M["earth"], z=0.0009))
    A.add("gate_apron", apron_cluster("gate_apron", 0.2, -37.5, 11.6, 7.2,
                                      seed=21, n=5, mat=M["cobble"]))
    A.add("gate_walk", apron("gate_walk", T_at(0.2, -31.0, 0, rz=0.03),
                             6.2, 4.4, mat=M["cobble"], z=0.0023))
    CK["hard"].append((0.2, -37.5, 11.6, 7.2, 0.0))
    A.add("street_apron", apron("street_apron", T_at(0.0, -1.0, 0, rz=0.01),
                                9.4, 21.0, mat=M["cobble"], z=0.0025))
    CK["hard"].append((0.0, -1.0, 9.4, 21.0, 0.01))
    A.add("mill_apron", apron_cluster("mill_apron", 0.0, 13.9, 9.6, 5.6,
                                      seed=25, n=4, mat=M["cobble"]))
    CK["hard"].append((0.0, 13.9, 9.6, 5.6, 0.0))

    # ---- mill terrace (level +0.90) --------------------------------------
    A.add("mill_pad", pad("mill_pad", 0.0, 19.6, 12.6, 8.4, 0.90, M["earth"]))
    retwall(A, "mill_wall_sl", [(-6.3, 15.4), (-1.9, 15.4)], 0.90)
    retwall(A, "mill_wall_sr", [(1.9, 15.4), (6.3, 15.4)], 0.90)
    wall_run(A, "mill_wall_w", [(-6.3, 23.8), (-6.3, 15.4)])
    wall_run(A, "mill_wall_e", [(6.3, 15.4), (6.3, 23.8)])
    wall_run(A, "mill_wall_n", [(-6.3, 23.8), (6.3, 23.8)])
    stairs(A, "mill_steps", 0.0, 15.35, 0.0, -1.0, 3.3, 0.90)
    A.add("mill", windmill("mill", T_at(0.0, 20.1, 0.90, rz=math.pi),
                           tower_h=5.6, r_base=2.05, r_top=1.50, sail_len=4.20))
    A.add("mill_shed", fk.shed("mill_shed", T_at(4.7, 21.0, 0.90, rz=-math.pi * 0.5),
                               w=3.8, d=2.5, h=2.35))
    prop_cluster(A, "mill_props", -3.6, 17.2, 47, barrels=2, crates=1, sacks=2)

    # ---- a widening in the middle of the lane ---------------------------
    A.add("street_place", apron("street_place", T_at(0.0, -12.6, 0, rz=0.008),
                                12.6, 13.4, mat=M["cobble"], z=0.0026))
    CK["hard"].append((0.0, -12.6, 12.6, 13.4, 0.008))

    # ---- west row: the long street wall ---------------------------------
    hw = []
    for i, (ey, W, D, pi, ti, si, ex, st) in enumerate([
            (-21.4, 6.0, 5.1, 0, 0, 1, -2.45, 0.9),
            (-14.6, 5.8, 5.0, 1, 1, 0, -5.9, 1.15),
            (-8.0, 5.8, 5.0, 2, 2, 2, -5.6, 0.7),
            (-1.6, 5.8, 5.0, 3, 3, 1, -2.45, 0.65),
            (5.0, 5.8, 5.0, 4, 1, 2, -2.45, 1.0)]):
        hw.append(front(A, "house_w_%d" % (i + 1), ex, ey, 1, 0, 120 + i,
                        W=W, D=D, pi=pi, ti=ti, si=si, setback=st,
                        win_side=1 if i % 2 else 0, win_front=1,
                        firewood=False))
    for i in range(len(hw) - 1):
        link(A, "w_%d_%d" % (i, i + 1), hw[i], hw[i + 1],
             style="hedge" if i == 1 else "stone")

    # ---- east row, up to the green --------------------------------------
    he = []
    for i, (ey, W, D, pi, ti, si, ex, st) in enumerate([
            (-20.4, 5.6, 4.9, 5, 2, 0, 2.45, 0.9),
            (-13.7, 5.8, 5.0, 1, 3, 1, 5.6, 1.0),
            (-7.0, 6.0, 5.1, 4, 0, 2, 5.2, 0.7)]):
        he.append(front(A, "house_e_%d" % (i + 1), ex, ey, -1, 0, 130 + i,
                        W=W, D=D, pi=pi, ti=ti, si=si, setback=st, win_front=1,
                        firewood=False))
    for i in range(len(he) - 1):
        link(A, "e_%d_%d" % (i, i + 1), he[i], he[i + 1])

    # ---- street furniture ------------------------------------------------
    A.add("notice", notice_board("notice", T_at(-6.0, -12.4, 0, rz=-1.45)))
    A.add("banner", banner("banner", T_at(3.1, -4.2, 0), h=5.0))
    A.add("lanterns", fk.lantern_post("lan1", T_at(-3.2, -6.4, 0)))
    A.add("street_cart", medbuild.cart("street_cart", T_at(3.4, 3.0, 0, rz=0.6),
                                       rng=random.Random(19)))
    A.add("street_bench", fk.bench("street_bench", T_at(-6.6, -9.2, 0,
                                                        rz=math.pi * 0.5)))
    tree_at(A, "place_tree", 5.6, -10.0, 9.4, 168, "broad")
    A.add("street_trough", trough("street_trough", T_at(6.4, -13.6, 0, rz=0.1)))
    prop_cluster(A, "street_props", 3.6, -8.4, 49, barrels=2, crates=1, sacks=1)

    # ---- the green -------------------------------------------------------
    gx, gy, gw, gd = 11.4, 1.2, 13.6, 10.0
    pasture_plot(A, "green", gx, gy, gw, gd, seed=44, gate_side="w", tuft=True)
    A.add("green_well", well("green_well", T_at(7.4, 2.2, 0, rz=0.2)))
    tree_at(A, "green_oak", 15.4, 1.0, 12.4, 161, "broad")
    A.add("green_bench", fk.bench("green_bench", T_at(7.7, -0.8, 0, rz=1.45)))
    A.add("green_stall", fk.stall("green_stall", T_at(6.3, -1.5, 0, rz=math.pi * 0.5),
                                  w=2.7, d=2.0))
    A.add("green_trough", trough("green_trough", T_at(13.2, -1.6, 0, rz=0.4)))
    A.add("green_hay", haystack("green_hay", T_at(16.8, 4.4, 0),
                                r=1.35, h=2.0, rng=random.Random(23)))

    # ---- inn on the green's north-west corner ----------------------------
    inn = front(A, "inn", 2.45, 9.6, -1, 0, 141, W=6.4, D=5.6,
                pi=0, ti=2, si=1, nF=2)
    A.add("inn_yard", apron("inn_yard", T_at(7.4, 13.2, 0, rz=0.02), 6.2, 3.4,
                            mat=M["earth"], z=0.0022))
    A.add("inn_laundry", fk.laundry("inn_laundry", T_at(8.2, 13.6, 0), L=3.4))
    wall_run(A, "inn_wall", [(5.4, 12.7), (5.4, 14.8), (11.6, 14.8),
                             (11.6, 6.4)])

    # ---- barn + its yards ------------------------------------------------
    A.add("barn", barn("barn", T_at(14.4, -9.8, 0, rz=math.pi),
                       W=10.2, D=7.0, ti=1))
    A.add("barn_yard", apron("barn_yard", T_at(14.2, -13.6, 0, rz=0.02),
                             10.6, 3.2, mat=M["earth"], z=0.0022))
    A.add("barn_cart", medbuild.cart("barn_cart", T_at(9.6, -13.2, 0, rz=1.4),
                                     rng=random.Random(9)))
    prop_cluster(A, "barn_props", 17.6, -13.0, 43, barrels=2, crates=2, sacks=1)
    A.add("barn_hay", haystack("barn_hay", T_at(20.0, -6.4, 0),
                               r=1.5, h=2.1, rng=random.Random(24)))

    # ---- west back plots -------------------------------------------------
    kitchen_garden(A, "g_w1", -9.4, -18.6, 6.2, 4.6, 73, gate_side="n")
    kitchen_garden(A, "g_w2", -9.4, 8.0, 6.0, 4.6, 74, gate_side="s")
    orchard(A, "orchard_w", -13.2, -4.0, 7.4, 8.0, seed=62, n=(2, 3),
            gate_side="e")
    pasture_plot(A, "p_w", -12.6, 15.0, 6.0, 5.2, seed=35, gate_side="s")
    A.add("west_shed", fk.shed("west_shed", T_at(-8.4, 12.4, 0, rz=0.0),
                               w=3.6, d=2.5, h=2.35))
    enclosure(A, "shed_yard", -8.4, 12.4, 5.4, 4.4, gate_side="s")
    A.add("west_wood", woodpile("west_wood", T_at(-4.6, 11.4, 0, rz=0.2),
                                w=2.2, rows=4))

    # ---- village edge ----------------------------------------------------
    ring = [(2.9, -29.0), (7.0, -29.0), (17.5, -22.0), (21.5, -11.0),
            (22.0, 0.0), (18.5, 11.0), (12.0, 19.0), (3.0, 23.5),
            (-6.0, 23.0), (-14.0, 17.5), (-18.0, 6.0), (-17.5, -10.0),
            (-15.5, -18.0), (-14.0, -24.0), (-7.2, -29.0), (-2.2, -29.0)]
    wall_run(A, "edge", ring, h=1.30, t=0.52)
    corner_posts(A, "edge", ring, 1.30, 0.52)

    # ---- gate, avenue, fields -------------------------------------------
    village_gate(A, "gate", 0.2, -29.0, w=5.8, h=3.40)
    tree_at(A, "avenue_w", -3.9, -38.6, 8.4, 51, "broad")
    tree_at(A, "avenue_e", 4.3, -38.6, 8.6, 52, "broad")
    tree_at(A, "tree_back1", -10.0, -12.6, 9.2, 154, "broad")
    tree_at(A, "tree_back2", 8.0, 19.6, 9.0, 155, "broad")
    hedge(A, "hedge_w", (-2.6, -5.2), (-9.5, -5.2), 62, r=0.66)

    field_plot(A, "field_wheat", -14.2, -35.0, 15.0, 12.0, open_side="e", seed=81)
    wall_run(A, "field_wall_w", [(-6.7, -29.0), (-6.7, -33.85)])
    wall_run(A, "field_wall_w2", [(-6.7, -36.75), (-6.7, -41.0)])
    field_plot(A, "field_veg", 14.2, -35.0, 13.0, 12.0, open_side="w", seed=82,
               crop="veggie")
    wall_run(A, "field_wall_e", [(7.7, -29.0), (7.7, -33.85)])
    wall_run(A, "field_wall_e2", [(7.7, -36.75), (7.7, -41.0)])
    A.add("field_gate_w", gate("field_gate_w", T_at(-6.7, -35.3, 0,
                                                   rz=math.pi * 0.5), w=2.9))
    A.add("field_gate_e", gate("field_gate_e", T_at(7.7, -35.3, 0,
                                                   rz=math.pi * 0.5), w=2.9))
    CK["walls"].append(("gate", (-6.7, -33.85), (-6.7, -36.75)))
    CK["walls"].append(("gate", (7.7, -33.85), (7.7, -36.75)))

    A.add("paths", CK["paths"])


# ------------------------------------------------------------------ farm_c
def layout_c(A):
    """Forked village: one lane, a green island, the mill in the crotch."""
    ck_clear()
    SW = 4.9
    BW = 4.4
    core = [(-12.0, -24.0), (-6.6, -29.0), (8.0, -29.0), (18.0, -21.0),
            (23.5, -8.0), (24.0, 3.0), (20.0, 13.0), (12.0, 21.0),
            (0.0, 24.0), (-12.0, 20.0), (-20.0, 13.0), (-23.0, 2.0),
            (-21.0, -10.0), (-17.0, -19.0)]
    A.add("core", poly_plate("core", core, M["pasture"], top=0.0))

    arrive = [(0.0, -44.6), (0.4, -39.0), (-0.3, -33.0), (0.2, -29.8)]
    lane_road(A, "lane_arrive", arrive, SW, seed=11, ruts=True)
    add_street(arrive, SW * 0.5)
    # dirt turns to stone at the gate, as on farm_a
    main = [(0.2, -29.8), (0.1, -24.0), (0.0, -18.0), (0.1, -12.0),
            (0.0, -6.0), (0.0, 0.4)]
    A.add("street", road_ribbon("street", main, SW, M["cobble"], z=0.0035,
                                wob=SW * 0.05, seed=17))
    add_street(main, SW * 0.5)
    nw = [(-0.1, 0.2), (-3.4, 5.0), (-7.8, 10.2), (-12.8, 14.8), (-17.4, 18.0)]
    A.add("lane_nw", road_ribbon("lane_nw", nw, BW, M["cobble"], z=0.0032,
                                 wob=BW * 0.05, seed=14))
    add_street(nw, BW * 0.5)
    ne = [(0.1, 0.2), (3.6, 5.4), (8.4, 10.2), (13.2, 14.2), (17.6, 16.8)]
    A.add("lane_ne", road_ribbon("lane_ne", ne, BW, M["cobble"], z=0.0031,
                                 wob=BW * 0.05, seed=15))
    add_street(ne, BW * 0.5)

    A.add("verge_w", apron("verge_w", T_at(-4.7, -35.0, 0), 4.6, 18.6,
                           mat=M["earth"], z=0.0009))
    A.add("verge_e", apron("verge_e", T_at(5.2, -35.0, 0), 5.4, 18.6,
                           mat=M["earth"], z=0.0009))
    A.add("gate_apron", apron_cluster("gate_apron", 0.2, -37.5, 11.6, 7.2,
                                      seed=21, n=5, mat=M["cobble"]))
    A.add("gate_walk", apron("gate_walk", T_at(0.2, -31.0, 0, rz=0.03),
                             6.2, 4.4, mat=M["cobble"], z=0.0023))
    CK["hard"].append((0.2, -37.5, 11.6, 7.2, 0.0))
    A.add("north_pass", apron("north_pass", T_at(0.0, -1.0, 0, rz=0.02),
                              11.0, 4.2, mat=M["cobble"], z=0.0024))
    CK["hard"].append((0.0, -1.0, 11.0, 4.2, 0.02))
    A.add("fork_apron", apron_cluster("fork_apron", 0.0, 2.6, 10.4, 6.0,
                                      seed=26, n=5, mat=M["cobble"]))
    CK["hard"].append((0.0, 2.6, 10.4, 6.0, 0.0))
    A.add("street_apron", apron("street_apron", T_at(0.0, -9.0, 0, rz=0.01),
                                11.2, 13.4, mat=M["cobble"], z=0.0025))
    CK["hard"].append((0.0, -9.0, 11.2, 13.4, 0.01))

    # ---- the island between the branches --------------------------------
    A.add("island_pad", pad("island_pad", 0.0, 8.6, 7.6, 9.6, 0.22, M["earth"],
                            rot=0.02))
    retwall(A, "island_wall_w", [(-3.7, 9.4), (-2.5, 5.4), (0.0, 4.0)], 0.22,
            cap=0.06)
    retwall(A, "island_wall_e", [(0.0, 4.0), (2.7, 5.6), (3.7, 9.6)], 0.22,
            cap=0.06)
    A.add("island_grass", ground_plate("island_grass", T_at(0.0, 8.8, 0),
                                       6.7, 8.5, M["pasture"], top=0.232,
                                       depth=1.4))
    CK["soft"].append((0.0, 8.8, 6.7, 8.5, 0.0))
    r_i = random.Random(46)
    A.add("island_tufts", tufts("island_tufts", T_at(0.0, 8.8, 0.22),
                                [(r_i.uniform(-2.4, 2.4),
                                  r_i.uniform(-3.0, 3.0), 0.224)
                                 for _ in range(14)],
                                r=0.12, h=0.32, mat=M["crop_green"], rng=r_i))
    A.add("well", well("well", T_at(0.4, 6.4, 0.22, rz=0.25)))
    A.add("banner", banner("banner", T_at(2.3, 8.4, 0.22), h=4.8))
    tree_at(A, "island_tree", -7.2, 9.0, 8.8, 162, "broad")
    A.add("island_bench", fk.bench("island_bench", T_at(-1.9, 9.6, 0.22, rz=0.9)))
    A.add("island_shrine", shrine("shrine", T_at(-1.6, 12.2, 0.22, rz=0.2)))

    # ---- mill terrace in the crotch (level +0.90) -----------------------
    A.add("mill_pad", pad("mill_pad", 0.0, 18.5, 12.6, 8.0, 0.90, M["earth"]))
    retwall(A, "mill_wall_sl", [(-6.3, 14.5), (-1.9, 14.5)], 0.90)
    retwall(A, "mill_wall_sr", [(1.9, 14.5), (6.3, 14.5)], 0.90)
    wall_run(A, "mill_wall_w", [(-6.3, 22.5), (-6.3, 14.5)])
    wall_run(A, "mill_wall_e", [(6.3, 14.5), (6.3, 22.5)])
    wall_run(A, "mill_wall_n", [(-6.3, 22.5), (6.3, 22.5)])
    stairs(A, "mill_steps", 0.0, 14.45, 0.0, -1.0, 3.3, 0.90)
    A.add("mill", windmill("mill", T_at(0.0, 19.0, 0.90, rz=math.pi),
                           tower_h=5.6, r_base=2.05, r_top=1.50, sail_len=4.20))
    A.add("mill_shed_w", fk.shed("mill_shed_w",
                                 T_at(-4.8, 20.3, 0.90, rz=math.pi * 0.5),
                                 w=3.4, d=2.4, h=2.3))
    A.add("mill_shed_e", fk.shed("mill_shed_e",
                                 T_at(4.8, 19.5, 0.90, rz=-math.pi * 0.5),
                                 w=3.4, d=2.4, h=2.3))
    prop_cluster(A, "mill_props", -3.6, 16.0, 49, barrels=2, crates=1, sacks=2)

    # ---- main street pair ------------------------------------------------
    w1 = front(A, "house_w_1", -4.85, -10.6, 1, 0, 151, W=5.8, D=5.0,
               pi=1, ti=1, si=1, win_front=1, firewood=False)
    w2 = front(A, "house_w_2", -4.85, -4.0, 1, 0, 152, W=5.8, D=5.0,
               pi=3, ti=3, si=1, win_front=1, firewood=False)
    e1 = front(A, "house_e_1", 4.55, -10.4, -1, 0, 153, W=5.6, D=4.9,
               pi=2, ti=2, si=0, win_side=0, win_front=1, firewood=False)
    inn = front(A, "inn", 3.55, -3.2, -1, 0, 154, W=6.4, D=5.6,
                pi=0, ti=2, si=2, nF=2)
    link(A, "w_1_2", w1, w2)
    link(A, "e_1_inn", e1, inn)

    # ---- branch houses ---------------------------------------------------
    def branch_house(key, pts, t, side, seed, W, D, **kw):
        p0, p1 = pts[0], pts[-1]
        ux, uy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        nx, ny = (-uy, uy * 0 - ux * 0 - uy, 0)[0:2] if False else \
            ((-uy, ux) if side > 0 else (uy, -ux))
        ex = p0[0] + ux * L * t + nx * 2.2
        ey = p0[1] + uy * L * t + ny * 2.2
        return front(A, key, ex, ey, -nx, -ny, seed, W=W, D=D, **kw)

    b1 = branch_house("branch_nw_1", nw, 0.46, -1, 161, 5.8, 5.0,
                      pi=4, ti=3, si=3, win_front=1, firewood=False)
    b2 = branch_house("branch_nw_2", nw, 0.80, -1, 162, 5.6, 4.9,
                      pi=5, ti=1, si=0, win_front=1, firewood=False)
    b3 = branch_house("branch_nw_3", nw, 0.66, 1, 163, 5.4, 4.8,
                      pi=2, ti=2, si=2, win_front=1, firewood=False)
    link(A, "nw_1_2", b1, b2)
    b4 = branch_house("branch_ne_1", ne, 0.48, 1, 171, 5.8, 5.0,
                      pi=0, ti=3, si=1, win_front=1, firewood=False)
    b5 = branch_house("branch_ne_2", ne, 0.82, 1, 172, 5.6, 4.9,
                      pi=1, ti=2, si=0, win_front=1, firewood=False)
    b6 = branch_house("branch_ne_3", ne, 0.68, -1, 173, 5.4, 4.8,
                      pi=3, ti=1, si=3, win_front=1, firewood=False)
    link(A, "ne_1_2", b4, b5)

    # ---- barn + side plots ----------------------------------------------
    A.add("barn", barn("barn", T_at(-16.8, -6.4, 0, rz=-math.pi * 0.42),
                       W=10.0, D=7.0, ti=1))
    A.add("barn_yard", apron("barn_yard", T_at(-11.6, -9.6, 0, rz=0.03),
                             5.2, 7.0, mat=M["earth"], z=0.0022))
    A.add("barn_cart", medbuild.cart("barn_cart", T_at(-11.4, -6.6, 0, rz=2.1),
                                     rng=random.Random(9)))
    prop_cluster(A, "barn_props", -19.8, -1.8, 43, barrels=2, crates=2, sacks=1)
    A.add("barn_hay", haystack("barn_hay", T_at(-20.6, -8.6, 0),
                               r=1.5, h=2.1, rng=random.Random(25)))
    A.add("barn_laundry", fk.laundry("barn_laundry", T_at(-11.0, -1.6, 0,
                                                          rz=0.9), L=3.2))

    kitchen_garden(A, "g_e", 10.2, -6.6, 6.0, 5.0, 75, gate_side="w")
    pasture_plot(A, "p_e", 16.0, 2.4, 6.4, 7.0, seed=36, gate_side="w")
    kitchen_garden(A, "g_w", -9.8, -17.4, 6.2, 4.6, 76, gate_side="e")
    pasture_plot(A, "p_nw", -14.6, 6.0, 6.6, 6.4, seed=37, gate_side="e")
    A.add("p_nw_hay", haystack("p_nw_hay", T_at(-15.6, 7.2, 0), r=1.3, h=1.9,
                               rng=random.Random(27)))
    pasture_plot(A, "p_sw", -8.4, -21.6, 5.4, 4.2, seed=39, gate_side="n")
    A.add("p_sw_hay", haystack("p_sw_hay", T_at(-9.6, -21.2, 0), r=1.25, h=1.8,
                               rng=random.Random(28)))
    pasture_plot(A, "p_se", 9.2, -20.4, 6.0, 4.6, seed=38, gate_side="n")
    A.add("p_se_wood", woodpile("p_se_wood", T_at(11.4, -21.8, 0, rz=1.5),
                                w=2.0, rows=3))

    # ---- street furniture ------------------------------------------------
    A.add("notice", notice_board("notice", T_at(-3.4, 1.6, 0, rz=1.2)))
    A.add("stall", fk.stall("stall", T_at(4.2, 3.4, 0, rz=1.9), w=2.7, d=2.0))
    A.add("lanterns", fk.lantern_post("lan1", T_at(-2.9, -5.6, 0))
          + fk.lantern_post("lan2", T_at(2.9, 1.4, 0, rz=math.pi)))

    # ---- village edge ----------------------------------------------------
    ring = [(2.8, -29.8), (8.0, -29.0), (18.0, -21.0), (23.5, -8.0),
            (24.0, 3.0), (20.0, 13.0), (12.0, 21.0), (0.0, 24.0),
            (-12.0, 20.0), (-20.0, 13.0), (-23.0, 2.0), (-21.0, -10.0),
            (-17.0, -19.0), (-12.0, -24.0), (-6.6, -29.0), (-2.2, -29.8)]
    wall_run(A, "edge", ring, h=1.30, t=0.52)
    corner_posts(A, "edge", ring, 1.30, 0.52)

    # ---- gate, avenue, fields -------------------------------------------
    village_gate(A, "gate", 0.2, -29.8, w=5.6, h=3.40)
    tree_at(A, "avenue_w", -3.9, -38.6, 8.4, 51, "broad")
    tree_at(A, "avenue_e", 4.3, -38.6, 8.6, 52, "broad")
    tree_at(A, "tree_back1", -8.0, -20.6, 9.0, 156, "poplar")
    tree_at(A, "tree_back2", 11.4, -12.6, 9.4, 156, "broad")
    tree_at(A, "tree_back3", -12.6, 16.4, 9.6, 157, "broad")
    hedge(A, "hedge_w", (-2.6, -15.1), (-6.7, -15.1), 63, r=0.66)

    field_plot(A, "field_wheat", -14.2, -35.0, 15.0, 12.0, open_side="e", seed=81)
    wall_run(A, "field_wall_w", [(-6.6, -29.0), (-6.6, -33.85)])
    wall_run(A, "field_wall_w2", [(-6.6, -36.75), (-6.6, -41.0)])
    field_plot(A, "field_veg", 14.2, -35.0, 13.0, 12.0, open_side="w", seed=82,
               crop="veggie")
    wall_run(A, "field_wall_e", [(8.0, -29.0), (8.0, -33.85)])
    wall_run(A, "field_wall_e2", [(8.0, -36.75), (8.0, -41.0)])
    A.add("field_gate_w", gate("field_gate_w", T_at(-6.6, -35.3, 0,
                                                   rz=math.pi * 0.5), w=2.9))
    A.add("field_gate_e", gate("field_gate_e", T_at(8.0, -35.3, 0,
                                                   rz=math.pi * 0.5), w=2.9))
    CK["walls"].append(("gate", (-6.6, -33.85), (-6.6, -36.75)))
    CK["walls"].append(("gate", (8.0, -33.85), (8.0, -36.75)))

    A.add("paths", CK["paths"])


# ---------------------------------------------------------------- driver
VARIANTS = {
    "farm_a": dict(layout=layout_a, cam=(38.0, -104.0, 86.0), target=(0.0, -8.0, 1.5),
                   lens=42.0, sun=(50.0, 0.0, 34.0), cam2=(11.0, -28.0, 17.0),
                   target2=(0.0, 1.0, 2.4), lens2=46.0),
    "farm_b": dict(layout=layout_b, cam=(8.0, -110.0, 90.0), target=(-2.0, -5.0, 1.5),
                   lens=42.0, sun=(52.0, 0.0, 26.0), cam2=(12.0, -22.0, 17.0),
                   target2=(0.0, 10.0, 2.4), lens2=46.0),
    "farm_c": dict(layout=layout_c, cam=(62.0, -98.0, 90.0), target=(2.0, -9.0, 1.5),
                   lens=43.0, sun=(48.0, 0.0, 40.0), cam2=(9.0, -24.0, 17.0),
                   target2=(0.0, 8.0, 2.4), lens2=46.0),
}


def dedupe_materials(objs):
    """mat_gold()/mat_glass() are created per call, so slots end up as
    gold.001, gold.002 ... Remap every suffixed duplicate onto one material."""
    import re
    canon = {}
    for m in bpy.data.materials:
        root = re.sub(r"\.\d{3}$", "", m.name)
        if root != m.name and bpy.data.materials.get(root) is not None:
            canon[m.name] = root
    for ob in objs:
        for slot in ob.material_slots:
            m = slot.material
            if m and m.name in canon:
                slot.material = bpy.data.materials[canon[m.name]]
    for name in list(canon):
        m = bpy.data.materials.get(name)
        if m and m.users == 0:
            bpy.data.materials.remove(m)


def build(key, do_render=True, detail_render=True):
    cfg = VARIANTS[key]
    medkit.reset_scene()
    medkit._MAT_CACHE.clear()
    fk.init_materials()

    A = Assemblies()
    cfg["layout"](A)
    layout_check(key)
    objs = join_groups(A, key)
    dedupe_materials(objs)

    stats = scene_stats(objs)
    faces = sum(len(o.data.polygons) for o in objs)
    gt = {}
    for o in objs:
        o.data.calc_loop_triangles()
        gt[o.name] = len(o.data.loop_triangles)
    heavy = [(k, v) for k, v in sorted(gt.items(), key=lambda kv: -kv[1])
             if not k.startswith(key + "_house")][:16]
    print("GROUPSTATS " + json.dumps(heavy))
    print("FARMSTATS " + json.dumps(dict(variant=key, objects=stats["objects"],
                                         tris=stats["tris"], faces=faces,
                                         materials=stats["materials"],
                                         bbox=stats["bbox"],
                                         mats=stats["mat_names"])))

    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    fbx = os.path.join(EXPORT_DIR, key + ".fbx")
    export_fbx(fbx)
    print("EXPORT", fbx)

    # ---- render rig (built after export so it never lands in the FBX)
    clear_lights_cameras()
    setup_render()
    add_lights(sun_rot=cfg["sun"])
    add_ground(460.0)
    setup_camera(cfg["cam"], cfg["target"], cfg["lens"])
    if do_render:
        render_to(os.path.join(RENDER_DIR, key + ".png"))
    if detail_render:
        setup_camera(cfg["cam2"], cfg["target2"], cfg["lens2"])
        render_to(os.path.join(RENDER_DIR, key + "_detail.png"))
        # the three judging shots: in-game camera, eye level, and the approach
        setup_camera((0.0, -13.5, 17.3), (0.0, 0.5, 0.0), 40.0)
        render_to(os.path.join(RENDER_DIR, key + "_player.png"))
        setup_camera((2.2, -9.0, 1.7), (0.0, 3.5, 2.2), 35.0)
        render_to(os.path.join(RENDER_DIR, key + "_eye.png"))
        setup_camera(cfg.get("gatecam", (0.2, -45.2, 1.72)),
                     cfg.get("gatetarget", (0.3, -10.0, 3.0)), 35.0)
        render_to(os.path.join(RENDER_DIR, key + "_gate.png"))

    blend = os.path.join(KING, key + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("BLEND", blend)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    key = "farm_a"
    do_render = True
    for i, a in enumerate(argv):
        if a.startswith("--variant"):
            key = a.split("=")[1] if "=" in a else argv[i + 1]
        if a == "--no-render":
            do_render = False
    build(key, do_render=do_render)


if __name__ == "__main__":
    main()

