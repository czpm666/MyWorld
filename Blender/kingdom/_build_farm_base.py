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
                      lane_strip, apron, path_to_door, tufts, simple_tree)

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
    parts = []
    for i in range(n):
        ang = r.uniform(-0.20, 0.20)
        ww = w * r.uniform(0.70, 1.0)
        dd = d * r.uniform(0.70, 1.0)
        ox = r.uniform(-0.13, 0.13) * w
        oy = r.uniform(-0.13, 0.13) * d
        parts.append(apron("%s_%d" % (key, i),
                           T_at(cx + ox, cy + oy, 0, rz=ang),
                           ww, dd, mat=mat, z=0.0005 - i * 0.0008))
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
    is fed TexCoord.Object, each object sampled a different patch of noise — the
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

    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 2.2
    n1.inputs["Detail"].default_value = 2.4
    n1.inputs["Roughness"].default_value = 0.62
    nt.links.new(mp.outputs["Vector"], n1.inputs["Vector"])

    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 0.30
    n2.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs["Vector"], n2.inputs["Vector"])

    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position = 0.28
    els[0].color = medkit.c("#40592a")
    e = els.new(0.55)
    e.color = medkit.c("#5f7d38")
    e = els.new(0.78)
    e.color = medkit.c("#8aa154")
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


# ---------------------------------------------------------------- layouts
def house_row(A, prefix, specs, base_seed):
    """specs: list of (x, y, rz, kwargs-dict).

    Every house gets a seeded variation pass so a row never reads as a stamped
    asset: off-grid rotation of 2-6 degrees, roof-tile tint jitter, independent
    plaster / shutter tints, small plan-size jitter and - where the plot allows -
    the gable turned to face the lane instead of the eave.
    """
    for i, (x, y, rz, kw) in enumerate(specs):
        r = random.Random(base_seed * 977 + i * 131)
        k = dict(pi=r.randrange(6), ti=r.randrange(4), si=r.randrange(4),
                 rng=random.Random(base_seed + i))
        if i % 3 == 2:                       # gable-on house
            k["ridge_along_front"] = False
        k.update(kw)
        k["W"] = round(k.get("W", 6.2) + r.uniform(-0.45, 0.45), 2)
        k["D"] = round(k.get("D", 5.0) + r.uniform(-0.35, 0.35), 2)
        jr = math.radians(r.uniform(2.0, 6.0)) * (1 if r.random() < 0.5 else -1)
        A.add("%s_%d" % (prefix, i), farmhouse("%s_%d" % (prefix, i),
                                               T_at(x, y, 0, rz=rz + jr), **k))


def doorstep(A, key, p0, p1, w=1.35):
    A.add(key, slab_between(key, p0, p1, w, M["cobble"], z=-0.001))


def field_fence(A, key, cx, cy, w, d, gate_side="e", seed=0):
    """Fence around a field, one gate."""
    gy = cy
    if gate_side == "e":
        A.add(key + "_fe1", fence_run(key + "_fe1",
                                      T_at(cx + w * 0.5 + 0.45, gy - d * 0.22, 0,
                                           rz=math.pi * 0.5), d * 0.52))
        A.add(key + "_fe2", fence_run(key + "_fe2",
                                      T_at(cx + w * 0.5 + 0.45, gy + d * 0.22, 0,
                                           rz=math.pi * 0.5), d * 0.52))
        A.add(key + "_gate", gate(key + "_gate",
                                  T_at(cx + w * 0.5 + 0.45, gy, 0, rz=math.pi * 0.5),
                                  w=2.9))
    A.add(key + "_fn", fence_run(key + "_fn",
                                 T_at(cx, cy + d * 0.5 + 0.45, 0), w + 0.9))
    A.add(key + "_fw", fence_run(key + "_fw",
                                 T_at(cx - w * 0.5 - 0.45, cy, 0, rz=math.pi * 0.5),
                                 d + 0.9))


