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
        "moss": noisy_mat("hu_moss", "#414c2e", "#26301c", scale=9.0, rough=0.97,
                          bump=0.3, bdist=0.01),
        "moss2": noisy_mat("hu_moss2", "#55603a", "#39422a", scale=13.0, rough=0.97),
        "lichen": noisy_mat("hu_lichen", "#8b8866", "#5b5c44", scale=14.0, rough=0.95),
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
         ov_v=0.42, ov_g=0.46, course=0.36, riser=0.058, mortar=None,
         ridge=True, moss=0.55, rng=None, crest=False):
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
    tilt = math.radians(5.0)
    # course slabs: lower edge lifted, upper edge flush with the slope plane.
    # 5 deg past the slope + 0.03 thick puts the lip ~0.06 m proud, which is
    # what throws the shadow line at 39.5 px/m.
    for s in (-1, 1):
        F = slope_frame(s, hw, rh, eave_z, sl)
        specs = []
        for i in range(n):
            u = (i + 0.5) * c
            o = 0.030
            M = F @ Ts(u, 0.0, o) @ Matrix.Rotation(tilt, 4, "Y")
            specs.append((M, (c * 1.015, run, 0.030)))
        out.append(boxmesh("%s_crs%d" % (name, s + 2), specs, tile))
        # double course at the eave: a fatter lip so the eave line reads even
        # when the individual courses merge into one tone at distance
        M = F @ Ts(0.055, 0.0, 0.052) @ Matrix.Rotation(tilt * 1.5, 4, "Y")
        out.append(K.box("%s_evc%d" % (name, s + 2), M, (0.30, run + 0.02, 0.048),
                         tile, bev=0.006))
        # barge / rake boards along both gable edges, deep enough (0.11) to
        # hide the course ends and to read as a dark line in the silhouette
        for sy in (-1, 1):
            M = F @ Ts(sl * 0.5, sy * (hd - 0.062), 0.022)
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

    # ridge: a continuous bed plus overlapping half-round ridge tiles
    if ridge and rh > 0.4:
        rlen = 2.0 * hd - 0.02
        out.append(K.box(name + "_rbed", T @ Ts(0, 0, top_z + 0.00),
                         (0.42, rlen, 0.09), trim, bev=0.012))
        specs = []
        nt = max(3, int(round(rlen / 0.44)))
        seg = rlen / nt
        for k in range(nt):
            y = -rlen * 0.5 + (k + 0.5) * seg
            z = top_z + 0.10 + (0.006 if k % 2 else 0.0)
            specs.append((T @ Ts(0.0, y, z, rx=math.pi * 0.5), 0.118, seg * 0.99))
        out.append(cylmesh(name + "_rt", specs, tile, seg=8))
        for sy in (-1, 1):
            out.append(K.box("%s_rfin%d" % (name, sy), T @ Ts(0, sy * (rlen * 0.5 + 0.01),
                             top_z + 0.02), (0.46, 0.16, 0.30), trim, bev=0.02))

    # ---- weathering: moss along the eave and in the ridge valley, lichen
    # patches mid-slope, soot streaks handled by chimney_roof_stain()
    nm = int(3 + 4 * moss)
    for s in (-1, 1):
        F = slope_frame(s, hw, rh, eave_z, sl)
        for k in range(nm):
            u = r.uniform(0.12, 0.30) * sl
            v = r.uniform(-hd * 0.86, hd * 0.86)
            rx = r.uniform(0.16, 0.40)
            ry = r.uniform(0.24, 0.62)
            mv = "moss" if k % 3 else "moss2"
            G = F @ Ts(u, v, 0.050)
            # patches live just above the course lips so they never z-fight
            out.append(blob("%s_ms%d_%d" % (name, s + 2, k), G, rx, ry,
                            MAT_MOSS[mv], n=6, jitter=0.34, rng=r, lift=0.004))
        # one lichen field higher up, sparse
        if r.random() < 0.75:
            u = r.uniform(0.45, 0.85) * sl
            v = r.uniform(-hd * 0.7, hd * 0.7)
            G = F @ Ts(u, v, 0.050)
            out.append(blob("%s_ln%d" % (name, s + 2), G, r.uniform(0.2, 0.5),
                            r.uniform(0.3, 0.8), MAT_MOSS["lichen"], n=6,
                            jitter=0.32, rng=r, lift=0.004))
        if r.random() < 0.45:
            # a lifted / slipped tile: catches light, reads as age
            u = r.uniform(0.2, 0.8) * sl
            v = r.uniform(-hd * 0.7, hd * 0.7)
            G = F @ Ts(u, v, 0.062) @ Matrix.Rotation(math.radians(r.uniform(6, 13)), 4, "Y")
            out.append(K.box("%s_brk%d" % (name, s + 2), G, (c * 0.9, 0.34, 0.028),
                             tile, bev=0.004))

    info = dict(hw=hw, hd=hd, rh=rh, sl=sl, eave_z=eave_z, top_z=top_z,
                pitch=pitch, span=span, length=length, course=c,
                F={-1: slope_frame(-1, hw, rh, eave_z, sl),
                   1: slope_frame(1, hw, rh, eave_z, sl)})

    def _dormer_T(s, u, v):
        return info["F"][s] @ Ts(u, v, 0.0) @ Matrix.Rotation(math.pi * 0.5, 4, "Z")

    info["dormer_T"] = _dormer_T
    return out, info


