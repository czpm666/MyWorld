"""hd_house_parts.py - detail kit behind hd_houses.house().

Everything here is parametric geometry in metres, Blender Z-up, and keeps the
house convention: local +Y is the street facade, origin is the footprint
centre, z=0 is the ground.

WHY THIS MODULE EXISTS
----------------------
The original hd_houses put a shader-tiled slab on the roof and a picture frame
around each window.  At the player camera (pitch 52 deg, 34 m, vertical FOV 30
deg -> 39.5 px per metre) a 0.17 m tile row is 6.7 px and a 0.06 m sill is
2.4 px, so *only silhouette and self-shadowing survive*.  Every detail below is
therefore sized in metres and checked against that 39.5 px/m budget:

  * roof courses are real 0.36 m overlapping slabs with a 0.06 m step, tilted
    5 deg past the slope, so each course throws a shadow onto the one below.
    A flat plane with a brick texture -- what the old roof was -- reads as a
    brick WALL at this angle.  This is the single biggest win.
  * ridge is a bead of overlapping half-round tiles on a bed, not a thin strip.
  * rakes get a bargeboard deep enough to be a 4 px dark line, plus the course
    lips stop 0.13 m short of the rake so no blade ends show past the gable.
  * windows are holes in the wall (the caller cuts them) with the glass setback
    0.17 m, a projecting stone sill, a lintel, mullion + transom and optional
    shutters that open outward so their top faces catch the sun.
  * weathering is GEOMETRY (moss/lichen patches, soot smear), not a shader
    trick: capital_hd_glue.house_mats() replaces MAT["tile"] and
    MAT["plaster"] with its own medkit materials, so anything I hide in a
    custom node tree would silently vanish in the real city.  A patch carrying
    its own material survives any palette.

Object count is kept low by merging repeated boxes into one mesh (boxmesh /
cylmesh): a 40-course roof is 2 objects.
"""

import math
import random

import bpy
from mathutils import Matrix, Vector

import medkit as K

Ts = K.T_at
TAU = 2.0 * math.pi


class _Mats(object):
    """Filled by bind(); module-level because every helper needs them."""
    VOID = None
    LEAD = None
    IRON = None
    OAKDK = None
    GLOW = None


KM = _Mats