# ------------------------------------------------------------------ farm_a
def layout_a(A):
    """Crossroads hamlet: N-S lane with an E-W spur east, nine cottages in two
    rows, barns closing the north and south ends, mill on the east shoulder."""
    rng = random.Random(4101)

    # --- lanes and the junction ---------------------------------------
    lane_road(A, "lane_ns", [(0, -46), (0.9, -20), (0.2, -6),
                             (0.2, 6), (-0.7, 20), (0, 46)], 6.6, seed=11,
              skip=[(0, 0.4, 8.6)])
    lane_road(A, "lane_ew", [(0.2, 0), (22, 1.1), (48, 0.2)], 5.4, seed=12,
              skip=[(0, 0.4, 8.6)])
    A.add("junction", apron_cluster("junction", 0, 0.4, 12.4, 10.2, seed=7))
    A.add("rut_n1", cart_ruts("rut_n1", T_at(0, -26, 0, rz=math.pi * 0.5), 30.0))
    A.add("rut_n2", cart_ruts("rut_n2", T_at(0, 24, 0, rz=math.pi * 0.5), 26.0))
    A.add("rut_e", cart_ruts("rut_e", T_at(30, 0, 0), 26.0))
    A.add("well_step", apron("well_step", T_at(-5.8, 4.2, 0), 4.8, 4.8))

    # --- centre of the village ----------------------------------------
    A.add("well", well("well", T_at(-5.8, 4.2, 0, rz=math.radians(24.0)), r=0.95))
    A.add("banner", banner("banner", T_at(4.7, 5.0, 0, rz=math.radians(-16.0))))
    A.add("notice", notice_board("notice", T_at(6.3, -4.2, 0, rz=math.pi * 0.5)))
    A.add("trough", trough("trough", T_at(-3.4, 7.6, 0, rz=math.radians(74.0))))
    prop_cluster(A, "props_well", -3.0, 1.4, 61, barrels=2, sacks=1)

    # --- cottages: west row faces east, east row faces west ------------
    west = [(-9.3, -32.0, -math.pi * 0.5, dict(nF=1, W=6.2, D=5.0)),
            (-9.3, -21.5, -math.pi * 0.5, dict(nF=2, W=5.8, D=4.8, dormers=1)),
            (-9.3, 13.5, -math.pi * 0.5, dict(nF=1, W=6.4, D=5.2, lean_to=2.4)),
            (-9.3, 25.0, -math.pi * 0.5, dict(nF=1, W=5.6, D=4.8,
                                              stone_ground=True))]
    east = [(9.5, -34.5, math.pi * 0.5, dict(nF=1, W=6.4, D=5.0)),
            (9.5, -23.5, math.pi * 0.5, dict(nF=1, W=5.8, D=4.6)),
            (9.5, 11.5, math.pi * 0.5, dict(nF=2, W=6.2, D=5.2, dormers=2)),
            (9.5, 23.0, math.pi * 0.5, dict(nF=1, W=6.0, D=5.0)),
            (9.5, 34.0, math.pi * 0.5, dict(nF=1, W=5.8, D=4.8,
                                            corner="quoin"))]
    house_row(A, "house_w", west, 1100)
    house_row(A, "house_e", east, 1200)
    for i, (hx, hy) in enumerate([(-9.3, -32.0), (-9.3, -21.5), (-9.3, 13.5),
                                  (-9.3, 25.0), (9.5, -34.5), (9.5, -23.5),
                                  (9.5, 11.5), (9.5, 23.0), (9.5, 34.0)]):
        sx = 1.0 if hx < 0 else -1.0
        doorstep(A, "step_%d" % i, (hx + sx * 2.9, hy), (hx + sx * 3.9, hy))

    # --- barns ---------------------------------------------------------
    A.add("barn_a", barn("barn_a", T_at(-21.6, 28.0, 0, rz=-math.pi * 0.5),
                         W=11.0, D=7.6, ti=None, rng=random.Random(1300)))
    A.add("barn_b", barn("barn_b", T_at(16.5, -30.0, 0, rz=math.pi * 0.5),
                         W=10.0, D=7.2, ti=None, rng=random.Random(1301)))
    A.add("yard_a", apron("yard_a", T_at(-16.4, 24.0, 0), 6.0, 11.0))
    A.add("yard_b", apron("yard_b", T_at(11.0, -30.0, 0), 5.5, 10.0))
    for i, (wx, wy) in enumerate([(-16.6, 20.4), (11.4, -26.6)]):
        A.add("woodpile_%d" % i, woodpile("woodpile_%d" % i, T_at(wx, wy, 0,
                                                                 rz=math.radians(90 * i)),
                                          w=2.6, rows=4))
    prop_cluster(A, "props_barn_a", -17.2, 33.0, 64, barrels=2, crates=2)
    prop_cluster(A, "props_barn_b", 12.0, -35.0, 65, crates=2, sacks=2)

    # --- windmill ------------------------------------------------------
    A.add("windmill", windmill("windmill", T_at(28.0, 22.0, 0, rz=-3.06)))
    A.add("mill_yard", apron("mill_yard", T_at(24.6, 18.0, 0), 7.0, 4.6,
                             rot=math.radians(-50)))
    prop_cluster(A, "props_mill", 25.4, 16.6, 66, sacks=2, barrels=1)

    # --- fields --------------------------------------------------------
    A.add("wheat", wheat_field("wheat", T_at(-33, -18, 0), 24.0, 24.0,
                                     rng=random.Random(71), spacing=0.92))
    A.add("veg_soil", apron("veg_soil", T_at(33, -11, 0), 20.6, 16.6,
                            mat=M["earth"], z=0.0))
    A.add("veg", veg_rows("veg", T_at(33, -11, 0), 20.0, 16.0, M["crop_cabbage"],
                          M["crop_green"], rng=random.Random(72), spacing=0.98))
    for i, (mx, my) in enumerate([(-36.0, 8.6), (-28.0, 13.4), (-33.0, 15.4)]):
        A.add("hay%d" % i, haystack("hay%d" % i, T_at(mx, my, 0, rz=rng.uniform(0, TAU)),
                                    r=1.45 + 0.1 * i, h=2.1 + 0.12 * i,
                                    rng=random.Random(80 + i)))
    A.add("scarecrow", scarecrow("scarecrow", T_at(-24.5, -24.0, 0,
                                                   rz=math.radians(35.0))))
    field_fence(A, "fence_wheat", -33, -18, 24, 24, gate_side="e")
    field_fence(A, "fence_veg", 33, -11, 20, 16, gate_side="w")
    A.add("meadow_fence", fence_run("meadow_fence",
                                    T_at(-31, 17.9, 0), 20.0))

    # --- kitchen gardens / orchard / hedges -----------------------------
    garden(A, "garden_w1", -16.0, -32.0, 7.2, 5.4, 401, rot=0.0)
    garden(A, "garden_e1", 16.6, 11.5, 7.4, 5.6, 402, rot=math.pi)
    garden(A, "garden_w2", -15.6, -11.6, 7.0, 5.2, 407, rot=0.0)
    garden(A, "garden_w3", -15.2, 5.4, 6.8, 5.0, 408, rot=0.0)
    garden(A, "garden_e2", 17.0, -13.4, 7.2, 5.4, 409, rot=math.pi)
    garden(A, "garden_e3", 17.4, 19.6, 6.8, 5.0, 410, rot=math.pi)
    orchard(A, "orchard", -33.0, 28.0, 2, 2, 5.0, 5.4, 510, 4.6, 5.8)
    orchard(A, "woodlot", 31.0, 36.0, 2, 2, 5.6, 6.0, 514, 6.4, 8.4)
    hedge_row(A, "hedge_veg", (21.2, -20.0), (21.2, -2.0), 511, step=1.7)
    hedge_row(A, "hedge_n", (-46.0, 6.0), (-40.0, -2.0), 512, step=1.8, r=0.82)
    hedge_row(A, "hedge_sw", (-40.0, -38.0), (-24.0, -38.0), 518, step=1.8)
    hedge_row(A, "hedge_se", (24.0, 5.0), (40.0, 5.0), 519, step=1.8)
    paddock(A, "paddock_e", 16.6, 1.0, 7.4, 9.0, 421, rot=0.0)
    paddock(A, "paddock_s", -17.0, -41.0, 8.0, 7.0, 422, rot=0.0)
    paddock(A, "paddock_se", 31.0, -31.0, 10.0, 8.0, 423, rot=0.0, hay=2)
    # plot boundaries behind the two house rows
    for i, (bx, y0, y1) in enumerate([(-13.7, -38.0, -15.0), (-13.7, 9.0, 35.0),
                                      (13.9, -40.0, -15.0), (13.9, 4.0, 38.0)]):
        A.add("bnd_%d" % i, fence_run("bnd_%d" % i,
                                      T_at(bx, (y0 + y1) * 0.5, 0,
                                           rz=math.pi * 0.5), y1 - y0))
    for i, (fy0, fy1) in enumerate([(-24.0, -18.0)]):
        A.add("verge_fence_w%d" % i, fence_run(
            "verge_fence_w%d" % i, T_at(-14.0, (fy0 + fy1) * 0.5, 0,
                                        rz=math.pi * 0.5), fy1 - fy0))

    # --- street furniture ----------------------------------------------
    A.add("cart", medbuild.cart("cart", T_at(2.2, -16.0, 0, rz=math.radians(94.0)),
                                L=2.2, Wd=1.2, rng=random.Random(91)))
    for i, (lx, ly) in enumerate([(-4.6, -6.2), (4.6, 6.6), (-4.6, 18.0),
                                  (4.6, -20.0), (-4.6, 31.0)]):
        A.add("lantern%d" % i, lantern_post("lantern%d" % i, T_at(lx, ly, 0),
                                            h=2.5))

    # --- trees ----------------------------------------------------------
    trees = [(-14.0, -40.5, 9.8, "broad"), (14.0, -42.0, 10.4, "broad"),
             (-15.0, 36.5, 10.0, "broad"), (16.0, 40.5, 8.6, "poplar"),
             (-50.0, -6.0, 9.6, "broad"), (44.0, -22.0, 10.8, "broad"),
             (20.5, 4.0, 7.4, "broad"), (-46.0, 24.0, 9.2, "poplar"),
             (40.0, 12.0, 8.0, "broad"), (-22.0, -40.0, 8.8, "broad"),
             (6.0, -42.5, 9.4, "broad"), (-38.0, 38.0, 10.2, "broad")]
    for i, (tx, ty, th, sp) in enumerate(trees):
        tree_at(A, "tree%d" % i, tx, ty, th, 200 + i, sp)
    bushes = [(-6.6, -11.0, 0.52), (6.6, -9.0, 0.5), (-6.6, 2.0, 0.46),
              (6.6, 29.0, 0.5), (-6.6, -26.0, 0.48), (18.5, -8.0, 0.44),
              (-12.5, 6.0, 0.42), (12.0, 17.0, 0.46)]
    for i, (bx, by, br) in enumerate(bushes):
        bush_at(A, "bush%d" % i, bx, by, br, 300 + i)
    boundary_ditch(A, "bditch", -52, 44, -45, 43)