# filled in by hd_houses.make_mats() so roof() can weather itself
MAT_MOSS = {"moss": None, "moss2": None, "lichen": None}


def set_weather_mats(m):
    MAT_MOSS.update(m)


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
        out.append(blob("%s_%d" % (name, k), F @ Ts(u0 - ds, v + (k - 1) * 0.05, 0.052),
                        wide * (0.55 + 0.2 * k), 0.5 - 0.1 * k, soot, n=5,
                        jitter=0.3, rng=random.Random(k + 7), lift=0.004))
    return out


def dormer(name, T, w=1.05, h=1.05, d=0.95, pitch=52, wall=None, trim=None,
           tile=None, frame_mat=None, glass=None, rng=None, hood=0.12):
    """Gabled dormer standing on the slope.  T must sit ON the roof surface
    with local +Y facing DOWN-slope (see roof()["dormer_T"])."""
    out = []
    body_h = h + 0.42
    out.append(K.box(name + "_body", T @ Ts(0, 0, body_h * 0.5 - 0.42),
                     (w, d, body_h), wall, bev=0.01))
    # cheeks: the roof cuts the body, so only the front half is really visible
    rp, ri = roof(name + "_r", T @ Ts(0, 0.02, h), w + 0.16, d + 0.10, 0.0, pitch,
                  tile, trim, wall, ov_v=0.11, ov_g=0.13, course=0.16, riser=0.03,
                  ridge=True, moss=0.0, rng=rng)
    out += rp
    # window: a real recess in the front face, not a plate
    out += window(name + "_w", T @ Ts(0, d * 0.5, h * 0.42), w * 0.56, h * 0.5,
                  frame=frame_mat, glass=glass, wall_mat=wall, deep=0.10,
                  sill=False, hood=False, bars=(1, 1), arch=None)
    out.append(K.box(name + "_lid", T @ Ts(0, d * 0.5 + 0.035, h * 0.42 + h * 0.25),
                     (w * 0.72, 0.10, 0.09), trim, bev=0.008))
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
    out.append(K.box(name + "_kp", T @ Ts(0, 0, height * 0.52),
                     (post, 0.12, height * 0.96), wood, bev=0.006))
    for k, t in enumerate((0.34, 0.62)):
        z = height * t
        ww = 2.0 * hw * (1.0 - t) * 0.97
        out.append(K.box(name + "_cl%d" % k, T @ Ts(0, 0, z), (ww, 0.11, 0.15), wood,
                         bev=0.005))
    for sx in (-1, 1):
        b = bar(name + "_rb%d" % sx, T,
                (sx * hw * 0.10, 0, height * 0.18), (sx * hw * 0.86, 0, height * 0.80),
                0.13, wood, wide=0.10, bev=0.005)
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
