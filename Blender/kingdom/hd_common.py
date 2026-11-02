"""hd_common.py - high-detail architectural toolkit for the Asura capital.

Everything here is parametric and repeatable: building scripts call these
functions and never hand-place vertices.  Units are metres, Blender Z-up,
local +Y is the FRONT of a building (the side that faces the street).

The toolkit is deliberately dependency-light: it only needs medkit (primitives
and materials) plus bpy/mathutils.  Rendering lives in `render_preview`, which
sets up a neutral sky, a sun and three cameras and writes PNGs to
`Blender/renders/kingdom/`.

Usage from a build module:

    import hd_common as H
    parts = []
    parts += H.window_arched(H.Ts(0, 5.0, 4.0), 1.4, 2.6, MAT["stone"], MAT["glass"])
    ...
    H.apply(parts, H.Ts(cx, cy, z0))          # move a finished block into place
    H.render_preview("castle", parts, size=(4.0, 4.0))
"""

import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (_HERE, _PARENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy
from mathutils import Matrix, Vector

import medkit as K
from medkit import T_at, box, cyl, cone, sphere, mat_stone, mat_wood, mat_tile

Ts = T_at

OUT_DIR = r"E:\My World\Blender\renders\kingdom"
MAT_CACHE = {}


# --------------------------------------------------------------------------
# generic mesh helpers
# --------------------------------------------------------------------------
def poly(name, verts, faces, mat, T=None):
    """Arbitrary mesh from absolute verts/faces, optionally transformed."""
    if T is not None:
        verts = [T @ Vector(v) for v in verts]
    ob = K.mesh_obj(name, [tuple(v) for v in verts], faces)
    if mat is not None:
        K.assign(ob, mat)
    return ob


def lathe(name, profile, mat, seg=32, T=None, close_bottom=True, close_top=True,
          smooth=True):
    """Revolve a [(radius, z), ...] profile around local Z."""
    verts, faces = [], []
    n = len(profile)
    for i in range(seg):
        a = 2.0 * math.pi * i / seg
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in profile:
            verts.append((r * ca, r * sa, z))
    for i in range(seg):
        i2 = (i + 1) % seg
        for j in range(n - 1):
            a0 = i * n + j
            a1 = i * n + j + 1
            b0 = i2 * n + j
            b1 = i2 * n + j + 1
            faces.append((a0, b0, b1, a1))
    if close_bottom and profile[0][0] > 1e-4:
        base = len(verts)
        verts.append((0.0, 0.0, profile[0][1]))
        for i in range(seg):
            faces.append((base, (i + 1) % seg * n, i * n))
    if close_top and profile[-1][0] > 1e-4:
        top = len(verts)
        verts.append((0.0, 0.0, profile[-1][1]))
        for i in range(seg):
            faces.append((top, i * n + n - 1, ((i + 1) % seg) * n + n - 1))
    ob = poly(name, verts, faces, mat, T)
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def prism(name, T, pts, depth, mat, axis="y"):
    """Extrude a 2D polygon (list of (u, v)) by depth along `axis`."""
    n = len(pts)
    h = depth * 0.5
    verts = []
    for s in (-h, h):
        for (u, v) in pts:
            if axis == "y":
                verts.append((u, s, v))
            elif axis == "x":
                verts.append((s, u, v))
            else:
                verts.append((u, v, s))
    faces = []
    for i in range(n):
        i2 = (i + 1) % n
        faces.append((i, i2, n + i2, n + i))
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range(n, 2 * n)))
    return poly(name, verts, faces, mat, T)


def wedge(name, T, w, h, d, mat):
    """Triangular gable block: base w x d, ridge along Y at height h."""
    hw, hd = w * 0.5, d * 0.5
    verts = [(-hw, -hd, 0), (hw, -hd, 0), (0, -hd, h),
             (-hw, hd, 0), (hw, hd, 0), (0, hd, h)]
    faces = [(0, 3, 5, 2), (2, 5, 4, 1), (0, 1, 4, 3), (0, 2, 1), (3, 4, 5)]
    return poly(name, verts, faces, mat, T)