# ------------------------------------------------------------------ farm_b
def layout_b(A):
    """Linear street village: one long E-W street, a green with well, shrine,
    banner at the heart, barns flanking it, windmill closing the north view."""
    rng = random.Random(4102)

    lane_road(A, "lane_main", [(-44, 0.4), (-18, 1.7), (6, -1.3), (44, 0.3)], 6.6, seed=3)
    A.add("rut_e", cart_ruts("rut_e", T_at(26, 0, 0), 34.0))
    A.add("rut_w", cart_ruts("rut_w", T_at(-26, 0, 0), 34.0))
    A.add("well_step", apron("well_step", T_at(0, 12.4, 0), 4.6, 4.6))

    A.add("well", well("well", T_at(0, 12.4, 0, rz=0.35), r=0.95))
    A.add("shrine", shrine("shrine", T_at(9.0, 17.6, 0, rz=math.radians(-118.0))))
    A.add("notice", notice_board("notice", T_at(-8.0, 7.4, 0, rz=math.pi)))
    A.add("banner", banner("banner", T_at(-13.0, 6.6, 0, rz=math.radians(10.0))))
    A.add("trough", trough("trough", T_at(3.0, 16.2, 0, rz=0.08)))
    prop_cluster(A, "props_green", 2.2, 9.4, 67, barrels=2, sacks=2)
    A.add("cart", medbuild.cart("cart", T_at(-16.0, 3.4, 0, rz=math.radians(6.0)),
                                L=2.2, Wd=1.2, rng=random.Random(92)))

    south = [(-38.0, -9.0, 0.0, dict(nF=1, W=6.2, D=5.0)),
             (-27.0, -9.0, 0.0, dict(nF=1, W=5.8, D=4.8)),
             (-16.0, -9.2, 0.0, dict(nF=2, W=6.2, D=5.2, dormers=1)),
             (16.0, -9.2, 0.0, dict(nF=1, W=6.4, D=5.0, lean_to=2.4)),
             (27.0, -9.0, 0.0, dict(nF=1, W=5.8, D=4.6, stone_ground=True)),
             (38.0, -9.0, 0.0, dict(nF=1, W=6.2, D=5.0))]
    north = [(-42.0, 9.0, math.pi, dict(nF=1, W=5.8, D=4.8)),
             (-22.0, 9.2, math.pi, dict(nF=1, W=6.2, D=5.0)),
             (22.0, 9.2, math.pi, dict(nF=2, W=6.0, D=5.0, dormers=2)),
             (42.0, 9.0, math.pi, dict(nF=1, W=5.6, D=4.8, corner="quoin"))]
    house_row(A, "house_s", south, 1400)
    house_row(A, "house_n", north, 1500)
    for i, (hx, hy, rz) in enumerate([(x, y, z) for x, y, z, _ in south + north]):
        sy = 1.0 if hy < 0 else -1.0
        doorstep(A, "step_%d" % i, (hx, hy + sy * 2.9), (hx, hy + sy * 4.1))

    A.add("barn_e", barn("barn_e", T_at(32.0, 15.0, 0, rz=math.pi * 0.5),
                         W=10.4, D=7.2, ti=None, rng=random.Random(1600)))
    A.add("barn_w", barn("barn_w", T_at(-32.0, 15.0, 0, rz=-math.pi * 0.5),
                         W=10.0, D=7.0, ti=None, rng=random.Random(1601)))
    A.add("yard_e", apron("yard_e", T_at(27.0, 11.0, 0), 5.5, 10.0))
    A.add("yard_w", apron("yard_w", T_at(-27.0, 11.0, 0), 5.5, 10.0))
    A.add("woodpile_0", woodpile("woodpile_0", T_at(35.4, 9.6, 0, rz=math.radians(90)),
                                 w=2.6, rows=4))
    A.add("woodpile_1", woodpile("woodpile_1", T_at(-35.2, 9.6, 0, rz=math.radians(90)),
                                 w=2.4, rows=3))
    prop_cluster(A, "props_barn_e", 26.4, 18.6, 68, crates=2, sacks=2)
    prop_cluster(A, "props_barn_w", -26.6, 18.4, 69, barrels=2, crates=1)

    A.add("windmill", windmill("windmill", T_at(0, 30.5, 0, rz=math.pi)))
    A.add("mill_yard", apron("mill_yard", T_at(0, 25.4, 0), 8.0, 4.0))
    prop_cluster(A, "props_mill", -3.2, 26.0, 70, sacks=2)

    A.add("wheat", wheat_field("wheat", T_at(34, 34, 0), 24.0, 18.0,
                                     rng=random.Random(73), spacing=0.94))
    A.add("veg_soil", apron("veg_soil", T_at(-34, -30, 0), 24.6, 18.6,
                            mat=M["earth"], z=0.0))
    A.add("veg", veg_rows("veg", T_at(-34, -30, 0), 24.0, 18.0, M["crop_cabbage"],
                          M["crop_green"], rng=random.Random(74), spacing=0.98))
    for i, (mx, my) in enumerate([(27.5, -25.0), (35.0, -30.0), (31.0, -33.0)]):
        A.add("hay%d" % i, haystack("hay%d" % i, T_at(mx, my, 0, rz=rng.uniform(0, TAU)),
                                    r=1.4 + 0.1 * i, h=2.05 + 0.12 * i,
                                    rng=random.Random(180 + i)))
    A.add("scarecrow", scarecrow("scarecrow", T_at(-24.0, -33.0, 0,
                                                   rz=math.radians(-25.0))))
    field_fence(A, "fence_wheat", 34, 34, 24, 18, gate_side="w")
    field_fence(A, "fence_veg", -34, -30, 24, 18, gate_side="e")
    A.add("meadow_fence", fence_run("meadow_fence", T_at(32, -20.9, 0), 18.0))

    garden(A, "garden_s1", -16.0, -16.0, 7.2, 5.2, 403, rot=0.0)
    garden(A, "garden_n1", 16.4, -16.0, 7.4, 5.4, 404, rot=0.0)
    orchard(A, "orchard", -34.0, 27.0, 2, 2, 5.2, 5.6, 520, 4.6, 5.8)
    orchard(A, "woodlot", 12.0, -32.0, 2, 2, 5.4, 6.0, 522, 6.4, 8.2)
    hedge_row(A, "hedge_wheat", (21.4, 25.0), (21.4, 43.0), 513, step=1.7)
    hedge_row(A, "hedge_veg", (-46.4, -21.0), (-46.4, -39.0), 514, step=1.7)
    paddock(A, "paddock_nw", -46.0, 31.0, 8.0, 8.0, 431, rot=0.0)
    paddock(A, "paddock_s", 1.0, -27.0, 9.0, 8.0, 432, rot=0.0, hay=2)
    paddock(A, "paddock_e", 27.0, 33.0, 8.0, 7.0, 433, rot=0.0)
    for i, (by, x0, x1) in enumerate([(13.4, -47.0, -10.0), (13.4, 10.0, 47.0),
                                      (-13.4, -47.0, -10.0), (-13.4, 10.0, 47.0)]):
        A.add("bnd_%d" % i, fence_run("bnd_%d" % i,
                                      T_at((x0 + x1) * 0.5, by, 0), x1 - x0))

    for i, (lx, ly) in enumerate([(-24.0, 4.6), (-40.0, 4.6), (0.0, 4.6),
                                  (24.0, 4.6), (40.0, 4.6)]):
        A.add("lantern%d" % i, lantern_post("lantern%d" % i, T_at(lx, ly, 0),
                                            h=2.5))

    trees = [(-49.0, 22.0, 9.8, "broad"), (-49.0, -22.0, 10.2, "broad"),
             (49.0, 24.0, 9.6, "broad"), (49.0, -20.0, 10.8, "broad"),
             (-20.0, 33.0, 10.0, "broad"), (20.0, 36.0, 9.4, "poplar"),
             (-44.0, 38.0, 10.4, "broad"), (44.0, 40.0, 9.2, "broad"),
             (-6.0, 40.0, 8.8, "broad"), (6.0, -40.0, 9.6, "broad"),
             (-46.0, -6.0, 8.0, "broad"), (46.0, 6.0, 8.4, "broad")]
    for i, (tx, ty, th, sp) in enumerate(trees):
        tree_at(A, "tree%d" % i, tx, ty, th, 210 + i, sp)
    bushes = [(-6.5, -4.6, 0.5), (6.5, -4.6, 0.48), (-16.0, 4.4, 0.46),
              (16.0, 4.4, 0.44), (-44.0, 0.0, 0.5), (44.0, 0.0, 0.5),
              (-19.4, 21.0, 0.46), (19.4, 21.0, 0.46)]
    for i, (bx, by, br) in enumerate(bushes):
        bush_at(A, "bush%d" % i, bx, by, br, 310 + i)
    boundary_ditch(A, "bditch", -52, 52, -43, 44)