# ==========================================================================
# 0.  mesh helpers
# ==========================================================================
_BOX_V = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
          (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
_BOX_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
          (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def frame(xa, ya, za, origin):
    """4x4 matrix whose columns are the given axes (world space)."""
    m = Matrix.Identity(4)
    m[0][0], m[1][0], m[2][0] = xa[0], xa[1], xa[2]
    m[0][1], m[1][1], m[2][1] = ya[0], ya[1], ya[2]
    m[0][2], m[1][2], m[2][2] = za[0], za[1], za[2]
    m[0][3], m[1][3], m[2][3] = origin[0], origin[1], origin[2]
    return m


def boxmesh(name, specs, mat=None, bev=0.0):
    """Many boxes -> one mesh.  specs = [(matrix, (sx, sy, sz)), ...]."""
    vs, fs = [], []
    for (T, size) in specs:
        i0 = len(vs)
        sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        for (a, b, c) in _BOX_V:
            vs.append(T @ Vector((a * sx, b * sy, c * sz)))
        for f in _BOX_F:
            fs.append(tuple(i0 + k for k in f))
    ob = K.mesh_obj(name, [tuple(v) for v in vs], fs)
    if mat is not None:
        K.assign(ob, mat)
    if bev > 0:
        K.bevel(ob, bev)
    return ob


def cylmesh(name, specs, mat=None, seg=8):
    """Many cylinders -> one mesh.  specs = [(matrix, r, h), ...]."""
    vs, fs = [], []
    for (T, r, h) in specs:
        i0 = len(vs)
        hz = h * 0.5
        for z in (-hz, hz):
            for i in range(seg):
                a = TAU * i / seg
                vs.append(T @ Vector((math.cos(a) * r, math.sin(a) * r, z)))
        for i in range(seg):
            j = (i + 1) % seg
            fs.append((i0 + i, i0 + j, i0 + seg + j, i0 + seg + i))
        fs.append(tuple(i0 + k for k in range(seg - 1, -1, -1)))
        fs.append(tuple(i0 + seg + k for k in range(seg)))
    ob = K.mesh_obj(name, [tuple(v) for v in vs], fs)
    if mat is not None:
        K.assign(ob, mat)
    return ob


def patch(name, T, pts, mat, lift=0.006):
    """A flat convex n-gon in the local XY plane, lifted along local +Z."""
    vs = [T @ Vector((x, y, lift)) for (x, y) in pts]
    ob = K.mesh_obj(name, [tuple(v) for v in vs], [tuple(range(len(vs)))])
    K.assign(ob, mat)
    return ob


def blob(name, T, rx, ry, mat, n=7, jitter=0.30, rng=None, lift=0.006):
    """Irregular convex-ish patch (moss/lichen/damp), rng-stable."""
    r = rng or random
    pts = []
    for i in range(n):
        a = TAU * i / n
        k = 1.0 + r.uniform(-jitter, jitter)
        pts.append((math.cos(a) * rx * k, math.sin(a) * ry * k))
    return patch(name, T, pts, mat, lift)


def bar(name, T, p0, p1, thick, mat, wide=None, bev=0.0):
    """A box spanning p0->p1 (local coords), square or rectangular section."""
    a = Vector(p0)
    b = Vector(p1)
    d = b - a
    L = d.length
    if L < 1e-5:
        return None
    w = thick if wide is None else wide
    q = d.normalized().to_track_quat("X", "Z")
    M = Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4()
    return K.box(name, T @ M, (L, w, thick), mat, bev=bev)


def torus(name, T, R, r, mat, nseg=10, nring=5):
    """Ring in the local XY plane (for door knockers / chain links)."""
    vs, fs = [], []
    for i in range(nseg):
        a = TAU * i / nseg
        ca, sa = math.cos(a), math.sin(a)
        for j in range(nring):
            b = TAU * j / nring
            vs.append(T @ Vector(((R + r * math.cos(b)) * ca,
                                  (R + r * math.cos(b)) * sa,
                                  r * math.sin(b))))
    for i in range(nseg):
        i2 = (i + 1) % nseg
        for j in range(nring):
            j2 = (j + 1) % nring
            fs.append((i * nring + j, i2 * nring + j, i2 * nring + j2, i * nring + j2))
    ob = K.mesh_obj(name, [tuple(v) for v in vs], fs, smooth=True)
    K.assign(ob, mat)
    return ob


def slab(name, T, w, h, thick, mat, bev=0.0):
    return K.box(name, T, (w, thick, h), mat, bev=bev)


# ==========================================================================
# 1.  materials
# ==========================================================================
def _mat(name, hexcol, rough=0.8, metal=0.0):
    if name in K._MAT_CACHE:
        return K._MAT_CACHE[name]
    m, b = K._new_mat(name)
    K._put(b, ["Base Color"], K.c(hexcol))
    K._put(b, ["Roughness"], rough)
    K._put(b, ["Metallic"], metal)
    K._MAT_CACHE[name] = m
    return m


def noisy_mat(name, base, dark, scale=6.0, rough=0.88, bump=0.20, bdist=0.02,
              stretch=None):
    """Noise-mottled material on TexCoord.Object (never Generated)."""
    if name in K._MAT_CACHE:
        return K._MAT_CACHE[name]
    m, b = K._new_mat(name)
    K._put(b, ["Roughness"], rough)
    K._put(b, ["Metallic"], 0.0)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vec = tc.outputs["Object"]
    if stretch is not None:
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = stretch
        nt.links.new(vec, mp.inputs["Vector"])
        vec = mp.outputs["Vector"]
    n = K._noise(nt, scale=scale, detail=8.0, rough=0.6)
    nt.links.new(vec, n.inputs["Vector"])
    r = K._ramp(nt, [(0.28, K.c(base)), (0.66, K.c(dark)), (0.88, K.c(base))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    K._bump(nt, b, n.outputs["Fac"], strength=bump, distance=bdist)
    K._MAT_CACHE[name] = m
    return m


def house_materials():
    """The extra palette the detail kit needs.  Safe to call repeatedly."""
    return {
        "oak": K.mat_wood("hu_oak", "#3a2a1d", "#5c4330", rough=0.80, scale=17.0),
        "oak_dk": K.mat_wood("hu_oak_dk", "#241a12", "#3a2a1d", rough=0.84, scale=22.0),
        "stone": K.mat_stone("hu_stone", "#7b7264", "#484238", "#968d7e", 2.2),
        "stone_warm": K.mat_stone("hu_stone_warm", "#8c7d64", "#544a38", "#a89877", 2.6),
        "brick": K.mat_stone("hu_brick", "#8a513d", "#4d2b22", "#a2654c", 4.0),
        "glass": noisy_mat("hu_glass", "#1b242c", "#0c1216", scale=5.0, rough=0.22,
                           bump=0.05),
        "lead": _mat("hu_lead", "#3d4145", 0.48, 0.65),
        "iron": _mat("hu_iron", "#26262b", 0.55, 0.75),
        "void": _mat("hu_void", "#0b0b0c", 0.98),
        "glow": _mat("hu_glow", "#ffb44a", 0.55),
        "moss": noisy_mat("hu_moss", "#313b22", "#1c2414", scale=9.0, rough=0.97,
                          bump=0.3, bdist=0.01),
        "moss2": noisy_mat("hu_moss2", "#3d4629", "#28301c", scale=13.0, rough=0.97),
        "lichen": noisy_mat("hu_lichen", "#5c5f45", "#3a3d2c", scale=14.0, rough=0.95),
        "soot": _mat("hu_soot", "#141210", 0.96),
        "pot": _mat("hu_pot", "#8e4b34", 0.86),
        "plaster": noisy_mat("hu_plaster_grime", "#a89b85", "#7d7460", scale=3.0,
                             rough=0.92, stretch=(2.2, 2.2, 0.45)),
    }


def bind(MAT):
    """Point the helper globals at a palette and return it.

    Called once at the top of house(): the module keeps no state between
    buildings, so a palette swap (capital_hd_glue re-colours every house) is
    picked up on the next call.
    """
    g = house_materials()
    for k, v in g.items():
        MAT.setdefault(k, v)
    KM.MAT_VOID = MAT.get("void") or g["void"]
    KM.MAT_LEAD = MAT.get("lead") or g["lead"]
    KM.MAT_IRON = MAT.get("iron") or g["iron"]
    KM.MAT_OAKDK = MAT.get("oak_dk") or g["oak_dk"]
    KM.MAT_GLOW = MAT.get("glow") or g["glow"]
    MAT_MOSS["moss"] = MAT.get("moss") or g["moss"]
    MAT_MOSS["moss2"] = MAT.get("moss2") or g["moss2"]
    MAT_MOSS["lichen"] = MAT.get("lichen") or g["lichen"]
    return MAT


# ==========================================================================
# 2.  roof
# ==========================================================================
def slope_frame(s, hw, rh, eave_z, sl):
    """Frame on the slope: +X up-slope, +Y along the ridge, +Z out of the roof.

    Origin sits on the eave line at x = s*hw, z = eave_z.
    """
    d = (-s * hw / sl, 0.0, rh / sl)
    e = (0.0, 1.0, 0.0)
    n = (s * rh / sl, 0.0, hw / sl)
    return frame(d, e, n, (s * hw, 0.0, eave_z))


def roof(name, T, span, length, eave_z, pitch, tile, trim, end_mat,
         ov_v=0.42, ov_g=0.46, course=0.36, riser=0.09, mortar=None,
         ridge=True, moss=0.55, rng=None, crest=False, tiles=None):
    """Tiled gable roof.  Ridge runs along local Y, slopes face +/-X.

    Returns (parts, info).  `info["F"][s]` is the slope frame (see
    slope_frame); `info["dormer_T"](s, u, v)` returns a matrix whose local +Y
    faces DOWN-slope, ready for dormer().
    """
    r = rng or random.Random(0)
    hw = span * 0.5 + ov_v
    hd = length * 0.5 + ov_g
    rh = hw * math.tan(math.radians(pitch))
    sl = math.hypot(hw, rh)
    top_z = eave_z + rh
    out = []

    n = max(2, int(round(sl / course)))
    c = sl / n
    run = 2.0 * (hd - 0.135)
    # Course relief, honestly sized.  At the game camera (52 deg pitch, 34 m)
    # the view direction is almost perpendicular to a 50 deg slope, so the
    # TOP faces of every course are seen face-on and all shade identically -
    # a stepped course geometry is invisible there.  What does read is the
    # shadow each course lip throws down-slope onto the course below, so the
    # courses stay coplanar and a separate lip bar (0.085 x riser) sits on
    # every boundary.  That keeps the roof plane flat (a rising staircase of
    # 17 courses would lift the ridge 1.5 m) while still giving a shadow band
    # every 0.34 m, plus a hard value step from the lip material.
    cth = 0.055
    pal = list(tiles) if tiles else [tile]
    npal = len(pal)
    for s in (-1, 1):
        F = slope_frame(s, hw, rh, eave_z, sl)
        groups = {}
        lips = []
        for i in range(n):
            u = (i + 0.5) * c
            th = cth * 1.7 if i == 0 else cth      # fatter lip on the eave course
            M = T @ F @ Ts(u, 0.0, 0.012 + th * 0.5)
            groups.setdefault(i % npal, []).append((M, (c * 1.05, run, th)))
            if 0 < i <= 3:
                lips.append((T @ F @ Ts(i * c, 0.0, 0.012 + riser * 0.5),
                             (0.085, run, riser)))
        for gi in sorted(groups):
            out.append(boxmesh("%s_crs%d_%d" % (name, s + 2, gi),
                               groups[gi], pal[gi]))
        if lips:
            out.append(boxmesh("%s_lip%d" % (name, s + 2), lips, pal[0]))
        # barge / rake boards along both gable edges, deep enough (0.11) to
        # hide the course ends and to read as a dark line in the silhouette
        for sy in (-1, 1):
            M = T @ F @ Ts(sl * 0.5, sy * (hd - 0.062), 0.022)
            out.append(K.box("%s_rk%d_%d" % (name, s + 2, sy + 2), M,
                             (sl, 0.135, 0.115), trim, bev=0.008))
        # eave fascia under the overhang
        out.append(K.box("%s_fs%d" % (name, s + 2),
                         T @ Ts(s * hw, 0.0, eave_z - 0.10),
                         (0.135, 2.0 * hd, 0.24), trim, bev=0.008))
        # a shallow soffit so the overhang is not a floating knife edge from
        # a low camera (bay/facade shots sit at 26-38 deg)
        out.append(K.box("%s_sf%d" % (name, s + 2),
                         T @ Ts(s * (hw - 0.09), 0.0, eave_z - 0.205),
                         (0.20, 2.0 * hd, 0.035), trim))

    # ridge: a continuous bed plus overlapping half-round ridge tiles.  The bed
    # has to clear the top course lip or the ridge vanishes into the slope -
    # a roof with no visible ridge line reads as a folded plane, not a roof.
    # The ridge is also the roofline the player reads against the sky, so it is
    # deliberately overscaled (0.33 m of tile above the slope) and cut from the
    # darkest course shade so it separates from both slopes by value.
    rmat = pal[0] if pal else tile
    if ridge and rh > 0.4:
        rlen = 2.0 * hd - 0.02
        out.append(K.box(name + "_rbed", T @ Ts(0, 0, top_z + 0.07),
                         (0.52, rlen, 0.20), rmat))
        specs = []
        nt = max(3, int(round(rlen / 0.90)))
        seg = rlen / nt
        for k in range(nt):
            y = -rlen * 0.5 + (k + 0.5) * seg
            z = top_z + 0.20 + (0.008 if k % 2 else 0.0)
            specs.append((T @ Ts(0.0, y, z, rx=math.pi * 0.5), 0.165, seg * 1.01))
        out.append(cylmesh(name + "_rt", specs, rmat, seg=6))
        for sy in (-1, 1):
            out.append(K.box("%s_rfin%d" % (name, sy), T @ Ts(0, sy * (rlen * 0.5 + 0.01),
                             top_z + 0.03), (0.52, 0.18, 0.34), rmat, bev=0.02))

    # Moss belongs in the damp strip along the eave, as a broken band of long
    # thin streaks that merge into the shadow line.  Big isolated lozenges
    # scattered mid-slope read as green leaves lying on the roof, which is
    # worse than no moss at all.
    nm = int(5 + 7 * moss)
    for s in (-1, 1):
        F = slope_frame(s, hw, rh, eave_z, sl)
        for k in range(nm):
            u = (0.012 + 0.075 * (k % 6) / 5.0 + r.uniform(0.0, 0.015)) * sl
            v = r.uniform(-hd * 0.92, hd * 0.92)
            rx = r.uniform(0.035, 0.080)
            ry = r.uniform(0.11, 0.28)
            mv = "moss" if k % 3 else "moss2"
            # half sunk into the course lip: a raised patch reads as a leaf
            # lying on the roof, a sunken one as growth in the joint
            G = T @ F @ Ts(u, v, 0.012 + cth * 0.55)
            out.append(blob("%s_ms%d_%d" % (name, s + 2, k), G, rx, ry,
                            MAT_MOSS[mv], n=6, jitter=0.45, rng=r, lift=0.004))
        # one lichen field higher up, sparse
        if r.random() < 0.75:
            u = r.uniform(0.45, 0.85) * sl
            v = r.uniform(-hd * 0.7, hd * 0.7)
            G = T @ F @ Ts(u, v, 0.012 + cth * 0.55)
            out.append(blob("%s_ln%d" % (name, s + 2), G, r.uniform(0.045, 0.10),
                            r.uniform(0.08, 0.18), MAT_MOSS["lichen"], n=6,
                            jitter=0.35, rng=r, lift=0.004))
        if r.random() < 0.45:
            # a lifted / slipped tile: catches light, reads as age
            u = r.uniform(0.2, 0.8) * sl
            v = r.uniform(-hd * 0.7, hd * 0.7)
            G = T @ F @ Ts(u, v, 0.012 + cth + 0.022) @ Matrix.Rotation(math.radians(r.uniform(6, 13)), 4, "Y")
            out.append(K.box("%s_brk%d" % (name, s + 2), G, (c * 0.9, 0.34, 0.028),
                             tile, bev=0.004))

    info = dict(hw=hw, hd=hd, rh=rh, sl=sl, eave_z=eave_z, top_z=top_z,
                pitch=pitch, span=span, length=length, course=c,
                F={-1: slope_frame(-1, hw, rh, eave_z, sl),
                   1: slope_frame(1, hw, rh, eave_z, sl)})

    def _dormer_T(s, u, v):
        # A dormer stands VERTICAL on the slope and its little roof is pitched
        # against the world, not against the tiles it sits on.  Squaring it to
        # the roof plane instead tips the whole hut over with the slope, and
        # its roof ends up only ~25 deg from horizontal with the ridge running
        # downhill - which is why it read as two flat wings.  So this frame is
        # world-up: +Z vertical, +Y the horizontal down-slope direction, and
        # the origin sits on the roof surface so dormer() can sink its body
        # far enough into the tiles at the front.
        F = info["F"][s]
        p = F.to_translation() + u * F.col[0].xyz + v * F.col[1].xyz
        yax = F.col[2].xyz          # roof normal: its horizontal part points
        yax.z = 0.0                 # AWAY from the ridge, i.e. down-slope
        if yax.length < 1e-5:
            yax = Vector((0.0, 1.0, 0.0))
        yax.normalize()
        zax = Vector((0.0, 0.0, 1.0))
        xax = yax.cross(zax).normalized()
        M = Matrix((xax, yax, zax)).transposed().to_4x4()
        M.translation = p
        return M          # roof-local: the caller premultiplies roof T

    info["dormer_T"] = _dormer_T
    return out, info


# filled in by hd_houses.make_mats() so roof() can weather itself
MAT_MOSS = {"moss": None, "moss2": None, "lichen": None}


def set_weather_mats(m):
    MAT_MOSS.update(m)


# ==========================================================================
# 2a. roof surface shader
# ==========================================================================
_RM_CACHE = {}


def roof_materials(src):
    """Three value steps of one roof colour, cycled course by course.

    At 34 m a 0.34 m course is 13 px and its lip shadow is about 6 px, but
    shadow alone is not enough to separate courses under a bright sun - real
    tile roofs also vary course to course because each row was fired and laid
    at a different time.  Cycling three value steps (0.86 / 1.00 / 1.12) gives
    a stable horizontal reading at every distance and costs no geometry.
    """
    return [roof_material(src, 0.86), roof_material(src, 1.00),
            roof_material(src, 1.12)]


def _mul(col, f):
    return (min(1.0, col[0] * f), min(1.0, col[1] * f),
            min(1.0, col[2] * f), 1.0)


def roof_material(src, shade=1.0):
    """Rebuild a medkit roof material so the roof stops looking like brickwork.

    medkit.mat_tile() is a ShaderNodeTexBrick (Brick Width 0.30 m, Row Height
    0.17 m, Mortar 12 mm) driven by OBJECT coordinates.  Object space is world
    aligned, so on a 44-58 deg roof those rows run horizontally across the
    slope and every roof in the city reads as a masonry wall.  At the game
    camera the roofs are 60-90 % of the frame, so this one shader is the
    dominant surface in the whole shot and it is the wrong surface.

    The real course geometry built by roof() already carries the horizontal
    reading, so this shader only has to supply the colour family plus micro
    relief.  The variant's own colour is read back out of the source brick
    node, so capital_hd_glue's eight terracotta families and three slates
    survive untouched -- this is a re-skin of the same material, not a
    replacement palette.
    """
    if src is None:
        return None
    key = "hu_roof_%s_%03d" % (src.name, int(round(shade * 100)))
    if key in _RM_CACHE:
        return _RM_CACHE[key]

    base = None
    try:
        nt = src.node_tree
        for n in nt.nodes:
            if n.bl_idname == "ShaderNodeTexBrick":
                col = n.inputs["Color1"].default_value
                base = (col[0], col[1], col[2])
                break
        if base is None:
            bs = None
            for n in nt.nodes:
                if n.bl_idname == "ShaderNodeBsdfPrincipled":
                    bs = n
                    break
            if bs is not None:
                col = bs.inputs["Base Color"].default_value
                base = (col[0], col[1], col[2])
    except Exception:
        base = None
    if base is None:
        base = (0.36, 0.13, 0.08)
    base = _mul(base, shade)

    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt2 = m.node_tree
    out = None
    for n in list(nt2.nodes):
        if n.bl_idname == "ShaderNodeOutputMaterial":
            out = n
        else:
            nt2.nodes.remove(n)
    if out is None:
        out = nt2.nodes.new("ShaderNodeOutputMaterial")
    bs = nt2.nodes.new("ShaderNodeBsdfPrincipled")
    nt2.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    if "Roughness" in bs.inputs:
        bs.inputs["Roughness"].default_value = 0.78
    if "Metallic" in bs.inputs:
        bs.inputs["Metallic"].default_value = 0.0

    tc = nt2.nodes.new("ShaderNodeTexCoord")

    # broad tonal drift: whole slopes and gables are never one flat colour
    n1 = K._noise(nt2, scale=0.60, detail=3.0, rough=0.50)
    nt2.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    r1 = K._ramp(nt2, [(0.28, _mul(base, 0.70)), (0.74, _mul(base, 1.14))])
    nt2.links.new(n1.outputs["Fac"], r1.inputs["Fac"])

    # fine mottling: individual tiles fired at slightly different temperatures
    n2 = K._noise(nt2, scale=12.0, detail=6.0, rough=0.62)
    nt2.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    r2 = K._ramp(nt2, [(0.34, _mul(base, 0.84)), (0.68, _mul(base, 1.06))])
    nt2.links.new(n2.outputs["Fac"], r2.inputs["Fac"])

    mix = nt2.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 0.55
    nt2.links.new(r1.outputs["Color"], mix.inputs["Color1"])
    nt2.links.new(r2.outputs["Color"], mix.inputs["Color2"])
    nt2.links.new(mix.outputs["Color"], bs.inputs["Base Color"])

    n3 = K._noise(nt2, scale=48.0, detail=4.0, rough=0.60)
    nt2.links.new(tc.outputs["Object"], n3.inputs["Vector"])
    K._bump(nt2, bs, n3.outputs["Fac"], strength=0.16, distance=0.010)

    # ---- slope-aligned tile courses ------------------------------------
    # This is the layer that actually carries the roof at the game camera.
    # At pitch 52 / dist 34 the view is perpendicular to a 50 deg slope, so
    # the real course lips are seen end-on and vanish; what survives is
    # shading, so the courses have to be in the shader as well as in the mesh.
    # A plain OBJECT-space brick pattern would run horizontally in world
    # space and read as masonry, which is the exact bug being fixed - so the
    # pattern is projected onto the roof's own plane: take the surface
    # normal, cross it with world up to get the ridge direction, cross that
    # back to get the down-slope direction, and use the two dot products as
    # the brick's U/V.  That is correct for any slope angle, for hips, and
    # for dormer roofs, from a single shared material.
    geo = nt2.nodes.new("ShaderNodeNewGeometry")
    upv = nt2.nodes.new("ShaderNodeCombineXYZ")
    upv.inputs["X"].default_value = 0.0
    upv.inputs["Y"].default_value = 0.0
    upv.inputs["Z"].default_value = 1.0
    crs = nt2.nodes.new("ShaderNodeVectorMath")
    crs.operation = "CROSS_PRODUCT"
    nt2.links.new(geo.outputs["Normal"], crs.inputs[0])
    nt2.links.new(upv.outputs["Vector"], crs.inputs[1])
    tnorm = nt2.nodes.new("ShaderNodeVectorMath")
    tnorm.operation = "NORMALIZE"
    nt2.links.new(crs.outputs["Vector"], tnorm.inputs[0])
    crs2 = nt2.nodes.new("ShaderNodeVectorMath")
    crs2.operation = "CROSS_PRODUCT"
    nt2.links.new(tnorm.outputs["Vector"], crs2.inputs[0])
    nt2.links.new(geo.outputs["Normal"], crs2.inputs[1])
    dnorm = nt2.nodes.new("ShaderNodeVectorMath")
    dnorm.operation = "NORMALIZE"
    nt2.links.new(crs2.outputs["Vector"], dnorm.inputs[0])
    du = nt2.nodes.new("ShaderNodeVectorMath")
    du.operation = "DOT_PRODUCT"
    nt2.links.new(tc.outputs["Object"], du.inputs[0])
    nt2.links.new(dnorm.outputs["Vector"], du.inputs[1])
    dv = nt2.nodes.new("ShaderNodeVectorMath")
    dv.operation = "DOT_PRODUCT"
    nt2.links.new(tc.outputs["Object"], dv.inputs[0])
    nt2.links.new(tnorm.outputs["Vector"], dv.inputs[1])
    comb = nt2.nodes.new("ShaderNodeCombineXYZ")
    nt2.links.new(dv.outputs["Value"], comb.inputs["X"])
    nt2.links.new(du.outputs["Value"], comb.inputs["Y"])

    # Roof tiles are NOT bricks.  A brick texture draws mortar on all four
    # sides of every cell, which is why the first attempt at this still read
    # as masonry: a roof tile only has one real shadow line, the gap under
    # the tile in the course above, and its side joints are thin and dark
    # rather than pale.  So the pattern is built from the two slope
    # coordinates directly: a deep wide band once per 0.34 m course, and a
    # faint staggered joint once per 0.26 m tile.
    def _math(op, a=None, b=None, vb=None):
        mn = nt2.nodes.new("ShaderNodeMath")
        mn.operation = op
        if a is not None:
            nt2.links.new(a, mn.inputs[0])
        if b is not None:
            nt2.links.new(b, mn.inputs[1])
        elif vb is not None:
            mn.inputs[1].default_value = vb
        return mn.outputs["Value"]

    COURSE, TWIDE = 0.34, 0.26
    ru = _math("FRACT", _math("DIVIDE", du.outputs["Value"], vb=COURSE))
    rowsh = nt2.nodes.new("ShaderNodeValToRGB")
    rowsh.color_ramp.interpolation = "EASE"
    rowsh.color_ramp.elements[0].position = 0.0
    rowsh.color_ramp.elements[0].color = (0.30, 0.28, 0.28, 1.0)
    rowsh.color_ramp.elements[1].position = 0.26
    rowsh.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    nt2.links.new(ru, rowsh.inputs["Fac"])

    rowi = _math("FLOOR", _math("DIVIDE", du.outputs["Value"], vb=COURSE))
    vs = _math("ADD", _math("DIVIDE", dv.outputs["Value"], vb=TWIDE),
               _math("MULTIPLY", rowi, vb=0.5))
    edge = _math("MULTIPLY", _math("ABSOLUTE",
                _math("SUBTRACT", _math("FRACT", vs), vb=0.5)), vb=2.0)
    colsh = nt2.nodes.new("ShaderNodeValToRGB")
    colsh.color_ramp.interpolation = "EASE"
    colsh.color_ramp.elements[0].position = 0.80
    colsh.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    colsh.color_ramp.elements[1].position = 1.0
    colsh.color_ramp.elements[1].color = (0.66, 0.66, 0.68, 1.0)
    nt2.links.new(edge, colsh.inputs["Fac"])

    m1 = nt2.nodes.new("ShaderNodeMixRGB")
    m1.blend_type = "MULTIPLY"
    m1.inputs["Fac"].default_value = 1.0
    nt2.links.new(mix.outputs["Color"], m1.inputs["Color1"])
    nt2.links.new(rowsh.outputs["Color"], m1.inputs["Color2"])
    m2 = nt2.nodes.new("ShaderNodeMixRGB")
    m2.blend_type = "MULTIPLY"
    m2.inputs["Fac"].default_value = 1.0
    nt2.links.new(m1.outputs["Color"], m2.inputs["Color1"])
    nt2.links.new(colsh.outputs["Color"], m2.inputs["Color2"])
    nt2.links.new(m2.outputs["Color"], bs.inputs["Base Color"])

    # and the same period as a real normal perturbation, so grazing light on
    # the 3/4 and eye shots breaks the plane up too
    K._bump(nt2, bs, rowsh.outputs["Color"], strength=0.34, distance=0.020)

    _RM_CACHE[key] = m
    return m


# ==========================================================================
# 2b. hip roof
# ==========================================================================
def quad_slab(name, items, mat):
    """items = [(T, [(x, y), ...], thick)] -> one mesh of extruded polygons."""
    vs, fs = [], []
    for (T, pts, th) in items:
        i0 = len(vs)
        n = len(pts)
        for (x, y) in pts:
            vs.append(T @ Vector((x, y, 0.0)))
        for (x, y) in pts:
            vs.append(T @ Vector((x, y, th)))
        fs.append(tuple(i0 + k for k in range(n - 1, -1, -1)))
        fs.append(tuple(i0 + n + k for k in range(n)))
        for k in range(n):
            j = (k + 1) % n
            fs.append((i0 + k, i0 + j, i0 + n + j, i0 + n + k))
    ob = K.mesh_obj(name, [tuple(v) for v in vs], fs)
    if mat is not None:
        K.assign(ob, mat)
    return ob


def hip_roof(name, T, span, length, eave_z, pitch, tile, trim, end_mat=None,
             ov_v=0.40, ov_g=0.40, course=0.34, riser=0.09, moss=0.35,
             rng=None, ridge=True):
    """Hipped roof: four slopes at one pitch, ridge runs along local Y.

    All four faces rise at the same angle, so the hip arrises are straight
    lines from each eave corner to a ridge end - the single strongest
    silhouette cue that separates a manor from a gabled merchant house.
    Course slabs are trapezoids, so the hip edge steps like real tiling
    instead of staircasing out of the roof.
    """
    r = rng or random.Random(0)
    hw = span * 0.5 + ov_v
    hd = length * 0.5 + ov_g
    p = math.radians(pitch)
    rh = hw * math.tan(p)
    sl = math.hypot(hw, rh)
    top_z = eave_z + rh
    hr = max(0.12, hd - hw)
    out = []
    n = max(2, int(round(sl / course)))
    c = sl / n

    def _course(items, u0, u1, half0, half1):
        items.append((Ts(0, 0, riser * 0.5),
                      [(u0, -half0), (u0, half0), (u1, half1), (u1, -half1)], riser))

    # long slopes (+/-X)
    for s in (-1, 1):
        F = slope_frame(s, hw, rh, eave_z, sl)
        items = []
        for i in range(n):
            u0, u1 = i * c, (i + 1) * c
            _course(items, u0, u1, max(0.02, hd - hw * u0 / sl),
                    max(0.02, hd - hw * u1 / sl))
        out.append(quad_slab("%s_hc%d" % (name, s + 2),
                             [(F @ it[0], it[1], it[2]) for it in items], tile))
        out.append(K.box("%s_hf%d" % (name, s + 2),
                         T @ Ts(s * hw, 0.0, eave_z - 0.10),
                         (0.135, 2.0 * hd, 0.24), trim, bev=0.008))
        out.append(K.box("%s_hs%d" % (name, s + 2),
                         T @ Ts(s * (hw - 0.09), 0.0, eave_z - 0.205),
                         (0.20, 2.0 * hd, 0.035), trim))

    # hip ends (+/-Y)
    for sy in (-1, 1):
        xa = Vector((0.0, -sy * math.cos(p), math.sin(p)))
        za = Vector((0.0, sy * math.sin(p), math.cos(p)))
        G = frame(xa, (sy * 1.0, 0.0, 0.0), za, (0.0, sy * hd, eave_z))
        items = []
        for i in range(n):
            u0, u1 = i * c, (i + 1) * c
            _course(items, u0, u1, max(0.02, hw * (1.0 - u0 / sl)),
                    max(0.02, hw * (1.0 - u1 / sl)))
        out.append(quad_slab("%s_hh%d" % (name, sy + 2),
                             [(G @ it[0], it[1], it[2]) for it in items], tile))
        out.append(K.box("%s_hhf%d" % (name, sy + 2),
                         T @ Ts(0.0, sy * hd, eave_z - 0.10),
                         (2.0 * hw, 0.135, 0.24), trim, bev=0.008))
        out.append(K.box("%s_hhs%d" % (name, sy + 2),
                         T @ Ts(0.0, sy * (hd - 0.09), eave_z - 0.205),
                         (2.0 * hw, 0.20, 0.035), trim))

    # hip arrises: a rounded tile roll along each of the four diagonals
    for sx in (-1, 1):
        for sy in (-1, 1):
            b = bar("%s_hip%d%d" % (name, sx + 2, sy + 2), T,
                    (sx * hw, sy * hd, eave_z + 0.03),
                    (0.0, sy * hr, top_z + 0.06), 0.145, trim, wide=0.17,
                    bev=0.01)
            if b is not None:
                out.append(b)

    # ridge
    if ridge and hr > 0.10:
        rlen = 2.0 * hr + 0.16
        out.append(K.box(name + "_rbed", T @ Ts(0, 0, top_z),
                         (0.40, rlen, 0.09), trim, bev=0.012))
        specs = []
        nt = max(2, int(round(rlen / 0.44)))
        seg = rlen / nt
        for k in range(nt):
            y = -rlen * 0.5 + (k + 0.5) * seg
            specs.append((T @ Ts(0.0, y, top_z + 0.10, rx=math.pi * 0.5),
                          0.118, seg * 0.99))
        out.append(cylmesh(name + "_rt", specs, tile, seg=8))
        for sy in (-1, 1):
            out.append(K.box("%s_hfin%d" % (name, sy + 2),
                             T @ Ts(0, sy * (rlen * 0.5 + 0.01), top_z + 0.02),
                             (0.44, 0.16, 0.30), trim, bev=0.02))

    # moss along the eaves
    nm = int(2 + 4 * moss)
    for s in (-1, 1):
        F = slope_frame(s, hw, rh, eave_z, sl)
        for k in range(nm):
            u = r.uniform(0.10, 0.26) * sl
            v = r.uniform(-(hd - hw * u / sl) * 0.8, (hd - hw * u / sl) * 0.8)
            rx = r.uniform(0.16, 0.36)
            ry = r.uniform(0.22, 0.55)
            out.append(blob("%s_hm%d_%d" % (name, s + 2, k), T @ F @ Ts(u, v, riser + 0.02),
                            rx, ry, MAT_MOSS["moss" if k % 3 else "moss2"], n=7,
                            jitter=0.30, rng=r, lift=0.004))

    info = dict(hw=hw, hd=hd, rh=rh, sl=sl, eave_z=eave_z, top_z=top_z,
                pitch=pitch, span=span, length=length, course=c, hr=hr, hip=True)
    return out, info


# ==========================================================================
# 3.  chimney, dormer, skylight
# ==========================================================================
def chimney(name, T, z0, z1, mat, pot, soot=None, pots=2, w=0.86, d=0.74,
            rng=None):
    """Stack from z0 (buried in the roof) to z1, corbelled cap, clay pots."""
    r = rng or random.Random(3)
    out = []
    h = z1 - z0
    zb = z0 + h * 0.34                      # where the stack leaves the roof
    out.append(K.box(name + "_gath", T @ Ts(0, 0, (z0 + zb) * 0.5),
                     (w * 1.42, d * 1.42, max(0.12, zb - z0)), mat, bev=0.014))
    out.append(K.box(name + "_sh", T @ Ts(0, 0, (zb + z1) * 0.5),
                     (w, d, z1 - zb), mat, bev=0.012))
    # corbel + cap: two projecting slabs, then the pots
    out.append(K.box(name + "_cb", T @ Ts(0, 0, z1 - 0.02),
                     (w + 0.20, d + 0.18, 0.10), mat, bev=0.014))
    out.append(K.box(name + "_cap", T @ Ts(0, 0, z1 + 0.075),
                     (w + 0.34, d + 0.30, 0.13), mat, bev=0.018))
    out.append(K.box(name + "_cap2", T @ Ts(0, 0, z1 + 0.155),
                     (w + 0.26, d + 0.22, 0.05), mat, bev=0.01))
    specs = []
    pitch_x = (w + 0.14) / max(1, pots)
    for i in range(pots):
        x = (i - (pots - 1) * 0.5) * pitch_x
        specs.append((T @ Ts(x, 0.0, z1 + 0.34), 0.108, 0.46))
    out.append(cylmesh(name + "_pot", specs, pot, seg=9))
    # dark mouths so the pots are not solid discs
    for i in range(pots):
        x = (i - (pots - 1) * 0.5) * pitch_x
        out.append(K.cyl(name + "_mouth%d" % i, T @ Ts(x, 0.0, z1 + 0.545),
                         0.082, 0.06, KM.MAT_VOID, seg=9))
    if soot is not None:
        # one-sided smoke stain: a thin sheet on the leeward face
        sy = -1
        out.append(K.box(name + "_soot", T @ Ts(0, sy * (d * 0.5 + 0.008),
                                                zb + (z1 - zb) * 0.72),
                         (w * 0.80, 0.012, (z1 - zb) * 0.66), soot))
        out.append(K.box(name + "_soot2", T @ Ts(0, 0, z1 + 0.215),
                         (w + 0.30, d + 0.26, 0.08), soot))
    return out


def chimney_stain(name, F, u0, v, soot, length=1.7, wide=0.34):
    """Soot streak running down-slope from a chimney."""
    out = []
    for k in range(3):
        ds = length * (0.3 + 0.3 * k)
        out.append(blob("%s_%d" % (name, k), F @ Ts(u0 - ds, v + (k - 1) * 0.05, 0.128),
                        wide * (0.55 + 0.2 * k), 0.5 - 0.1 * k, soot, n=5,
                        jitter=0.3, rng=random.Random(k + 7), lift=0.004))
    return out


def dormer(name, T, w=1.05, h=1.05, d=0.95, pitch=52, wall=None, trim=None,
           tile=None, frame_mat=None, glass=None, rng=None, hood=0.12,
           tiles=None):
    """Gabled dormer standing on the slope.  T must sit ON the roof surface
    with local +Y facing DOWN-slope (see roof()["dormer_T"]).

    Built from scratch rather than by stacking a box and roof() on it.  The
    box version failed for two reasons that both show at the game camera:
    a solid box has no hole, so window() had nothing to look through and the
    glazing read as a sticker on a crate; and roof() leaves its gable ends
    open, so the little roof was a bright hole punched through the slope.
    Here the front wall is four boxes around a real opening, the gable is a
    closed triangle, and the two roof planes are slabs set at their own pitch.
    """
    out = []
    hw = w * 0.5
    hd = d * 0.5
    ft = 0.11                                   # front / side wall thickness
    # The body has to reach well below the slope: a dormer stands square to the
    # roof plane while the tiles fall away under its down-slope face, so a body
    # that only sinks a few centimetres floats clear at the front.
    tanp = math.tan(math.radians(pitch))
    sink = 0.55 + hd * tanp
    # The tiles climb away from the dormer's front face, so the visible face
    # is bounded below by the roof surface at +hd, not by the body floor.  Put
    # the window just above that line and let it fill the face; a dormer with
    # a metre of blank wall under its window reads as a box on the roof.
    fs = -hd * tanp
    ow = max(0.34, min(w * 0.52, w - 0.34))
    z0 = fs + 0.26
    oh = max(0.40, h - 0.20 - z0)
    zb, zt = -(sink), h
    midz = (zb + zt) * 0.5
    specs = []
    specs.append((T @ Ts(0, -hd + ft * 0.5, midz), (w, ft, zt - zb)))
    for sx in (-1, 1):
        specs.append((T @ Ts(sx * (hw - ft * 0.5), 0, midz),
                      (ft, d - 2 * ft, zt - zb)))
    fy = hd - ft * 0.5
    side_w = hw - ow * 0.5
    for sx in (-1, 1):
        specs.append((T @ Ts(sx * (hw + ow * 0.5) * 0.5, fy, midz),
                      (side_w, ft, zt - zb)))
    specs.append((T @ Ts(0, fy, (zb + z0) * 0.5), (ow, ft, z0 - zb)))
    specs.append((T @ Ts(0, fy, (z0 + oh + zt) * 0.5), (ow, ft, zt - z0 - oh)))
    out.append(boxmesh(name + "_bd", specs, wall))
    # gable triangle closing the front, standing on the eave line
    pr = math.radians(44.0)
    ex = hw + 0.12                              # eave overhang past the body
    ez = h - 0.06                               # eave height
    rh = ex * math.tan(pr)
    gy = hd                                     # gable sits flush with the face
    out.append(quad_slab(name + "_gk",
                         [(T @ Matrix.Translation((0.0, gy, 0.0))
                           @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
                           [(-hw, ez), (hw, ez), (0.0, ez + rh)], 0.12)], wall))
    # the two roof planes: slabs laid in their own slope frame
    sl = math.hypot(ex, rh)
    rspec = []
    for s in (-1, 1):
        F = frame((-s * math.cos(pr), 0.0, math.sin(pr)), (0.0, 1.0, 0.0),
                  (s * math.sin(pr), 0.0, math.cos(pr)), (s * ex, 0.0, ez))
        rspec.append((T @ F @ Ts(sl * 0.5, 0.0, 0.055),
                      (sl * 1.03, d + 0.26, 0.11)))
    out.append(boxmesh(name + "_rf", rspec, tile))
    # ridge bead, so the dormer has a lit top edge against the main slope
    out.append(K.box(name + "_rg", T @ Ts(0, 0, ez + rh + 0.045),
                     (0.17, d + 0.30, 0.11), tile, bev=0.012))
    # window with a real reveal, plus a sill that casts a line under it
    out += window(name + "_w", T @ Ts(0, hd, z0), ow, oh, frame=frame_mat,
                  glass=glass, wall_mat=wall, deep=0.13, sill=False,
                  hood=False, bars=(1, 1), arch=None)
    out.append(K.box(name + "_sil", T @ Ts(0, hd + 0.055, z0 - 0.045),
                     (ow + 0.17, 0.16, 0.075), trim, bev=0.008))
    out.append(K.box(name + "_lid", T @ Ts(0, hd + 0.045, z0 + oh + 0.055),
                     (ow + 0.15, 0.13, 0.085), trim, bev=0.008))
    # barge boards down both gable edges.  A gabled dormer is seen head-on at
    # the game camera - you get the gable triangle, not the roof - so its
    # outline has to be drawn for it or it dissolves into the tiles behind.
    bl = math.hypot(hw, rh)
    for s in (-1, 1):
        th = math.atan2(-rh, -s * hw)
        out.append(K.box("%s_bb%d" % (name, s),
                         T @ Ts(s * hw * 0.5, gy + 0.04, ez + rh * 0.5)
                         @ Matrix.Rotation(th, 4, "Y"),
                         (bl + 0.12, 0.17, 0.095), trim, bev=0.006))
    return out


def skylight(name, T, w=0.72, h=0.86, frame_mat=None, glass=None):
    """Flat glazed roof-light; T on the slope, +Y down-slope, +Z out."""
    out = []
    out.append(K.box(name + "_fr", T @ Ts(0, 0, 0.03), (w, h, 0.09), frame_mat,
                     bev=0.008))
    out.append(K.box(name + "_gl", T @ Ts(0, 0, 0.078), (w * 0.80, h * 0.82, 0.02),
                     glass))
    for sx in (-1, 1):
        out.append(boxmesh(name + "_lb%d" % sx,
                           [(T @ Ts(sx * w * 0.40, 0, 0.055, ry=sx * 0.34),
                             (0.035, h * 0.86, 0.10))], frame_mat))
    return out


# ==========================================================================
# 4.  windows
# ==========================================================================
def window(name, T, w, h, frame=None, glass=None, wall_mat=None, arch=None,
           shutters=None, sill=True, hood=False, bars=(2, 1), deep=0.17,
           flower=False, rng=None):
    """A window in an already-cut rectangular hole.

    T sits at the opening's bottom centre on the facade plane, +Y outward.
    `arch` = None (flat lintel), "seg" (3-piece segmental stone arch) or
    "round" (full semicircular arch inside the hole).
    """
    r = rng or random.Random(5)
    out = []
    jamb = 0.075
    # dark interior behind everything: this is what makes the hole read as a
    # hole instead of a sticker at 34 m
    out.append(K.box(name + "_dk", T @ Ts(0, -deep - 0.05, h * 0.5),
                     (w - 0.02, 0.06, h - 0.02), KM.MAT_VOID))
    gh = max(0.26, h - w * 0.5) if arch == "round" else h
    # glass, set back and split by a mullion + transom
    out.append(K.box(name + "_gl", T @ Ts(0, -deep, gh * 0.5),
                     (w - 0.02, 0.025, gh - 0.01), glass))
    if arch == "round":
        rr = w * 0.5
        pts = [(math.cos(math.pi * i / 8.0) * rr * 0.995,
                math.sin(math.pi * i / 8.0) * rr * 0.995) for i in range(9)]
        gg = K.mesh_obj(name + "_tm", [tuple(T @ Vector((x, -deep, z + gh)))
                                       for (x, z) in pts],
                        [tuple(range(len(pts)))])
        K.assign(gg, glass)
        out.append(gg)
    # outer frame ring, inset into the reveal
    yf = -deep * 0.42
    for sx in (-1, 1):
        out.append(K.box(name + "_j%d" % sx,
                         T @ Ts(sx * (w * 0.5 - jamb * 0.5), yf, gh * 0.5),
                         (jamb, 0.10, gh), frame, bev=0.006))
    out.append(K.box(name + "_sb", T @ Ts(0, yf, jamb * 0.5),
                     (w, 0.10, jamb * 0.9), frame))
    if arch != "round":
        out.append(K.box(name + "_hb", T @ Ts(0, yf, gh - jamb * 0.45),
                         (w, 0.10, jamb * 0.9), frame))
    if arch == "seg":
        # three-piece segmental arch: covers the top corners of the hole
        rise = 0.13
        for k in (-1, 0, 1):
            x = k * w * 0.31
            z = gh - 0.055 - rise * (1.0 - (k * k) * 0.60)
            out.append(K.box(name + "_vo%d" % (k + 2),
                             T @ Ts(x, yf + 0.01, z, ry=-k * 0.20),
                             (w * 0.40, 0.13, 0.145), wall_mat, bev=0.008))
    # mullion + transom (the cross the brief asks for)
    if bars[0]:
        out.append(K.box(name + "_mu", T @ Ts(0, yf - 0.01, gh * 0.5),
                         (0.05, 0.085, gh), frame, bev=0.004))
    if bars[1]:
        out.append(K.box(name + "_tr", T @ Ts(0, yf - 0.01, gh * 0.46),
                         (w, 0.075, 0.042), frame, bev=0.004))
    # lead cames: two hairlines that read as leaded lights under grazing light
    for k in (0.28, 0.70):
        out.append(K.box(name + "_cm%d" % int(k * 100), T @ Ts(0, -deep + 0.018, gh * k),
                         (w, 0.012, 0.012), KM.MAT_LEAD))
    # projecting stone sill + drip
    if sill:
        out.append(K.box(name + "_si", T @ Ts(0, 0.055, -0.045),
                         (w + 0.26, 0.34, 0.09), wall_mat, bev=0.01))
        out.append(K.box(name + "_sp", T @ Ts(0, 0.16, -0.115),
                         (w + 0.20, 0.13, 0.055), wall_mat, bev=0.008))
    if hood:
        out.append(K.box(name + "_hd", T @ Ts(0, 0.045, h + 0.075),
                         (w + 0.40, 0.20, 0.11), wall_mat, bev=0.012))
    # shutters: opened outward so their top faces catch the key light
    if shutters:
        for sx in (-1, 1):
            ang = sx * math.radians(r.uniform(14, 26))
            M = T @ Matrix.Translation((sx * (w * 0.5 + 0.10), 0.10, h * 0.5)) @ \
                Matrix.Rotation(-ang, 4, "Z")
            out.append(K.box(name + "_sh%d" % sx, M, (w * 0.50, 0.045, h * 0.94),
                             shutters, bev=0.006))
            for k in (0.22, 0.72):
                out.append(K.box(name + "_shb%d%d" % (sx, int(k * 100)),
                                 M @ Ts(0, 0.028, (k - 0.5) * h * 0.94),
                                 (w * 0.46, 0.02, 0.06), KM.MAT_IRON))
            out.append(K.box(name + "_shh%d" % sx,
                             T @ Ts(sx * (w * 0.5 + 0.03), 0.06, h * 0.80),
                             (0.10, 0.05, 0.05), KM.MAT_IRON))
    if flower:
        out.append(K.box(name + "_fb", T @ Ts(0, 0.16, -0.10),
                         (w * 0.80, 0.20, 0.16), K.mat_wood("hu_oak", "#3a2a1d")))
        for i in range(3):
            out.append(blob(name + "_fl%d" % i,
                            T @ Ts(-w * 0.24 + i * w * 0.24, 0.16, 0.0),
                            0.11, 0.09, MAT_MOSS["moss2"], n=5, rng=r))
    return out


def arrow_slit(name, T, w=0.16, h=1.05, mat=None, deep=0.22):
    """Splayed arrow loop: wide dark inner reveal, narrow outer slot."""
    out = []
    out.append(K.box(name + "_o", T @ Ts(0, -0.02, h * 0.5), (w, 0.10, h), mat,
                     bev=0.006))
    out.append(K.box(name + "_i", T @ Ts(0, -0.20, h * 0.5), (w * 2.6, 0.16, h * 0.94),
                     KM.MAT_VOID))
    out.append(K.box(name + "_s", T @ Ts(0, 0.01, h * 0.5), (w * 1.9, 0.09, 0.10), mat))
    return out


# ==========================================================================
# 5.  doors
# ==========================================================================
def door(name, T, w=1.18, h=2.30, wood=None, iron=None, stone=None, steps=2,
         arch=False, double=False, threshold=True, lamp=False, rng=None,
         split=False, planks=5):
    """Planked door in a hole cut by the caller.  T at bottom centre, +Y out."""
    r = rng or random.Random(9)
    out = []
    out.append(K.box(name + "_void", T @ Ts(0, -0.44, h * 0.5), (w, 0.10, h),
                     KM.MAT_VOID))
    # leaves
    nl = 2 if double else 1
    for k in range(nl):
        cx = 0.0 if nl == 1 else (k - 0.5) * w * 0.5
        lw = w - 0.04 if nl == 1 else w * 0.5 - 0.035
        out.append(K.box(name + "_lf%d" % k, T @ Ts(cx, -0.16, h * 0.5),
                         (lw, 0.075, h - 0.03), wood, bev=0.006))
        for i in range(1, planks):
            x = cx - lw * 0.5 + lw * i / planks
            out.append(K.box(name + "_pl%d_%d" % (k, i), T @ Ts(x, -0.118, h * 0.5),
                             (0.012, 0.02, h - 0.10), KM.MAT_OAKDK))
        # iron straps with studs
        for j in range(3):
            z = h * (0.20 + 0.30 * j)
            out.append(K.box(name + "_st%d_%d" % (k, j), T @ Ts(cx, -0.112, z),
                             (lw * 0.92, 0.022, 0.075), iron, bev=0.004))
    if split:
        out.append(K.box(name + "_sp", T @ Ts(0, -0.108, h * 0.52),
                         (w - 0.06, 0.03, 0.10), wood))
    # ring knocker + escutcheon
    out.append(torus(name + "_ring", T @ Ts(w * 0.30, -0.088, h * 0.50), 0.052, 0.012,
                     iron, nseg=8, nring=4))
    out.append(K.box(name + "_esc", T @ Ts(w * 0.30, -0.104, h * 0.56),
                     (0.075, 0.02, 0.10), iron, bev=0.004))
    out.append(K.box(name + "_kh", T @ Ts(w * 0.30, -0.112, h * 0.54),
                     (0.016, 0.02, 0.045), KM.MAT_VOID))
    # surround: jambs, head, threshold, steps
    for sx in (-1, 1):
        out.append(K.box(name + "_jm%d" % sx,
                         T @ Ts(sx * (w * 0.5 + 0.075), 0.02, h * 0.5),
                         (0.15, 0.28, h + 0.10), stone, bev=0.01))
    if arch:
        for k in range(5):
            a = math.pi * (k + 0.5) / 5
            out.append(K.box(name + "_ar%d" % k,
                             T @ Ts(-math.cos(a) * (w * 0.5 + 0.075), 0.02,
                                    h + math.sin(a) * (w * 0.5 + 0.05)),
                             (0.42, 0.26, 0.20), stone, bev=0.01))
    else:
        out.append(K.box(name + "_lin", T @ Ts(0, 0.02, h + 0.075),
                         (w + 0.46, 0.28, 0.20), stone, bev=0.012))
        out.append(K.box(name + "_lin2", T @ Ts(0, 0.05, h + 0.205),
                         (w + 0.30, 0.22, 0.07), stone, bev=0.008))
    if threshold:
        out.append(K.box(name + "_th", T @ Ts(0, 0.10, -0.06),
                         (w + 0.42, 0.42, 0.12), stone, bev=0.01))
    for i in range(steps):
        out.append(K.box(name + "_sr%d" % i, T @ Ts(0, 0.34 + i * 0.30, -0.13 - i * 0.145),
                         (w + 0.30 - i * 0.02, 0.30, 0.145), stone, bev=0.008))
    if lamp:
        out.append(K.box(name + "_lb", T @ Ts(w * 0.5 + 0.42, 0.10, h * 0.92),
                         (0.50, 0.06, 0.05), iron))
        out.append(K.box(name + "_lh", T @ Ts(w * 0.5 + 0.55, 0.10, h * 0.80),
                         (0.02, 0.02, 0.22), iron))
        out.append(K.box(name + "_lg", T @ Ts(w * 0.5 + 0.55, 0.10, h * 0.72),
                         (0.16, 0.16, 0.20), KM.MAT_GLOW))
        out.append(K.box(name + "_lj", T @ Ts(w * 0.5 + 0.55, 0.10, h * 0.61),
                         (0.09, 0.09, 0.04), iron))
    return out


def hood_canopy(name, T, w, d, tile, trim, brackets=2):
    """Small tiled pent roof over a door (a real roof surface, not a slab)."""
    out = []
    ang = math.radians(22)
    out.append(K.box(name + "_b", T @ Ts(0, d * 0.5, 0.0, rx=ang),
                     (w, math.hypot(d, 0.34), 0.10), tile, bev=0.006))
    for k in range(brackets):
        x = -w * 0.5 + 0.16 + k * (w - 0.32) / max(1, brackets - 1)
        b = bar(name + "_br%d" % k, T, (x, 0.06, -0.62), (x, d * 0.92, -0.10),
                0.075, trim, wide=0.075, bev=0.005)
        if b is not None:
            out.append(b)
    out.append(K.box(name + "_f", T @ Ts(0, d * 0.96, -0.20), (w, 0.06, 0.12), trim))
    return out


# ==========================================================================
# 6.  timber frame, jetty, plinth
# ==========================================================================
def timber_frame(name, T, w, h, wood, ops=(), stud=0.94, y=0.0, proud=0.055,
                 post=0.20, braces=True, plate=True, rng=None):
    """Close-studded frame standing proud of the plaster wall.

    `ops` = [(u0, u1)] spans (local x) that must stay clear for a window/door.
    """
    r = rng or random.Random(13)
    out = []
    hw = w * 0.5
    specs = []
    specs.append((T @ Ts(-hw + post * 0.5, y, h * 0.5, rz=math.radians(-2.0)),
                  (post, 0.14, h + 0.09)))
    specs.append((T @ Ts(hw - post * 0.5, y, h * 0.5, rz=math.radians(2.0)),
                  (post, 0.14, h + 0.09)))
    if plate:
        specs.append((T @ Ts(0, y + 0.012, h - 0.085), (w, 0.135, 0.17)))
        specs.append((T @ Ts(0, y, 0.07), (w, 0.115, 0.14)))
    n = max(2, int(round((w - 2.0 * post) / stud)))
    for i in range(1, n):
        x = -hw + post + i * (w - 2.0 * post) / n
        if any(a - 0.12 <= x <= b + 0.12 for (a, b) in ops):
            continue
        specs.append((T @ Ts(x, y, h * 0.5), (0.125, 0.115, h - 0.02)))
    out.append(boxmesh(name + "_fr", specs, wood, bev=0.006))
    if braces:
        bs = []
        corners = []
        if n >= 2:
            x0 = -hw + post + (w - 2.0 * post) / n
            corners.append((x0 - 0.02, -1))
            corners.append((-x0 + 0.02, 1))
        for (xc, d) in corners:
            if any(a - 0.15 <= xc <= b + 0.15 for (a, b) in ops):
                continue
            p0 = (xc + d * 0.72, y + 0.005, 0.16)
            p1 = (xc - d * 0.02, y + 0.005, h * 0.55)
            b = bar(name + "_br%d" % int(xc * 10), T, p0, p1, 0.115, wood,
                    wide=0.10, bev=0.005)
            if b is not None:
                bs.append(b)
        out += bs
    return out


def gable_frame(name, T, half_w, height, wood, post=0.18):
    """Timber in a gable triangle: king post, collar, two rake braces."""
    out = []
    hw = half_w
    # tie beam at the base: without it the gable has no bottom edge and the
    # triangle floats on top of the wall
    out.append(K.box(name + "_tie", T @ Ts(0, 0, 0.09),
                     (2.0 * hw * 0.97, 0.13, 0.18), wood, bev=0.006))
    out.append(K.box(name + "_kp", T @ Ts(0, 0, height * 0.52),
                     (post, 0.12, height * 0.94), wood, bev=0.006))
    for k, t in enumerate((0.34, 0.62)):
        z = height * t
        ww = 2.0 * hw * (1.0 - t) * 0.94
        out.append(K.box(name + "_cl%d" % k, T @ Ts(0, 0, z), (ww, 0.11, 0.15), wood,
                         bev=0.005))
    # rake boards FOLLOW the roof edge.  The old braces ran from 0.10*hw at
    # 0.18h to 0.86*hw at 0.80h, but the half-width available at 0.80h is only
    # 0.20*hw - so they speared straight out through the roof surface, which is
    # what those two beams crossing the slopes in the render were.
    for sx in (-1, 1):
        b = bar(name + "_rb%d" % sx, T,
                (sx * (hw - 0.11), 0, 0.10), (sx * 0.055, 0, height * 0.95),
                0.12, wood, wide=0.10, bev=0.005)
        if b is not None:
            out.append(b)
    # short struts from the king post out to the lower collar
    for sx in (-1, 1):
        b = bar(name + "_st%d" % sx, T,
                (sx * post * 0.6, 0, height * 0.18),
                (sx * hw * 0.55, 0, height * 0.34),
                0.10, wood, wide=0.09, bev=0.004)
        if b is not None:
            out.append(b)
    return out


def jetty(name, T, w, y_lo, y_hi, z, wood, iron=None, njoist=None, brackets=True,
          depth_lo=None):
    """Bressumer + joist ends + corner brackets for a jettied upper floor.

    y_lo = lower wall face, y_hi = upper wall face, z = upper floor level.
    The open slot between the two faces is what makes the shadow line; the
    joist ends break it into a rhythm instead of one flat dark band.
    """
    out = []
    span = w + 2.0 * max(0.0, y_hi - y_lo)
    out.append(K.box(name + "_brs", T @ Ts(0, (y_lo + y_hi) * 0.5 - 0.03, z - 0.15),
                     (span, (y_hi - y_lo) + 0.26, 0.30), wood, bev=0.01))
    nj = njoist or max(3, int(round(w / 0.46)))
    specs = []
    for i in range(nj):
        x = -w * 0.5 + (i + 0.5) * w / nj
        specs.append((T @ Ts(x, (y_lo + y_hi) * 0.5 + 0.02, z - 0.40),
                      (0.095, (y_hi - y_lo) + 0.20, 0.20)))
    out.append(boxmesh(name + "_js", specs, wood, bev=0.004))
    if brackets:
        for sx in (-1, 1):
            x = sx * (w * 0.5 - 0.02)
            b = bar(name + "_bk%d" % sx, T, (x, y_lo - 0.10, z - 0.86),
                    (x, y_hi - 0.06, z - 0.30), 0.13, wood, wide=0.14, bev=0.006)
            if b is not None:
                out.append(b)
    return out


def plinth(name, T, w, d, h, stone, moss=None, rng=None, spout=None, steps=0,
           step_dir=1):
    """Stone base with footing, cap course, ground moss and an optional spout."""
    r = rng or random.Random(17)
    out = []
    out.append(K.box(name + "_ft", T @ Ts(0, 0, 0.085), (w + 0.34, d + 0.34, 0.17),
                     stone, bev=0.01))
    out.append(K.box(name + "_bd", T @ Ts(0, 0, h * 0.5), (w + 0.20, d + 0.20, h),
                     stone, bev=0.012))
    out.append(K.box(name + "_cp", T @ Ts(0, 0, h - 0.045), (w + 0.30, d + 0.30, 0.09),
                     stone, bev=0.012))
    if moss is not None:
        specs = []
        for sy in (-1, 1):
            specs.append((T @ Ts(0, sy * (d * 0.5 + 0.085), 0.035), (w + 0.30, 0.03, 0.07)))
        for sx in (-1, 1):
            specs.append((T @ Ts(sx * (w * 0.5 + 0.085), 0, 0.035), (0.03, d + 0.30, 0.07)))
        out.append(boxmesh(name + "_ms", specs, moss))
        for k in range(3):
            sx = r.choice((-1, 1))
            out.append(blob(name + "_mb%d" % k,
                            T @ Ts(sx * (w * 0.5 + 0.02) * r.uniform(0.1, 0.9),
                                   r.uniform(-0.5, 0.5) * d, 0.10),
                            r.uniform(0.10, 0.22), r.uniform(0.10, 0.22), moss,
                            n=5, rng=r))
    if spout:
        sx = r.choice((-1, 1))
        out.append(K.box(name + "_spb", T @ Ts(sx * (w * 0.5 + 0.13), d * 0.5 - 0.3,
                                              h + 0.06), (0.16, 0.22, 0.14), stone))
        out.append(K.cyl(name + "_spp", T @ Ts(sx * (w * 0.5 + 0.16), d * 0.42,
                                              0.34, rx=math.radians(70)),
                         0.05, 0.62, KM.MAT_LEAD, seg=8))
    return out


def steps(name, T, w, n, stone, rise=0.16, run=0.30, dirsign=1):
    out = []
    for i in range(n):
        out.append(K.box(name + "_s%d" % i,
                         T @ Ts(0, dirsign * run * (i + 0.5), rise * (n - i) - rise * 0.5),
                         (w, run, rise * (n - i)), stone, bev=0.008))
    return out


# ==========================================================================
# 7.  signs, hoists, clutter
# ==========================================================================
def sign(name, T, w=0.95, h=0.62, board=None, iron=None, face=None, kind="hang",
         paint=None):
    """Hanging shop sign on a wrought-iron bracket (reads as a dark silhouette
    at 39 px/m, which is exactly what a shop needs)."""
    out = []
    out.append(K.box(name + "_arm", T @ Ts(w * 0.5 + 0.10, 0, 0), (w + 0.2, 0.055, 0.055),
                     iron))
    out.append(K.box(name + "_wall", T @ Ts(0.02, 0, -0.16), (0.07, 0.05, 0.36), iron))
    out.append(bar(name + "_sc", T, (0.06, 0, -0.34), (w * 0.42, 0, 0.02), 0.04, iron))
    for sx in (-1, 1):
        out.append(K.box(name + "_ln%d" % sx, T @ Ts(w * 0.5 + sx * w * 0.32, 0,
                                                     -0.10), (0.014, 0.014, 0.16), iron))
    out.append(K.box(name + "_bd", T @ Ts(w * 0.5, 0, -0.46), (w, 0.055, h), board,
                     bev=0.008))
    if face is not None:
        out.append(K.box(name + "_fc", T @ Ts(w * 0.5, 0.032, -0.46),
                         (w * 0.80, 0.012, h * 0.74), face))
    out.append(K.box(name + "_bd2", T @ Ts(w * 0.5, 0, -0.46 - h * 0.5),
                     (w + 0.05, 0.075, 0.04), iron))
    return out


def hoist(name, T, z, wood=None, iron=None, rope=None, load=True):
    """Warehouse cathead: projecting beam, pulley block, rope and a hanging
    crate.  Silhouettes over the street, which is why warehouses read."""
    out = []
    L = 1.45
    out.append(K.box(name + "_cat", T @ Ts(L * 0.42, 0, z), (L, 0.14, 0.16), wood,
                     bev=0.008))
    out.append(bar(name + "_br", T, (0.02, 0, z - 0.55), (L * 0.52, 0, z - 0.05),
                   0.10, wood, wide=0.10))
    out.append(K.cyl(name + "_pu", T @ Ts(L * 0.80, 0, z - 0.11, rx=math.pi * 0.5),
                     0.085, 0.10, iron, seg=10))
    out.append(K.box(name + "_hp", T @ Ts(L * 0.80, 0, z - 0.20), (0.12, 0.10, 0.10),
                     iron))
    rl = z - 1.30
    out.append(bar(name + "_rp", T, (L * 0.80, 0, z - 0.26), (L * 0.80, 0, rl),
                   0.022, rope or K.mat_wood("hu_oak", "#6a5a3a")))
    out.append(K.box(name + "_hk", T @ Ts(L * 0.80, 0, rl - 0.10), (0.03, 0.16, 0.22),
                     iron))
    if load:
        out.append(K.box(name + "_cr", T @ Ts(L * 0.80, 0, rl - 0.68), (0.78, 0.66, 0.62),
                         wood, bev=0.01))
        for sx in (-1, 1):
            out.append(K.box(name + "_crb%d" % sx,
                             T @ Ts(L * 0.80 + sx * 0.30, 0, rl - 0.68),
                             (0.05, 0.70, 0.09), KM.MAT_OAKDK))
    return out


def awning(name, T, w, d, tile, trim, drop=0.42, brackets=3):
    """Tiled pent roof over a shopfront (replaces the old red slab)."""
    out = []
    ang = math.atan2(drop, d)
    L = math.hypot(d, drop)
    out.append(K.box(name + "_t", T @ Ts(0, d * 0.5 * 0.5 + 0.02, -drop * 0.5, rx=-ang),
                     (w, L, 0.10), tile, bev=0.006))
    out.append(K.box(name + "_f", T @ Ts(0, d * 0.98, -drop - 0.06),
                     (w, 0.07, 0.13), trim))
    for k in range(brackets):
        x = -w * 0.5 + 0.14 + k * (w - 0.28) / max(1, brackets - 1)
        b = bar(name + "_br%d" % k, T, (x, 0.02, -drop - 0.40), (x, d * 0.94, -drop - 0.06),
                0.07, trim, wide=0.075, bev=0.004)
        if b is not None:
            out.append(b)
    out.append(K.box(name + "_b", T @ Ts(0, 0, -drop - 0.52), (w - 0.1, 0.10, 0.18), trim))
    return out


def counter(name, T, w, wood, iron=None):
    """Open shopfront counter with a shutter board hinged up as a canopy."""
    out = []
    out.append(K.box(name + "_top", T @ Ts(0, 0.30, 0.92), (w, 0.62, 0.09), wood,
                     bev=0.008))
    out.append(K.box(name + "_ap", T @ Ts(0, 0.60, 0.46), (w, 0.10, 0.92), wood,
                     bev=0.008))
    for sx in (-1, 1):
        out.append(K.box(name + "_p%d" % sx, T @ Ts(sx * (w * 0.5 - 0.06), 0.30, 0.46),
                         (0.10, 0.54, 0.92), wood, bev=0.006))
    out.append(K.box(name + "_bd", T @ Ts(0, 0.32, 1.0), (w - 0.1, 0.55, 0.045),
                     KM.MAT_OAKDK))
    return out


# ==========================================================================
# 8.  kind signatures
# ==========================================================================
def crenel_row(name, T, length, stone, h=0.95, merlon=0.72, gap=0.46, depth=0.5):
    """Battlement row sitting on z=0, running along local X."""
    out = []
    pitch = merlon + gap
    n = max(1, int(length / pitch))
    total = n * pitch - gap
    x0 = -total * 0.5 + merlon * 0.5
    specs = []
    for i in range(n):
        x = x0 + i * pitch
        specs.append((T @ Ts(x, 0, h * 0.5), (merlon, depth, h)))
        specs.append((T @ Ts(x, 0, h + 0.045), (merlon + 0.09, depth + 0.09, 0.09)))
    out.append(boxmesh(name + "_m", specs, stone, bev=0.008))
    out.append(K.box(name + "_par", T @ Ts(0, 0, -0.16), (length, depth * 0.94, 0.32),
                     stone, bev=0.01))
    return out


def corbel_table(name, T, length, stone, n=None, z=0.0):
    out = []
    n = n or max(2, int(length / 0.62))
    specs = []
    for i in range(n):
        x = -length * 0.5 + (i + 0.5) * length / n
        specs.append((T @ Ts(x, 0, z), (0.20, 0.42, 0.34)))
    out.append(boxmesh(name + "_cb", specs, stone, bev=0.006))
    return out


def bartizan(name, T, z, r=0.75, h=2.4, stone=None, tile=None, end_mat=None):
    """Corbelled corner turret: the strongest silhouette cue a tower has."""
    out = []
    out.append(K.cyl(name + "_corb", T @ Ts(0, 0, z - 0.30), r * 1.02, 0.62, stone,
                     seg=12))
    out.append(K.cyl(name + "_body", T @ Ts(0, 0, z + h * 0.5), r, h, stone, seg=12))
    out.append(K.cyl(name + "_ring", T @ Ts(0, 0, z + h - 0.10), r * 1.06, 0.20, stone,
                     seg=12))
    rp, _ = roof(name + "_r", T @ Ts(0, 0, z + h), 2.0 * r, 2.0 * r, 0.0, 30,
                 tile, K.mat_wood("hu_oak_dk", "#241a12"), stone,
                 ov_v=0.10, ov_g=0.10, course=0.20, riser=0.03, ridge=False,
                 moss=0.0)
    out += rp
    out.append(K.cyl(name + "_fin", T @ Ts(0, 0, z + h + 0.55), 0.05, 0.7, stone, seg=6))
    for k in range(3):
        a = TAU * k / 3.0 + 0.5
        out += arrow_slit(name + "_sl%d" % k,
                          T @ Ts(math.cos(a) * r, math.sin(a) * r, z + h * 0.35,
                                 rz=a + math.pi * 0.5), mat=stone)
    return out


def balcony(name, T, w, d, stone, iron=None, tile=None, trim=None):
    """Stone corbels + balustrade; a manor signature that reads from above."""
    out = []
    out.append(K.box(name + "_sl", T @ Ts(0, d * 0.5, -0.06), (w, d, 0.12), stone,
                     bev=0.01))
    specs = []
    for i in range(4):
        x = -w * 0.5 + (i + 0.5) * w / 4
        specs.append((T @ Ts(x, d * 0.30, -0.32), (0.20, d * 0.6, 0.42)))
    out.append(boxmesh(name + "_cb", specs, stone, bev=0.006))
    specs = []
    k = max(3, int(w / 0.34))
    for i in range(k):
        x = -w * 0.5 + (i + 0.5) * w / k
        specs.append((T @ Ts(x, d * 0.94, 0.34), (0.13, 0.13, 0.68)))
    out.append(boxmesh(name + "_bl", specs, stone, bev=0.006))
    out.append(K.box(name + "_cap", T @ Ts(0, d * 0.94, 0.72), (w + 0.06, 0.20, 0.10),
                     stone, bev=0.008))
    for sx in (-1, 1):
        out.append(K.box(name + "_ss%d" % sx, T @ Ts(sx * w * 0.5, d * 0.5, 0.34),
                         (0.16, d, 0.68), stone, bev=0.008))
    return out


def market_board(name, T, w=1.6, h=0.9, board=None, face=None, iron=None, legs=True):
    """Signboard on legs (inns, apothecaries, taverns)."""
    out = [K.box(name + "_b", T @ Ts(0, 0, h * 0.5 + 0.55), (w, 0.07, h), board,
                 bev=0.008)]
    hw = w * 0.5 - 0.08
    for sx in (-1, 1):
        out.append(K.box(name + "_l%d" % sx, T @ Ts(sx * hw, 0, 0.55), (0.10, 0.10, 1.10),
                         board, bev=0.006))
    out.append(K.box(name + "_c", T @ Ts(0, 0, h + 0.62), (w + 0.12, 0.12, 0.10), board))
    if face is not None:
        for sy in (-1, 1):
            out.append(K.box(name + "_f%d" % sy, T @ Ts(0, sy * 0.042, h * 0.5 + 0.55),
                             (w * 0.82, 0.012, h * 0.74), face))
    return out