def apply(parts, T):
    """Move a finished block of objects by matrix T (bakes into mesh data)."""
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        ob.data.transform(T @ ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
    return parts


def bbox(parts):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        for v in ob.data.vertices:
            p = ob.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    return lo, hi


def tri_count(parts):
    n = 0
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        for p in ob.data.polygons:
            n += max(1, len(p.vertices) - 2)
    return n


# --------------------------------------------------------------------------
# masonry
# --------------------------------------------------------------------------
def crenel(name, T, length, merlon=0.9, gap=0.55, h=1.35, depth=0.55, mat=None,
           parapet=0.0, parapet_h=0.0):
    """Battlement row along local X, sitting on z=0."""
    mat = mat or mat_stone()
    out = []
    if parapet_h > 0:
        out.append(box(name + "_par", T @ Ts(0, 0, parapet_h * 0.5),
                       (length, parapet, parapet_h), mat, bev=0.02))
    pitch = merlon + gap
    n = max(1, int(length / pitch))
    total = n * pitch - gap
    x0 = -total * 0.5 + merlon * 0.5
    for i in range(n):
        out.append(box(name + "_m%d" % i, T @ Ts(x0 + i * pitch, 0, h * 0.5),
                       (merlon, depth, h), mat, bev=0.025))
        # a chamfered cap makes the merlon read as cut stone, not a box
        out.append(box(name + "_c%d" % i, T @ Ts(x0 + i * pitch, 0, h + 0.05),
                       (merlon + 0.10, depth + 0.10, 0.10), mat, bev=0.03))
    return out


def machicolation(name, T, length, mat=None, corbels=None, h=1.1, depth=0.9):
    """Corbelled overhang carrying a battlement - the 'murder hole' gallery."""
    mat = mat or mat_stone()
    out = []
    n = max(2, int(length / 1.05))
    for i in range(n):
        x = -length * 0.5 + (i + 0.5) * length / n
        out.append(box(name + "_cb%d" % i, T @ Ts(x, 0, -0.55),
                       (0.42, depth * 0.9, 1.05), mat, bev=0.03))
        out.append(box(name + "_cc%d" % i, T @ Ts(x, 0, -1.02),
                       (0.30, depth * 0.7, 0.28), mat, bev=0.02))
    out.append(box(name + "_gal", T @ Ts(0, 0, 0.05), (length, depth, h), mat, bev=0.02))
    out += crenel(name + "_cr", T @ Ts(0, 0, h * 0.5), length, mat=mat, depth=depth * 0.9)
    return out


def wall_course(name, T, length, thickness, height, mat, course_h=0.42, step=0.03):
    """Wall with visible horizontal courses (alternating slightly proud stones)."""
    out = [box(name + "_core", T @ Ts(0, 0, height * 0.5), (length, thickness, height), mat)]
    n = max(1, int(height / course_h))
    for i in range(n):
        z = course_h * (i + 0.5)
        sign = 1 if i % 2 == 0 else -1
        out.append(box(name + "_c%d" % i, T @ Ts(0, sign * step, z),
                       (length + 0.015, thickness + 0.035, course_h * 0.90), mat,
                       bev=0.012))
    return out


def quoin(name, T, h, size=0.55, mat=None):
    """Corner stones running up an edge."""
    mat = mat or mat_stone()
    out = []
    n = max(2, int(h / 0.48))
    for i in range(n):
        big = (i % 2 == 0)
        s = size if big else size * 0.72
        out.append(box(name + "_q%d" % i, T @ Ts(0, 0, (i + 0.5) * h / n),
                       (s, s, h / n * 0.92), mat, bev=0.02))
    return out


# --------------------------------------------------------------------------
# openings
# --------------------------------------------------------------------------
def window_arched(name, T, w, h, frame_mat, glass_mat, tracery=2, sill=True,
                  hood=False, shutters=None, depth=0.42, dark_mat=None,
                  arch=True):
    """Recessed opening: dark reveal, glass, stone surround, mullions, hood."""
    out = []
    dk = dark_mat or glass_mat
    hw = w * 0.5
    out.append(box(name + "_back", T @ Ts(0, -depth * 0.5, h * 0.5),
                   (w, depth, h), dk))
    # stone surround
    jamb = 0.30
    for s in (-1, 1):
        out.append(box(name + "_j%d" % s, T @ Ts(s * (hw + jamb * 0.5), 0, h * 0.5),
                       (jamb, depth + 0.10, h + jamb), frame_mat, bev=0.02))
    out.append(box(name + "_sill", T @ Ts(0, 0.05, -0.06), (w + jamb * 2.4, depth + 0.34, 0.16),
                   frame_mat, bev=0.02))
    if sill:
        out.append(box(name + "_slope", T @ Ts(0, 0.16, -0.16), (w + jamb * 2.0, 0.30, 0.10),
                       frame_mat, bev=0.015))
    # glass panes + lead cames
    ncol = max(1, tracery)
    for i in range(ncol):
        x = (i + 0.5) * w / ncol - hw
        out.append(box(name + "_g%d" % i, T @ Ts(x, -depth * 0.34, h * 0.5),
                       (w / ncol * 0.94, 0.05, h * 0.94), glass_mat))
    for i in range(1, ncol):
        x = i * w / ncol - hw
        out.append(box(name + "_m%d" % i, T @ Ts(x, -depth * 0.18, h * 0.5),
                       (0.055, 0.12, h), frame_mat, bev=0.008))
    for k in range(max(2, int(h / 1.1))):
        z = (k + 0.5) * h / max(2, int(h / 1.1))
        out.append(box(name + "_tr%d" % k, T @ Ts(0, -depth * 0.20, z),
                       (w, 0.09, 0.045), frame_mat))
    if arch:
        # two-centred arch head made of voussoirs
        r = hw + jamb * 0.5
        n = 9
        for i in range(n):
            a = math.pi * (i + 0.5) / n
            x = -math.cos(a) * r
            z = h + math.sin(a) * r
            out.append(box(name + "_v%d" % i, T @ Ts(x, 0, z),
                           (r * math.pi / n * 1.05, depth + 0.10, 0.34), frame_mat,
                           bev=0.015))
        out.append(box(name + "_fill", T @ Ts(0, -depth * 0.35, h + r * 0.35),
                       (w * 0.94, 0.06, r * 0.62), glass_mat))
        if hood:
            out.append(box(name + "_hood", T @ Ts(0, 0.18, h + r + 0.18),
                           (w + jamb * 3.2, 0.34, 0.22), frame_mat, bev=0.02))
    if shutters is not None:
        for s in (-1, 1):
            out.append(box(name + "_sh%d" % s,
                           T @ Ts(s * (hw + jamb + 0.12), 0.16, h * 0.5),
                           (0.16, 0.06, h * 0.98), shutters, bev=0.01))
    return out


def window_slit(name, T, w=0.28, h=1.25, mat=None):
    """Arrow slit with a splayed inner reveal."""
    mat = mat or mat_stone()
    out = [box(name + "_s", T @ Ts(0, 0, h * 0.5), (w, 0.30, h), mat, bev=0.01)]
    out.append(box(name + "_d", T @ Ts(0, -0.16, h * 0.5), (w * 0.45, 0.10, h * 0.9),
                   K.mat_metal("void", "#0d0d10", 0.9)))
    return out


def rose_window(name, T, r, stone, glass, lobes=12, depth=0.55, seg=36):
    """Wheel window: stone ring, spoke tracery, coloured glass behind."""
    out = []
    out.append(cyl(name + "_glass", T @ Ts(0, -depth * 0.55, 0), r * 0.96, 0.06, glass, seg=seg))
    # ring
    out.append(lathe(name + "_ring", [(r, -depth * 0.5), (r, depth * 0.5),
                                      (r * 1.16, depth * 0.5), (r * 1.16, -depth * 0.5)],
                     stone, seg=seg, T=T @ Ts(0, 0, 0)))
    # spokes
    for i in range(lobes):
        a = 2 * math.pi * i / lobes
        out.append(box(name + "_sp%d" % i,
                       T @ Ts(math.cos(a) * r * 0.5, 0.0, math.sin(a) * r * 0.5,
                              ry=-a) if False else T @ Ts(0, 0, 0),
                       (r, 0.30, 0.26), stone))
    # spokes were placed with a rotation about Y; rebuild properly below
    for i in range(lobes):
        a = 2 * math.pi * (i + 0.5) / lobes
        M = T @ Matrix.Translation(Vector((math.cos(a) * r * 0.5, 0.06,
                                           math.sin(a) * r * 0.5))) @ \
            Matrix.Rotation(-a, 4, "Y")
        out.append(box(name + "_spk%d" % i, M, (r * 0.98, 0.22, 0.26), stone, bev=0.01))
    # inner hub + outer lobes
    out.append(cyl(name + "_hub", T @ Ts(0, 0.10, 0), r * 0.16, 0.30, stone, seg=16))
    for i in range(lobes * 2):
        a = 2 * math.pi * i / (lobes * 2)
        out.append(cyl(name + "_lb%d" % i,
                       T @ Ts(math.cos(a) * r * 0.80, 0.10, math.sin(a) * r * 0.80),
                       r * 0.11, 0.28, stone, seg=10))
    return out


def door_arched(name, T, w, h, wood, iron, stone=None, steps=0, double=True):
    """Planked door in an arched stone surround, optional steps."""
    out = []
    stone = stone or mat_stone()
    r = w * 0.5
    out.append(box(name + "_rec", T @ Ts(0, -0.35, h * 0.5), (w, 0.5, h), wood))
    n = 6 if double else 4
    for i in range(n + 1):
        x = -w * 0.5 + w * i / n
        out.append(box(name + "_pl%d" % i, T @ Ts(x, -0.10, h * 0.5),
                       (0.03, 0.05, h * 0.98), iron))
    for k in range(3):
        z = h * (0.22 + 0.28 * k)
        out.append(box(name + "_bd%d" % k, T @ Ts(0, -0.08, z), (w * 0.96, 0.06, 0.10), iron))
    out.append(cyl(name + "_knob", T @ Ts(w * 0.30, -0.04, h * 0.46), 0.07, 0.14, iron, seg=10))
    # arch surround
    jamb = 0.34
    for s in (-1, 1):
        out.append(box(name + "_j%d" % s, T @ Ts(s * (r + jamb * 0.5), 0, h * 0.5),
                       (jamb, 0.75, h), stone, bev=0.02))
    for i in range(11):
        a = math.pi * (i + 0.5) / 11
        x = -math.cos(a) * (r + jamb * 0.5)
        z = h + math.sin(a) * (r + jamb * 0.5)
        out.append(box(name + "_v%d" % i, T @ Ts(x, 0, z),
                       ((r + jamb) * math.pi / 11 * 1.05, 0.78, 0.40), stone, bev=0.02))
    out.append(box(name + "_tymp", T @ Ts(0, -0.30, h + r * 0.42), (w * 0.96, 0.08, r * 0.8), wood))
    for s in (-1, 1):
        out.append(box(name + "_post%d" % s, T @ Ts(s * (r + jamb + 0.22), 0.10, h * 0.5),
                       (0.22, 0.22, h), stone))
    for i in range(steps):
        out.append(box(name + "_st%d" % i, T @ Ts(0, 0.55 + i * 0.34, 0.09 + i * 0.0),
                       (w + 1.4, 0.34, 0.18 + 0.0), stone, bev=0.015))
    return out


# --------------------------------------------------------------------------
# towers, roofs, spires
# --------------------------------------------------------------------------
def round_tower(name, T, r, h, stone, roof_mat=None, cap="cone", cone_h=None,
                corbel_out=0.55, slit_rows=3, mat_band=None):
    """Cylindrical tower: plinth, shaft, corbelled head, crenellation or cone."""
    out = []
    out.append(cyl(name + "_plinth", T @ Ts(0, 0, 0.55), r * 1.10, 1.1, stone, seg=32))
    out.append(cyl(name + "_shaft", T @ Ts(0, 0, h * 0.5 + 1.0),
                   r, h - 1.0, stone, seg=32))
    # string courses
    band = mat_band or stone
    for k in range(3):
        z = h * (0.28 + 0.22 * k)
        out.append(cyl(name + "_bc%d" % k, T @ Ts(0, 0, z), r * 1.035, 0.22, band, seg=32))
    # corbels under the head
    n = max(8, int(2 * math.pi * r / 0.9))
    for i in range(n):
        a = 2 * math.pi * i / n
        M = T @ Matrix.Translation(Vector((math.cos(a) * r * 0.98, math.sin(a) * r * 0.98,
                                           h - 0.30))) @ Matrix.Rotation(-a, 4, "Z")
        out.append(box(name + "_cb%d" % i, M, (0.22, 0.55, 0.75), stone, bev=0.02))
    # head
    hr = r + corbel_out
    out.append(cyl(name + "_head", T @ Ts(0, 0, h + 0.6), hr, 1.2, stone, seg=32))
    for a in range(slit_rows):
        z = h * (0.22 + 0.20 * a)
        for k in range(4):
            ang = 2 * math.pi * k / 4 + a * 0.5
            M = T @ Matrix.Translation(Vector((math.cos(ang) * (r + 0.02),
                                               math.sin(ang) * (r + 0.02), z))) @ \
                Matrix.Rotation(math.atan2(math.sin(ang), math.cos(ang)) - math.pi * 0.5, 4, "Z")
            out += window_slit(name + "_sl%d_%d" % (a, k), M, mat=stone)
    if cap == "cone":
        ch = cone_h or hr * 2.4
        out.append(cone(name + "_cone", T @ Ts(0, 0, h + 1.2), hr * 1.06, ch,
                        roof_mat or mat_tile(), seg=32))
        out.append(cyl(name + "_finial", T @ Ts(0, 0, h + 1.2 + ch), 0.10, 1.4, mat_band or stone))
        out.append(sphere(name + "_ball", T @ Ts(0, 0, h + 1.2 + ch + 1.4), 0.22, mat_band or stone))
    else:
        out += crenel(name + "_cr", T @ Ts(0, 0, h + 1.2), 2 * math.pi * hr * 0.98,
                      mat=stone, depth=0.5)
    return out


def spire(name, T, r, h, mat, seg=8, base_z=0.0):
    """Octagonal spire with a slight concave curve and a finial."""
    prof = []
    steps = 6
    for i in range(steps + 1):
        t = i / steps
        rr = r * (1.0 - t) ** 0.92
        prof.append((max(0.03, rr), base_z + h * t))
    out = [lathe(name + "_body", prof, mat, seg=seg, T=T)]
    out.append(cyl(name + "_ring", T @ Ts(0, 0, base_z + 0.2), r * 1.06, 0.4, mat, seg=seg))
    # crockets up the edges
    for i in range(4):
        t = 0.18 + 0.18 * i
        rr = r * (1.0 - t) * 0.85
        for k in range(4):
            a = math.pi * 0.5 * k
            out.append(box(name + "_cr%d_%d" % (i, k),
                           T @ Ts(math.cos(a) * rr, math.sin(a) * rr, base_z + h * t),
                           (0.20, 0.20, 0.34), mat, bev=0.02))
    out.append(cyl(name + "_fin", T @ Ts(0, 0, base_z + h + 0.7), 0.07, 1.4, mat, seg=8))
    return out


def pinnacle(name, T, w, h, mat):
    base = w
    out = [box(name + "_b", T @ Ts(0, 0, 0.35), (base, base, 0.7), mat, bev=0.02)]
    out.append(lathe(name + "_t", [(w * 0.62, 0.7), (w * 0.42, h * 0.55),
                                   (w * 0.10, h)], mat, seg=4,
                     T=T @ Matrix.Rotation(math.pi * 0.25, 4, "Z")))
    return out


def buttress(name, T, h, depth, stages=3, mat=None):
    """Stepped buttress against a wall face (+Y), with an offset cap each stage."""
    mat = mat or mat_stone()
    out = []
    d = depth
    for s in range(stages):
        z0 = h * s / stages
        z1 = h * (s + 1) / stages
        out.append(box(name + "_s%d" % s, T @ Ts(0, d * 0.5, (z0 + z1) * 0.5),
                       (0.9 - 0.16 * s, d, z1 - z0), mat, bev=0.02))
        out.append(box(name + "_cap%d" % s, T @ Ts(0, d * 0.5 + 0.04, z1),
                       (1.0 - 0.16 * s, d + 0.12, 0.22), mat, bev=0.03))
        d *= 0.72
    out.append(pinnacle(name + "_pin", T @ Ts(0, depth * 0.3, h), 0.7, 2.2, mat))
    return out


def flying_buttress(name, T, span, h, mat, rise=2.4):
    """A quarter-arc flyer from a pier to the clerestory."""
    out = []
    n = 8
    for i in range(n):
        t0 = i / n
        t1 = (i + 1) / n
        y0 = span * t0
        y1 = span * t1
        z0 = h + rise * math.sin(math.pi * 0.5 * t0)
        z1 = h + rise * math.sin(math.pi * 0.5 * t1)
        L = math.hypot(y1 - y0, z1 - z0)
        ang = math.atan2(z1 - z0, y1 - y0)
        out.append(box(name + "_f%d" % i,
                       T @ Ts(0, (y0 + y1) * 0.5, (z0 + z1) * 0.5, rz=0, ry=-ang),
                       (0.75, L * 1.06, 0.55), mat, bev=0.02))
    return out


def roof(name, T, w, d, eave_z, pitch, tile_mat, deck_mat, courses=True,
         course_h=0.34, verge=0.45, ridge=True, gable_ends=True, end_mat=None,
         ov_gable=0.4):
    """Pitched roof with eave boards, tile courses and a capped ridge.

    Ridge runs along local Y; slopes face +/-X.

    GABLE-END COLOUR TRAP -- read this before calling:
    medkit.gable_roof paints its two gable-end triangles with `gable_mat` (the
    deck material) whenever `end_mat` is None.  Pass plank-dark as deck_mat on a
    plastered house and you get a chocolate #402e24 board where the wall should
    be; that exact bug cost a full review round.  Callers MUST pass
    end_mat=<wall material>.  We still allow the None case (other scenes rely on
    it) but resolve it HERE, explicitly, so the fallback is a visible decision
    instead of an accident buried in medkit.

    NOTE: courses here are one full-length slab per course, run out to the
    overhang plane -- at a gable their ends read as a fan of loose blades.  For
    anything seen closer than ~20 m use tiled_roof() below instead.
    """
    hw = w * 0.5 + verge
    rh = hw * math.tan(math.radians(pitch))
    end_m = end_mat if end_mat is not None else deck_mat
    out = [K.gable_roof(name + "_core", T, w, d, eave_z, pitch, tile_mat, deck_mat,
                        ov_side=verge, ov_gable=ov_gable, end_mat=end_m)]
    if courses:
        n = max(2, int(math.hypot(hw, rh) / course_h))
        for i in range(n):
            t = (i + 0.5) / n
            # t = 0 at the ridge, 1 at the eave: the course has to follow the
            # surface equation z = eave + rh*(1-t), otherwise the whole run
            # mirrors into a "louver" hovering rh above the tiles.
            x = hw * t
            z = eave_z + rh * (1.0 - t)
            for s in (-1, 1):
                out.append(box(name + "_tc%d_%d" % (i, s + 1),
                               T @ Ts(s * x, 0, z + 0.055, ry=s * math.radians(pitch)),
                               (0.28, d + 0.74, 0.10), tile_mat, bev=0.008))
        # ridge
        if ridge:
            out.append(box(name + "_ridge", T @ Ts(0, 0, eave_z + rh + 0.10),
                           (0.46, d + 0.95, 0.22), tile_mat, bev=0.03))
            for k in range(3):
                out.append(cyl(name + "_rc%d" % k,
                               T @ Ts(0, (k - 1) * (d + 0.8) / 3.4, eave_z + rh + 0.20),
                               0.22, 0.30, tile_mat, seg=10))
    # eave boards
    for s in (-1, 1):
        out.append(box(name + "_eb%d" % s, T @ Ts(s * hw, 0, eave_z - 0.05),
                       (0.12, d + 2.0 * ov_gable + 0.1, 0.22), deck_mat, bev=0.02))
    # barge boards on the gable edges
    rl = math.hypot(hw, rh)
    for s in (-1, 1):
        for sy in (-1, 1):
            out.append(box(name + "_bb%d_%d" % (s, sy),
                           T @ Ts(s * hw * 0.5, sy * (d * 0.5 + ov_gable + 0.02),
                                  eave_z + rh * 0.5, ry=math.atan2(-rh, -s * hw)),
                           (rl, 0.10, 0.26), deck_mat, bev=0.015))
    if gable_ends:
        for sy in (-1, 1):
            out.append(wedge(name + "_gm%d" % sy, T @ Ts(0, sy * (d * 0.5 - 0.06), eave_z),
                             w * 0.98, 0.12, rh * 0.99, deck_mat))
    return out


def tiled_roof(name, T, w, d, eave_z, pitch, tile_mat, deck_mat, courses=True,
               course_h=0.34, verge=0.45, ridge=True, gable_ends=True,
               end_mat=None, ov_gable=0.4, crest=False):
    """Same footprint as roof(), but tile courses are sunk ribs, not slabs.

    This exists because of the "louver / ladder hovering over the roof" bug that
    every viewer reported.  roof() lays each course down as ONE slab running out
    to the roof's overhang plane, so at a gable the course ends stack up as a fan
    of separated blades, and the whole run reads as venetian blinds laid on the
    slope.  Ported from hd_castle.tiled_roof (which was written for exactly this
    failure and is the version that renders clean):

      * each course is a rib `step*0.95` wide and 0.05 thick, sunk 0.028 into
        the surface and following z = eave + rh*(1 - |x|/hw), so neighbouring
        ribs meet at a shadow joint instead of a see-through slot;
      * the run stops 0.17 m short of the roof end and a 0.40 m deep rake board
        caps the ends, so no blade ends are visible past the gable;
      * the ridge is a run of separate ridge tiles over a continuous bed --
        no single slab and no cylinder stubs.

    Pass end_mat=<wall material> on any building with plaster gables (see the
    warning in roof()).
    """
    hw = w * 0.5 + verge
    rh = hw * math.tan(math.radians(pitch))
    end_m = end_mat if end_mat is not None else deck_mat
    out = [K.gable_roof(name + "_core", T, w, d, eave_z, pitch, tile_mat, deck_mat,
                        ov_side=verge, ov_gable=ov_gable, end_mat=end_m)]
    sl = math.hypot(hw, rh)
    if courses:
        n = max(2, int(sl / course_h))
        step = sl / n
        # 0.17 m tucked behind the rake board at each gable end
        run = d + 2.0 * ov_gable - 0.34
        for i in range(n):
            t = (i + 0.5) / n
            # t = 1 at the ridge, 0 at the eave: the rib has to follow the
            # surface equation, or the run mirrors into the hovering louver.
            x = hw * (1.0 - t)
            z = eave_z + rh * t
            for s in (-1, 1):
                out.append(box(name + "_tc%d_%d" % (i, s + 1),
                               T @ Ts(s * x, 0, z + 0.028, ry=s * math.radians(pitch)),
                               (step * 0.95, run, 0.05), tile_mat, bev=0.005))
    # eave fascia, then a deep rake board over the course ends.  Both are capped
    # by the slope length: on a 1 m dormer hood a fixed 0.40 m board swallows the
    # whole slope and the hood reads as a brown plank instead of tiles.
    ev_d = min(0.34, sl * 0.30)
    rb_d = min(0.40, sl * 0.22)
    for s in (-1, 1):
        out.append(box(name + "_ev%d" % (s + 1), T @ Ts(s * hw, 0, eave_z - 0.07),
                       (0.13, d + 2.0 * ov_gable, ev_d), deck_mat, bev=0.018))
        for sy in (-1, 1):
            out.append(box(name + "_rb%d_%d" % (s + 1, sy + 1),
                           T @ Ts(s * hw * 0.5, sy * (d * 0.5 + ov_gable - 0.05),
                                  eave_z + rh * 0.5,
                                  ry=math.atan2(-rh, -s * hw)),
                           (sl * (1.02 if sl > 2.0 else 0.97), 0.15, rb_d),
                           deck_mat, bev=0.018))
    if ridge and rh > 0.35:
        rlen = d + 2.0 * ov_gable
        # continuous bed first: the tiles below must never show sky at the apex
        out.append(box(name + "_rbed", T @ Ts(0, 0, eave_z + rh + 0.03),
                       (0.40, rlen, 0.10), tile_mat, bev=0.015))
        nr = max(3, int(round(rlen / 0.62)))
        seg = rlen / nr
        for k in range(nr):
            zz = eave_z + rh + 0.13 + (0.004 if k % 2 else 0.0)
            out.append(box(name + "_rt%d" % k,
                           T @ Ts(0, -rlen * 0.5 + (k + 0.5) * seg, zz),
                           (0.56, seg * 0.975, 0.14), tile_mat, bev=0.028))
        # ridge end caps sit flush with the rake boards -- no block stack
        for sy in (-1, 1):
            out.append(box(name + "_re%d" % sy,
                           T @ Ts(0, sy * (rlen * 0.5 - 0.12), eave_z + rh + 0.06),
                           (0.54, 0.24, 0.24), deck_mat, bev=0.025))
    if crest:
        nc = max(3, int(w / 1.5))
        for k in range(nc):
            x = -w * 0.5 + (k + 0.5) * w / nc
            zt = eave_z + rh * (1.0 - abs(x) / hw)
            out.append(pinnacle("%s_cr%d" % (name, k), T @ Ts(x, 0, zt + 0.2),
                                0.34, 1.15, deck_mat))
    if gable_ends:
        for sy in (-1, 1):
            out.append(wedge(name + "_gm%d" % sy, T @ Ts(0, sy * (d * 0.5 - 0.06), eave_z),
                             w * 0.98, 0.12, rh * 0.99, deck_mat))
    return out


def chimney(name, T, h, mat, pots=2):
    out = [box(name + "_b", T @ Ts(0, 0, h * 0.5), (1.1, 0.9, h), mat, bev=0.02)]
    out.append(box(name + "_cap", T @ Ts(0, 0, h + 0.06), (1.35, 1.15, 0.14), mat, bev=0.02))
    for i in range(pots):
        x = (i - (pots - 1) * 0.5) * 0.45
        out.append(cyl(name + "_p%d" % i, T @ Ts(x, 0, h + 0.3), 0.16, 0.5, mat, seg=10))
    return out


def dormer(name, T, w=1.0, h=1.15, d=0.9, pitch=50, wall=None, roof_mat=None,
           frame=None, glass=None, trim=None):
    """A gabled dormer. T must already sit ON the roof surface.

    The caller is responsible for the z: place the body so its base is ~0.2 m
    below the slope, i.e. z = eave_z + rh*(1 - |x|/hw) - 0.2.  Getting that
    wrong buries the body inside the roof and leaves only the hood poking out as
    a floating grey chevron.

    The body is deliberately 0.8 m taller than `h` and hangs below the caller's
    z, so the front face reaches down into the slope instead of ending in mid
    air: the slope drops ~0.45 across the body's own depth, and a body cut off
    at z=0 shows a lit slab of open air under the window.
    """
    wall = wall or mat_stone()
    trim = trim or mat_wood()
    # body slightly smaller than the hood so the roof overhangs all four cheeks
    out = [box(name + "_body", T @ Ts(0, 0, h * 0.5 - 0.4),
               (w * 0.92, d * 0.96, h + 0.8), wall)]
    # tiled_roof, not roof(): roof() still lays the courses as full-length slabs
    # and still puts three cylinder stubs on the ridge, which on a 1 m hood reads
    # as a row of knobs.  The dark `trim` also matters -- with the wall material
    # as the rake board the pale frame plus the slate slopes read as an empty
    # window frame lying flat on the roof.
    out += tiled_roof(name + "_r", T @ Ts(0, 0, h), w, d, 0.0, pitch, roof_mat,
                      trim, courses=False, course_h=0.30, verge=0.12,
                      ridge=True, gable_ends=True, end_mat=wall, ov_gable=0.10)
    out += window_arched(name + "_w", T @ Ts(0, d * 0.5 + 0.02, h * 0.55),
                         w * 0.58, h * 0.55, frame, glass, tracery=2, arch=False,
                         depth=0.18)
    return out


# --------------------------------------------------------------------------
# street furniture and clutter
# --------------------------------------------------------------------------
def banner(name, T, w, h, cloth_mat, pole_mat, pole_h=None):
    ph = pole_h if pole_h is not None else h + 1.2
    out = [cyl(name + "_pole", T @ Ts(0, 0, ph * 0.5), 0.10, ph, pole_mat, seg=8)]
    out.append(sphere(name + "_knob", T @ Ts(0, 0, ph + 0.12), 0.16, pole_mat))
    out.append(box(name + "_cl", T @ Ts(w * 0.5 + 0.08, 0, ph - h * 0.55),
                   (w, 0.05, h), cloth_mat, bev=0.01))
    out.append(box(name + "_bar", T @ Ts(w * 0.5 + 0.08, 0, ph - 0.10),
                   (w + 0.2, 0.07, 0.08), pole_mat))
    return out


def lantern_post(name, T, h, iron, glow):
    out = [cyl(name + "_p", T @ Ts(0, 0, h * 0.5), 0.09, h, iron, seg=10)]
    out.append(box(name + "_arm", T @ Ts(0.32, 0, h - 0.1), (0.7, 0.08, 0.08), iron))
    out.append(box(name + "_box", T @ Ts(0.62, 0, h - 0.42), (0.30, 0.30, 0.52), iron))
    out.append(box(name + "_gl", T @ Ts(0.62, 0, h - 0.42), (0.22, 0.22, 0.42), glow))
    out.append(cone(name + "_cap", T @ Ts(0.62, 0, h - 0.12), 0.26, 0.22, iron, seg=4))
    return out


def barrel(name, T, r=0.30, h=0.84, wood=None, hoop=None):
    wood = wood or mat_wood()
    hoop = hoop or K.mat_metal()
    prof = [(r * 0.92, 0), (r, h * 0.22), (r * 1.06, h * 0.5), (r, h * 0.78), (r * 0.92, h)]
    out = [lathe(name + "_body", prof, wood, seg=14, T=T)]
    for k in (0.18, 0.5, 0.82):
        out.append(cyl(name + "_h%d" % int(k * 100), T @ Ts(0, 0, h * k), r * 1.02, 0.055,
                       hoop, seg=14))
    return out


def crate(name, T, s=0.62, wood=None):
    wood = wood or mat_wood()
    out = [box(name + "_b", T @ Ts(0, 0, s * 0.5), (s, s, s), wood, bev=0.01)]
    for sy in (-1, 1):
        out.append(box(name + "_r%d" % sy, T @ Ts(0, sy * s * 0.5, s * 0.5),
                       (s * 1.02, 0.05, 0.08), wood))
    return out


def cart(name, T, wood, iron, L=2.0, W=1.1):
    out = [box(name + "_bed", T @ Ts(0, 0, 0.72), (L, W, 0.16), wood, bev=0.02)]
    for s in (-1, 1):
        out.append(box(name + "_s%d" % s, T @ Ts(0, s * (W * 0.5 - 0.04), 0.95),
                       (L, 0.07, 0.42), wood))
    for sy in (-1, 1):
        for sx in (-1, 1):
            out.append(cyl(name + "_wh%d%d" % (sy, sx),
                           T @ Ts(sx * L * 0.33, sy * (W * 0.5 + 0.06), 0.48, rx=math.pi * 0.5),
                           0.46, 0.10, wood, seg=14))
    out.append(cyl(name + "_axle", T @ Ts(0, 0, 0.48, rx=math.pi * 0.5), 0.06, W + 0.2, iron, seg=8))
    for s in (-1, 1):
        out.append(box(name + "_sh%d" % s, T @ Ts(-L * 0.5 - 0.6, s * 0.34, 0.72),
                       (1.5, 0.09, 0.09), wood))
    return out


def market_stall(name, T, w=2.4, d=1.5, wood=None, cloth=None, cloth2=None):
    wood = wood or mat_wood()
    cloth = cloth or K.mat_cloth("cloth_a", "#a8543f")
    cloth2 = cloth2 or K.mat_cloth("cloth_b", "#3f5a56")
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(cyl(name + "_p%d%d" % (sx, sy),
                           T @ Ts(sx * w * 0.42, sy * d * 0.42, 1.05), 0.055, 2.1, wood, seg=8))
    out.append(box(name + "_top", T @ Ts(0, 0, 1.02), (w, d, 0.09), wood, bev=0.01))
    # awning: two sloped sheets with a scalloped valance
    out.append(box(name + "_aw", T @ Ts(0, 0, 2.28, rx=math.radians(12)),
                   (w + 0.7, d + 0.9, 0.05), cloth))
    out.append(box(name + "_val", T @ Ts(0, d * 0.5 + 0.44, 2.08), (w + 0.7, 0.04, 0.34), cloth2))
    for i in range(7):
        x = (i - 3) * (w + 0.7) / 7
        out.append(box(name + "_sc%d" % i, T @ Ts(x, d * 0.5 + 0.44, 1.88),
                       ((w + 0.7) / 9, 0.05, 0.22), cloth, bev=0.01))
    # goods on the counter
    rng = random.Random(hash(name) & 0xFFFF)
    for i in range(4):
        x = -w * 0.34 + i * w * 0.22
        out.append(box(name + "_g%d" % i, T @ Ts(x, 0.05 + rng.uniform(-0.2, 0.2), 1.16),
                       (0.30, 0.30, 0.18), K.mat_cloth("goods_%d" % i,
                                                       rng.choice(("#b8843a", "#8e3f2f", "#5a7a44")))))
    return out


def haystack(name, T, r=1.1, h=1.4, mat=None):
    mat = mat or K.mat_earth("thatch", base="#b39a58", dark="#8a7539", scale=6)
    prof = [(r * 0.9, 0), (r, h * 0.35), (r * 0.85, h * 0.72), (r * 0.35, h), (0.02, h * 1.05)]
    return [lathe(name, prof, mat, seg=16, T=T)]


def statue(name, T, h, stone):
    """Abstract but readable figure: plinth, body, head, arm, cloak."""
    out = [box(name + "_pl", T @ Ts(0, 0, 0.4), (1.2, 1.2, 0.8), stone, bev=0.03)]
    out.append(lathe(name + "_body", [(0.42, 0.8), (0.34, h * 0.55), (0.30, h * 0.72),
                                      (0.20, h * 0.80)], stone, seg=10, T=T))
    out.append(sphere(name + "_hd", T @ Ts(0, 0, h * 0.88), 0.19, stone, seg=12, ring=8))
    out.append(box(name + "_arm", T @ Ts(0.24, 0, h * 0.74, ry=math.radians(-35)),
                   (0.14, 0.14, 0.62), stone))
    out.append(box(name + "_sw", T @ Ts(0.40, 0, h * 0.62, ry=math.radians(-20)),
                   (0.08, 0.05, 0.9), stone))
    return out


def stairs(name, T, w, steps, rise=0.18, run=0.32, mat=None):
    mat = mat or mat_stone()
    out = []
    for i in range(steps):
        out.append(box(name + "_s%d" % i, T @ Ts(0, run * (i + 0.5), rise * (steps - i) - rise * 0.5),
                       (w, run, rise * (steps - i)), mat, bev=0.012))
    return out


# --------------------------------------------------------------------------
# preview rendering
# --------------------------------------------------------------------------
def _clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _mk_mat(name, hexcol, rough=0.8, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = K.c(hexcol, 1.0)
            n.inputs["Roughness"].default_value = rough
            break
    if metal:
        for n in mat.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Metallic"].default_value = metal
                break
    return mat


def setup_world(sun_energy=4.2, sky="#9fc4e8", fill=0.0):
    """Sky + key sun.  `fill` adds a shadowless bounce sun from the far side.

    Defaults are unchanged (fill=0) so scenes that already look right keep
    looking right.  Pass fill=1.8..2.4 when the subject's face toward the
    camera is the one the key sun is behind: every +Y facade of the town set
    otherwise renders at #262b30 (shadowed plaster) and reads as a dark slab.
    """
    world = bpy.data.worlds.new("hd_world")
    world.use_nodes = True
    nt = world.node_tree
    bg = None
    for n in nt.nodes:
        if n.type == "BACKGROUND":
            bg = n
    if bg is not None:
        bg.inputs[0].default_value = K.c(sky, 1.0)
        bg.inputs[1].default_value = 1.1
    bpy.context.scene.world = world

    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = sun_energy
    sun_data.angle = math.radians(3.0)
    sun = bpy.data.objects.new("sun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(52), 0, math.radians(38))
    if fill:
        fd = bpy.data.lights.new("fill", "SUN")
        fd.energy = fill
        fd.angle = math.radians(28.0)
        fd.use_shadow = False
        fd.color = (0.70, 0.80, 1.0)
        fo = bpy.data.objects.new("fill", fd)
        bpy.context.collection.objects.link(fo)
        # lights +Y and +Z: the street side and the roof slopes
        fo.rotation_euler = (math.radians(58), 0, math.radians(198))
    return sun


def setup_engine(samples=64, res=(1400, 900), gpu=True):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    try:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "GPU" if gpu else "CPU"
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "OPTIX"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = True
        except Exception:
            pass
    except Exception:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"


def camera(name, loc, look_at, lens=50.0, ortho=None):
    cam_data = bpy.data.cameras.new(name)
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = Vector(loc)
    d = Vector(look_at) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam


def render_to(path, cam):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[hd] wrote", path, flush=True)


def diorama_floor(mat=None, size=260.0):
    mat = mat or K.mat_flag("ground", base="#8a8274", dark="#5d574c")
    return box("ground", Ts(0, 0, -0.05), (size, size, 0.1), mat)


def three_views(name, center=(0, 0, 8), size=(6, 6), dist=None, out_dir=None,
                samples=64, res=(1400, 900)):
    """Render a 3/4, a front and an aerial view of something `size` metres wide."""
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    cx, cy, cz = center
    w, d = size
    r = dist or max(w, d) * 1.25
    hz = cz
    views = [
        ("a", (r * 0.95, -r * 1.05, hz + r * 0.45), (cx, cy, cz)),
        ("b", (cx, cy - r * 1.55, hz + r * 0.12), (cx, cy, cz)),
        ("c", (cx - r * 0.35, cy - r * 0.55, hz + r * 1.35), (cx, cy, cz)),
    ]
    cams = []
    for tag, loc, tgt in views:
        cams.append((tag, camera("cam_" + tag, loc, tgt, lens=55)))
    for tag, cam in cams:
        render_to(os.path.join(out_dir, "hd_%s_%s.png" % (name, tag)), cam)
    return [c.name for _, c in cams]