# ------------------------------------------------------------------ farm_c
def layout_c(A):
    """Forked lane: the road splits around a wooded island holding the well and
    a wayside shrine; cottages line both branches, mill on the west shoulder."""
    rng = random.Random(4103)

    lane_road(A, "lane_main", [(0, -41), (0.9, -24), (-0.7, -6), (0, 4.6)], 6.6,
              seed=4, skip=[(0, 4.6, 7.4)])
    A.add("fork", apron_cluster("fork", 0, 4.6, 11.0, 8.4, seed=11))
    lane_road(A, "lane_nw", [(0.0, 4.0), (-14.0, 17.0), (-30.0, 32.0)], 5.8, seed=5,
              skip=[(0, 4.6, 7.4)])
    lane_road(A, "lane_ne", [(0.0, 4.0), (14.0, 15.0), (30.0, 28.0)], 5.8, seed=6,
              skip=[(0, 4.6, 7.4)])
    A.add("rut_s", cart_ruts("rut_s", T_at(0, -30, 0, rz=math.pi * 0.5), 26.0))
    A.add("rut_n", cart_ruts("rut_n", T_at(0, -10, 0, rz=math.pi * 0.5), 18.0))

    A.add("well_step", apron("well_step", T_at(0.5, 15.4, 0), 4.6, 4.6))
    A.add("well", well("well", T_at(0.5, 15.4, 0, rz=0.42), r=0.95))
    A.add("shrine", shrine("shrine", T_at(3.4, 20.6, 0, rz=math.radians(160.0))))
    A.add("banner", banner("banner", T_at(-4.6, 8.2, 0, rz=math.radians(-28.0))))
    A.add("notice", notice_board("notice", T_at(-5.6, -1.4, 0, rz=math.radians(-70.0))))
    prop_cluster(A, "props_well", 4.4, 11.6, 71, barrels=2, sacks=1)

    west = [(-9.4, -30.0, -math.pi * 0.5, dict(nF=1, W=6.2, D=5.0)),
            (-9.4, -19.0, -math.pi * 0.5, dict(nF=2, W=5.8, D=4.8, dormers=1))]
    east = [(9.6, -33.0, math.pi * 0.5, dict(nF=1, W=6.2, D=5.0)),
            (9.6, -22.0, math.pi * 0.5, dict(nF=1, W=5.8, D=4.6)),
            (9.6, -11.0, math.pi * 0.5, dict(nF=1, W=6.4, D=5.0, lean_to=2.4))]
    house_row(A, "house_w", west, 1700)
    house_row(A, "house_e", east, 1800)
    for i, (hx, hy) in enumerate([(-9.4, -30.0), (-9.4, -19.0), (9.6, -33.0),
                                  (9.6, -22.0), (9.6, -11.0)]):
        sx = 1.0 if hx < 0 else -1.0
        doorstep(A, "step_%d" % i, (hx + sx * 2.9, hy), (hx + sx * 3.9, hy))

    # cottages on the two branches
    ne_specs = [(14.0, 19.5, math.radians(-128.0), dict(nF=1, W=6.0, D=4.8)),
                (21.6, 24.4, math.radians(-128.0), dict(nF=2, W=6.2, D=5.0,
                                                        dormers=1))]
    nw_specs = [(-14.6, 18.6, math.radians(128.0), dict(nF=1, W=6.2, D=4.8)),
                (-22.4, 24.6, math.radians(128.0), dict(nF=1, W=5.8, D=4.6,
                                                        corner="quoin"))]
    house_row(A, "house_ne", ne_specs, 1900)
    house_row(A, "house_nw", nw_specs, 2000)
    for i, (hx, hy, rz, _) in enumerate(ne_specs + nw_specs):
        ox, oy = -math.sin(rz), math.cos(rz)
        doorstep(A, "bstep_%d" % i, (hx - ox * 2.9, hy - oy * 2.9),
                 (hx - ox * 4.0, hy - oy * 4.0))

    A.add("barn", barn("barn", T_at(22.0, 11.0, 0, rz=math.pi * 0.5),
                       W=10.4, D=7.2, ti=None, rng=random.Random(2100)))
    A.add("yard_barn", apron("yard_barn", T_at(16.6, 8.0, 0), 5.5, 9.0))
    A.add("woodpile_0", woodpile("woodpile_0", T_at(25.6, 4.6, 0, rz=math.radians(90)),
                                 w=2.6, rows=4))
    prop_cluster(A, "props_barn", 16.4, 13.0, 72, crates=2, sacks=2)

    A.add("windmill", windmill("windmill", T_at(-24.0, 22.0, 0, rz=-2.52)))
    A.add("mill_yard", apron("mill_yard", T_at(-20.6, 18.4, 0), 6.5, 4.4,
                             rot=math.radians(-40)))
    prop_cluster(A, "props_mill", -20.0, 16.6, 73, sacks=2)

    A.add("wheat", wheat_field("wheat", T_at(-33, -20, 0), 24.0, 24.0,
                                     rng=random.Random(75), spacing=0.94))
    A.add("veg_soil", apron("veg_soil", T_at(36, -7, 0), 20.6, 22.6,
                            mat=M["earth"], z=0.0))
    A.add("veg", veg_rows("veg", T_at(36, -7, 0), 20.0, 22.0, M["crop_cabbage"],
                          M["crop_green"], rng=random.Random(76), spacing=0.98))
    for i, (mx, my) in enumerate([(-34.5, 3.4), (-28.0, 8.6)]):
        A.add("hay%d" % i, haystack("hay%d" % i, T_at(mx, my, 0, rz=rng.uniform(0, TAU)),
                                    r=1.45 + 0.1 * i, h=2.1 + 0.12 * i,
                                    rng=random.Random(280 + i)))
    A.add("scarecrow", scarecrow("scarecrow", T_at(-24.5, -26.0, 0,
                                                   rz=math.radians(50.0))))
    field_fence(A, "fence_wheat", -33, -20, 24, 24, gate_side="e")
    field_fence(A, "fence_veg", 36, -7, 20, 22, gate_side="w")
    A.add("meadow_fence", fence_run("meadow_fence", T_at(-31, 12.1, 0), 16.0))

    garden(A, "garden_e1", 16.6, -33.0, 7.2, 5.4, 405, rot=math.pi)
    garden(A, "garden_ne", 27.0, 20.0, 6.6, 5.0, 406, rot=math.radians(-38.0))
    orchard(A, "orchard", 30.0, 36.0, 2, 2, 5.4, 5.6, 540, 4.6, 5.8)
    hedge_row(A, "hedge_veg", (24.4, -18.0), (24.4, 2.0), 515, step=1.7)
    hedge_row(A, "hedge_sw", (-46.0, -6.0), (-46.0, -34.0), 516, step=1.7)
    hedge_row(A, "hedge_island", (-7.0, 10.6), (7.0, 10.6), 517, step=1.5, r=0.68)
    paddock(A, "paddock_e", 17.0, -40.0, 8.0, 7.0, 441, rot=0.0)
    paddock(A, "paddock_w", -16.5, -10.0, 7.5, 7.0, 442, rot=0.0)
    paddock(A, "paddock_nw", -40.0, 22.0, 8.0, 8.0, 443, rot=0.0, hay=2)
    paddock(A, "paddock_se", 34.0, -34.0, 9.0, 8.0, 444, rot=0.0)
    for i, (bx, y0, y1) in enumerate([(-13.8, -36.0, -6.0), (14.0, -37.0, -5.0)]):
        A.add("bnd_%d" % i, fence_run("bnd_%d" % i,
                                      T_at(bx, (y0 + y1) * 0.5, 0,
                                           rz=math.pi * 0.5), y1 - y0))

    A.add("cart", medbuild.cart("cart", T_at(2.4, -25.0, 0, rz=math.radians(96.0)),
                                L=2.2, Wd=1.2, rng=random.Random(93)))
    for i, (lx, ly) in enumerate([(-4.6, -6.0), (4.6, -14.0), (-4.6, -24.0),
                                  (4.6, 6.0), (-12.0, 12.0), (13.0, 12.0)]):
        A.add("lantern%d" % i, lantern_post("lantern%d" % i, T_at(lx, ly, 0),
                                            h=2.5))

    trees = [(-14.0, -40.0, 9.8, "broad"), (14.0, -41.0, 10.4, "broad"),
             (-30.0, 38.0, 10.0, "poplar"), (30.0, 26.0, 9.2, "broad"),
             (-44.0, 12.0, 10.2, "broad"), (44.0, -30.0, 10.8, "broad"),
             (-40.0, -40.0, 9.6, "broad"), (44.0, 14.0, 8.8, "broad"),
             (-6.0, 26.0, 7.4, "broad"), (7.5, 25.0, 7.0, "broad"),
             (-34.0, -6.0, 8.6, "broad"), (20.0, 30.0, 8.0, "broad")]
    for i, (tx, ty, th, sp) in enumerate(trees):
        tree_at(A, "tree%d" % i, tx, ty, th, 220 + i, sp)
    bushes = [(-6.6, -8.0, 0.5), (6.6, -28.0, 0.48), (-6.6, 2.6, 0.46),
              (6.6, 2.6, 0.44), (-14.5, 6.0, 0.46), (14.0, 4.0, 0.46),
              (-27.0, 14.0, 0.44), (27.0, 6.0, 0.46)]
    for i, (bx, by, br) in enumerate(bushes):
        bush_at(A, "bush%d" % i, bx, by, br, 320 + i)
    boundary_ditch(A, "bditch", -48, 48, -44, 44)


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
