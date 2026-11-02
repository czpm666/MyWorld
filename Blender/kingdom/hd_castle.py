"""hd_castle.py - the royal castle: hero landmark of the capital.

Builds on flat ground (z=0) with the origin at the footprint centre and the
MAIN GATE on +Y (the city-facing side).  The caller lifts the whole thing onto
the rock plateau.

Layout (design space, before the final centring shift):

    +Y  gatehouse (twin drum towers, machicolation, portcullis, drawbridge)
        curtain wall, 10 runs / 4 corner drum towers, walk + crenels
        courtyard: fountain, well, market, smithy, stable, guardhouse
    -Y  keep (28 x 22 x 42 m donjon, 4 corner turrets, 3 window storeys)
        great hall wing (west), chapel with rose window (east)

Everything is parametric: no hand-placed vertices.  The only local primitives
are the ones the kit lacks (arrow loop with a real recess, round corbel ring,
rose window in a vertical plane, chain, portcullis, fire).
"""

import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bpy
from mathutils import Matrix, Vector

import hd_common as H
import medkit as K
from medkit import T_at as Ts

OUT = H.OUT_DIR

# ---------------------------------------------------------------------------
# master parameters
# ---------------------------------------------------------------------------
WALL_H = 10.6          # curtain wall walk level
WALL_T = 3.4           # curtain wall thickness
CY = 1.30              # courtyard level (the plateau top outside is z=0)
KEEP_H = 42.0
TOWER_R = 5.0

# curtain outline, CCW, front (+Y) is the gate side.  The last run (10 -> 0)
# is not a wall: the gatehouse closes it.
OUTLINE = [
    (-13.5, 40.0), (-33.0, 35.0), (-42.0, 15.0), (-40.0, -13.0),
    (-24.0, -33.0), (0.0, -41.0), (24.0, -33.0), (40.0, -13.0),
    (42.0, 15.0), (33.0, 35.0), (13.5, 40.0),
]
TOWER_AT = (2, 3, 7, 8)          # outline indices carrying corner drum towers
GATE_HW = 13.5                   # gatehouse half width
GATE_YF, GATE_YB = 40.0, 27.6    # gate block front / back (12.4 m deep passage)
SHIFT_Y = -4.50                  # centring shift applied at the very end
RZ = {"+y": 0.0, "-y": math.pi, "+x": -math.pi * 0.5, "-x": math.pi * 0.5}

FIRE = None


# ---------------------------------------------------------------------------
# tiny local toolkit
# ---------------------------------------------------------------------------
def bx(name, T, size, mat, bev=0.02):
    return K.box(name, T, size, mat, bev=bev)


def cyl(name, T, r, h, mat, seg=24, r2=None, cap=True):
    return K.cyl(name, T, r, h, mat, seg=seg, r2=r2, cap=cap)


def FT(x, y, z, n="+y"):
    """Frame on a wall face whose outward normal is n."""
    return Ts(x, y, z, rz=RZ[n])


def seg_frame(A, B):
    """Frame for a curtain run: local +X along the run, local +Y OUTWARD.

    The outline is CCW, so the interior is on the left of A->B; adding pi puts
    +Y on the right, i.e. outside the castle.
    """
    d = B - A
    L = d.length
    th = math.atan2(d.y, d.x) + math.pi
    M = (A + B) * 0.5
    return Ts(M.x, M.y, 0.0, rz=th), L


def rmat(T, a, r, z):
    """Matrix on a circle of radius r at angle a, local +Y radial outward."""
    return T @ Matrix.Translation(Vector((math.cos(a) * r, math.sin(a) * r, z))) \
             @ Matrix.Rotation(a - math.pi * 0.5, 4, "Z")


def tmat(T, a, r, z):
    """As rmat but local +X tangential (for merlons)."""
    return T @ Matrix.Translation(Vector((math.cos(a) * r, math.sin(a) * r, z))) \
             @ Matrix.Rotation(a + math.pi * 0.5, 4, "Z")


def fire_mat():
    """Orange emissive used for forge / brazier flames (created once)."""
    global FIRE
    if FIRE is not None:
        return FIRE
    m = bpy.data.materials.new("fire_glow")
    m.use_nodes = True
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = K.c("#ff7a1e")
            n.inputs["Emission Color"].default_value = K.c("#ff8a24")
            n.inputs["Emission Strength"].default_value = 4.5
            n.inputs["Roughness"].default_value = 0.6
    FIRE = m
    return m


SHADOW = None


def shadow_mat():
    """Near-black stone for recesses (niches, loops, tunnel mouths).

    MAT["iron"] is a real metal -- used for a window recess it renders as a
    bright blue-grey plate instead of a hole.  One shared dark material keeps
    every opening reading as depth.
    """
    global SHADOW
    if SHADOW is not None:
        return SHADOW
    SHADOW = K.mat_stone("castle_shadow", base="#1d1a16", dark="#0d0c0a",
                         light="#2b2721", scale=8.0)
    return SHADOW


def shield(name, T, w, h, mat, border=None, d=0.13):
    """Heraldic escutcheon: tapered top edge, pointed base, optional border."""
    hw, hh = w * 0.5, h * 0.5
    pts = [(0.0, -hh), (hw * 0.94, -hh * 0.28), (hw, hh * 0.52), (hw, hh),
           (-hw, hh), (-hw, hh * 0.52), (-hw * 0.94, -hh * 0.28)]
    out = [H.prism(name + "_f", T, pts, d, mat, axis="y")]
    if border is not None:
        bp = [(0.0, -hh - 0.10), (hw + 0.09, -hh * 0.26), (hw + 0.11, hh * 0.54),
              (hw + 0.11, hh + 0.10), (-hw - 0.11, hh + 0.10),
              (-hw - 0.11, hh * 0.54), (-hw - 0.09, -hh * 0.26)]
        out.insert(0, H.prism(name + "_b", T @ Ts(0, -0.05, 0), bp, d * 0.7, border,
                              axis="y"))
    # small boss in the middle
    out.append(K.sphere(name + "_n", T @ Ts(0, d * 0.5 + 0.02, h * 0.06), w * 0.11,
                        border or mat, seg=10, ring=6))
    return out


# ---------------------------------------------------------------------------
# masonry details the kit does not have
# ---------------------------------------------------------------------------
def slit(name, T, mat, dark=None, h=1.5, w=0.34, bev=0.012):
    """Arrow loop: stone surround with a genuinely recessed dark slot.

    H.window_slit puts its dark box *inside* its own stone block, so it renders
    as a protruding fin with no visible opening.  This one frames an actual
    recess: four jamb stones proud of the wall, a slot set 0.1 m behind them,
    and an iron crosslet bar in front of the slot.  `dark` is accepted for
    call-site compatibility but always resolves to the shared shadow material.
    """
    dark = shadow_mat()
    out = []
    j = 0.075
    for s in (-1, 1):
        out.append(bx("%s_j%d" % (name, s), T @ Ts(s * (w * 0.5 + j), 0, 0),
                      (j * 2, 0.22, h + 0.30), mat, bev=bev))
    for s in (-1, 1):
        out.append(bx("%s_l%d" % (name, s), T @ Ts(0, 0, s * (h * 0.5 + j)),
                      (w + 0.30, 0.22, j * 2), mat, bev=bev))
    out.append(bx(name + "_d", T @ Ts(0, -0.055, 0), (w, 0.13, h), dark))
    out.append(bx(name + "_x", T @ Ts(0, 0.045, h * 0.12), (w + 0.16, 0.07, 0.075), dark))
    return out


def corbel_bell(name, T, r_base, r_top, z, mat, courses=5, course_h=0.30,
                splay=0.12, seg=32, nblk=14):
    """A turret carried on a real corbel table.

    Each course steps out and the underside of every step is a splayed soffit.
    The course face itself is built as separate stones around the ring, not a
    turned cylinder: a smooth cone with rings reads as a wedding cake, blocks
    with vertical joints read as cantilevered masonry.
    """
    out = []
    dr = (r_top - r_base) / courses
    for k in range(courses):
        r = r_base + dr * k
        out.append(cyl("%s_sp%d" % (name, k),
                       T @ Ts(0, 0, z + course_h * k + splay * 0.5),
                       max(0.2, r - 0.20), splay, mat, seg=seg, r2=r))
        # core ring keeps daylight from showing between the blocks
        out.append(cyl("%s_cc%d" % (name, k),
                       T @ Ts(0, 0, z + course_h * k + splay * 0.5 + course_h * 0.5),
                       max(0.2, r - 0.16), course_h * 0.98, mat, seg=seg))
        for i in range(nblk):
            a = 2.0 * math.pi * i / nblk
            out.append(bx("%s_bk%d_%d" % (name, k, i),
                          T @ Ts(r * math.cos(a), r * math.sin(a),
                                 z + course_h * k + splay * 0.5 + course_h * 0.5,
                                 rz=a - math.pi * 0.5),
                          (2.0 * math.pi * r / nblk * 0.84, 0.30, course_h * 0.94),
                          mat, bev=0.012))
    # the last course is the springer: a taller drum the shaft sits on
    r = r_top
    out.append(cyl("%s_ring" % name, T @ Ts(0, 0, z + course_h * courses
                                             + splay * 0.5 + 0.16),
                   r + 0.10, 0.34, mat, seg=seg))
    return out


def corbel_row(name, T, length, mat, step=0.92, w=0.34, d=0.62, h=0.5):
    """Row of corbels along local X, projecting toward +Y."""
    out = []
    n = max(1, int(length / step))
    for i in range(n):
        x = -length * 0.5 + (i + 0.5) * length / n
        out.append(bx("%s_cb%d" % (name, i), T @ Ts(x, d * 0.5, 0),
                      (w, d, h), mat, bev=0.02))
        out.append(bx("%s_nb%d" % (name, i), T @ Ts(x, d * 0.5, -h * 0.55),
                      (w * 0.72, d * 0.55, h * 0.4), mat, bev=0.015))
    return out


def round_mach(name, T, r, z, mat, n=24, ring_h=1.0, merl=14, merl_h=1.35):
    """Machicolated gallery wrapped round a drum tower at height z.

    Returns (objects, merlon_top_z) -- the caller needs the top so the roof
    cone can be seated above the merlons instead of through them.
    """
    out = []
    for i in range(n):
        a = 2.0 * math.pi * i / n
        out.append(bx("%s_cb%d" % (name, i), rmat(T, a, r, z - 0.55),
                      (0.34, 0.72, 1.1), mat, bev=0.02))
        out.append(bx("%s_nb%d" % (name, i), rmat(T, a, r, z - 1.02),
                      (0.26, 0.5, 0.3), mat, bev=0.015))
    out.append(cyl(name + "_gal", T @ Ts(0, 0, z + ring_h * 0.35), r + 0.62,
                   ring_h + 0.5, mat, seg=40))
    for i in range(merl):
        a = 2.0 * math.pi * i / merl
        out.append(bx("%s_m%d" % (name, i), tmat(T, a, r + 0.62, z + ring_h + 0.72),
                      (0.98, 0.56, merl_h), mat, bev=0.025))
    return out, z + ring_h + 0.72 + merl_h * 0.5


def cone_cap(name, T, r, z, mat, h, seg=8, ring_mat=None, finial=True,
             gold=None):
    """Cone roof seated on a merlon ring, with a stone coping band between.

    The coping is the point: the merlon ring is square in plan and the cone is
    round, so without a band wide enough to cover the merlon corners the slate
    is cut by a ring of grey teeth at the eave -- which is exactly what the
    first renders showed on every tower.
    """
    out = [cyl(name + "_cop", T @ Ts(0, 0, z + 0.14), r + 0.22, 0.32,
               ring_mat or mat, seg=48),
           cyl(name + "_cop2", T @ Ts(0, 0, z - 0.06), r + 0.06, 0.24,
               ring_mat or mat, seg=48)]
    out += H.spire(name + "_sp", T @ Ts(0, 0, z + 0.30), r, h, mat, seg=seg)
    # tile courses: thin proud rings up the cone.  A bare slate cone is a
    # featureless grey triangle from any distance, and these are the only
    # silhouette elements above 30 m.
    ncr = 7
    for i in range(1, ncr):
        f = i / float(ncr)
        rr = r * (1.0 - f) + 0.055
        out.append(cyl("%s_cr%d" % (name, i), T @ Ts(0, 0, z + 0.30 + h * f),
                       rr, 0.11, ring_mat or mat, seg=seg))
    if finial:
        top = z + 0.30 + h
        out.append(cyl(name + "_fn", T @ Ts(0, 0, top - 0.35), 0.08, 1.0,
                       ring_mat or mat, seg=8))
        out.append(K.sphere(name + "_fb", T @ Ts(0, 0, top + 0.30), 0.20,
                            gold or mat, seg=12, ring=8))
    return out



def rose(name, T, r, stone, glass, lobes=12, depth=0.5, seg=40):
    """Wheel window in the local XZ plane, facing +Y."""
    out = []
    out.append(cyl(name + "_gl", T @ Ts(0, -0.16, 0, rx=math.pi * 0.5),
                   r * 0.97, 0.07, glass, seg=seg))
    out.append(cyl(name + "_gl2", T @ Ts(0, 0.02, 0, rx=math.pi * 0.5),
                   r * 0.97, 0.05, glass, seg=seg))
    # stone ring (radial voussoirs)
    n = 26
    for i in range(n):
        a = 2.0 * math.pi * (i + 0.5) / n
        out.append(bx("%s_rv%d" % (name, i),
                      T @ Ts(math.cos(a) * r * 1.06, 0.0, math.sin(a) * r * 1.06,
                             ry=math.pi * 0.5 - a),
                      (r * 0.26, depth, r * 0.30), stone, bev=0.015))
    # spokes
    for i in range(lobes):
        a = 2.0 * math.pi * (i + 0.5) / lobes
        out.append(bx("%s_sp%d" % (name, i),
                      T @ Ts(math.cos(a) * r * 0.5, 0.06, math.sin(a) * r * 0.5,
                             ry=math.pi * 0.5 - a),
                      (0.85, 0.20, r * 0.22), stone, bev=0.012))
        out.append(bx("%s_sp2%d" % (name, i),
                      T @ Ts(math.cos(a) * r * 0.5, 0.06, math.sin(a) * r * 0.5,
                             ry=math.pi * 0.5 - a),
                      (r * 0.28, 0.17, 0.72), stone, bev=0.012))
    out.append(cyl(name + "_hub", T @ Ts(0, 0.10, 0, rx=math.pi * 0.5),
                   r * 0.20, 0.34, stone, seg=18))
    # projecting hood ring: without it the wheel sinks into the wall and reads
    # as a painted disc from more than ten metres away
    nh = 30
    for i in range(nh):
        a = 2.0 * math.pi * (i + 0.5) / nh
        out.append(bx("%s_hd%d" % (name, i),
                      T @ Ts(math.cos(a) * r * 1.30, 0.14, math.sin(a) * r * 1.30,
                             ry=math.pi * 0.5 - a),
                      (r * 0.30, depth * 0.72, r * 0.34), stone, bev=0.018))
    for i in range(lobes * 2):
        a = 2.0 * math.pi * i / (lobes * 2)
        out.append(cyl("%s_lb%d" % (name, i),
                       T @ Ts(math.cos(a) * r * 0.82, 0.08, math.sin(a) * r * 0.82,
                              rx=math.pi * 0.5),
                       r * 0.10, 0.26, stone, seg=10))
    return out


def chain(name, p0, p1, sag, mat, n=13, r=0.055):
    """Sagging chain from p0 to p1, built from short links."""
    p0, p1 = Vector(p0), Vector(p1)
    out = []

    def P(t):
        p = p0.lerp(p1, t)
        p.z -= sag * math.sin(math.pi * t)
        return p

    for i in range(n):
        a, b = P(i / n), P((i + 1) / n)
        d = b - a
        q = d.normalized().to_track_quat("Z", "Y")
        out.append(K.cyl("%s_l%d" % (name, i),
                         Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4(),
                         r, d.length * 1.12, mat, seg=6))
    return out


def portcullis(name, T, half_w, z0, z1, iron, nbars=9, nrows=4):
    """Forged herse: square bars with forged spikes, horizontal rails, a
    rivetted band on every second rail, and the rivet heads themselves.

    Plain boxes read as a wire fence at 25 m; the read comes from the bands and
    the rivets catching light along the grid.
    """
    out = []
    for i in range(nbars):
        x = -half_w + 2 * half_w * i / (nbars - 1)
        out.append(bx("%s_v%d" % (name, i), T @ Ts(x, 0, (z0 + z1) * 0.5),
                      (0.15, 0.15, z1 - z0), iron, bev=0.012))
        # forged collar and spike below each bar
        out.append(bx("%s_vc%d" % (name, i), T @ Ts(x, 0, z0 + 0.30),
                      (0.21, 0.21, 0.22), iron, bev=0.02))
        out.append(K.cone("%s_p%d" % (name, i), T @ Ts(x, 0, z0 - 0.12, rx=math.pi),
                          0.115, 0.26, iron, seg=6))
    for k in range(nrows):
        z = z0 + (z1 - z0) * (k + 0.5) / nrows
        out.append(bx("%s_h%d" % (name, k), T @ Ts(0, -0.03, z),
                      (half_w * 2 + 0.2, 0.12, 0.13), iron, bev=0.01))
        if k % 2 == 0:
            # rivetted strap over every second rail
            out.append(bx("%s_hb%d" % (name, k),
                          T @ Ts(0, -0.10, z), (half_w * 2 - 0.1, 0.06, 0.30),
                          iron, bev=0.012))
            for i in range(nbars):
                x = -half_w + 2 * half_w * i / (nbars - 1)
                for sy in (-1, 1):
                    out.append(bx("%s_hv%d_%d_%d" % (name, k, i, sy),
                                  T @ Ts(x + sy * 0.055, -0.14, z + 0.075),
                                  (0.055, 0.05, 0.055), iron, bev=0.0))
        for i in range(nbars):
            x = -half_w + 2 * half_w * i / (nbars - 1)
            out.append(bx("%s_j%d_%d" % (name, k, i), T @ Ts(x, -0.06, z),
                          (0.20, 0.07, 0.20), iron, bev=0.0))
    # top strap and the two lifting eyes the chains ride on
    out.append(bx("%s_top" % name, T @ Ts(0, -0.03, z1 - 0.10),
                  (half_w * 2 + 0.24, 0.16, 0.20), iron, bev=0.012))
    for s in (-1, 1):
        out.append(cyl("%s_eye%d" % (name, s),
                       T @ Ts(s * half_w * 0.62, -0.03, z1 + 0.16, rx=math.pi * 0.5),
                       0.09, 0.14, iron, seg=10))
    return out


def arch_prism(name, T, half_w, spring, height, depth, mat):
    """Solid block over a round-headed opening (the intrados is the arc)."""
    pts = []
    n = 20
    for i in range(n + 1):
        x = -half_w + 2.0 * half_w * i / n
        pts.append((x, spring + math.sqrt(max(0.0, half_w * half_w - x * x))))
    pts.append((half_w, height))
    pts.append((-half_w, height))
    return H.prism(name, T, pts, depth, mat, axis="y")


def voussoirs(name, T, half_w, spring, mat, seg=15, r_in=0.18, r_out=0.62,
              depth=0.66, y=0.0, h=None, w_scale=1.0):
    """Ring of arch stones on the local XY->XZ plane (arc centred on z=spring)."""
    out = []
    hm = h if h is not None else (r_out - r_in)
    for i in range(seg):
        a = math.pi * (i + 0.5) / seg
        R = half_w + (r_in + r_out) * 0.5
        x = R * math.cos(a)
        z = spring + R * math.sin(a)
        out.append(bx("%s_v%d" % (name, i),
                      T @ Ts(x, y, z, ry=math.pi * 0.5 - a),
                      ((r_out - r_in) * 1.16 * w_scale, depth, hm * 1.04),
                      mat, bev=0.018))
    return out


_ARCH_CENTRE = 0.34                     # c/hw of the two-centred arch
_ARCH_RISE = math.sqrt((1.0 + _ARCH_CENTRE) ** 2 - _ARCH_CENTRE ** 2)


def _win_outline(hw, z0, spring, n=9):
    """Closed (x,z) outline of a two-centred arched opening, CCW from bottom left.

    The left arc springs at (-hw, spring) from a centre at (+c, spring) and the
    right arc mirrors it, so the two arcs cross at the apex -- a proper Gothic
    pointed head rather than a semicircle.
    """
    c = hw * _ARCH_CENTRE
    R = c + hw
    amax = math.acos(c / R)
    pts = [(-hw, z0), (hw, z0), (hw, spring)]
    for i in range(n + 1):                # right half, centre (-c, spring)
        a = amax * i / n
        pts.append((-c + R * math.cos(a), spring + R * math.sin(a)))
    for i in range(1, n + 1):             # left half, centre (+c, spring)
        a = amax * (1.0 - i / n)
        pts.append((c - R * math.cos(a), spring + R * math.sin(a)))
    return pts


def win(name, T, w, h, frame, glass, dark=None, mull=2, transom=1, hood=True,
        sill=True, spring_frac=0.80, **kw):
    """Arched window built ENTIRELY in front of the wall plane.
    (Accepts and ignores the kit's `depth`/`arch` keywords, which do nothing
    here because nothing is sunk.)

    H.window_arched sinks its glass `depth` behind the wall face, so on a solid
    wall all you ever see is its flat dark back plate flush with the masonry --
    the opening reads as a painted rectangle and the tracery disappears.  This
    one stacks outward instead:

        +0.02 dark reveal (full silhouette, one prism)
        +0.06 glass        (one prism, the mullions divide it visually)
        +0.11 mullions, transoms, lead cames
        +0.14 jambs, voussoirs, sill
        +0.26 hood mould + label stops

    Nothing is buried, and the frame thrown 0.3-0.5 m off the wall casts a
    shadow onto the reveal that reads as depth at any distance.  Local +Y is
    outward, so it drops into every call site the kit version occupied.
    """
    out = []
    hw = w * 0.5
    z0 = -h * 0.5
    spring = z0 + h * spring_frac
    rise = _ARCH_RISE * hw
    dk = dark or shadow_mat()
    out.append(H.prism(name + "_bk", T @ Ts(0, 0.035, 0),
                       _win_outline(hw + 0.20, z0 - 0.16, spring), 0.07, dk, axis="y"))
    out.append(H.prism(name + "_gl", T @ Ts(0, 0.075, 0),
                       _win_outline(hw - 0.01, z0 + 0.06, spring), 0.06, glass, axis="y"))
    # lead cames across the lights (skipped where a transom already sits, or
    # they stack into a double line)
    nrow = max(2, int((spring - z0) / 1.05))
    tz = [z0 + (spring - z0) * (0.40 + 0.42 * k) for k in range(transom)]
    for k in range(nrow):
        z = z0 + (spring - z0) * (k + 0.5) / nrow
        if any(abs(z - t) < 0.24 for t in tz):
            continue
        out.append(bx("%s_cam%d" % (name, k), T @ Ts(0, 0.13, z),
                      (2 * hw - 0.14, 0.05, 0.045), frame, bev=0.0))
    # lead quarry lattice: without it the glass is a flat plastic pane at any
    # distance under 20 m
    if w >= 1.15:
        nmq = max(1, mull)
        lw = w / nmq
        nq = max(2, int((spring - z0) / 0.62))
        for i in range(nmq):
            xc = (i + 0.5) * lw - hw
            for k in range(nq):
                z = z0 + 0.30 + k * (spring - z0 - 0.30) / max(1, nq - 1)
                if z > spring - 0.10:
                    continue
                for s in (-1, 1):
                    out.append(bx("%s_lq%d_%d_%d" % (name, i, k, s),
                                  T @ Ts(xc, 0.115, z, ry=s * math.pi * 0.25),
                                  (lw * 1.45, 0.03, 0.030), frame, bev=0.0))
    # mullions (straight + into the arch head) and transoms
    nm = max(1, mull)
    for i in range(1, nm):
        x = i * w / nm - hw
        out.append(bx("%s_mu%d" % (name, i), T @ Ts(x, 0.14, z0 + (spring - z0) * 0.5),
                      (0.15, 0.17, spring - z0), frame, bev=0.012))
        out.append(bx("%s_mc%d" % (name, i), T @ Ts(x, 0.14, spring + rise * 0.34),
                      (0.13, 0.15, rise * 0.62), frame, bev=0.012))
    for k in range(transom):
        z = z0 + (spring - z0) * (0.40 + 0.42 * k)
        out.append(bx("%s_tr%d" % (name, k), T @ Ts(0, 0.15, z),
                      (2 * hw, 0.17, 0.15), frame, bev=0.014))
    # jambs up to the springing
    for s in (-1, 1):
        out.append(bx("%s_j%d" % (name, s), T @ Ts(s * (hw + 0.17), 0.16,
                                                   (z0 + spring) * 0.5 - 0.08),
                      (0.34, 0.26, spring - z0 + 0.30), frame, bev=0.02))
    # sill, mensa slope, and corbelled ends
    if sill:
        out.append(bx(name + "_si", T @ Ts(0, 0.18, z0 - 0.16),
                      (w + 1.00, 0.44, 0.22), frame, bev=0.024))
        out.append(bx(name + "_ss", T @ Ts(0, 0.15, z0 - 0.33),
                      (w + 0.78, 0.34, 0.12), frame, bev=0.018))
        for s in (-1, 1):
            out.append(bx("%s_sc%d" % (name, s), T @ Ts(s * (hw - 0.30), 0.15, z0 - 0.50),
                          (0.26, 0.30, 0.26), frame, bev=0.014))
    # arch ring (voussoirs) + hood mould, two-centred, block by block
    c = hw * _ARCH_CENTRE
    R = c + hw
    amax = math.acos(c / R)
    nv = 5
    for s in (1, -1):
        for i in range(nv):
            a = (i + 0.5) / nv * amax
            rr = R + 0.17
            px = s * (-c + rr * math.cos(a))
            pz = spring + rr * math.sin(a)
            ry = -a if s > 0 else a
            blk = rr * amax / nv * 1.16
            out.append(bx("%s_v%d_%d" % (name, s, i), T @ Ts(px, 0.17, pz, ry=ry),
                          (0.32, 0.34, blk), frame, bev=0.016))
            if hood:
                rh = R + 0.46
                hx = s * (-c + rh * math.cos(a))
                hz = spring + rh * math.sin(a)
                out.append(bx("%s_h%d_%d" % (name, s, i), T @ Ts(hx, 0.24, hz, ry=ry),
                              (0.26, 0.34, blk * 1.08), frame, bev=0.016))
    if hood:
        for s in (-1, 1):
            out.append(bx("%s_hs%d" % (name, s), T @ Ts(s * (hw + 0.34), 0.24, spring - 0.30),
                          (0.30, 0.34, 0.66), frame, bev=0.02))
    # keystone: the two arcs meet in a sharp point, and without a block over it
    # the apex reads as a dark V-shaped hole
    out.append(bx(name + "_key", T @ Ts(0, 0.195, spring + rise + 0.30),
                  (0.40, 0.40, 0.64), frame, bev=0.02))
    return out


def flag(name, T, w, h, cloth, pole_mat, ph, amp=0.26, seg=7, notch=0.24,
         droop=0.14, rows=6):
    """Pole at T flying a rippling cloth with a swallow tail.

    H.banner's cloth is a flat card offset from the pole, which on the towers
    read as a slab floating beside the stone.  This lofts a sheet whose fly end
    travels in a wave, sags under its own weight, and is cut into a swallow tail
    -- three things that stop a flag reading as a coloured post-it.
    """
    out = [cyl(name + "_p", T @ Ts(0, 0, ph * 0.5), 0.105, ph, pole_mat, seg=10)]
    out.append(K.sphere(name + "_k", T @ Ts(0, 0, ph + 0.11), 0.155, pole_mat, seg=10,
                        ring=6))
    out.append(bx(name + "_bar", T @ Ts(w * 0.5 + 0.05, 0, ph - 0.07),
                  (w + 0.18, 0.07, 0.07), pole_mat))
    verts, faces = [], []
    for i in range(seg + 1):
        u = i / float(seg)
        cut = 1.0 - notch * math.sin(math.pi * (min(0.999, max(0.001, u)) ** 1.6))
        for j in range(rows):
            v = j / float(rows - 1)
            x = u * w * cut
            y = amp * math.sin(u * 4.6 - v * 0.7) * (0.22 + 0.78 * u) \
                + 0.06 * math.sin(v * 3.0) * u
            z = ph - 0.13 - v * h - droop * u * u * (0.4 + 0.6 * v)
            verts.append((x, y, z))
    for i in range(seg):
        for j in range(rows - 1):
            a = i * rows + j
            b = (i + 1) * rows + j
            faces.append((a, b, b + 1, a + 1))
    out.append(H.poly(name + "_cl", verts, faces, cloth, T=T))
    return out


def banner3(name, T, w, h, cloth, pole_mat, pole_h=None, **kw):
    """Swap-in for H.banner: same call shape, but the cloth is `flag`'s lofted
    sheet instead of the kit's flat card (which reads as a coloured post-it)."""
    ph = pole_h if pole_h else (h * 1.16 + 0.55)
    return flag(name, T, w, h, cloth, pole_mat, ph, **kw)


def tower_hanging(name, T, r, ang, w_ang, z_top, h, cloth, iron, n=9):
    """Cloth hung against a round tower: folded, scalloped, and shut.

    A single-sided sheet with no fold modulation is indistinguishable from a
    painted card once the sun is off it, so this lofts two shells 0.08 m apart
    with the radius breathing in and out across the width (folds read in the
    shading) and a V-cut hem.
    """
    verts, faces = [], []
    cols = n + 1
    rows = 5
    for layer, off in ((0, 0.0), (1, 0.085)):
        for i in range(cols):
            u = i / float(n)
            a = ang + (u - 0.5) * w_ang
            fold = 0.075 * math.cos(u * math.pi * 5.0)
            rr = r + 0.10 + off + fold
            hem = 0.26 * math.sin(math.pi * u) * (1 if i % 2 == 0 else 0.55)
            for j in range(rows):
                v = j / float(rows - 1)
                z = z_top - v * (h - hem)
                # a slight outward flare at the bottom, like real hanging cloth
                rr2 = rr + 0.05 * v
                verts.append((math.cos(a) * rr2, math.sin(a) * rr2, z))
    base = cols * rows
    for i in range(n):
        for j in range(rows - 1):
            a = i * rows + j
            b = (i + 1) * rows + j
            faces.append((a, b, b + 1, a + 1))
            A, B = a + base, b + base
            faces.append((A + 1, B + 1, B, A))
    for i in range(n):
        a = i * rows
        b = (i + 1) * rows
        faces.append((a, b, b + base, a + base))
        a2 = i * rows + rows - 1
        b2 = (i + 1) * rows + rows - 1
        faces.append((a2 + base, b2 + base, b2, a2))
    out = [H.poly(name + "_cl", verts, faces, cloth, T=T)]
    # top bar + two iron rings
    out.append(bx(name + "_bar", rmat(T, ang, r + 0.12, z_top + 0.06),
                  (2.0 * r * math.tan(w_ang * 0.5), 0.10, 0.10), iron))
    for k in (-1, 1):
        out.append(bx("%s_rg%d" % (name, k),
                      rmat(T, ang + k * w_ang * 0.40, r + 0.10, z_top - 0.06),
                      (0.11, 0.18, 0.18), iron, bev=0.01))
    out.append(bx(name + "_fin", rmat(T, ang, r + 0.16, z_top + 0.22),
                  (0.07, 0.07, 0.34), iron))
    return out


def tiled_roof(name, T, w, d, eave_z, pitch, tile, deck, course_h=0.55,
               verge=0.5, ov=0.42, crest=False, rolls=0,
               hip_f=0.0, hip_b=0.0, stone=None):
    """Gable or hipped roof, ridge along local Y, courses lying IN the slope.

    H.roof's course slabs are lifted 0.055 above the surface and run out to the
    roof's overhang plane, so at each gable the ends read as a fan of separated
    blades.  Here the courses are near-continuous ribs sunk into the surface and
    a deep rake board caps their ends at the gable.

    hip_f / hip_b pull the ridge in from the +Y / -Y end, producing a genuine
    hipped face there (its own courses, its own arris rolls) instead of a gable.
    `stone` swaps a gable end for a stone parapet gable standing proud of the
    tiles -- the difference between a French chateau roof and an English tower.
    """
    hw = w * 0.5 + verge
    hd = d * 0.5 + ov
    rh = hw * math.tan(math.radians(pitch))
    pr = math.radians(pitch)
    out = []
    hipped = (hip_f > 0.05 or hip_b > 0.05)
    if not hipped:
        out.append(K.gable_roof(name + "_c", T, w, d, eave_z, pitch, tile, deck,
                                ov_side=verge, ov_gable=ov))
    else:
        # deck as two slope slabs; the hip faces get their own backings below
        dd = 2 * hd - (hip_f + hip_b) * 0.55
        for s in (-1, 1):
            out.append(bx("%s_dk%d" % (name, s + 1),
                          T @ Ts(s * hw * 0.5, 0, eave_z + rh * 0.5 - 0.06,
                                 ry=s * pr),
                          (math.hypot(hw, rh) * 1.02, dd, 0.20), deck, bev=0.01))
    sl = math.hypot(hw, rh)
    n = max(2, int(sl / course_h))
    step = sl / n
    for i in range(n):
        # t runs from the eave (0) to the ridge (1): x shrinks as z rises.
        # Each rib is a course LIP: 0.10 thick, lifted 0.05, so its lower edge
        # throws the shadow line that makes tiling read at 25 m.  A 5 cm rib
        # vanished completely and the roof came out as a smooth grey tent.
        t = (i + 0.5) / n
        x = hw * (1.0 - t)
        z = eave_z + rh * t
        yc = (hip_b - hip_f) * t * 0.5
        run = (2 * hd - (hip_f + hip_b) * t) - 0.34
        for s in (-1, 1):
            out.append(bx("%s_tc%d_%d" % (name, i, s + 1),
                          T @ Ts(s * x, yc, z + 0.050, ry=s * pr),
                          (step * 0.90, run, 0.10), tile, bev=0.008))
    for s in (-1, 1):
        # eave fascia board, then a deep rake board over the tile ends
        out.append(bx("%s_ev%d" % (name, s + 1),
                      T @ Ts(s * hw, 0, eave_z - 0.07),
                      (0.13, d + 2 * ov, 0.34), deck, bev=0.018))
        if hipped:
            pass            # rake boards only exist on gable ends (see below)
        for sy in (-1, 1):
            if (sy > 0 and hip_f > 0.05) or (sy < 0 and hip_b > 0.05):
                continue
            out.append(bx("%s_rb%d_%d" % (name, s + 1, sy + 1),
                          T @ Ts(s * hw * 0.5, sy * (d * 0.5 + ov - 0.05),
                                 eave_z + rh * 0.5,
                                 ry=math.atan2(-rh, -s * hw)),
                          (sl * 1.03, 0.15, 0.40), deck, bev=0.018))
    # ---- hipped faces: courses running ACROSS the slope, their own deck
    for sy in (-1, 1):
        hp = hip_f if sy > 0 else hip_b
        if hp <= 0.05:
            continue
        hl = math.hypot(hp, rh)
        nh = max(2, int(hl / course_h))
        hstep = hl / nh
        ang = math.atan2(rh, -sy * hp)
        ye = sy * hd
        for j in range(nh):
            t = (j + 0.5) / nh
            xw = hw * (1.0 - t)
            z = eave_z + rh * t
            yy = ye - sy * hp * t
            out.append(bx("%s_hb%d_%d" % (name, sy + 1, j),
                          T @ Ts(0, yy, z - 0.045, rx=ang),
                          (2 * xw * 1.04, hstep * 1.02, 0.16), deck, bev=0.008))
            out.append(bx("%s_hc%d_%d" % (name, sy + 1, j),
                          T @ Ts(0, yy, z + 0.050, rx=ang),
                          (2 * xw * 0.95, hstep * 0.88, 0.10), tile, bev=0.006))
        # fascia along the hip eave + the two arris rolls up to the ridge
        out.append(bx("%s_hf%d" % (name, sy + 1),
                      T @ Ts(0, ye, eave_z - 0.07), (2 * hw + 0.1, 0.13, 0.32),
                      deck, bev=0.018))
        for s in (-1, 1):
            out += chain("%s_hr%d_%d" % (name, sy + 1, s + 1),
                         (s * hw, ye, eave_z + 0.10),
                         (0, ye - sy * hp, eave_z + rh + 0.10), 0.04, deck, n=12, r=0.13)
    # ---- stone parapet gable on any end that is not hipped
    if stone is not None:
        for sy in (-1, 1):
            if (sy > 0 and hip_f > 0.05) or (sy < 0 and hip_b > 0.05):
                continue
            gp = 0.52
            ye = sy * (d * 0.5 + ov - 0.10)
            pts = [(-hw - 0.18, eave_z - 0.06), (hw + 0.18, eave_z - 0.06),
                   (0, eave_z + rh + gp)]
            out.append(H.prism("%s_sg%d" % (name, sy + 1), T @ Ts(0, ye, 0), pts,
                               0.56, stone, axis="y"))
            # coping on both rakes and a finial over the apex
            for s in (-1, 1):
                out.append(bx("%s_sgc%d_%d" % (name, sy + 1, s + 1),
                              T @ Ts(s * (hw + 0.18) * 0.5, ye,
                                     eave_z + (rh + gp) * 0.5 + 0.10,
                                     ry=math.atan2(rh + gp, s * (hw + 0.18))),
                              (math.hypot(hw + 0.18, rh + gp), 0.66, 0.24),
                              deck, bev=0.02))
            out.append(H.pinnacle("%s_sgf%d" % (name, sy + 1),
                                  T @ Ts(0, ye, eave_z + rh + gp - 0.30), 0.44, 1.30,
                                  stone))
    if rh > 0.35:
        rl = d + 2 * ov - (hip_f + hip_b)
        out.append(bx(name + "_rg", T @ Ts(0, (hip_b - hip_f) * 0.5, eave_z + rh + 0.09),
                      (0.52, rl + 0.04, 0.24), deck, bev=0.025))
        nr = max(2, int(rl / 2.3))
        for k in range(nr):
            out.append(cyl("%s_rc%d" % (name, k),
                           T @ Ts(0, (hip_b - hip_f) * 0.5 - rl * 0.5
                                  + (k + 0.5) * rl / nr,
                                 eave_z + rh + 0.22),
                           0.23, 0.30, tile, seg=10))
    if crest:
        nc = max(3, int(w / 1.5))
        for k in range(nc):
            x = -w * 0.5 + (k + 0.5) * w / nc
            zt = eave_z + rh * (1 - abs(x) / hw)
            out.append(H.pinnacle("%s_cr%d" % (name, k), T @ Ts(x, 0, zt + 0.2),
                                  0.34, 1.15, deck))
    if rolls:
        # lead roof: rolls batten the slope from eave to ridge.  Without them a
        # big slate slope is one flat card from the air, whatever its courses do.
        rr = d + 2 * ov - (hip_f + hip_b)
        for k in range(rolls):
            y = (hip_b - hip_f) * 0.5 - rr * 0.5 + (k + 0.5) * rr / rolls
            for s in (-1, 1):
                out.append(bx("%s_rl%d_%d" % (name, k, s + 1),
                              T @ Ts(s * hw * 0.5, y, eave_z + rh * 0.5 + 0.10,
                                     ry=s * pr),
                              (sl * 0.99, 0.15, 0.13), deck, bev=0.01))
    return out


# ---------------------------------------------------------------------------
# ground platform + curtain wall
# ---------------------------------------------------------------------------
def build_base(parts, MAT):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    # courtyard platform: the whole outline, lifted to CY
    pts = [(x, y) for (x, y) in OUTLINE]
    parts.append(H.prism("base_floor", Ts(0, 0, CY - 0.18), pts, 0.36, S2, axis="z"))
    # recessed paving border so the platform reads as built, not extruded
    parts.append(H.prism("base_floor2", Ts(0, 0, CY - 0.30), pts, 0.30, S, axis="z"))
    # plinth ring under every run, proud of the wall foot
    n = len(OUTLINE)
    for i in range(n - 1):
        A, B = Vector(OUTLINE[i]), Vector(OUTLINE[i + 1])
        T, L = seg_frame(A, B)
        parts.append(bx("base_p%d_a" % i, T @ Ts(0, 0.55, 0.30),
                        (L + 3.0, WALL_T + 2.6, 0.60), S, bev=0.03))
        parts.append(bx("base_p%d_b" % i, T @ Ts(0, 0.30, 0.82),
                        (L + 2.2, WALL_T + 1.7, 0.44), S, bev=0.025))


def build_wall_run(parts, MAT, A, B, i, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    DK = MAT["iron"]
    T, L = seg_frame(A, B)
    nm = "w%d" % i

    # ---- wall body: coursed ashlar from the plinth to the walk.  The curtain
    # runs a cooler stone than the keep, so the hero mass reads in front of it.
    parts += H.wall_course(nm + "_c", T @ Ts(0, 0, 0.9), L + 1.4, WALL_T,
                          WALL_H - 0.9, S2)
    # ---- base batter (two offsets)
    parts.append(bx(nm + "_bt0", T @ Ts(0, 0.0, 1.35), (L + 1.2, WALL_T + 0.55, 0.9), S2,
                    bev=0.02))
    # ---- walkway deck + coping
    parts.append(bx(nm + "_deck", T @ Ts(0, 0, WALL_H + 0.07), (L + 1.4, WALL_T - 0.5, 0.16),
                    S2, bev=0.015))
    # ---- string course under the parapet
    parts.append(bx(nm + "_sc", T @ Ts(0, 0.10, WALL_H - 0.55), (L + 1.5, WALL_T + 0.32, 0.30),
                    S, bev=0.02))
    parts += corbel_row(nm + "_ct", T @ Ts(0, WALL_T * 0.5 + 0.16, WALL_H - 0.95),
                            L + 0.8, S, step=0.95, w=0.32, d=0.5, h=0.4)
    # ---- outer crenellation (local +Y is outside)
    parts += H.crenel(nm + "_cr", T @ Ts(0, WALL_T * 0.5 - 0.28, WALL_H + 0.15), L + 1.2,
                      merlon=1.05, gap=0.62, h=1.35, depth=0.64, mat=S)
    # ---- inner parapet (low, so the courtyard reads as enclosed)
    parts.append(bx(nm + "_ip", T @ Ts(0, -(WALL_T * 0.5 - 0.22), WALL_H + 0.52),
                    (L + 1.2, 0.44, 0.9), S, bev=0.02))
    parts.append(bx(nm + "_ipc", T @ Ts(0, -(WALL_T * 0.5 - 0.22), WALL_H + 1.0),
                    (L + 1.3, 0.52, 0.1), S2, bev=0.02))
    # ---- flow joints in the walk deck, so it reads as laid slabs
    nj = max(2, int(L / 1.35))
    for k in range(1, nj):
        parts.append(bx("%s_wj%d" % (nm, k),
                        T @ Ts(-L * 0.5 + k * L / nj, 0, WALL_H + 0.16),
                        (0.05, WALL_T - 0.55, 0.02), shadow_mat(), bev=0.0))

    # ---- bretèches: only where a castle actually needs them -- one either side
    # of the gate, and a garderobe on the rear wall.  Hanging two identical
    # boxes on every long run is what made the earlier version look mechanical.
    if i in (0, 9, 5):
        lat = (i == 5)
        bw = rng.uniform(1.15, 1.35) if lat else rng.uniform(1.62, 2.10)
        proj = rng.uniform(1.00, 1.22) if lat else rng.uniform(0.95, 1.30)
        xx = (L * 0.20) if lat else (-L * rng.uniform(0.18, 0.32))
        nb2 = "%s_bre" % nm
        BT = T @ Ts(xx, -(WALL_T * 0.5 + proj * 0.5 + 0.22), WALL_H + 0.28)
        for j in range(3):
            xo = -bw * 0.31 + j * bw * 0.31
            parts.append(bx(nb2 + "_c%d" % j, BT @ Ts(xo, 0.30 * proj, -0.62),
                            (0.32, 0.86 * proj, 0.78), S2, bev=0.02))
            parts.append(bx(nb2 + "_c2%d" % j, BT @ Ts(xo, 0.55 * proj, -1.02),
                            (0.24, 0.54 * proj, 0.44), S2, bev=0.015))
            parts.append(bx(nb2 + "_c3%d" % j, BT @ Ts(xo, 0.78 * proj, -1.36),
                            (0.20, 0.32 * proj, 0.26), S2, bev=0.012))
        parts.append(bx(nb2 + "_bx", BT @ Ts(0, 0.02, 0.34), (bw, proj + 0.44, 0.92), S,
                        bev=0.03))
        parts.append(bx(nb2 + "_cr", BT @ Ts(0, 0.02, 0.98), (bw + 0.16, proj + 0.58, 0.22),
                        S2, bev=0.02))
        parts.append(bx(nb2 + "_sl", BT @ Ts(0, 0.06, -0.09),
                        (bw * 0.57, proj * 0.36, 0.12), shadow_mat(), bev=0.0))
        parts += slit(nb2 + "_lp", BT @ Ts(0, -proj * 0.5 - 0.28, 0.40, rz=math.pi), S, DK,
                      h=0.78)
        parts.append(bx(nb2 + "_sh", BT @ Ts(0, -0.05, -0.28), (bw - 0.1, 0.12, 0.10), S2,
                        bev=0.01))
        if lat:
            # garderobe chute: the shaft dropping down the wall face, with the
            # dark discharge opening at its foot
            for j in range(4):
                parts.append(bx(nb2 + "_ch%d" % j,
                                BT @ Ts(0, -proj * 0.16, -1.55 - j * 0.92),
                                (0.86 - j * 0.055, 0.58 - j * 0.03, 0.96), S2,
                                bev=0.014))
            parts.append(bx(nb2 + "_cho", BT @ Ts(0, -proj * 0.16, -5.35),
                            (0.62, 0.46, 0.22), shadow_mat(), bev=0.0))
            parts.append(bx(nb2 + "_chs", BT @ Ts(0, -proj * 0.14, -5.50),
                            (0.84, 0.62, 0.16), S2, bev=0.012))

    # ---- timber pentice over the walk on two runs: covered passage, and from
    # the air it breaks the long grey ribbon of the wall-walk
    # NOTE: a timber pentice over the walk was tried here and removed -- on a
    # 10.6 m curtain wall its ridge cleared the merlons from outside, where it
    # read as a broken shed roof stuck to the battlements.  The bretèches and
    # the deck joints carry the "military passage" reading on their own.

    # ---- buttresses outside
    nb = max(2, int(round(L / 6.2)))
    for k in range(nb):
        x = -L * 0.5 + (k + 0.5) * L / nb
        parts += H.buttress("%s_bu%d" % (nm, k), T @ Ts(x, WALL_T * 0.5, 0), 7.4, 1.45,
                            3, S)
        parts.append(bx("%s_buc%d" % (nm, k), T @ Ts(x, WALL_T * 0.5 + 0.55, 8.4),
                        (1.1, 1.7, 0.22), S, bev=0.025))

    # ---- arrow loops on the outer face, two rows
    ns = max(2, int(round(L / 3.6)))
    for k in range(ns):
        x = -L * 0.5 + (k + 0.5) * L / ns
        for j, z in enumerate((4.35, 7.55)):
            parts += slit("%s_sl%d_%d" % (nm, k, j),
                          T @ Ts(x, WALL_T * 0.5 - 0.02, z), S, MAT["iron"],
                          h=1.45 if j == 0 else 1.15)
    # ---- a postern door in one run
    if i == 6:
        parts += H.door_arched(nm + "_post", T @ Ts(0, -WALL_T * 0.5 + 0.15, CY),
                               1.9, 2.9, MAT["wood_dark"], MAT["iron"], S, steps=0)

    # ---- banner poles on the walk
    if i % 3 == 1:
        for k, (x, col) in enumerate(((0.0, "banner_red"),)):
            parts += banner3("%s_bn%d" % (nm, k), T @ Ts(x, -0.9, WALL_H + 1.6),
                              1.5, 3.4, MAT[col], MAT["wood_dark"], pole_h=5.4)


def build_curtain(parts, MAT, rng):
    n = len(OUTLINE)
    for i in range(n - 1):
        build_wall_run(parts, MAT, Vector(OUTLINE[i]), Vector(OUTLINE[i + 1]), i, rng)
    # a vaulted lean-to arcade along six runs: the four front runs the player
    # walks through, plus the two rear runs that frame the service side of the
    # yard.  Blind arches, a real row of piers and a tiled pent roof: this is
    # what turns a flat inner wall face into architecture.
    for i in (0, 1, 2, 6, 8, 9):
        inner_arcade(parts, MAT, Vector(OUTLINE[i]), Vector(OUTLINE[i + 1]), rng, i)


def inner_arcade(parts, MAT, A, B, rng, i):
    """Open arcade: piers + arches on the courtyard side, blind arched recesses
    on the wall, lean-to tiled pent roof between them."""
    T, L = seg_frame(A, B)
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    TL = MAT["tile_blue"]
    SH = shadow_mat()
    bays = max(3, int(L / 3.45))
    bw = L / bays
    dy = -WALL_T * 0.5                 # inner face of the curtain wall
    depth = 2.55
    yf = dy - depth                    # front line of the arcade
    hw = bw * 0.5 - 0.34               # clear half width of one bay
    spring = CY + 3.30                 # arch springing
    apex = spring + hw * _ARCH_RISE
    # raised floor with a step, so the arcade sits a little above the yard
    parts.append(bx("ac_fl%d" % i, T @ Ts(0, yf + depth * 0.5 + 0.08, CY + 0.10),
                    (L - 0.2, depth + 0.30, 0.20), S2, bev=0.012))
    parts.append(bx("ac_fs%d" % i, T @ Ts(0, yf - 0.16, CY + 0.06),
                    (L - 0.2, 0.20, 0.12), S, bev=0.02))

    def arch_ring(nm, TT, hwv, spring, blocks=6, r_in=0.10, r_out=0.58, nscale=1.0):
        """Radial voussoir ring following the two-centred arch of the opening."""
        cc = hwv * _ARCH_CENTRE
        RR = cc + hwv
        am = math.acos(cc / RR)
        out = []
        for s in (1, -1):
            for k in range(blocks):
                a = (k + 0.5) / blocks * am
                rr = RR + r_in
                px = s * (-cc + rr * math.cos(a))
                pz = spring + rr * math.sin(a)
                blk = rr * am / blocks * 1.14
                out.append(bx("%s_v%d_%d" % (nm, s, k),
                              TT @ Ts(px, 0.0, pz, ry=(-a if s > 0 else a)),
                              (0.34 * nscale, 0.42, blk), S, bev=0.014))
                if r_out > 0.0:
                    rh = RR + r_out
                    out.append(bx("%s_h%d_%d" % (nm, s, k),
                                  TT @ Ts(s * (-cc + rh * math.cos(a)), 0.0,
                                          spring + rh * math.sin(a),
                                          ry=(-a if s > 0 else a)),
                                  (0.28 * nscale, 0.38, blk * 1.06), S2, bev=0.014))
        return out

    for k in range(bays + 1):
        x = -L * 0.5 + k * bw
        # front pier, plinth and capital
        parts.append(bx("ac_p%d_%d" % (i, k), T @ Ts(x, yf + 0.30, CY + 1.86),
                        (0.66, 0.68, 3.66), S, bev=0.02))
        parts.append(bx("ac_pb%d_%d" % (i, k), T @ Ts(x, yf + 0.30, CY + 0.26),
                        (0.84, 0.86, 0.36), S2, bev=0.022))
        parts.append(bx("ac_pc%d_%d" % (i, k), T @ Ts(x, yf + 0.30, CY + 3.52),
                        (0.80, 0.82, 0.24), S2, bev=0.024))
        # small corbel under each capital
        parts.append(bx("ac_pk%d_%d" % (i, k), T @ Ts(x, yf + 0.30, CY + 3.32),
                        (0.56, 0.58, 0.18), S2, bev=0.02))
    for k in range(bays):
        x = -L * 0.5 + (k + 0.5) * bw
        # the arch itself: a recessed dark arch head behind the pier line
        pts = _win_outline(hw, CY + 0.22, spring, 7)
        parts.append(H.prism("ac_ar%d_%d" % (i, k),
                             T @ Ts(x, dy - 0.62, 0), pts, 0.66, SH, axis="y"))
        parts += arch_ring("ac_a%d_%d" % (i, k), T @ Ts(x, yf + 0.30, 0),
                           hw, spring, 6, 0.02, 0.52)
        # jambs down the two sides of the opening
        for s in (-1, 1):
            parts.append(bx("ac_j%d_%d_%d" % (i, k, s),
                            T @ Ts(x + s * (hw + 0.16), yf + 0.30,
                                   (CY + 0.22 + spring) * 0.5),
                            (0.32, 0.42, spring - CY - 0.22), S, bev=0.014))
        # keystone
        parts.append(bx("ac_ak%d_%d" % (i, k),
                        T @ Ts(x, yf + 0.30, apex + 0.24),
                        (0.34, 0.42, 0.56), S, bev=0.02))
    # lean-to roof: one sloped slab plus tile courses, rising toward the wall
    rz = math.atan2(0.62, depth)
    sl = math.sqrt(depth * depth + 0.62 * 0.62)
    parts.append(bx("ac_rf%d" % i, T @ Ts(0, (yf + dy) * 0.5 + 0.10,
                                          CY + 5.86, rx=rz),
                    (L, sl + 0.5, 0.16), TL, bev=0.01))
    ncr = max(3, int(L / 1.15))
    for k in range(ncr):
        tt = (k + 0.5) / ncr
        parts.append(bx("ac_rc%d_%d" % (i, k),
                        T @ Ts(-L * 0.5 + tt * L, (yf + dy) * 0.5 + 0.10,
                               CY + 5.96, rx=rz),
                        (L / ncr * 0.90, sl + 0.5, 0.10), WD, bev=0.006))
    parts.append(bx("ac_fe%d" % i, T @ Ts(0, yf - 0.06, CY + 5.66),
                    (L, 0.22, 0.34), S2, bev=0.02))
    parts.append(bx("ac_fr%d" % i, T @ Ts(0, dy - 0.10, CY + 6.26),
                    (L, 0.30, 0.28), S2, bev=0.02))
    # ---- furniture: an arcade that stands empty reads as a facade, not a place
    for k in range(bays):
        x = -L * 0.5 + (k + 0.5) * bw
        zf = CY + 0.20
        if k % 4 == 0:
            parts.append(bx("ac_tb%d_%d" % (i, k), T @ Ts(x, yf + 1.35, zf + 0.72),
                            (1.85, 0.86, 0.12), WD, bev=0.012))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    parts.append(bx("ac_tl%d_%d_%d_%d" % (i, k, sx, sy),
                                    T @ Ts(x + sx * 0.78, yf + 1.35 + sy * 0.32,
                                           zf + 0.36),
                                    (0.14, 0.14, 0.72), WD, bev=0.006))
            for sy in (-1, 1):
                parts.append(bx("ac_bn%d_%d_%d" % (i, k, sy),
                                T @ Ts(x, yf + 1.35 + sy * 0.92, zf + 0.42),
                                (1.85, 0.26, 0.10), WD, bev=0.008))
        elif k % 4 == 1:
            for j in range(2):
                parts += H.barrel("ac_br%d_%d_%d" % (i, k, j),
                                  T @ Ts(x - 0.42 + j * 0.84, yf + 1.30, zf),
                                  0.30, 0.80, MAT["wood"], IR)
        elif k % 4 == 2:
            parts.append(bx("ac_cr%d_%d" % (i, k), T @ Ts(x, yf + 1.15, zf + 0.42),
                            (1.05, 0.85, 0.84), MAT["wood"], bev=0.02))
            parts.append(bx("ac_cb%d_%d" % (i, k), T @ Ts(x, yf + 1.15, zf + 0.88),
                            (1.12, 0.92, 0.10), MAT["wood"], bev=0.02))
    # a lantern bracket on every fourth pier, and a bowl of coals beneath it
    for k in range(0, bays + 1, 4):
        x = -L * 0.5 + k * bw
        parts.append(bx("ac_lb%d_%d" % (i, k), T @ Ts(x, yf - 0.06, CY + 3.30),
                        (0.10, 0.55, 0.10), IR, bev=0.0))
        parts.append(bx("ac_ln%d_%d" % (i, k), T @ Ts(x, yf - 0.28, CY + 3.10),
                        (0.26, 0.26, 0.34), MAT["gold"], bev=0.01))
        parts.append(cyl("ac_lf%d_%d" % (i, k), T @ Ts(x, yf - 0.28, CY + 3.06),
                         0.09, 0.10, fire_mat(), seg=8))


def build_corner_towers(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    caps = {2: ("slate", "cone"), 3: ("tile", "cone"),
            7: ("slate", "cone"), 8: ("tile", "cone")}
    for k, vi in enumerate(TOWER_AT):
        x, y = OUTLINE[vi]
        r = TOWER_R
        h = 17.4 + 0.6 * (k % 2)
        T = Ts(x, y, 0)
        nm = "tw%d" % k
        # base: battered drum
        parts.append(cyl(nm + "_bat", T @ Ts(0, 0, 1.1), r * 1.20, 2.2, S, seg=40,
                         r2=r * 1.02))
        parts.append(cyl(nm + "_shoe", T @ Ts(0, 0, 0.22), r * 1.30, 0.44, S, seg=40))
        # shaft
        parts.append(cyl(nm + "_sh", T @ Ts(0, 0, 2.2 + (h - 2.2) * 0.5), r,
                         h - 2.2, S, seg=40))
        # string courses
        for j in range(3):
            z = h * (0.30 + 0.21 * j)
            parts.append(cyl("%s_bc%d" % (nm, j), T @ Ts(0, 0, z), r * 1.035, 0.22, S2, seg=40))
            parts.append(cyl("%s_bc2%d" % (nm, j), T @ Ts(0, 0, z + 0.20), r * 1.055, 0.10, S,
                             seg=40))
        # arrow loops, 3 bands
        for j, z in enumerate((4.6, 8.4, 12.2)):
            for a in range(6):
                ang = 2.0 * math.pi * a / 6 + j * 0.52
                parts += slit("%s_sl%d_%d" % (nm, j, a), rmat(T, ang, r - 0.02, z),
                              S, MAT["iron"], h=1.35)
        # door onto the wall walk, courtyard side
        ang = math.atan2(-y, -x)
        parts.append(bx(nm + "_dw", rmat(T, ang, r - 0.05, WALL_H + 1.0),
                        (1.7, 0.5, 2.6), MAT["wood_dark"]))
        parts += voussoirs(nm + "_dva", rmat(T, ang, r - 0.05, 0.0), 1.0, WALL_H + 2.3, S,
                           seg=9, r_in=0.2, r_out=0.55, depth=0.55, y=0.0)
        # head: corbelled gallery, coping, then the roof
        pm, mt = round_mach(nm + "_mc", T, r, h + 0.8, S, n=26, ring_h=0.9, merl=15)
        parts += pm
        cap, kind = caps[vi]
        if kind == "cone":
            parts += cone_cap(nm, T, r * 1.30, mt, MAT[cap], r * 3.1, seg=8,
                              ring_mat=S2, gold=MAT["gold"])
        else:
            parts += cone_cap(nm, T, r * 1.32, mt, MAT[cap], r * 3.0, seg=32,
                              ring_mat=S2, gold=MAT["gold"])
        # flag off the cap, on the town side of the tower
        fh = mt + 0.30 + r * 3.1 - 0.4
        parts += flag(nm + "_bn", T @ Ts(0, 0, fh), 1.9, 2.6,
                      MAT["banner_blue"], MAT["iron"], 4.6)


# ---------------------------------------------------------------------------
# gatehouse - the hero view
# ---------------------------------------------------------------------------
def gate_tower(parts, MAT, x, y, r, h, nm, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    IR = MAT["iron"]
    T = Ts(x, y, 0)
    parts.append(cyl(nm + "_shoe", T @ Ts(0, 0, 0.30), r * 1.26, 0.60, S, seg=44))
    parts.append(cyl(nm + "_bat", T @ Ts(0, 0, 1.45), r * 1.14, 2.3, S, seg=44, r2=r))
    parts.append(cyl(nm + "_sh", T @ Ts(0, 0, 2.6 + (h - 2.6) * 0.5), r, h - 2.6, S, seg=44))
    for j in range(4):
        z = h * (0.26 + 0.175 * j)
        parts.append(cyl("%s_bc%d" % (nm, j), T @ Ts(0, 0, z), r * 1.03, 0.24, S2, seg=44))
        parts.append(cyl("%s_bd%d" % (nm, j), T @ Ts(0, 0, z + 0.21), r * 1.05, 0.11, S, seg=44))
    # arrow loops, 4 bands, denser than the curtain towers
    for j, z in enumerate((3.9, 7.4, 10.9, 14.4)):
        for a in range(6):
            ang = 2.0 * math.pi * a / 6 + j * 0.52
            parts += slit("%s_sl%d_%d" % (nm, j, a), rmat(T, ang, r - 0.02, z), S, IR, h=1.5)
    # tall traceried windows on the city face, two storeys
    for j, z in enumerate((9.0, 14.2)):
        for a in (-0.30, 0.0, 0.30):
            ang = math.atan2(y, x) + a
            parts += win("%s_win%d_%d" % (nm, j, int(a * 100)),
                                     rmat(T, ang, r - 0.05, z), 0.95, 2.0, S, MAT["glass"],
                                     mull=1, hood=True, depth=0.4)
    pm, mt = round_mach(nm + "_mc", T, r, h + 0.9, S, n=28, ring_h=0.95, merl=16)
    parts += pm
    # slate spire, seated on a coping ring above the merlon heads
    parts += cone_cap(nm, T, r * 1.24, mt, MAT["slate"], r * 3.3, seg=8,
                      ring_mat=S2, gold=MAT["gold"])
    # banners front and back
    ang = math.atan2(y, x)
    parts += flag(nm + "_bnf", T @ Ts(0, 0, mt + 0.10 + r * 3.30), 2.1, 2.9,
                  MAT["banner_red"], MAT["iron"], 5.6)
    parts += tower_hanging(nm + "_bnb", T, r, ang + math.pi, 0.62, h * 0.80, 3.4,
                           MAT["banner_gold"], MAT["iron"])
    parts += tower_hanging(nm + "_bnc", T, r, ang + math.pi, -0.62, h * 0.80, 3.4,
                           MAT["banner_blue"], MAT["iron"])


def barbican(MAT, rng, y0, y1, hw, deck_hw):
    """An outwork beyond the moat: gate block on its own island, two projecting
    drum towers, low crenellated flank walls, its own raised herse, and a stair
    down to the road.  This is the first thing the player walks through, so it
    gets the same facade logic as the main gate, one scale down.

    Returns its OWN list: a helper that appends into the caller's list and
    returns it silently doubles every object when the caller does `parts +=`.
    """
    parts = []
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    WD = MAT["wood_dark"]
    W = MAT["wood"]
    IR = MAT["iron"]
    GL = MAT["glass"]
    SH = shadow_mat()

    BX = hw
    D = y1 - y0
    yc = (y0 + y1) * 0.5
    GW = 4.90                  # gate-block half width
    BH = 11.0                  # gate-block height
    OWB = 2.30                 # passage half width
    SWB = 4.30                 # springing

    # ---------- island: plinth out of the moat, paved deck, kerb
    parts.append(bx("b_isl", Ts(0, yc, CY * 0.5 + 0.02), (2 * BX, D, CY + 0.04), S2, bev=0.02))
    parts.append(bx("b_isk", Ts(0, yc, 0.26), (2 * BX + 0.8, D + 0.8, 0.52), S, bev=0.03))
    for s in (-1, 1):
        for k in range(3):
            parts.append(bx("b_pv%d_%d" % (s, k), Ts(s * (deck_hw + 0.85 + k * 1.12), yc,
                                                     CY + 0.05), (1.02, D - 0.24, 0.10),
                            S2, bev=0.0))
        parts.append(bx("b_ker%d" % s, Ts(s * (BX - 0.16), yc, CY + 0.22),
                        (0.34, D, 0.38), S, bev=0.02))
    # ---------- flank walls: crenellated parapets either side of the gate block
    for s in (-1, 1):
        wl = BX - GW
        parts.append(bx("b_fl%d" % s, Ts(s * (GW + wl * 0.5), yc, 4.30),
                        (wl, D, 8.60), S))
        parts.append(bx("b_flc%d" % s, Ts(s * (GW + wl * 0.5), yc, 8.72),
                        (wl + 0.24, D + 0.24, 0.24), S2, bev=0.02))
        parts += H.crenel("b_flm%d" % s, Ts(s * (GW + wl * 0.5), y1 - 0.26, 8.84),
                          wl * 0.98, merlon=0.76, gap=0.48, h=1.18, depth=0.48, mat=S)
        for j in range(2):
            parts += slit("b_fls%d_%d" % (s, j),
                          Ts(s * (GW + 0.55 + j * 1.35), y1 + 0.02, 5.4), S, IR, h=1.15)
        # corner pier terminating the flank wall
        parts.append(bx("b_cp%d" % s, Ts(s * (BX - 0.45), y1 - 0.45, 4.9),
                        (1.30, 1.30, 9.8), S, bev=0.02))
        parts.append(bx("b_cpc%d" % s, Ts(s * (BX - 0.45), y1 - 0.45, 9.92),
                        (1.58, 1.58, 0.26), S2, bev=0.02))
        parts += H.pinnacle("b_cpp%d" % s, Ts(s * (BX - 0.45), y1 - 0.45, 10.05),
                            0.62, 1.9, S2)

    # ---------- gate block: piers, head over the arch, passage
    for s in (-1, 1):
        w = GW - OWB
        parts.append(bx("b_pier%d" % s, Ts(s * (OWB + w * 0.5), yc, BH * 0.5),
                        (w, D, BH), S))
        for j in range(5):
            parts.append(bx("b_pc%d_%d" % (s, j), Ts(s * (OWB + w * 0.5), y1 + 0.02,
                                                     1.30 + j * 2.05),
                            (w + 0.34, 0.16, 1.90), S2, bev=0.015))
        parts.append(bx("b_q%d" % s, Ts(s * GW, y1 + 0.03, BH * 0.5),
                        (0.30, 0.20, BH), S2, bev=0.012))
    parts.append(arch_prism("b_head", Ts(0, yc, 0), OWB, SWB, BH, D, S))
    # passage floor, ribs, herse slot
    parts.append(bx("b_tfl", Ts(0, yc, CY + 0.06), (2 * OWB - 0.08, D, 0.20), S2, bev=0.0))
    for k in range(2):
        parts += voussoirs("b_rib%d" % k, Ts(0, y0 + 1.35 + k * 1.95, 0), OWB, SWB, S,
                           seg=15, r_in=0.0, r_out=0.26, depth=0.30)
    parts.append(bx("b_slot", Ts(0, y1 - 0.95, SWB + OWB - 0.30),
                    (2 * OWB + 0.1, 0.85, 1.30), SH))
    parts += portcullis("b_pc", Ts(0, y1 - 0.98, 0), 1.86, 3.05, 6.55, IR, nbars=10, nrows=3)
    for s in (-1, 1):
        parts.append(bx("b_pcg%d" % s, Ts(s * 2.02, y1 - 0.98, 5.1), (0.14, 0.26, 3.6), S2))
        # torch cressets in the passage
        parts.append(bx("b_tbr%d" % s, Ts(s * (OWB - 0.16), y0 + 2.4, CY + 2.30),
                        (0.18, 0.22, 0.16), IR))
        parts.append(cyl("b_tst%d" % s, Ts(s * (OWB - 0.32), y0 + 2.4, CY + 2.30,
                                           rz=math.pi * 0.5), 0.045, 0.36, IR, seg=6))
        parts.append(H.sphere("b_tgl%d" % s, Ts(s * (OWB - 0.50), y0 + 2.4, CY + 2.44),
                              0.10, fire_mat(), 8))
    # murder hole over the passage
    parts.append(bx("b_mh", Ts(0, y0 + 2.9, SWB + OWB - 0.34), (0.86, 0.70, 0.40), SH,
                    bev=0.0))
    for j in range(3):
        parts.append(bx("b_mhg%d" % j, Ts(-0.28 + j * 0.28, y0 + 2.9,
                                          SWB + OWB - 0.22), (0.05, 0.72, 0.05), IR,
                        bev=0.0))

    # ---------- outer facade: voussoirs, hood, keystone, string, window, arms
    parts += voussoirs("b_ova", Ts(0, y1 - 0.10, 0), OWB, SWB, S, seg=13, r_in=0.0,
                       r_out=0.54, depth=0.72)
    parts += voussoirs("b_ohd", Ts(0, y1 + 0.04, 0), OWB, SWB, S2, seg=13, r_in=0.66,
                       r_out=0.88, depth=0.36)
    parts.append(bx("b_key", Ts(0, y1 + 0.08, SWB + OWB + 0.62), (0.44, 0.44, 0.86), S2,
                    bev=0.02))
    for s in (-1, 1):
        parts.append(bx("b_pil%d" % s, Ts(s * (OWB + 0.52), y1 + 0.16, SWB * 0.5 + 0.5),
                        (0.48, 0.38, SWB + 0.9), S, bev=0.02))
    parts.append(bx("b_fr", Ts(0, y1 + 0.12, SWB + OWB + 1.30),
                    (2 * GW - 0.4, 0.36, 0.36), S2, bev=0.02))
    for k in range(7):
        parts.append(bx("b_frc%d" % k, Ts(-3.9 + k * 1.3, y1 + 0.24,
                                          SWB + OWB + 1.06), (0.42, 0.52, 0.16), S2,
                        bev=0.014))
    for k, xw in enumerate((-1.34, 0.0, 1.34)):
        parts += win("b_win%d" % k, Ts(xw, y1 - 0.02, 8.30), 0.98, 2.20, S2, GL,
                     mull=1, hood=True, depth=0.40)
    for s in (-1, 1):
        parts += shield("b_sh%d" % s, Ts(s * 3.06, y1 + 0.10, 8.72), 1.05, 1.24,
                        MAT["banner_red"] if s < 0 else MAT["banner_blue"],
                        MAT["gold"] if s < 0 else MAT["banner_gold"])
        parts.append(bx("b_shp%d" % s, Ts(s * 3.06, y1 + 0.01, 8.72),
                        (1.34, 0.10, 1.50), SH, bev=0.0))
    # ---------- machicolation + corbels over the gate, crenels on the block top
    parts += H.machicolation("b_mach", Ts(0, y1 - 0.30, BH), 2 * GW + 0.3, S,
                             h=1.05, depth=0.92)
    for s in (-1, 1):
        parts += H.machicolation("b_machb%d" % s,
                                 Ts(s * (GW + 0.02), yc, BH, rz=s * math.pi * 0.5),
                                 D, S, h=1.05, depth=0.90)
    # ---------- inner face: the yard side of the barbican
    parts += voussoirs("b_iva", Ts(0, y0 + 0.02, 0), OWB, SWB, S, seg=13, r_in=0.02,
                       r_out=0.52, depth=0.44, w_scale=0.9)
    parts.append(bx("b_isc", Ts(0, y0 - 0.10, 7.30), (2 * GW - 0.3, 0.30, 0.30), S2,
                    bev=0.02))

    # ---------- the twin towers, projecting past the island edge
    gate_tower(parts, MAT, 5.50, y1 - 1.55, 2.45, 14.2, "b_tl", rng)
    gate_tower(parts, MAT, -5.50, y1 - 1.55, 2.45, 14.2, "b_tr", rng)

    # ---------- stair from the barbican deck down to the road, and the apron
    for k in range(5):
        parts.append(bx("b_st%d" % k, Ts(0, y1 + 0.18 + k * 0.26, CY - 0.13 - k * 0.26),
                        (2 * deck_hw, 0.30, 0.30), S2, bev=0.012))
    parts.append(bx("b_apr", Ts(0, y1 + 1.15, 0.09), (2 * deck_hw + 2.4, 0.95, 0.18), S2,
                    bev=0.02))
    for s in (-1, 1):
        parts.append(bx("b_apk%d" % s, Ts(s * (deck_hw + 0.9), y1 + 1.15, 0.30),
                        (0.60, 0.95, 0.60), S, bev=0.02))
    # lanterns either side of the outer arch, standing on the island itself
    for s in (-1, 1):
        parts += H.lantern_post("b_lp%d" % s, Ts(s * (OWB + 1.15), y1 - 0.35, CY + 0.02),
                                2.3, IR, MAT["gold"])
    # a guard bench and a barrel under the arch
    parts.append(bx("b_ben", Ts(3.35, y0 + 1.4, CY + 0.44), (0.52, 1.70, 0.14), W,
                    bev=0.014))
    for k in (-1, 1):
        parts.append(bx("b_benl%d" % k, Ts(3.35, y0 + 1.4 + k * 0.72, CY + 0.22),
                        (0.46, 0.16, 0.46), W, bev=0.012))
    parts += H.barrel("b_brl", Ts(-3.35, y0 + 1.25, CY + 0.02), 0.34, 0.86, W, IR)
    return parts


def gatehouse(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    GL = MAT["glass"]
    TL = MAT["tile"]
    SL = MAT["slate"]

    GX = GATE_HW
    YF, YB = GATE_YF, GATE_YB
    GH = 18.0          # gate block height
    OW = 3.4           # half width of the gate opening
    SPR = 6.2          # arch springing
    APEX = SPR + OW
    YC = (YF + YB) * 0.5
    DY = YF - YB

    # ---------- plinth and threshold
    parts.append(bx("g_pl0", Ts(0, YC + 0.15, 0.34), (2 * GX + 2.0, DY + 1.9, 0.68), S,
                    bev=0.03))
    parts.append(bx("g_pl1", Ts(0, YC + 0.10, 0.10), (2 * GX + 3.0, DY + 3.0, 0.34), S,
                    bev=0.03))

    # ---------- side piers (these are also the tunnel walls)
    for s in (-1, 1):
        w = GX - OW
        parts.append(bx("g_pier%d" % s, Ts(s * (OW + w * 0.5), YC, GH * 0.5),
                        (w, DY, GH), S))
    # banded courses + quoins on the pier faces
    for s in (-1, 1):
        for j in range(9):
            z = 0.9 + j * 1.85
            parts.append(bx("g_pc%d_%d" % (s, j), Ts(s * (OW + (GX - OW) * 0.5), YF + 0.02, z),
                            (GX - OW + 0.4, 0.16, 1.72), S2, bev=0.015))
    # ---------- solid above the arch, built as FOUR piers around a real
    # window opening.  A recess cut into a solid box is invisible: the wall
    # face hides it.  So the head is assembled from pieces that leave an
    # actual hole, and the reveal you see is the wall's own thickness.
    GWS, GWT, GWL = 10.90, 13.60, 2.50     # gate window sill / springing / half w

    def _arc(cx, r, zsp, x0, x1, n=16):
        out = []
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            d = max(r * r - (x - cx) ** 2, 0.0)
            out.append((x, zsp + math.sqrt(d)))
        return out

    def _prism(nm, pts, mat=S):
        parts.append(H.prism(nm, Ts(0, YC, 0), pts, DY, mat, axis="y"))

    GWL2 = GWL
    _prism("g_head_l", [(x, z) for x, z in _arc(0, OW, SPR, -OW, -GWL2)] +
           [(-GWL2, GH), (-OW, GH)])
    _prism("g_head_r", _arc(0, OW, SPR, GWL2, OW) + [(OW, GH), (GWL2, GH)])
    _prism("g_head_b", _arc(0, OW, SPR, -GWL2, GWL2) + [(GWL2, GWS), (-GWL2, GWS)])
    _prism("g_head_t", _arc(0, GWL2, GWT, -GWL2, GWL2) + [(GWL2, GH), (-GWL2, GH)])
    # ---------- yard-side arch face (inner facade)
    parts += voussoirs("g_iva", Ts(0, YB - 0.02, 0), OW, SPR, S, seg=15,
                       r_in=0.02, r_out=0.62, depth=0.5, w_scale=0.9)

    # ---------- outer facade: voussoirs, hood, mouldings
    parts += voussoirs("g_ova", Ts(0, YF - 0.10, 0), OW, SPR, S, seg=17,
                       r_in=0.0, r_out=0.66, depth=0.78)
    parts += voussoirs("g_hood", Ts(0, YF + 0.06, 0), OW, SPR, S2, seg=15,
                       r_in=0.80, r_out=1.05, depth=0.42)
    # pilaster strips flanking the arch
    for s in (-1, 1):
        parts.append(bx("g_pil%d" % s, Ts(s * (OW + 0.62), YF + 0.18, SPR * 0.5 + 0.6),
                        (0.55, 0.42, SPR + 1.0), S, bev=0.02))
        for j in range(4):
            parts.append(bx("g_pilc%d_%d" % (s, j), Ts(s * (OW + 0.62), YF + 0.22,
                                                      1.1 + j * 1.55),
                            (0.62, 0.46, 0.22), S2, bev=0.02))
    # ---------- facade above the arch: frieze, corbel course, window, heraldry
    SH = shadow_mat()
    parts.append(bx("g_fr", Ts(0, YF + 0.13, 9.86), (2 * GX - 0.3, 0.44, 0.50), S2,
                    bev=0.025))
    parts.append(bx("g_fr2", Ts(0, YF + 0.26, 10.20), (2 * GX - 0.2, 0.70, 0.22), S,
                    bev=0.03))
    for k in range(13):
        x = -12.6 + k * 2.1
        parts.append(bx("g_frc%d" % k, Ts(x, YF + 0.32, 10.44), (0.52, 0.80, 0.18), S2,
                        bev=0.02))
    # ---------- gate face: the guard-hall window, heraldry, chain anchors
    # The 6.5 m of wall between the arch head (9.6) and the machicolation
    # corbels (16.85) carries a five-light traceried window under a hood mould,
    # four shields, and the iron drums the drawbridge chains run to.  The four
    # g_head_* prisms above leave a genuine 5.0 x 5.2 m hole for it.
    WL, WS, WT = GWL, GWS, GWT
    WB = YF - 0.02                # wall face
    parts.append(bx("g_wsill", Ts(0, WB + 0.19, WS - 0.12), (2 * WL + 0.86, 0.62, 0.26),
                    S2, bev=0.03))
    for s in (-1, 1):
        for k in range(4):
            parts.append(bx("g_wsic%d_%d" % (s, k),
                            Ts(s * (0.60 + k * 1.27), WB + 0.28, WS - 0.34),
                            (0.30, 0.58, 0.22), S, bev=0.02))
    # glass lights, each struck with a diamond quarry lattice so it reads as
    # leaded glass rather than a flat blue card at close range
    nl = 5
    for k in range(nl):
        x = -WL + (k + 0.5) * (2 * WL / nl)
        lw = 2 * WL / nl - 0.40
        parts.append(bx("g_wgl%d" % k, Ts(x, YF - 0.62, (WS + 0.1 + WT) * 0.5),
                        (lw, 0.08, WT - WS - 0.2), GL))
        nb = 3
        for b in range(nb):
            zz = WS + 0.30 + b * (WT - WS - 0.6) / max(1, nb - 1)
            for sgn in (-1, 1):
                parts.append(bx("g_wq%d_%d_%d" % (k, b, sgn),
                                Ts(x, YF - 0.58, zz, ry=sgn * 0.785),
                                (0.05, 0.05, lw * 1.42), IR, bev=0.0))
    for k in range(nl - 1):
        x = -WL + (k + 1) * (2 * WL / nl)
        parts.append(bx("g_wmul%d" % k, Ts(x, YF - 0.52, (WS + WT) * 0.5),
                        (0.20, 0.28, WT - WS), S2, bev=0.014))
        parts.append(bx("g_wmph%d" % k, Ts(x, YF - 0.52, WT - 0.34),
                        (0.24, 0.30, 0.7), S2, bev=0.012))
    for zz in (11.95, 12.95):
        parts.append(bx("g_wtra%d" % int(zz * 10),
                        Ts(0, YF - 0.53, zz), (2 * WL - 0.1, 0.26, 0.18), S2, bev=0.014))
    # arch head: glass half-disc, radial tracery, voussoir ring, hood mould
    parts.append(cyl("g_wgh", Ts(0, YF - 0.62, WT, rx=math.pi * 0.5), WL - 0.06, 0.08, GL,
                     seg=28))
    for k in range(5):
        a = math.pi * (0.12 + 0.19 * k)
        parts.append(bx("g_wrad%d" % k,
                        Ts(math.cos(a) * WL * 0.5, YF - 0.58, WT + math.sin(a) * WL * 0.5,
                           rz=0.0, ry=math.pi * 0.5 - a),
                        (0.12, 0.10, WL * 0.98), IR, bev=0.0))
    # a dark plaster back wall behind the glass so the hole never reads as a tunnel
    parts.append(bx("g_wback", Ts(0, YF - 1.35, (WS + WT) * 0.5),
                    (2 * WL + 0.2, 0.20, WT - WS + 1.1), SH))
    parts.append(cyl("g_wbackh", Ts(0, YF - 1.35, WT, rx=math.pi * 0.5), WL + 0.1, 0.20, SH,
                     seg=24))
    parts += voussoirs("g_wv", Ts(0, WB + 0.08, WT), WL, 0.0, S2, seg=17, r_in=0.0,
                       r_out=0.36, depth=0.46)
    # hood mould: a stepped outer ring plus long label stops
    parts += voussoirs("g_whd", Ts(0, WB + 0.24, WT - 0.02), WL + 0.28, 0.0, S, seg=19,
                       r_in=0.16, r_out=0.32, depth=0.34)
    for s in (-1, 1):
        parts.append(bx("g_whs%d" % s, Ts(s * (WL + 0.38), WB + 0.28, WT - 0.66),
                        (0.40, 0.42, 0.62), S, bev=0.03))
    # frieze band + corbel course under the machicolation
    parts.append(bx("g_sc1", Ts(0, WB + 0.16, 16.46), (2 * GX - 0.4, 0.50, 0.24), S2,
                    bev=0.025))
    for s in (-1, 1):
        for k in range(4):
            parts.append(bx("g_sc1c%d_%d" % (s, k),
                            Ts(s * (1.15 + k * 1.62), WB + 0.26, 16.24),
                            (0.36, 0.62, 0.24), S, bev=0.02))
    # heraldry on the piers flanking the window
    for s in (-1, 1):
        for k in range(2):
            parts.append(bx("g_shp%d_%d" % (s, k),
                            Ts(s * 5.15, WB + 0.03, 11.55 + k * 2.40),
                            (1.14, 0.20, 1.44), SH))
            parts += shield("g_sh%d_%d" % (s, k), Ts(s * 5.15, WB + 0.24, 11.60 + k * 2.40),
                            0.80, 1.06,
                            (MAT["banner_red"], MAT["banner_blue"])[k],
                            MAT["gold"] if k == 0 else S2)
    # chain housings + iron drums on the gate face
    for s in (-1, 1):
        parts.append(bx("g_chh%d" % s, Ts(s * 6.14, YF + 0.14, 11.10), (0.90, 0.54, 1.10),
                        S2, bev=0.025))
        parts.append(cyl("g_chd%d" % s, Ts(s * 6.14, YF + 0.34, 11.10, ry=math.pi * 0.5),
                         0.30, 0.44, IR, seg=12))
        parts.append(bx("g_chp%d" % s, Ts(s * 6.14, YF + 0.44, 11.10), (0.62, 0.10, 0.62),
                        IR, bev=0.0))
    # ---------- tunnel: 12.4 m of barrel vault, floor, and vault ribs
    parts.append(bx("g_floor", Ts(0, YC, CY + 0.10), (2 * OW - 0.1, DY, 0.20), S2, bev=0.02))
    NRB = 5
    for k in range(NRB):
        y = YB + 1.6 + k * (DY - 3.0) / (NRB - 1)
        parts += voussoirs("g_rib%d" % k, Ts(0, y, 0), OW, SPR, S, seg=17,
                           r_in=0.0, r_out=0.30, depth=0.34)
    # ---------- murder holes in the vault: three dark slots in the crown, with
    # an iron grate in each.  A 12 m passage is only a room if the ceiling is
    # legible from below.
    for k, yy in enumerate((YB + 4.6, YB + 7.1, YB + 9.6)):
        parts.append(bx("g_mh%d" % k, Ts(0, yy, SPR + OW - 0.42),
                        (1.10, 0.86, 0.46), shadow_mat(), bev=0.0))
        for j in range(3):
            parts.append(bx("g_mhg%d_%d" % (k, j),
                            Ts(-0.36 + j * 0.36, yy, SPR + OW - 0.30),
                            (0.05, 0.90, 0.06), IR, bev=0.0))
        for j in range(2):
            parts.append(bx("g_mhb%d_%d" % (k, j),
                            Ts(0, yy - 0.24 + j * 0.48, SPR + OW - 0.30),
                            (1.10, 0.05, 0.06), IR, bev=0.0))
    # ---------- guard-room doors off the passage, one per side per end
    for s in (-1, 1):
        for j, yy in enumerate((YB + 2.6, YB + 8.4)):
            DD = Ts(s * (OW - 0.04), yy, CY, rz=-s * math.pi * 0.5)
            parts.append(bx("g_gd%d_%d" % (s, j), DD @ Ts(0, 0.02, 1.06),
                            (1.05, 0.14, 2.10), WD, bev=0.014))
            for m in range(4):
                parts.append(bx("g_gdp%d_%d_%d" % (s, j, m),
                                DD @ Ts(-0.38 + m * 0.25, 0.11, 1.06),
                                (0.09, 0.05, 2.02), WD, bev=0.006))
            parts.append(bx("g_gdb%d_%d" % (s, j), DD @ Ts(0, 0.12, 1.06),
                            (1.02, 0.05, 0.12), IR, bev=0.0))
            for m in (-1, 1):
                parts.append(bx("g_gdf%d_%d_%d" % (s, j, m),
                                DD @ Ts(m * 0.60, 0.05, 1.10), (0.16, 0.22, 2.28),
                                S2, bev=0.014))
            parts.append(bx("g_gdl%d_%d" % (s, j), DD @ Ts(0, 0.05, 2.28),
                            (1.36, 0.22, 0.18), S2, bev=0.014))
            # lamp bracket over each doorway
            parts.append(bx("g_gdlb%d_%d" % (s, j), DD @ Ts(0, 0.24, 2.56),
                            (0.16, 0.34, 0.10), IR, bev=0.0))
            parts.append(H.sphere("g_gdfl%d_%d" % (s, j),
                                  DD @ Ts(0, 0.40, 2.44), 0.10, fire_mat(), 8))
    # ---------- loopholes raking the passage walls
    for s in (-1, 1):
        for j, yy in enumerate((YB + 5.4, YB + 7.4, YB + 10.4)):
            parts += slit("g_plp%d_%d" % (s, j),
                          Ts(s * (OW - 0.02), yy, CY + 2.10, rz=-s * math.pi * 0.5),
                          S2, IR, h=0.86, w=0.24)
    # portcullis slot: dark recess above the raised grid
    parts.append(bx("g_slot", Ts(0, YF - 1.5, 10.30), (2 * OW + 0.1, 0.9, 1.5), shadow_mat()))
    # ---------- portcullis, HALF-RAISED: the grid hangs in the upper arch and
    # the tunnel vault ribs are visible through the opening below it
    parts += portcullis("g_pc", Ts(0, YF - 1.55, 0), 2.72, 6.05, 10.85, IR, nbars=14, nrows=4)
    for s in (-1, 1):
        parts.append(bx("g_pcg%d" % s, Ts(s * 2.86, YF - 1.55, 8.45), (0.16, 0.3, 5.1), S2))
    # ---------- SECOND portcullis, fully raised at the yard end: the slot, the
    # grid's lower 1.1 m and its guide rails read from inside the passage
    parts.append(bx("g_slot2", Ts(0, YB + 1.7, 10.55), (2 * OW + 0.1, 0.95, 1.7),
                    shadow_mat()))
    parts += portcullis("g_pc2", Ts(0, YB + 1.7, 0), 2.72, 7.60, 11.10, IR, nbars=12, nrows=3)
    for s in (-1, 1):
        parts.append(bx("g_pc2g%d" % s, Ts(s * 2.86, YB + 1.7, 8.90), (0.16, 0.3, 4.6), S2))
    # ---------- gate leaves, swung open against the tunnel walls
    for s in (-1, 1):
        M = Ts(s * (OW - 0.10), YB + 2.0, CY, rz=math.pi * 0.5)
        parts.append(bx("g_leaf%d" % s, M @ Ts(0, 0, 3.0), (3.9, 0.18, 5.95), WD, bev=0.02))
        for k in range(6):
            parts.append(bx("g_pl%d_%d" % (s, k), M @ Ts(-1.85 + k * 0.74, 0.10, 3.0),
                            (0.05, 0.06, 5.9), IR))
        for k in range(3):
            parts.append(bx("g_band%d_%d" % (s, k), M @ Ts(0, 0.10, 1.0 + k * 1.9),
                            (3.85, 0.06, 0.16), IR, bev=0.01))
        for k in range(10):
            parts.append(bx("g_stud%d_%d" % (s, k), M @ Ts(-1.69 + (k % 5) * 0.845,
                                                          0.12, 0.9 + (k // 5) * 4.2),
                            (0.09, 0.07, 0.09), IR))
    # ---------- herse gear that can actually be seen: a winch niche in each
    # side wall (drum, ratchet wheel, chain rising into the vault) plus the
    # transom beams and pulley drum that carry the inner grid.
    for s in (-1, 1):
        WV = Ts(s * (OW - 0.02), YF - 3.4, CY + 3.05, rz=-s * math.pi * 0.5)
        parts.append(bx("g_wnr%d" % s, WV @ Ts(0, 0.31, 0), (1.50, 0.64, 1.75),
                        shadow_mat(), bev=0.0))
        parts.append(bx("g_wns%d" % s, WV @ Ts(0, 0.06, -0.92), (1.72, 0.14, 0.16),
                        S2, bev=0.012))
        parts.append(bx("g_wns2%d" % s, WV @ Ts(0, 0.06, 0.92), (1.72, 0.14, 0.16),
                        S2, bev=0.012))
        parts.append(cyl("g_wnd%d" % s, WV @ Ts(0, 0.34, 0.06, rx=math.pi * 0.5),
                         0.24, 1.34, WD, seg=12))
        parts.append(cyl("g_wnw%d" % s, WV @ Ts(0.56, 0.34, 0.06, rx=math.pi * 0.5),
                         0.34, 0.12, IR, seg=14))
        for k in range(8):
            a = 2.0 * math.pi * k / 8
            parts.append(bx("g_wnk%d_%d" % (s, k),
                            WV @ Ts(0.56 + math.cos(a) * 0.28, 0.34,
                                    0.06 + math.sin(a) * 0.28, rx=math.pi * 0.5),
                            (0.10, 0.10, 0.18), IR, bev=0.0))
        parts.append(cyl("g_wnh%d" % s, WV @ Ts(0.24, 0.34, 0.62), 0.12, 0.30, WD, seg=8))
        for k in range(4):
            parts.append(bx("g_wcl%d_%d" % (s, k),
                            WV @ Ts(0.24, 0.34 - 0.02 * k, 0.96 + k * 0.28),
                            (0.09, 0.09, 0.24), IR, bev=0.0))
    for k in range(2):
        parts.append(bx("g_trb%d" % k, Ts(0, YB + 1.9 + k * 1.35, SPR + OW - 1.05),
                        (2 * OW + 0.16, 0.30, 0.30), WD, bev=0.02))
    parts.append(cyl("g_trd", Ts(0, YB + 2.55, SPR + OW - 0.90, rz=math.pi * 0.5),
                     0.22, 1.70, WD, seg=10))
    for s in (-1, 1):
        parts += chain("g_trc%d" % s, (s * 0.86, YB + 2.55, SPR + OW - 0.62),
                       (s * 0.86, YB + 1.75, 9.34), 0.05, IR, n=7, r=0.048)

    # ---------- tunnel interior: from the drawbridge the gate itself was a pure
    # black hole.  Pave it, rib it, and light it with two torches.
    parts.append(bx("g_tfl", Ts(0, YC - 0.2, CY - 0.14), (2 * OW - 0.12, DY - 0.5, 0.32),
                    S2, bev=0.0))
    for k in range(3):
        yy = YB + 1.5 + k * 2.2
        for j in range(9):
            a = math.pi * (j + 0.5) / 9.0
            rr = OW - 0.26
            parts.append(bx("g_tv%d_%d" % (k, j),
                            Ts(math.cos(a) * rr, yy, SPR + math.sin(a) * rr,
                               ry=math.pi * 0.5 - a),
                            (0.60, 0.40, 0.26), S2, bev=0.02))
    for s in (-1, 1):
        for k2 in range(2):
            yy = YB + 1.3 + k2 * 3.3
            parts.append(bx("g_tbr%d%d" % (s, k2), Ts(s * (OW - 0.34), yy, CY + 2.55),
                            (0.22, 0.26, 0.18), IR))
            parts.append(cyl("g_tst%d%d" % (s, k2),
                             Ts(s * (OW - 0.52), yy, CY + 2.55, rz=math.pi * 0.5),
                             0.05, 0.42, IR, seg=6))
            parts.append(cyl("g_tfi%d%d" % (s, k2), Ts(s * (OW - 0.74), yy, CY + 2.78),
                             0.19, 0.26, fire_mat(), seg=8))
            parts.append(H.sphere("g_tgl%d%d" % (s, k2),
                                  Ts(s * (OW - 0.74), yy, CY + 2.80), 0.085,
                                  fire_mat(), 8))

    # ---------- machicolation across the front + returns
    parts += H.machicolation("g_mach", Ts(0, YF - 0.35, GH), 2 * GX + 0.6, S,
                             h=1.15, depth=1.05)
    for s in (-1, 1):
        parts += H.machicolation("g_machb%d" % s,
                                 Ts(s * (GX + 0.05), YC, GH, rz=s * math.pi * 0.5),
                                 DY, S, h=1.15, depth=1.0)
    # ---------- rear machicolation over the courtyard face
    parts += H.machicolation("g_machr", Ts(0, YB + 0.3, GH, rz=math.pi), 2 * GX + 0.6, S,
                             h=1.0, depth=0.9)
    # ---------- yard-side face of the gate block: a 7 m blank band used to sit
    # above the inner arch.  String course + three windows + loops fix it, and
    # the yard is where the player walks, so it gets the same care as the front.
    parts.append(bx("g_isc", Ts(0, YB - 0.12, 10.30), (2 * GX + 0.4, 0.32, 0.34), S2,
                    bev=0.02))
    for s in (-1, 1):
        parts.append(bx("g_isc%d" % s, Ts(s * (GX - 2.2), YB - 0.10, 10.30),
                        (0.34, 0.30, 0.34), S2, bev=0.02))
    for k, xw in enumerate((-8.4, 0.0, 8.4)):
        parts += win("g_iw%d" % k, Ts(xw, YB - 0.02, CY + 12.55, rz=math.pi), 2.0, 3.4,
                     S2, GL, mull=2, hood=True, depth=0.44)
        parts.append(bx("g_iwl%d" % k, Ts(xw, YB - 0.22, CY + 14.9, rz=math.pi),
                        (2.6, 0.24, 0.20), S2, bev=0.015))
    for k, xw in enumerate((-11.4, -5.6, 5.6, 11.4)):
        parts += slit("g_ilp%d" % k, Ts(xw, YB - 0.04, CY + 6.4, rz=math.pi), S2, IR, h=1.0)

    # ---------- central superstructure: gate tower with a gable
    SW, SH = 5.6, 8.6
    parts.append(bx("g_st", Ts(0, YC + 0.2, GH + SH * 0.5), (SW * 2, DY - 0.6, SH), S))
    # corner quoins
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts += H.quoin("g_sq%d%d" % (sx, sy),
                             Ts(sx * SW, YC + 0.2 + sy * (DY * 0.5 - 0.3), GH), SH, 0.62, S2)
    # great window + rose on the city face
    parts += win("g_stw", Ts(0, YF - 0.1, GH + 1.9), 2.2, 3.2, S, GL,
                             mull=2, hood=True, depth=0.44)
    parts += rose("g_rose", Ts(0, YF + 0.02, GH + SH - 2.1), 1.5, S, GL, lobes=10)
    # cornice + gable roof
    parts.append(bx("g_cor", Ts(0, YC + 0.2, GH + SH + 0.10), (SW * 2 + 0.7, DY + 0.2, 0.28),
                    S, bev=0.03))
    parts += tiled_roof("g_sroof", Ts(0, YC + 0.2, 0), SW * 2 + 0.4, DY - 0.8,
                        GH + SH + 0.2, 44, SL, S, course_h=0.5, verge=0.42)
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts += H.pinnacle("g_pin%d%d" % (sx, sy),
                                Ts(sx * SW, YC + 0.2 + sy * (DY * 0.5 - 0.4), GH + SH + 0.2),
                                0.8, 3.2, S)

    # ---------- dressing the tympanum: the bare gable triangle above the great
    # window was the last big unarticulated surface on the city front.
    GYF = YC + 0.2 + (DY - 0.8) * 0.5          # plane of the city-facing gable
    g_hw = SW + 0.2
    g_z0 = GH + SH + 0.10
    g_rh = g_hw * math.tan(math.radians(44.0))
    g_sl = math.hypot(g_hw, g_rh)
    for sx in (-1, 1):
        parts.append(bx("g_gbc%d" % sx,
                        Ts(sx * g_hw * 0.5, GYF + 0.05, g_z0 + g_rh * 0.5,
                           ry=sx * math.radians(44.0)),
                        (g_sl + 0.3, 0.62, 0.30), S2, bev=0.03))
        parts.append(bx("g_gbc2%d" % sx,
                        Ts(sx * g_hw * 0.52, GYF + 0.30, g_z0 + g_rh * 0.52 + 0.16,
                           ry=sx * math.radians(44.0)),
                        (g_sl * 0.96, 0.20, 0.20), S, bev=0.02))
    parts += H.pinnacle("g_apex", Ts(0, GYF + 0.05, g_z0 + g_rh - 0.6), 0.72, 2.7, S)
    parts.append(H.sphere("g_apexb", Ts(0, GYF + 0.05, g_z0 + g_rh + 2.25), 0.17,
                          MAT["gold"], 10))
    parts += rose("g_tymp", Ts(0, GYF + 0.14, g_z0 + g_rh * 0.42), 0.72, S2, SHADOW,
                  lobes=8)
    for sx in (-1, 1):
        parts += win("g_gbl%d" % sx, Ts(sx * 3.05, GYF + 0.10, g_z0 + 0.55),
                     0.86, 2.35, S2, SHADOW, mull=0, transom=0, hood=False)
    # small corbel table at the gable base, tying it to the cornice
    for k in range(7):
        parts.append(bx("g_gcb%d" % k, Ts(-3.6 + k * 1.2, GYF + 0.02, g_z0 - 0.30),
                        (0.52, 0.30, 0.24), S2, bev=0.02))

    # ---------- the twin drum towers
    gate_tower(parts, MAT, 10.5, 38.5, 4.0, 22.0, "gtwr_l", rng)
    gate_tower(parts, MAT, -10.5, 38.5, 4.0, 22.0, "gtwr_r", rng)

    # ---------- great banners over the gate
    for s, col in ((-1, "banner_blue"), (1, "banner_gold")):
        parts += banner3("g_bn%d" % s, Ts(s * 4.2, YF + 0.35, GH + 2.2), 1.2, 2.6,
                          MAT[col], MAT["wood_dark"], pole_h=4.4)

    # ---------- the entrance sequence: 8 m moat, lifting drawbridge, timber
    # trestle bridge, then a barbican outwork on its own island.  Built as one
    # spatial run: gate passage -> leaf -> bridge -> barbican gate -> road.
    DW = 3.30                      # deck half width
    D0, D1 = 40.8, 48.8            # moat in plan (8.0 m wide)
    DB1 = 44.9                     # outer end of the lifting leaf
    BX = 8.0                       # barbican island half width
    MX = 30.0                      # moat half length: it must run across the
                                   # whole gate front, not just the bridge, or
                                   # it reads as a puddle instead of a moat
    WATER = MAT.get("water", MAT["slate"])

    # --- moat: revetments on all four sides, mud floor, water, boulders, piles
    for s in (-1, 1):
        parts.append(bx("g_mrv%d" % s, Ts(s * (MX + 0.55), (D0 + D1) * 0.5, CY * 0.5 - 0.05),
                        (1.10, D1 - D0 + 1.2, CY + 0.60), S, bev=0.02))
        parts.append(bx("g_mrvc%d" % s, Ts(s * (MX + 0.55), (D0 + D1) * 0.5, CY + 0.62),
                        (1.34, D1 - D0 + 1.4, 0.26), S2, bev=0.025))
        for k in range(3):
            parts.append(bx("g_mrs%d_%d" % (s, k),
                            Ts(s * (MX + 0.16), D0 + 1.4 + k * 2.4, CY + 0.30),
                            (0.32, 0.36, 0.34), S2, bev=0.014))
    for (nm, yy) in (("g_mri", D0 - 0.42), ("g_mro", D1 + 0.42)):
        parts.append(bx(nm, Ts(0, yy, CY * 0.5 - 0.08), (2 * MX + 1.2, 0.86, CY + 0.55),
                        S, bev=0.02))
        parts.append(bx(nm + "c", Ts(0, yy, CY + 0.52), (2 * MX + 1.44, 1.06, 0.24),
                        S2, bev=0.025))
    # mud, standing water and the ripples that keep it from reading as a slab
    parts.append(bx("g_mud", Ts(0, (D0 + D1) * 0.5, 0.06), (2 * MX + 1.0, D1 - D0 - 0.2, 0.12),
                    S2, bev=0.0))
    parts.append(bx("g_water", Ts(0, (D0 + D1) * 0.5, 0.40), (2 * MX - 0.5, D1 - D0 - 1.0, 0.06),
                    WATER, bev=0.0))
    for k in range(24):
        wx = -MX + 2.2 + k * 2.34
        if abs(wx) < 4.4:
            continue
        parts.append(bx("g_wrip%d" % k, Ts(wx, D0 + 1.4 + (k % 3) * 1.9, 0.437),
                        (1.9, 0.15, 0.02), MAT["plaster"], bev=0.0))
    for k in range(18):
        bx_ = -MX + 2.6 + k * 3.05
        if abs(bx_) < 4.9:
            continue
        parts.append(H.sphere("g_bld%d" % k, Ts(bx_, D0 + 1.1 + (k * 2.7) % 6.2,
                                                0.24), 0.44 + (k % 3) * 0.12, S2, 10,
                              squash=0.62))
    for j, yy in enumerate((45.9, 47.6)):
        for m in (-1, 0, 1):
            for s in (-1, 1):
                parts.append(cyl("g_pil%d_%d_%d" % (j, m, s),
                                 Ts(s * (DW - 0.55), yy + s * 0.02, 0.30), 0.16, 1.95,
                                 WD, seg=8))
        for s in (-1, 1):
            parts.append(bx("g_cap%d_%d" % (j, s), Ts(s * (DW - 0.55), yy, CY - 0.34),
                            (0.32, 0.36, 0.28), WD, bev=0.014))
            parts.append(bx("g_cap2%d_%d" % (j, s), Ts(s * 0.9, yy, CY - 0.20),
                            (4.4, 0.26, 0.24), WD, bev=0.014))

    # --- lifting leaf: deck, planks, beams, open balustrade
    parts.append(bx("g_deck", Ts(0, (YF + DB1) * 0.5 - 0.35, CY + 0.02),
                    (2 * DW, DB1 - YF + 1.3, 0.34), WD, bev=0.02))
    for k in range(10):
        parts.append(bx("g_plank%d" % k, Ts(0, YF + 0.72 + k * 0.44, CY + 0.20),
                        (2 * DW - 0.14, 0.36, 0.07), W, bev=0.01))
    RL = 1.12
    for s in (-1, 1):
        parts.append(bx("g_rail%d" % s, Ts(s * (DW - 0.14), (YF + DB1) * 0.5 - 0.35,
                                           CY + RL + 0.06),
                        (0.20, DB1 - YF + 1.05, 0.18), WD, bev=0.014))
        parts.append(bx("g_rail2%d" % s, Ts(s * (DW - 0.14), (YF + DB1) * 0.5 - 0.35,
                                            CY + 0.44),
                        (0.17, DB1 - YF + 1.05, 0.13), WD, bev=0.012))
        for k in range(5):
            parts.append(bx("g_rp%d_%d" % (s, k), Ts(s * (DW - 0.14), YF + 0.85 + k * 0.84,
                                                     CY + (RL + 0.44) * 0.5),
                            (0.20, 0.18, RL - 0.44), W, bev=0.01))
        parts.append(bx("g_rpc%d" % s, Ts(s * (DW - 0.14), YF + 0.70, CY + RL + 0.24),
                        (0.26, 0.30, 0.20), W, bev=0.012))
        parts.append(bx("g_rpc2%d" % s, Ts(s * (DW - 0.14), DB1 - 0.12, CY + RL + 0.24),
                        (0.26, 0.30, 0.20), W, bev=0.012))
    for k in range(4):
        parts.append(bx("g_beam%d" % k, Ts(0, YF + 1.1 + k * 1.05, CY - 0.22),
                        (2 * DW + 0.5, 0.24, 0.32), WD, bev=0.015))
    parts.append(bx("g_abulk", Ts(0, 39.9, CY - 0.03), (2 * DW + 0.6, 0.9, 0.42), S2,
                    bev=0.02))
    # hinge straps where the leaf meets the abutment
    for s in (-1, 1):
        parts.append(cyl("g_hinge%d" % s, Ts(s * (DW - 0.30), YF - 0.16, CY - 0.10,
                                             rz=math.pi * 0.5), 0.17, 1.10, IR, seg=10))
        parts.append(bx("g_hingb%d" % s, Ts(s * (DW - 0.30), YF + 0.30, CY - 0.10),
                        (0.34, 0.60, 0.20), IR, bev=0.0))
    # --- fixed trestle bridge from the leaf end to the barbican island
    parts.append(bx("g_brd", Ts(0, (DB1 + D1) * 0.5, CY - 0.14),
                    (2 * DW, D1 - DB1 + 0.5, 0.26), WD, bev=0.02))
    for k in range(9):
        parts.append(bx("g_brp%d" % k, Ts(0, DB1 + 0.18 + k * 0.44, CY + 0.06),
                        (2 * DW - 0.10, 0.36, 0.07), W, bev=0.01))
    for s in (-1, 1):
        parts.append(bx("g_brr%d" % s, Ts(s * (DW - 0.10), (DB1 + D1) * 0.5, CY + RL - 0.02),
                        (0.18, D1 - DB1, 0.16), WD, bev=0.012))
        parts.append(bx("g_brr2%d" % s, Ts(s * (DW - 0.10), (DB1 + D1) * 0.5, CY + 0.40),
                        (0.15, D1 - DB1, 0.12), WD, bev=0.01))
        for k in range(3):
            parts.append(bx("g_brq%d_%d" % (s, k),
                            Ts(s * (DW - 0.10), DB1 + 0.55 + k * 1.30,
                               CY + (RL + 0.38) * 0.5),
                            (0.18, 0.16, RL - 0.38), W, bev=0.01))
    # chains: taut, from the deck front corners up to the gate-face drums
    for s in (-1, 1):
        parts += chain("g_ch%d" % s, (s * (DW - 0.24), 44.78, CY + 1.42),
                       (s * 6.14, YF - 0.10, 11.10), 0.30, IR, n=52, r=0.105)
        # anchor: wrought-iron plate, eye and strap where the chain meets stone
        parts.append(bx("g_cha%d" % s, Ts(s * 6.14, YF + 0.02, 11.10),
                        (0.78, 0.16, 0.92), IR, bev=0.012))
        parts.append(cyl("g_che%d" % s, Ts(s * 6.14, YF + 0.22, 10.98, ry=math.pi * 0.5),
                         0.17, 0.20, IR, seg=12))
        for k in (-1, 1):
            parts.append(bx("g_chs%d_%d" % (s, k),
                            Ts(s * 6.14, YF + 0.06, 11.10 + k * 0.55),
                            (0.24, 0.10, 0.65, ), IR, bev=0.008))
    # eye bolts on the deck corners
    for s in (-1, 1):
        parts.append(cyl("g_chb%d" % s, Ts(s * (DW - 0.24), 44.78, CY + 1.42,
                                            ry=math.pi * 0.5), 0.15, 0.22, IR, seg=10))
        parts.append(bx("g_chbp%d" % s, Ts(s * (DW - 0.24), 44.78, CY + 1.28),
                        (0.44, 0.30, 0.22), IR, bev=0.0))
    # ---------- the barbican: an outwork on its own island beyond the moat
    parts += barbican(MAT, rng, D1, 52.9, 8.0, 3.30)


# ---------------------------------------------------------------------------
# the keep
# ---------------------------------------------------------------------------
def keep(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    GL = MAT["glass"]
    IR = MAT["iron"]
    WD = MAT["wood_dark"]
    SL = MAT["slate"]

    CX, CY_ = 0.0, -21.0
    HX, HY = 15.0, 11.0
    x0, x1 = CX - HX, CX + HX
    y0, y1 = CY_ - HY, CY_ + HY
    KH = KEEP_H

    # ---------- plinth / battered base
    parts.append(bx("k_pl0", Ts(CX, CY_, 0.30 + CY * 0.5), (2 * HX + 2.6, 2 * HY + 2.6,
                                                           0.60 + CY), S, bev=0.03))
    parts.append(bx("k_pl1", Ts(CX, CY_, CY + 0.62), (2 * HX + 1.6, 2 * HY + 1.6, 0.44), S,
                    bev=0.03))
    parts.append(bx("k_body", Ts(CX, CY_, CY + (KH - CY) * 0.5), (2 * HX, 2 * HY, KH - CY), S))

    # ---------- string courses on all four faces
    for k, z in enumerate((5.05, 16.25, 27.45, 38.6)):
        zb = CY + z
        parts.append(bx("k_sc_f%d" % k, Ts(CX, y1 + 0.10, zb), (2 * HX + 0.5, 0.34, 0.34), S2,
                        bev=0.02))
        parts.append(bx("k_sc_b%d" % k, Ts(CX, y0 - 0.10, zb), (2 * HX + 0.5, 0.34, 0.34), S2,
                        bev=0.02))
        parts.append(bx("k_sc_e%d" % k, Ts(x1 + 0.10, CY_, zb), (0.34, 2 * HY + 0.5, 0.34), S2,
                        bev=0.02))
        parts.append(bx("k_sc_w%d" % k, Ts(x0 - 0.10, CY_, zb), (0.34, 2 * HY + 0.5, 0.34), S2,
                        bev=0.02))
    # NOTE: the corbel table that used to sit under these string courses was
    # removed -- the courses now run AT the window sills, so their corbels
    # collided with the sill corbels of every window on the face.

    # ---------- quoins on the four corners
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts += H.quoin("k_q%d%d" % (sx, sy), Ts(CX + sx * HX, CY_ + sy * HY, CY),
                             KH - CY, 0.78, S2)

    # ---------- three storeys of tall windows + a small top row
    faces = (("f", CX, y1, "+y", 2 * HX, 4), ("b", CX, y0, "-y", 2 * HX, 4),
             ("e", x1, CY_, "+x", 2 * HY, 3), ("w", x0, CY_, "-x", 2 * HY, 3))
    for (tag, fx, fy, n, span, nw) in faces:
        for r, z in enumerate((7.0, 18.2, 29.4)):
            for i in range(nw):
                off = (i - (nw - 1) * 0.5) * (span / nw)
                if tag in ("f", "b"):
                    T = FT(fx + off, fy, CY + z, n)
                else:
                    T = FT(fx, fy + off, CY + z, n)
                parts += win("k_win_%s%d%d" % (tag, r, i), T, 2.15, 3.9, S2,
                                         GL, mull=2, hood=True, depth=0.46)
                # hood-mould stops / label
                parts.append(bx("k_lab_%s%d%d" % (tag, r, i), T @ Ts(0, 0.20, 5.05),
                                (2.9, 0.26, 0.20), S2, bev=0.015))
        # small attic windows
        for i in range(nw):
            off = (i - (nw - 1) * 0.5) * (span / nw)
            T = FT(fx + off, fy, CY + 36.6, n) if tag in ("f", "b") else \
                FT(fx, fy + off, CY + 36.6, n)
            parts += win("k_att_%s%d" % (tag, i), T, 1.25, 2.0, S2, GL,
                                     mull=1, hood=False, depth=0.34)

    # ---------- blind arcade at the base of the courtyard faces
    for (tag, fx, fy, n, span, nw) in (("f", CX, y1, "+y", 2 * HX, 7),):
        for i in range(nw + 1):
            off = (i - nw * 0.5) * (span / (nw + 1))
            T = FT(fx + off, fy, CY + 1.9, n)
            parts.append(bx("k_ar_d%s%d" % (tag, i), T @ Ts(0, 0, 0), (0.9, 0.16, 2.4), IR))
            parts += voussoirs("k_ar_v%s%d" % (tag, i), T @ Ts(0, 0.05, 1.2), 0.45, 0.0,
                               S2, seg=7, r_in=0.0, r_out=0.26, depth=0.28)

    # ---------- great door on the courtyard face
    parts.append(bx("k_terr", Ts(0, y1 + 1.9, CY + 0.16), (11.0, 4.4, 0.32), S2, bev=0.02))
    parts.append(bx("k_terr2", Ts(0, y1 + 1.9, CY - 0.05), (11.6, 4.9, 0.42), S, bev=0.02))
    parts += H.door_arched("k_door", Ts(0, y1 + 0.02, CY + 0.30), 3.4, 5.2, WD, IR, S2,
                           steps=0)
    for s in (-1, 1):
        parts.append(bx("k_dpr%d" % s, Ts(s * 2.6, y1 + 0.30, CY + 3.2), (0.7, 0.7, 6.4), S2,
                        bev=0.02))
        parts += voussoirs("k_dva%d" % s, Ts(s * 2.6, y1 + 0.35, CY + 6.4), 0.62, 0.0, S,
                           seg=9, r_in=0.0, r_out=0.3, depth=0.6)
    # stair tower porch
    parts += H.stairs("k_st", Ts(0, y1 + 4.6, CY + 0.30), 7.0, 7, rise=0.24, run=0.42,
                      mat=S2)
    for s in (-1, 1):
        parts.append(bx("k_sbal%d" % s, Ts(s * 3.9, y1 + 3.0, CY + 0.85), (0.6, 4.4, 1.1), S,
                        bev=0.02))
    # statues flanking the door
    for s in (-1, 1):
        parts += H.statue("k_sta%d" % s, Ts(s * 4.6, y1 + 1.3, CY + 0.30), 2.8, S2)

    # ---------- machicolated parapet
    parts += H.machicolation("k_mf", Ts(0, y1 + 0.25, CY + KH), 2 * HX + 0.4, S,
                             h=1.15, depth=1.05)
    parts += H.machicolation("k_mb", Ts(0, y0 - 0.25, CY + KH, rz=math.pi), 2 * HX + 0.4, S,
                             h=1.15, depth=1.05)
    parts += H.machicolation("k_me", Ts(x1 + 0.25, CY_, CY + KH, rz=-math.pi * 0.5),
                             2 * HY + 0.4, S, h=1.15, depth=1.05)
    parts += H.machicolation("k_mw", Ts(x0 - 0.25, CY_, CY + KH, rz=math.pi * 0.5),
                             2 * HY + 0.4, S, h=1.15, depth=1.05)
    # roof: a pitched lead roof inside a walkable terrace ring.  A single flat
    # slab over 30x22 m read as a stadium lid from the air, whatever seams it had.
    zd = CY + KH + 0.04
    parts.append(bx("k_roofdeck", Ts(CX, CY_, zd), (2 * HX - 0.5, 2 * HY - 0.5, 0.16),
                    MAT["slate"], bev=0.02))
    parts.append(bx("k_roofwalk", Ts(CX, CY_, zd + 0.10), (2 * HX - 1.7, 2 * HY - 1.7, 0.05),
                    MAT["slate"], bev=0.01))
    RW = 2 * HX - 8.2
    RD = 2 * HY - 7.2
    parts += tiled_roof("k_rf", Ts(CX, CY_, 0), RW, RD, zd + 0.14, 42.0,
                        MAT["slate"], MAT["slate"], course_h=0.58, ov=0.55, rolls=9,
                        hip_b=6.2, stone=S)
    kr = (RW * 0.5 + 0.55) * math.tan(math.radians(42.0))
    zr = zd + 0.14 + kr
    # terrace curb + lead rolls along the parapet foot
    for s in (-1, 1):
        parts.append(bx("k_cur%d" % s, Ts(CX + s * (HX - 1.35), CY_, zd + 0.42),
                        (0.55, 2 * HY - 2.6, 0.55), S2, bev=0.02))
        parts.append(bx("k_cur%d_b" % s, Ts(CX, CY_ + s * (HY - 1.35), zd + 0.42),
                        (2 * HX - 2.6, 0.55, 0.55), S2, bev=0.02))
    # lead rolls along the terrace, so the walk reads as roof, not as a slab.
    # Rolls follow the strip they sit on: along X on the long sides, along Y on
    # the short ones (a roll laid the wrong way pokes out of the wall).
    for s in (-1, 1):
        parts.append(cyl("k_lrN%d" % s, Ts(CX, CY_ + s * (HY - 1.95), zd + 0.30,
                                           ry=math.pi * 0.5), 0.19, 2 * HX - 4.6,
                         MAT["slate"], seg=10))
        parts.append(cyl("k_lrE%d" % s, Ts(CX + s * (HX - 1.95), CY_, zd + 0.30,
                                           rx=math.pi * 0.5), 0.19, 2 * HY - 5.4,
                         MAT["slate"], seg=10))
    # chimneys standing on the terrace ring, not under the roof
    parts += H.chimney("k_ch0", Ts(CX - 5.2, CY_ - 8.6, zd + 0.14), 3.2, S2, pots=3)
    parts += H.chimney("k_ch1", Ts(CX + 6.4, CY_ - 8.6, zd + 0.14), 2.8, S2, pots=2)
    parts += H.chimney("k_ch2", Ts(CX + 7.4, CY_ + 8.6, zd + 0.14), 2.6, S2, pots=2)
    parts += H.chimney("k_ch3", Ts(CX - 8.2, CY_ + 8.4, zd + 0.14), 2.4, S2, pots=2)
    # dormers on the long slopes (the rear end is hipped, so only two per side)
    for s in (-1, 1):
        for k in range(2):
            y = CY_ - 1.2 + k * 4.6
            t = 0.52
            x = s * (RW * 0.5 + 0.55) * (1.0 - t)
            z = zd + 0.14 + kr * t
            nm = "k_dm%d_%d" % (s, k)
            parts.append(bx(nm + "_b", Ts(CX + x * 1.02, y, z - 0.30),
                            (1.75, 1.85, 2.10), S, bev=0.02))
            parts.append(bx(nm + "_c", Ts(CX + x * 1.02, y, z + 0.78),
                            (2.05, 2.15, 0.20), S2, bev=0.02))
            parts += win(nm + "_w", Ts(CX + x * 1.02 + s * 0.92, y, z + 0.05,
                                       rz=-s * math.pi * 0.5),
                         0.80, 1.25, S2, MAT["glass"], mull=1, transom=0, hood=False,
                         sill=True)
            parts += tiled_roof(nm + "_r", Ts(CX + x * 1.02, y, 0), 2.20, 1.95,
                                z + 0.86, 40.0, MAT["slate"], MAT["slate"],
                                course_h=0.42, ov=0.26, verge=0.30)
    # ridge lantern: an octagonal drum piercing the ridge, slate spire
    parts.append(cyl("k_lant", Ts(CX, CY_ + 1.0, zr - 1.2), 1.62, 4.6, S, seg=8))
    parts.append(cyl("k_lant_c", Ts(CX, CY_ + 1.0, zr + 1.25), 1.90, 0.26, S2, seg=8))
    parts.append(cyl("k_lant_d", Ts(CX, CY_ + 1.0, zr + 1.45), 1.54, 0.22, MAT["gold"],
                     seg=8))
    parts += H.spire("k_lant_sp", Ts(CX, CY_ + 1.0, zr + 1.55), 1.80, 3.6,
                     MAT["slate"], seg=8)
    parts.append(cyl("k_lant_fin", Ts(CX, CY_ + 1.0, zr + 5.20), 0.07, 1.0, MAT["gold"],
                     seg=6))
    # great royal standard on the ridge
    parts += flag("k_std", Ts(CX, CY_ + 5.4, zr + 0.1), 3.4, 1.9, MAT["banner_gold"], S2,
                  7.4)
    # a small garderobe turret on the north-west corner of the deck
    parts.append(cyl("k_gd", Ts(CX - HX + 2.6, CY_ - HY + 2.4, zd + 0.40), 1.35, 3.0,
                     S, seg=12))
    parts += H.spire("k_gd_sp", Ts(CX - HX + 2.6, CY_ - HY + 2.4, zd + 2.1), 1.55, 2.6,
                     MAT["slate"], seg=8)

    # ---------- four corbelled corner turrets
    for sx in (-1, 1):
        for sy in (-1, 1):
            tx, ty = CX + sx * HX, CY_ + sy * HY
            nm = "k_t%d%d" % (sx, sy)
            base_z = CY + 30.0
            # a true corbel table: five courses stepping out 0.2 m each, every
            # step with a splayed soffit, then the shaft springs from the ring
            parts += corbel_bell(nm, Ts(tx, ty, 0), 1.55, 2.42, base_z - 1.62, S2,
                                 courses=5, course_h=0.30, splay=0.13)
            parts.append(cyl(nm + "_sh", Ts(tx, ty, base_z + 7.0), 2.55, 14.0, S, seg=32))
            for j in range(3):
                parts.append(cyl("%s_bc%d" % (nm, j), Ts(tx, ty, base_z + 1.6 + j * 4.4),
                                 2.65, 0.22, S2, seg=32))
            for j, z in enumerate((base_z + 3.0, base_z + 8.4)):
                for a in range(4):
                    ang = 2.0 * math.pi * a / 4 + j * 0.5
                    parts += slit("%s_sl%d_%d" % (nm, j, a),
                                  rmat(Ts(tx, ty, 0), ang, 2.53, z), S, IR, h=1.2)
            pm, mt = round_mach(nm + "_mc", Ts(tx, ty, 0), 2.55, base_z + 14.4, S,
                                n=14, ring_h=0.7, merl=8)
            parts += pm
            parts += cone_cap(nm, Ts(tx, ty, 0), 2.85, mt, SL, 7.4, seg=8,
                              ring_mat=S2, gold=MAT["gold"])

    # ---------- stair turret on the east face (rises above the parapet)
    parts.append(cyl("k_stt_shoe", Ts(x1 - 0.2, CY_ + 2.0, CY + 0.35), 2.3, 0.7, S, seg=24))
    parts.append(cyl("k_stt", Ts(x1 - 0.2, CY_ + 2.0, CY + 23.0), 2.0, 46.0, S, seg=24))
    for j in range(6):
        parts.append(cyl("k_stt_bc%d" % j, Ts(x1 - 0.2, CY_ + 2.0, CY + 6.0 + j * 7.2), 2.09,
                         0.22, S2, seg=24))
    for j, z in enumerate((12.0, 24.0, 34.0)):
        parts += slit("k_stt_sl%d" % j, Ts(x1 + 1.75, CY_ + 2.0, CY + z, rz=-math.pi * 0.5),
                      S, IR, h=1.2)
    pm, mt = round_mach("k_stt_mc", Ts(x1 - 0.2, CY_ + 2.0, 0), 2.0, CY + 46.6, S,
                        n=12, ring_h=0.62, merl=8)
    parts += pm
    parts += cone_cap("k_stt", Ts(x1 - 0.2, CY_ + 2.0, 0), 2.2, mt, SL, 8.6, seg=8,
                      ring_mat=S2, gold=MAT["gold"])
    parts += flag("k_stt_fl", Ts(x1 - 0.2, CY_ + 2.0, CY + 55.6), 1.8, 2.5,
                  MAT["banner_blue"], MAT["iron"], 4.2)

    # ---------- banners on the parapet
    for s, col in ((-1, "banner_red"), (1, "banner_red")):
        parts += banner3("k_bn%d" % s, Ts(s * 8.0, y1 + 2.3, CY + KH + 3.1), 1.7, 3.6,
                          MAT[col], MAT["wood_dark"], pole_h=7.0)
    parts += banner3("k_bnc", Ts(0, y0 - 0.9, CY + KH + 1.2), 2.0, 4.6, MAT["banner_gold"],
                      MAT["wood_dark"], pole_h=8.0)


# ---------------------------------------------------------------------------
# great hall wing + chapel
# ---------------------------------------------------------------------------
def great_hall(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    GL = MAT["glass"]
    WD = MAT["wood_dark"]
    TL = MAT["tile"]
    SL = MAT["slate"]
    x0, x1 = -32.6, -15.9
    y0, y1 = -16.0, 6.0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    W = x1 - x0
    D = y1 - y0
    WH = 12.0

    parts.append(bx("h_pl", Ts(cx, cy, CY + 0.14), (W + 1.8, D + 1.8, 0.30 + CY * 0.3), S,
                    bev=0.03))
    parts += H.wall_course("h_w", Ts(cx, cy, CY), W, D, WH, S)
    # east facade (courtyard): buttresses + tall windows
    for k in range(4):
        y = y0 + 3.4 + k * 5.2
        parts += H.buttress("h_bu%d" % k, Ts(x1, y, CY), WH - 1.0, 1.2, 3, S2)
    for k in range(3):
        y = y0 + 5.9 + k * 5.2
        parts += win("h_win%d" % k, FT(x1, y, CY + 3.6, "+x"), 2.4, 5.0, S2, GL,
                                 mull=3, hood=True, depth=0.46)
        parts.append(bx("h_wlab%d" % k, Ts(x1 + 0.2, y, CY + 9.1), (0.3, 3.2, 0.22), S2,
                        bev=0.015))
    # west flank + south gable: the rear three-quarter views see these, so they
    # get the same window rhythm as the courtyard face
    for k in range(3):
        y = y0 + 4.4 + k * 5.4
        parts += H.buttress("h_bu2%d" % k, Ts(x0, y, CY, rz=math.pi * 0.5), WH - 1.4, 1.1, 3, S2)
        parts += win("h_ww%d" % k, FT(x0, y, CY + 3.9, "-x"), 2.0, 4.2, S2, GL,
                     mull=2, hood=True, depth=0.44)
        parts.append(bx("h_wlabb%d" % k, Ts(x0 - 0.2, y, CY + 8.9), (0.3, 2.8, 0.22), S2,
                        bev=0.015))
    for k in range(3):
        xw = cx - 5.4 + k * 5.4
        parts += win("h_sw%d" % k, FT(xw, y0, CY + 5.6, "-y"), 1.7, 3.6, S2, GL,
                     mull=2, hood=True, depth=0.42)
    parts.append(bx("h_sband", Ts(cx, y0 - 0.10, CY + 3.02), (W - 1.2, 0.22, 0.26), S2,
                    bev=0.015))
    # front gable face: door + window + rose
    parts += H.door_arched("h_door", Ts(-22.0, y1 + 0.02, CY), 2.6, 3.6, WD, MAT["iron"], S2,
                           steps=0)
    parts += H.stairs("h_dst", Ts(-22.0, y1 + 1.9, CY), 5.0, 4, rise=0.22, run=0.38, mat=S2)
    parts += win("h_fw", Ts(-22.0, y1 + 0.02, CY + 5.2), 2.0, 3.0, S2, GL,
                             mull=2, hood=True, depth=0.44)
    for k in range(2):
        parts += win("h_fw%d" % k, Ts(-27.5 + k * 11.0, y1 + 0.02, CY + 5.4),
                                 1.5, 2.4, S2, GL, mull=1, depth=0.38)
    # roof
    parts += tiled_roof("h_rf", Ts(cx, cy, 0), W, D, CY + WH, 46, TL, S2,
                        course_h=0.56, verge=0.5, crest=True)
    # ridge cresting + finials
    rh = (W * 0.5 + 0.5) * math.tan(math.radians(46))
    for k in range(9):
        parts.append(bx("h_cr%d" % k, Ts(cx, y0 + 1.4 + k * 2.6, CY + WH + rh + 0.28),
                        (0.42, 0.9, 0.55), S2, bev=0.02))
    for sy in (-1, 1):
        parts += H.pinnacle("h_pin%d" % sy, Ts(cx, cy + sy * (D * 0.5 + 0.1), CY + WH),
                            0.9, 3.4, S2)
    parts += H.chimney("h_ch0", Ts(cx + 3.0, cy - 7.0, CY + WH + rh - 1.2), 3.6, S2, pots=3)
    parts += H.chimney("h_ch1", Ts(cx - 3.4, cy + 5.0, CY + WH + rh - 1.6), 3.2, S2, pots=2)
    # dormers on the courtyard slope
    for k in range(2):
        dz = (W * 0.5 + 0.5 - 3.2) * math.tan(math.radians(46))
        parts += H.dormer("h_dm%d" % k, Ts(cx + 4.9, cy - 4.0 + k * 8.0, CY + WH + dz - 0.6),
                          w=1.4, h=1.6, d=1.0, pitch=44, wall=S2, roof_mat=TL,
                          frame=WD, glass=GL)
    # banner on the gable
    parts += banner3("h_bn", Ts(-18.0, y1 + 1.0, CY + WH + 1.0), 1.4, 3.2,
                      MAT["banner_blue"], WD, pole_h=6.0)


def chapel(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    GL = MAT["glass"]
    WD = MAT["wood_dark"]
    SL = MAT["slate"]
    x0, x1 = 16.0, 26.2
    y0, y1 = -20.0, -6.0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    W = x1 - x0
    D = y1 - y0
    WH = 13.0

    parts.append(bx("c_pl", Ts(cx, cy, CY + 0.14), (W + 1.6, D + 1.6, 0.30 + CY * 0.3), S,
                    bev=0.03))
    parts += H.wall_course("c_w", Ts(cx, cy, CY), W, D, WH, S)
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts += H.quoin("c_q%d%d" % (sx, sy), Ts(cx + sx * W * 0.5, cy + sy * D * 0.5, CY),
                             WH, 0.6, S2)
    # front gable: rose window + two lancets + a door
    parts += rose("c_rose", Ts(cx, y1 + 0.04, CY + 9.6), 2.15, S2, GL, lobes=12)
    for s in (-1, 1):
        parts += win("c_lan%d" % s, Ts(cx + s * 2.4, y1 + 0.02, CY + 3.0),
                                 1.15, 4.2, S2, GL, mull=1, hood=True, depth=0.4)
    parts.append(bx("c_door", Ts(cx, y1 + 0.02, CY + 1.8), (2.2, 0.5, 3.6), WD, bev=0.02))
    parts += voussoirs("c_dva", Ts(cx, y1 + 0.06, CY + 3.6), 1.1, 0.0, S2, seg=9,
                       r_in=0.0, r_out=0.28, depth=0.4)
    parts += H.stairs("c_dst", Ts(cx, y1 + 1.6, CY), 4.0, 3, rise=0.22, run=0.36, mat=S2)
    # rear gable: three lancets + a small rose, so the south face is not blank
    for s in (-1, 0, 1):
        parts += win("c_rw%d" % s, FT(cx + s * 2.6, y0, CY + 3.2, "-y"), 1.05, 3.4, S2, GL,
                     mull=1, hood=True, depth=0.36)
    parts += rose("c_rrose", Ts(cx, y0 - 0.04, CY + 8.4, rz=math.pi), 1.55, S2, GL, lobes=10)
    for k in range(3):
        y = y0 + 3.2 + k * 4.0
        for sx, n in ((-1, "-x"), (1, "+x")):
            parts += win("c_sw%d_%d" % (k, sx), FT(cx + sx * W * 0.5, y, CY + 4.0, n),
                                     1.1, 3.6, S2, GL, mull=1, hood=True, depth=0.38)
    # flying buttresses on the yard flank: free-standing pier, quarter-arc
    # flyer carrying the thrust to the clerestory, pinnacle on the pier
    for k in range(3):
        y = y0 + 2.4 + k * 4.6
        PT = Ts(x1 + 3.6, y, CY, rz=math.pi * 0.5)
        parts.append(bx("c_fp%d" % k, PT @ Ts(0, -0.6, 1.00), (1.5, 1.7, 2.0), S2, bev=0.03))
        parts.append(bx("c_fp2%d" % k, PT @ Ts(0, -0.6, 4.10), (1.12, 1.28, 4.4), S2, bev=0.025))
        parts.append(bx("c_fpc%d" % k, PT @ Ts(0, -0.6, 6.42), (1.38, 1.52, 0.28), S2, bev=0.02))
        parts += H.flying_buttress("c_fb%d" % k, PT @ Ts(0, -0.6, 0), 3.6, WH - 4.4, S2,
                                   rise=2.0)
        parts += H.pinnacle("c_fpn%d" % k, PT @ Ts(0, -0.6, 6.6), 0.72, 2.4, S2)
    for k in range(3):
        y = y0 + 2.4 + k * 4.6
        parts += H.buttress("c_bu2%d" % k, Ts(x0, y, CY, rz=math.pi * 0.5), WH - 2.0, 1.0, 2,
                            S2)
    # steep roof + flèche
    parts += tiled_roof("c_rf", Ts(cx, cy, 0), W, D, CY + WH, 52, SL, S2,
                        course_h=0.5, verge=0.45, crest=True)
    rh = (W * 0.5 + 0.45) * math.tan(math.radians(52))
    parts.append(bx("c_flb", Ts(cx, cy + 0.6, CY + WH + rh + 0.2), (1.5, 1.5, 1.4), S2,
                    bev=0.02))
    parts += H.spire("c_fl", Ts(cx, cy + 0.6, CY + WH + rh + 0.9), 1.55, 7.0, SL, seg=8)
    for sy in (-1, 1):
        parts += H.pinnacle("c_pin%d" % sy, Ts(cx + sy * 0.0, cy + sy * (D * 0.5 + 0.1),
                                               CY + WH), 0.8, 3.0, S2)


def stable(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    TL = MAT["tile"]
    PR = MAT["plaster"]
    GL = MAT["glass"]
    x0, x1 = 28.0, 38.6
    y0, y1 = -8.0, 8.0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    Wd = x1 - x0
    D = y1 - y0
    WH = 5.4

    parts.append(bx("s_pl", Ts(cx, cy, CY + 0.12), (Wd + 1.4, D + 1.4, 0.28 + CY * 0.3), S2,
                    bev=0.03))
    # stone ground floor
    parts += H.wall_course("s_w0", Ts(cx, cy, CY), Wd, D, WH, S)
    # timber-framed upper? keep it a long stone range with a timber gallery on the west face
    parts += tiled_roof("s_rf", Ts(cx, cy, 0), Wd, D, CY + WH, 42, TL, S2,
                        course_h=0.52, verge=0.5)
    rh = (Wd * 0.5 + 0.5) * math.tan(math.radians(42))
    # west gallery (courtyard side)
    for k in range(7):
        y = y0 + 1.2 + k * (D - 2.4) / 6.0
        parts.append(bx("s_gal%d" % k, Ts(x0 - 1.55, y, CY + 2.9), (0.24, 0.24, 5.0), W,
                        bev=0.01))
    parts.append(bx("s_galt", Ts(x0 - 1.55, cy, CY + 5.25), (0.9, D - 1.2, 0.22), W, bev=0.015))
    parts.append(bx("s_galr", Ts(x0 - 1.95, cy, CY + 5.65), (1.7, D - 0.6, 0.16), MAT["tile_blue"],
                    bev=0.015))
    for k in range(9):
        parts.append(bx("s_bal%d" % k, Ts(x0 - 1.55, y0 + 1.0 + k * (D - 2.0) / 8.0,
                                          CY + 3.55), (0.14, 0.14, 1.0), W))
    # doors + windows on the courtyard face
    for k in range(3):
        y = y0 + 3.0 + k * 5.0
        parts.append(bx("s_door%d" % k, Ts(x0 - 0.06, y, CY + 1.6), (0.5, 2.2, 3.2), WD,
                        bev=0.02))
        parts += voussoirs("s_dv%d" % k, Ts(x0 - 0.1, y, CY + 3.2), 1.1, 0.0, S2, seg=9,
                           r_in=0.0, r_out=0.26, depth=0.44, w_scale=1.0)
    for k in range(4):
        y = y0 + 2.0 + k * 4.0
        parts += win("s_win%d" % k, FT(x0, y, CY + 3.5, "-x"), 1.0, 1.6, S2, GL,
                                 mull=1, depth=0.34)
    # hay loft opening + hoist beam
    parts.append(bx("s_loft", Ts(x0 - 0.08, cy, CY + 4.35), (0.6, 1.7, 1.5), MAT["iron"]))
    parts.append(bx("s_hoist", Ts(x0 - 1.1, cy, CY + 5.1), (2.4, 0.24, 0.26), WD, bev=0.01))
    parts += H.chimney("s_ch", Ts(x0 + 2.0, cy + 5.0, CY + WH + rh - 2.0), 3.0, S2, pots=2)


def guardhouse(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    WD = MAT["wood_dark"]
    TL = MAT["tile"]
    GL = MAT["glass"]
    x0, x1 = -30.0, -18.0
    y0, y1 = 20.0, 32.0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    W = x1 - x0
    D = y1 - y0
    WH = 10.5

    parts.append(bx("q_pl", Ts(cx, cy, CY + 0.14), (W + 1.6, D + 1.6, 0.30 + CY * 0.3), S2,
                    bev=0.03))
    parts += H.wall_course("q_w", Ts(cx, cy, CY), W, D, WH, S)
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts += H.quoin("q_q%d%d" % (sx, sy), Ts(cx + sx * W * 0.5, cy + sy * D * 0.5, CY),
                             WH, 0.62, S2)
    # two storeys of cross windows on both courtyard faces
    for r, z in enumerate((2.0, 6.4)):
        for k in range(3):
            y = y0 + 3.0 + k * 3.0
            parts += win("q_we%d_%d" % (r, k), FT(x1, y, CY + z, "+x"), 1.35, 2.2,
                                     S2, GL, mull=1, hood=True, depth=0.36)
        for k in range(2):
            x = x0 + 3.5 + k * 5.0
            parts += win("q_wf%d_%d" % (r, k), Ts(x, y1 + 0.02, CY + z), 1.35, 2.2,
                                     S2, GL, mull=1, hood=True, depth=0.36)
    # outer long wall + yard face: transom windows, so no face is a bare box
    for r, z in enumerate((2.1, 6.6)):
        for k in range(3):
            y = y0 + 3.2 + k * 3.2
            parts += win("q_wo%d_%d" % (r, k), FT(x0, y, CY + z, "-x"), 1.3, 2.1,
                         S2, GL, mull=1, hood=True, depth=0.34)
        for k in range(2):
            x = x0 + 3.4 + k * 5.2
            parts += win("q_ws%d_%d" % (r, k), FT(x, y0, CY + z, "-y"), 1.3, 2.1,
                         S2, GL, mull=1, hood=True, depth=0.34)
    for k in range(3):
        parts += H.buttress("q_bu%d" % k, Ts(x0, y0 + 2.6 + k * 3.6, CY, rz=math.pi * 0.5),
                            6.0, 0.9, 2, S2)
    parts += H.door_arched("q_door", Ts(-24.0, y1 + 0.02, CY), 2.2, 3.2, WD, MAT["iron"], S2,
                           steps=0)
    parts += H.stairs("q_dst", Ts(-24.0, y1 + 1.7, CY), 4.4, 4, rise=0.20, run=0.36, mat=S2)
    parts += tiled_roof("q_rf", Ts(cx, cy, 0), W, D, CY + WH, 44, TL, S2,
                        course_h=0.52, verge=0.45)
    rh = (W * 0.5 + 0.45) * math.tan(math.radians(44))
    parts += H.chimney("q_ch", Ts(cx + 3.4, cy - 2.0, CY + WH + rh - 1.6), 3.2, S2, pots=2)
    for sy in (-1, 1):
        parts += H.pinnacle("q_pin%d" % sy, Ts(cx, cy + sy * (D * 0.5 + 0.1), CY + WH),
                            0.8, 2.8, S2)
    parts += banner3("q_bn", Ts(x1 - 1.0, y1 + 0.8, CY + WH + 1.0), 1.3, 3.0,
                      MAT["banner_red"], WD, pole_h=5.6)


# ---------------------------------------------------------------------------
# courtyard
# ---------------------------------------------------------------------------
def fountain(parts, MAT, x, y, r=3.0):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    WA = K.mat_water()
    T = Ts(x, y, CY)
    prof = [(r * 0.86, 0.0), (r, 0.18), (r, 0.86), (r * 0.92, 0.96), (r * 0.80, 0.96),
            (r * 0.80, 0.74)]
    parts.append(H.lathe("f_basin", prof, S2, seg=32, T=T, close_bottom=True, close_top=False))
    parts.append(cyl("f_water", T @ Ts(0, 0, 0.78), r * 0.82, 0.06, WA, seg=32))
    # octagonal kerb blocks
    for i in range(16):
        a = 2.0 * math.pi * i / 16
        parts.append(bx("f_kb%d" % i, tmat(T, a, r * 1.02, 0.44),
                        (r * 0.40, 0.34, 0.9), S, bev=0.02))
    # central column, two tiers
    parts.append(cyl("f_col", T @ Ts(0, 0, 1.55), 0.52, 2.2, S, seg=16))
    parts.append(H.lathe("f_t1", [(1.45, 1.95), (1.55, 2.05), (1.55, 2.22), (1.20, 2.26),
                                  (1.20, 2.12)], S, seg=24, T=T, close_bottom=True,
                        close_top=False))
    parts.append(cyl("f_w1", T @ Ts(0, 0, 2.18), 1.28, 0.05, WA, seg=24))
    parts.append(cyl("f_col2", T @ Ts(0, 0, 3.15), 0.34, 1.8, S, seg=14))
    parts.append(H.lathe("f_t2", [(0.86, 3.55), (0.94, 3.63), (0.94, 3.78), (0.66, 3.82),
                                  (0.66, 3.68)], S, seg=20, T=T, close_bottom=True,
                        close_top=False))
    parts.append(cyl("f_w2", T @ Ts(0, 0, 3.74), 0.78, 0.04, WA, seg=20))
    # jets
    for i in range(8):
        a = 2.0 * math.pi * i / 8
        parts.append(cyl("f_jet%d" % i, tmat(T, a, 0.55, 3.0), 0.045, 0.9, WA, seg=6))
    parts += H.statue("f_st", T @ Ts(0, 0, 3.9), 2.6, MAT["gold"])
    # benches
    for i in range(4):
        a = 2.0 * math.pi * i / 4 + math.pi * 0.25
        parts.append(bx("f_bench%d" % i, tmat(T, a, r + 1.4, 0.42),
                        (3.0, 0.7, 0.22), S, bev=0.02))
        for s in (-1, 1):
            parts.append(bx("f_bl%d_%d" % (i, s), tmat(T, a, r + 1.4, 0.2),
                            (0.3, 0.55, 0.4), S2, bev=0.015))


def well(parts, MAT, x, y):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    TL = MAT["tile"]
    T = Ts(x, y, CY)
    r = 1.25
    for i in range(18):
        a = 2.0 * math.pi * i / 18
        parts.append(bx("wl_s%d" % i, tmat(T, a, r, 0.60), (r * 0.38, 0.42, 1.15), S, bev=0.02))
    parts.append(cyl("wl_dark", T @ Ts(0, 0, 0.55), r * 0.86, 1.05, MAT["iron"], seg=22))
    parts.append(cyl("wl_wat", T @ Ts(0, 0, 0.30), r * 0.82, 0.05, K.mat_water(), seg=22))
    parts.append(bx("wl_rim", T @ Ts(0, 0, 1.20), (2 * r + 0.5, 2 * r + 0.5, 0.16), S2,
                    bev=0.02))
    # posts + gable roof + windlass
    for s in (-1, 1):
        parts.append(cyl("wl_p%d" % s, T @ Ts(s * 1.05, 0, 1.95), 0.12, 3.0, W, seg=8))
    parts += tiled_roof("wl_rf", T @ Ts(0, 0, 0), 2.7, 2.2, 3.35, 42, TL, WD,
                        course_h=0.4, verge=0.25)
    parts.append(cyl("wl_drum", T @ Ts(0, 0, 2.55, ry=math.pi * 0.5), 0.16, 1.9, WD, seg=10))
    parts.append(cyl("wl_rope", T @ Ts(0, 0, 1.85), 0.03, 1.3, MAT["plaster"], seg=6))
    parts.append(cyl("wl_bkt", T @ Ts(0, 0, 1.15), 0.22, 0.34, WD, seg=10))
    parts.append(cyl("wl_crk", T @ Ts(1.15, 0, 2.55, ry=math.pi * 0.5), 0.06, 0.5, IR, seg=6))


def smithy(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    TL = MAT["tile"]
    SL = MAT["slate"]
    F = fire_mat()
    T = Ts(-32.0, 9.0, CY)
    Wd, D = 7.0, 9.0
    # hearth + chimney at the back
    parts.append(bx("sm_h", T @ Ts(-1.4, 3.0, 0.85), (2.6, 2.0, 1.7), S2, bev=0.02))
    parts.append(bx("sm_fire", T @ Ts(-1.4, 2.55, 0.80), (1.7, 0.7, 0.9), F, bev=0.0))
    parts.append(bx("sm_hood", T @ Ts(-1.4, 3.0, 2.35), (2.2, 1.7, 1.3), S, bev=0.02))
    parts.append(bx("sm_flue", T @ Ts(-1.4, 3.4, 4.6), (1.2, 1.2, 4.0), S2, bev=0.02))
    parts.append(bx("sm_flc", T @ Ts(-1.4, 3.4, 6.65), (1.5, 1.5, 0.18), S, bev=0.02))
    # anvil
    parts.append(bx("sm_ast", T @ Ts(0.4, -1.6, 0.34), (0.8, 0.9, 0.68), WD, bev=0.02))
    parts.append(bx("sm_anv", T @ Ts(0.4, -1.6, 0.80), (0.36, 1.25, 0.28), IR, bev=0.02))
    parts.append(K.cone("sm_horn", T @ Ts(0.4, -1.6, 0.80, rx=-math.pi * 0.5), 0.16, 0.5, IR,
                        seg=8))
    # 4 posts + lean-to roof
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cyl("sm_p%d%d" % (sx, sy),
                             T @ Ts(sx * (Wd * 0.5 - 0.3), sy * (D * 0.5 - 0.3), 1.9),
                             0.15, 3.8, W, seg=8))
    parts.append(bx("sm_beam", T @ Ts(0, D * 0.5 - 0.3, 3.75), (Wd, 0.2, 0.22), W, bev=0.01))
    parts.append(bx("sm_beam2", T @ Ts(0, -D * 0.5 + 0.3, 3.75), (Wd, 0.2, 0.22), W, bev=0.01))
    for k in range(7):
        parts.append(bx("sm_raf%d" % k, T @ Ts(0, -D * 0.5 + 0.5 + k * 1.3, 4.05),
                        (Wd + 0.9, 0.18, 0.18), WD, bev=0.01))
    parts.append(bx("sm_roof", T @ Ts(0.0, 0, 4.35, ry=-math.radians(14)),
                    (Wd + 1.6, D + 1.4, 0.16), TL, bev=0.01))
    for k in range(6):
        parts.append(bx("sm_rc%d" % k, T @ Ts(0.0, -D * 0.5 + 0.6 + k * 1.5, 4.47,
                                             ry=-math.radians(14)),
                        (Wd + 1.7, 0.3, 0.09), SL, bev=0.008))
    # tool rack, coal, quench barrel, grindstone
    parts.append(bx("sm_rack", T @ Ts(2.9, -3.2, 1.5), (0.3, 1.8, 1.5), W, bev=0.01))
    for k in range(5):
        parts.append(bx("sm_tool%d" % k, T @ Ts(2.7, -3.9 + k * 0.36, 1.7), (0.1, 0.1, 1.5),
                        IR, bev=0.006))
        parts.append(bx("sm_head%d" % k, T @ Ts(2.7, -3.9 + k * 0.36, 2.45), (0.18, 0.3, 0.2),
                        IR, bev=0.01))
    parts.append(K.sphere("sm_coal", T @ Ts(-2.2, -0.6, 0.22), 0.62, MAT["iron"], seg=12,
                          ring=8, squash=0.6))
    parts += H.barrel("sm_bar", T @ Ts(1.6, 2.2, 0), wood=WD, hoop=IR)
    parts.append(cyl("sm_grind", T @ Ts(-2.4, -2.2, 0.95, ry=math.pi * 0.5), 0.55, 0.2, S2,
                     seg=20))
    parts.append(bx("sm_gfrm", T @ Ts(-2.4, -2.2, 0.45), (0.9, 0.5, 0.9), W, bev=0.02))


def brazier(parts, MAT, x, y, z=None, s=1.0):
    IR = MAT["iron"]
    S = MAT["stone"]
    F = fire_mat()
    T = Ts(x, y, CY if z is None else z)
    tag = "bz%d_%d" % (int(x * 10), int(y * 10))
    parts.append(cyl(tag + "_b", T @ Ts(0, 0, 0.05), 0.46 * s, 0.06, S, seg=12))
    for i in range(3):
        a = 2.0 * math.pi * i / 3
        parts.append(bx("%s_l%d" % (tag, i), tmat(T, a, 0.30 * s, 0.45 * s),
                        (0.12 * s, 0.12 * s, 0.9 * s), IR, bev=0.006))
    parts.append(H.lathe(tag + "_bwl",
                         [(0.18 * s, 0.80 * s), (0.52 * s, 1.05 * s), (0.58 * s, 1.18 * s),
                          (0.50 * s, 1.16 * s), (0.16 * s, 0.92 * s)],
                         IR, seg=14, T=T, close_bottom=True, close_top=False))
    parts.append(cyl(tag + "_fire", T @ Ts(0, 0, 1.10 * s), 0.46 * s, 0.12, F, seg=12))
    for i in range(3):
        a = 2.0 * math.pi * i / 3 + 0.4
        parts.append(K.cone("%s_fl%d" % (tag, i), tmat(T, a, 0.16 * s, 1.42 * s),
                            0.17 * s, 0.55 * s, F, seg=6))


def market(parts, MAT, x, y, rz, col1, col2, rng):
    T = Ts(x, y, CY, rz=rz)
    parts += H.market_stall("mk%d%d" % (int(x), int(y)), T, 2.6, 1.6, MAT["wood"],
                            MAT[col1], MAT[col2])
    parts += H.barrel("mkb%d%d" % (int(x), int(y)), T @ Ts(-1.5, 0.6, 0), wood=MAT["wood"],
                      hoop=MAT["iron"])
    parts += H.crate("mkc%d%d" % (int(x), int(y)), T @ Ts(1.7, 0.4, 0), 0.62, MAT["wood"])


def courtyard(parts, MAT, rng):
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    TL = MAT["tile"]

    # ---- paving: a processional way from the gate to the keep
    for k in range(24):
        y = 31.0 - k * 1.42
        parts.append(bx("p_path%d_a" % k, Ts(0, y, CY + 0.055), (6.4, 1.34, 0.10), S2,
                        bev=0.01))
        for s in (-1, 1):
            parts.append(bx("p_path%d_b%d" % (k, s), Ts(s * 3.55, y, CY + 0.07),
                            (0.7, 1.34, 0.12), S, bev=0.012))
    # cross path
    for k in range(9):
        x = -26.0 + k * 6.4
        parts.append(bx("p_cross%d" % k, Ts(x, 14.0, CY + 0.05), (6.0, 4.4, 0.09), S2,
                        bev=0.01))
    # scattered flagging round the fountain
    for i in range(10):
        a = 2.0 * math.pi * i / 10
        parts.append(bx("p_ring%d" % i, tmat(Ts(1.0, 12.0, CY), a, 6.2, 0.05),
                        (3.6, 1.6, 0.09), S2, bev=0.01))

    # ---- fountain + well
    fountain(parts, MAT, 1.0, 12.0, 3.0)
    well(parts, MAT, -9.5, -2.0)

    # ---- stairs up to the keep terrace
    parts += H.stairs("cy_kst", Ts(0, -3.2, CY + 0.06), 11.0, 5, rise=0.26, run=0.44,
                      mat=S2)

    # ---- market row (proper stalls live in courtyard_bulk)

    # ---- carts, barrels, crates, hay
    parts += H.cart("cy_cart0", Ts(8.0, 26.5, CY, rz=0.35), W, IR)
    parts += H.cart("cy_cart1", Ts(-2.0, 27.5, CY, rz=-0.2), W, IR)
    for i, (x, y, s) in enumerate(((12.5, 5.0, 0.34), (13.4, 6.4, 0.32), (11.6, 6.9, 0.30),
                                   (-6.0, 24.0, 0.32), (-26.0, 18.0, 0.34),
                                   (20.0, 12.0, 0.33), (20.9, 13.2, 0.31),
                                   (34.0, -2.0, 0.35), (35.0, -1.0, 0.32))):
        parts += H.barrel("cy_bar%d" % i, Ts(x, y, CY), s, s * 2.6, W, IR)
    for i, (x, y, s) in enumerate(((12.0, 3.8, 0.66), (12.4, 3.6, 0.54), (-25.0, 16.4, 0.62),
                                   (21.6, 11.4, 0.58), (33.0, 0.5, 0.6), (-8.5, 25.0, 0.55))):
        parts += H.crate("cy_cr%d" % i, Ts(x, y, CY), s, W)
    for i, (x, y, r, h) in enumerate(((18.0, -2.0, 1.3, 1.7), (19.4, -0.6, 1.0, 1.2))):
        parts += H.haystack("cy_hay%d" % i, Ts(x, y, CY), r, h)
    for i, (x, y, rz) in enumerate(((16.4, 0.9, 0.3), (17.4, -3.2, -0.2), (20.6, -3.0, 0.9))):
        parts.append(bx("cy_hb%d" % i, Ts(x, y, CY + 0.42, rz=rz), (1.5, 0.9, 0.84),
                        MAT["plaster"], bev=0.05))

    # ---- smithy
    smithy(parts, MAT, rng)

    # ---- braziers
    for (x, y) in ((0.0, 30.4), (0.0, 17.5), (-11.0, 3.0), (11.0, 3.0), (-14.0, 18.0)):
        brazier(parts, MAT, x, y)

    # ---- lantern posts along the path
    for i in range(7):
        y = 29.0 - i * 4.6
        for s in (-1, 1):
            parts += H.lantern_post("cy_lp%d_%d" % (i, s), Ts(s * 4.6, y, CY + 0.06), 3.2, IR,
                                    MAT["gold"])

    # ---- training yard
    for i, (x, y) in enumerate(((16.0, 19.0), (21.0, 21.0))):
        parts.append(cyl("ty_p%d" % i, Ts(x, y, CY + 0.9), 0.10, 1.8, W, seg=6))
        parts.append(cyl("ty_t%d" % i, Ts(x, y, CY + 1.9, rx=math.pi * 0.5), 0.62, 0.36,
                         MAT["plaster"], seg=14))
        for k in range(3):
            parts.append(cyl("ty_r%d_%d" % (i, k), Ts(x, y, CY + 0.45 + k * 0.45), 0.66, 0.05,
                             MAT["banner_red"], seg=14))
    parts.append(cyl("ty_pell", Ts(12.0, 21.0, CY + 1.1), 0.16, 2.2, WD, seg=8))
    parts.append(bx("ty_arms", Ts(12.0, 21.0, CY + 1.7), (1.9, 0.18, 0.18), WD, bev=0.01))

    # ---- royal standard in the courtyard
    parts.append(cyl("cy_std", Ts(-4.0, -6.0, CY + 6.0), 0.16, 12.0, WD, seg=10))
    parts.append(K.sphere("cy_stdk", Ts(-4.0, -6.0, CY + 12.2), 0.30, MAT["gold"], seg=12,
                          ring=8))
    for i in range(3):
        parts.append(bx("cy_stdb%d" % i, Ts(-4.0 + 1.15, -6.0, CY + 9.6 - i * 1.5),
                        (2.2, 0.06, 1.34), MAT["banner_gold" if i % 2 else "banner_red"],
                        bev=0.01))

    # ---- staff on the walls: banners round the walk
    for i, (x, y, rz) in enumerate(((7.0, 33.0, 0.0), (-9.0, 32.0, 0.0))):
        parts += banner3("cy_wb%d" % i, Ts(x, y, CY + 0.2, rz=rz), 1.3, 3.0,
                          MAT["banner_red"], WD, pole_h=5.2)


def _inside(x, y, poly):
    """Ray-cast point test against the courtyard outline."""
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


_PAVE_HOLES = [(-15.4, 15.4, -32.4, -9.6),      # keep
               (-33.0, -15.5, -16.4, 6.4),      # great hall
               (15.6, 26.6, -20.4, -5.6),       # chapel
               (27.6, 39.0, -8.4, 8.4),         # stable
               (-30.4, -17.6, 19.6, 32.4),      # guardhouse
               (-13.9, 13.9, 27.0, 40.4),       # gatehouse
               (-3.4, 5.4, 8.0, 16.0)]          # fountain basin


def _in_hole(x, y, pad=0.0):
    for (x0, x1, y0, y1) in _PAVE_HOLES:
        if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
            return True
    return False


def paving(MAT, rng, inset=2.55):
    """Real flagstones, as ONE mesh.

    The v5 version drew dark joint lines on one big slab, which from the air
    read as graph paper pulled over a wooden deck.  This lays 3.3k individual
    stones in a running bond (0.62-1.15 m, three quarry tones, +-4 mm of settle)
    with 18 mm open joints over the dark platform, plus a lighter band course
    every seven rows so the yard reads as laid in bays rather than tiled.
    """
    cx = sum(p[0] for p in OUTLINE) / len(OUTLINE)
    cy = sum(p[1] for p in OUTLINE) / len(OUTLINE)
    inner = []
    for (x, y) in OUTLINE:
        dx, dy = x - cx, y - cy
        L = math.hypot(dx, dy) or 1.0
        inner.append((x - dx / L * inset, y - dy / L * inset))
    xs = [p[0] for p in inner]
    ys = [p[1] for p in inner]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    mats = [K.mat_stone("pave_a", base="#867c6d", dark="#4e4739", light="#a09687",
                        scale=1.6),
            K.mat_stone("pave_b", base="#7a7163", dark="#453f33", light="#948a7a",
                        scale=1.6),
            K.mat_stone("pave_c", base="#8d8373", dark="#554d40", light="#a89e8c",
                        scale=1.6)]
    verts, faces, fidx = [], [], []
    Z = CY + 0.035

    def quad(ax, ay, bx, by, z, mi):
        i = len(verts)
        verts.extend([(ax, ay, z), (bx, ay, z), (bx, by, z), (ax, by, z)])
        faces.append((i, i + 1, i + 2, i + 3))
        fidx.append(mi)

    y = y0 - 0.5
    row = 0
    while y < y1:
        band = (row % 7) == 6
        h = 0.62 if band else rng.uniform(0.62, 1.05)
        off = 0.0 if row % 2 == 0 else rng.uniform(0.28, 0.55)
        x = x0 - 1.2 + off
        while x < x1:
            w = 0.95 if band else rng.uniform(0.62, 1.15)
            mx, my = x + w * 0.5, y + h * 0.5
            if _inside(mx, my, inner) and not _in_hole(mx, my, 0.05):
                if band:
                    quad(x + 0.02, y + 0.05, x + w - 0.02, y + h - 0.05,
                         Z + 0.012, 1)
                else:
                    jz = Z + rng.uniform(-0.004, 0.004)
                    quad(x + 0.018, y + 0.018, x + w - 0.018, y + h - 0.018, jz,
                         rng.choice((0, 0, 2, 1)))
            x += w
        y += h
        row += 1

    me = bpy.data.meshes.new("cy_paving")
    me.from_pydata(verts, [], faces)
    me.update()
    for m in mats:
        me.materials.append(m)
    for f, mi in zip(me.polygons, fidx):
        f.material_index = mi
    me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
    ob = bpy.data.objects.new("cy_paving", me)
    bpy.context.scene.collection.objects.link(ob)
    print("[castle] paving slabs=%d" % len(faces), flush=True)
    return [ob]




def cobbles(MAT, rng, inset=0.95, pitch=0.30):
    """Cobbled traffic lanes, as ONE mesh.

    A castle yard is not uniformly paved: carts, horses and pack animals churn
    the lanes while the standing areas keep their flags.  These are real domed
    cobbles (base ring, shoulder ring, apex - 12 tris each) so the lanes read as
    small rounded stones from eye level instead of a painted-on texture, and the
    joints between them are real gaps down to the flag surface.
    """
    cx = sum(p[0] for p in OUTLINE) / len(OUTLINE)
    cy = sum(p[1] for p in OUTLINE) / len(OUTLINE)
    inner = []
    for (x, y) in OUTLINE:
        dx, dy = x - cx, y - cy
        L = math.hypot(dx, dy) or 1.0
        inner.append((x - dx / L * inset, y - dy / L * inset))
    mats = [K.mat_stone("cob_a", base="#6c665b", dark="#3f3b33", light="#867e6f", scale=2.2),
            K.mat_stone("cob_b", base="#5e594f", dark="#37342d", light="#766f61", scale=2.2),
            K.mat_stone("cob_c", base="#7b7365", dark="#4a453b", light="#918878", scale=2.2)]
    # lanes: (x0, x1, y0, y1) in courtyard coordinates - gate to keep door,
    # gate to the stable, and the service lane in front of the great hall
    lanes = [(-4.6, 4.6, -9.4, 27.2),
             (4.6, 27.2, 2.2, 10.4),
             (-22.4, -4.6, 3.6, 8.2)]
    verts, faces, fidx = [], [], []
    Z = CY + 0.055
    for (lx0, lx1, ly0, ly1) in lanes:
        ny = int((ly1 - ly0) / pitch)
        nx = int((lx1 - lx0) / pitch)
        for j in range(ny):
            for i in range(nx):
                mx = lx0 + (i + 0.5) * pitch + rng.uniform(-0.022, 0.022)
                my = ly0 + (j + 0.5) * pitch + rng.uniform(-0.022, 0.022)
                if not _inside(mx, my, inner) or _in_hole(mx, my, 0.06):
                    continue
                hw = pitch * 0.44 * rng.uniform(0.82, 1.02)
                z0 = Z + rng.uniform(0.0, 0.010)
                h1 = 0.030 * rng.uniform(0.75, 1.25)
                h2 = 0.016 * rng.uniform(0.7, 1.3)
                tw = hw * 0.84
                k = len(verts)
                verts.extend([(mx - hw, my - hw, z0), (mx + hw, my - hw, z0),
                              (mx + hw, my + hw, z0), (mx - hw, my + hw, z0),
                              (mx - tw, my - tw, z0 + h1), (mx + tw, my - tw, z0 + h1),
                              (mx + tw, my + tw, z0 + h1), (mx - tw, my + tw, z0 + h1),
                              (mx + rng.uniform(-0.02, 0.02), my + rng.uniform(-0.02, 0.02),
                               z0 + h1 + h2)])
                mi = rng.choices((0, 1, 2), (0.45, 0.34, 0.21))[0]
                for q in range(4):
                    a, b = k + q, k + (q + 1) % 4
                    faces.append((a, b, b + 4, a + 4))
                    fidx.append(mi)
                    faces.append((k + 4 + q, k + 4 + (q + 1) % 4, k + 8))
                    fidx.append(mi)
    me = bpy.data.meshes.new("cy_cobbles")
    me.from_pydata(verts, [], faces)
    me.update()
    for m in mats:
        me.materials.append(m)
    for f, mi in zip(me.polygons, fidx):
        f.material_index = mi
    me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
    ob = bpy.data.objects.new("cy_cobbles", me)
    bpy.context.scene.collection.objects.link(ob)
    print("[castle] cobbles stones=%d" % (len(verts) // 9), flush=True)
    return [ob]



def stall(parts, MAT, nm, x, y, rz, col, rng, w=2.9, d=1.9):
    """A market stall that reads as a stall: four posts, a sloping canvas, a
    counter and goods under it.  H.market_stall's awning collapsed into a heap
    of planks at this scale."""
    T = Ts(x, y, CY, rz=rz)
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    # muted canvas rather than the saturated banner cloth: a pure #c81e2b awning
    # reads as a coloured chip from the aerial, not as cloth
    CL = MAT.get("cv_" + col.split("_")[-1], MAT[col])
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(bx("%s_p%d%d" % (nm, sx, sy), T @ Ts(sx * (w * 0.5 - 0.10),
                                                            sy * (d * 0.5 - 0.10), 1.28),
                          (0.16, 0.16, 2.56), W, bev=0.012))
    # counter
    out.append(bx(nm + "_ct", T @ Ts(0, d * 0.30, 0.92), (w - 0.2, 0.72, 0.14), W, bev=0.012))
    for sx in (-1, 1):
        out.append(bx("%s_cl%d" % (nm, sx), T @ Ts(sx * (w * 0.5 - 0.32), d * 0.30, 0.46),
                      (0.14, 0.62, 0.92), WD, bev=0.01))
    out.append(bx(nm + "_cb", T @ Ts(0, d * 0.30, 0.40), (w - 0.7, 0.10, 0.10), WD))
    # sloping canvas: two panels meeting at a ridge, hanging over the front
    for sy, tilt in ((-1, 0.20), (1, -0.20)):
        out.append(bx("%s_cv%d" % (nm, sy), T @ Ts(0, sy * d * 0.28, 2.42, rx=tilt),
                      (w + 0.5, d * 0.62, 0.06), CL, bev=0.0))
    out.append(bx(nm + "_rg", T @ Ts(0, 0, 2.74), (w + 0.5, 0.10, 0.10), WD))
    # valance
    for sy in (-1, 1):
        out.append(bx("%s_va%d" % (nm, sy), T @ Ts(0, sy * (d * 0.5 + 0.14), 2.06),
                      (w + 0.5, 0.05, 0.34), CL, bev=0.0))
    # goods on the counter
    for k in range(4):
        out.append(H.crate("%s_g%d" % (nm, k),
                           T @ Ts(-w * 0.30 + k * (w * 0.22), d * 0.30, 1.08),
                           0.32 + 0.05 * (k % 2), W))
    out += H.barrel(nm + "_br", T @ Ts(w * 0.5 - 0.3, -d * 0.5 + 0.3, 0), 0.30, 0.78, W, IR)
    out.append(bx(nm + "_bn", T @ Ts(w * 0.5 + 0.1, 0, 2.3), (0.9, 0.05, 1.3), CL, bev=0.0))
    parts += out


def courtyard_bulk(parts, MAT, rng):
    """Density pass: the yard reads as a working fortress, not a plaza."""
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    PL = MAT["plaster"]
    # ---- firewood stacks along the hall wall
    for i in range(3):
        x = -12.2 + i * 0.0
        for k in range(7):
            parts.append(cyl("fw%d_%d" % (i, k), Ts(x - 0.55 + k * 0.19, 8.4 - i * 1.30,
                                                    CY + 0.18 + (k % 2) * 0.02, rx=math.pi * 0.5,
                                                    rz=0.0), 0.17, 1.5, WD, seg=7))
    # ---- plank stack + trestles (carpenters' yard)
    for k in range(6):
        parts.append(bx("pl%d" % k, Ts(-20.5, 12.5 + k * 0.02, CY + 0.14 + k * 0.13),
                        (4.2, 0.42, 0.11), W, bev=0.008))
    for k in range(2):
        parts.append(bx("plt%d" % k, Ts(-20.5, 12.1 + k * 0.8, CY + 0.42),
                        (0.16, 0.16, 0.8), WD))
    # ---- trestle tables + benches, market square
    for i, (x, y, rz) in enumerate(((-6.4, 17.6, 0.0), (-2.4, 17.6, 0.0),
                                    (9.0, 15.0, 0.35), (-16.0, 15.0, -0.2))):
        T = Ts(x, y, CY, rz=rz)
        parts.append(bx("tb%d_t" % i, T @ Ts(0, 0, 0.80), (3.0, 1.1, 0.10), W, bev=0.01))
        for sx in (-1, 1):
            parts.append(bx("tb%d_l%d" % (i, sx), T @ Ts(sx * 1.25, 0, 0.42),
                            (0.14, 0.9, 0.84), WD, bev=0.008))
            for sy in (-1, 1):
                parts.append(bx("tb%d_b%d%d" % (i, sx, sy),
                                T @ Ts(sx * 0.7, sy * 0.95, 0.40), (1.9, 0.28, 0.08), W,
                                bev=0.008))
                parts.append(bx("tb%d_bl%d%d" % (i, sx, sy),
                                T @ Ts(sx * 0.7, sy * 0.95, 0.20), (0.10, 0.24, 0.40), WD,
                                bev=0.006))
    # ---- sacks, baskets, pottery: small-scale clutter in clusters
    for i, (x, y) in enumerate(((-4.2, 20.2), (-3.4, 20.9), (-3.9, 19.6), (6.4, 13.2),
                                (7.1, 12.4), (-18.4, 6.2), (-17.9, 5.4), (25.0, 20.5),
                                (25.8, 21.4), (26.3, 20.1), (-28.0, 26.0), (-27.2, 26.8))):
        parts += H.barrel("sk%d" % i, Ts(x, y, CY), 0.30, 0.72, PL, MAT["wood"], ),
    for i, (x, y, s) in enumerate(((8.6, 12.0, 0.5), (9.1, 11.6, 0.44), (-5.0, 19.0, 0.48),
                                   (18.0, 22.5, 0.52), (18.6, 23.2, 0.42), (-15.0, 6.6, 0.46))):
        parts.append(K.sphere("sac%d" % i, Ts(x, y, CY + s * 0.45), s * 0.62, PL, seg=10,
                              ring=7))
    # ---- laundry lines between the hall and the well
    for i, (x0, y0, x1, y1) in enumerate(((-11.0, -1.0, -11.0, 6.0),
                                          (-11.0, 6.0, -18.0, 6.0))):
        a = Vector((x0, y0, 0))
        b = Vector((x1, y1, 0))
        n = 4
        for k in range(n + 1):
            p = a.lerp(b, k / n)
            parts.append(bx("ll%d_p%d" % (i, k), Ts(p.x, p.y, CY + 1.9),
                            (0.09, 0.09, 3.8), WD))
        mid = a.lerp(b, 0.5)
        L = (b - a).length
        rz = math.atan2(b.y - a.y, b.x - a.x)
        parts.append(bx("ll%d_r" % i, Ts(mid.x, mid.y, CY + 3.7, rz=rz),
                        (L, 0.035, 0.035), MAT["iron"]))
        for k in range(5):
            u = 0.12 + k * 0.19
            p = a.lerp(b, u)
            col = (MAT["plaster"], MAT["banner_blue"], MAT["banner_gold"],
                   MAT["plaster"], MAT["banner_red"])[k]
            parts.append(bx("ll%d_c%d" % (i, k), Ts(p.x, p.y, CY + 3.05, rz=rz),
                            (0.72, 0.03, 1.25), col, bev=0.0))
    # ---- horse trough + hitching rail
    parts.append(bx("trough", Ts(20.5, 3.4, CY + 0.42), (2.6, 0.85, 0.84), S2, bev=0.02))
    parts.append(bx("trough_w", Ts(20.5, 3.4, CY + 0.72), (2.2, 0.62, 0.30), MAT["glass"],
                    bev=0.0))
    for i in range(4):
        parts.append(bx("hr%d" % i, Ts(23.0, 1.0 + i * 1.8, CY + 0.55), (0.12, 0.12, 1.1), WD))
    parts.append(bx("hr_r", Ts(23.0, 3.7, CY + 1.05), (0.10, 5.4, 0.10), WD))
    # ---- two more carts, laden
    parts += H.cart("bl_cart2", Ts(-16.0, 26.5, CY, rz=1.15), W, IR)
    parts += H.cart("bl_cart3", Ts(24.5, 16.0, CY, rz=-0.8), W, IR)
    for i, (x, y) in enumerate(((-16.0, 26.5), (24.5, 16.0))):
        for k in range(3):
            parts += H.crate("bl_cc%d_%d" % (i, k), Ts(x - 0.8 + k * 0.75, y + 0.35, CY + 0.85),
                             0.5, W)
    # ---- hay rick + feed rack by the stable
    parts += H.haystack("bl_hay2", Ts(31.0, 10.5, CY), 1.7, 2.2)
    parts += H.haystack("bl_hay3", Ts(33.5, 11.6, CY), 1.2, 1.6)
    for i in range(3):
        parts.append(bx("fr%d" % i, Ts(29.0, 12.4 + i * 0.55, CY + 0.55), (1.5, 0.10, 1.1),
                        WD))
    # ---- paling fence round the training yard
    for i in range(6):
        parts.append(bx("pf%d" % i, Ts(13.0 + i * 1.9, 24.6, CY + 0.7), (0.12, 0.12, 1.4), WD))
    for i in range(2):
        parts.append(bx("pf_r%d" % i, Ts(17.7, 24.6, CY + 0.55 + i * 0.62),
                        (9.8, 0.09, 0.10), W))
    # ---- 3 proper market stalls replacing the collapsed awning piles
    stall(parts, MAT, "st_a", -18.6, 22.4, 0.05, "banner_red", rng)
    stall(parts, MAT, "st_b", -13.0, 23.6, -0.04, "banner_gold", rng)
    stall(parts, MAT, "st_c", -7.4, 21.6, 0.08, "banner_blue", rng)
    stall(parts, MAT, "st_d", 26.5, -12.0, 1.55, "banner_red", rng, w=2.4, d=1.7)
    # ---- 4 more braziers, warm points of light in the aerial
    for (x, y) in ((18.0, 8.0), (-20.0, 0.0), (6.0, -14.0), (-6.0, 28.0)):
        brazier(parts, MAT, x, y)
    return parts


def garrison_yard(parts, MAT, rng):
    """The north-east quadrant: the part of the yard the aerial showed empty."""
    S2 = MAT["stone"]
    W = MAT["wood"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    PL = MAT["plaster"]
    CV = MAT.get("cv_blue", MAT["banner_blue"])
    # ---- three garrison tents, ridge tents with a pole and guy ropes
    for i, (x, y, rz, s) in enumerate(((15.0, 25.5, 0.25, 1.0), (19.2, 27.3, -0.35, 0.85),
                                       (12.0, 29.0, 0.55, 0.9))):
        T = Ts(x, y, CY, rz=rz)
        w, d, h = 3.0 * s, 2.4 * s, 2.0 * s
        # a solid triangular prism, not two leaning plates: two thin panels in a
        # V read as a paper butterfly from the air
        parts.append(H.prism("gt%d_a" % i, T, [(-w * 0.5, 0.0), (w * 0.5, 0.0), (0.0, h)],
                             d, CV, axis="y"))
        parts.append(bx("gt%d_sk" % i, T @ Ts(0, 0, 0.10), (w + 0.24, d + 0.24, 0.10),
                        MAT["wood_dark"], bev=0.0))
        parts.append(cyl("gt%d_rd" % i, T @ Ts(0, 0, h + 0.02, rx=math.pi * 0.5), 0.055,
                         d + 0.10, WD, seg=6))
        parts.append(cyl("gt%d_p" % i, T @ Ts(0, 0, h + 0.55), 0.05, 1.2, WD, seg=6))
        # door flap and two guy ropes
        parts.append(bx("gt%d_dr" % i, T @ Ts(0, -d * 0.5 - 0.03, h * 0.28),
                        (0.72 * s, 0.06, h * 0.56), MAT["wood_dark"], bev=0.0))
        for sy in (-1, 1):
            parts.append(cyl("gt%d_g%d" % (i, sy),
                             T @ Ts(0, sy * (d * 0.5 + 0.55), 0.85, rx=sy * 0.72), 0.022,
                             1.9, WD, seg=4))
            parts.append(cyl("gt%d_gk%d" % (i, sy), T @ Ts(0, sy * (d * 0.5 + 1.45), 0.04),
                             0.035, 0.28, WD, seg=4))
    # ---- baggage wagon with a canvas tilt
    T = Ts(7.0, 20.5, CY, rz=0.9)
    parts.append(bx("gv_bed", T @ Ts(0, 0, 0.85), (2.0, 4.2, 0.18), W, bev=0.02))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cyl("gv_w%d%d" % (sx, sy), T @ Ts(sx * 1.05, sy * 1.45, 0.62,
                                                           ry=math.pi * 0.5),
                             0.62, 0.16, WD, seg=14))
    parts.append(bx("gv_tilt", T @ Ts(0, 0, 1.55), (1.7, 3.0, 0.8), CV, bev=0.10))
    parts.append(bx("gv_tilt2", T @ Ts(0, 0, 1.95), (1.2, 2.6, 0.16), CV, bev=0.06))
    for k in range(3):
        parts.append(bx("gv_rib%d" % k, T @ Ts(0, -1.0 + k * 1.0, 1.62),
                        (1.78, 0.10, 0.10), WD))
    # ---- pike rack and shield rack
    T = Ts(22.6, 6.0, CY, rz=-1.2)
    for k in range(8):
        parts.append(cyl("pk%d" % k, T @ Ts(-1.05 + k * 0.30, 0.10, 1.05), 0.045, 2.1, W,
                         seg=5, r2=0.02))
    for sy in (-1, 1):
        parts.append(bx("pk_r%d" % sy, T @ Ts(0, 0.10, 0.95 + sy * 0.42),
                        (2.6, 0.10, 0.10), WD))
    T = Ts(-11.4, 12.0, CY, rz=math.pi * 0.5)
    parts.append(bx("sr_f", T @ Ts(0, 0, 1.05), (3.0, 0.14, 0.14), WD))
    for k in range(4):
        parts += shield("sr_s%d" % k, T @ Ts(-1.05 + k * 0.70, 0.12, 1.05), 0.56, 0.74,
                        (MAT["banner_red"], MAT["banner_blue"], MAT["banner_gold"],
                         MAT["banner_red"])[k], MAT["iron"])
    # ---- cook fire: stone ring, cauldron, tripod, logs
    x, y = 17.0, 16.0
    for k in range(9):
        a = 2.0 * math.pi * k / 9
        parts.append(bx("cf_s%d" % k, Ts(x + math.cos(a) * 0.85, y + math.sin(a) * 0.85,
                                          CY + 0.11, rz=a), (0.42, 0.30, 0.22), S2,
                        bev=0.03))
    for k in range(3):
        a = 2.0 * math.pi * k / 3 + 0.4
        parts.append(cyl("cf_l%d" % k, Ts(x + math.cos(a) * 0.35, y + math.sin(a) * 0.35,
                                          CY + 0.22, rz=a, rx=0.3), 0.13, 1.1, WD, seg=6))
    parts.append(cyl("cf_fire", Ts(x, y, CY + 0.20), 0.56, 0.10, fire_mat(), seg=12))
    parts.append(H.lathe("cf_pot", [(0.10, 0.0), (0.46, 0.16), (0.52, 0.62), (0.42, 0.66),
                                    (0.38, 0.30), (0.10, 0.20)],
                         IR, seg=14, T=Ts(x, y, CY + 0.46), close_bottom=True,
                         close_top=False))
    for k in range(3):
        a = 2.0 * math.pi * k / 3
        parts.append(cyl("cf_tr%d" % k, Ts(x + math.cos(a) * 0.55, y + math.sin(a) * 0.55,
                                           CY + 0.95, rz=-a, rx=0.42), 0.045, 2.0, WD,
                         seg=5))
    # ---- timber hoist inside the gate (clear of the 12.4 m gate passage)
    T = Ts(4.6, 25.4, CY)
    parts.append(bx("gh_m", T @ Ts(0, 0, 2.9), (0.30, 0.30, 5.8), WD, bev=0.02))
    parts.append(bx("gh_j", T @ Ts(0, -1.5, 5.5), (0.24, 3.4, 0.24), WD, bev=0.02))
    parts.append(bx("gh_st", T @ Ts(0, -0.9, 4.9, rx=0.72), (0.16, 2.0, 0.16), WD))
    parts.append(cyl("gh_rope", T @ Ts(0, -3.0, 3.4), 0.045, 4.2, MAT["plaster"], seg=5))
    parts.append(bx("gh_hook", T @ Ts(0, -3.0, 1.25), (0.30, 0.16, 0.34), IR, bev=0.02))
    for k in range(2):
        parts.append(bx("gh_br%d" % k, T @ Ts(0, 0.55 + k * 0.5, 1.0), (0.14, 0.14, 2.0),
                        WD))
    return parts


# ---------------------------------------------------------------------------
# roof furniture and courtyard sculpture
# ---------------------------------------------------------------------------
def dormer(nm, T, S, S2, TL, GL, WD, wdt=1.30, dep=1.10, hgt=1.52):
    """A roof dormer: body, cheeks, glazed light, pitched cap and sill."""
    out = [bx(nm + "_b", T @ Ts(0, -0.32, hgt * 0.5), (wdt, dep + 0.68, hgt), S, bev=0.02)]
    for s in (-1, 1):
        out.append(bx(nm + "_c%d" % s, T @ Ts(s * (wdt * 0.5 - 0.09), 0.06, hgt * 0.52),
                      (0.18, dep, hgt * 0.96), S2, bev=0.012))
    out.append(bx(nm + "_dk", T @ Ts(0, 0.24, hgt * 0.46), (wdt * 0.62, 0.10, hgt * 0.62),
                  shadow_mat(), bev=0.0))
    out.append(bx(nm + "_gl", T @ Ts(0, 0.29, hgt * 0.46), (wdt * 0.56, 0.05, hgt * 0.56),
                  GL, bev=0.0))
    for s in (-1, 1):
        out.append(bx(nm + "_mb%d" % s, T @ Ts(s * wdt * 0.15, 0.32, hgt * 0.46),
                      (0.07, 0.04, hgt * 0.56), WD, bev=0.0))
    out.append(bx(nm + "_sl", T @ Ts(0, 0.31, hgt * 0.14), (wdt * 0.76, 0.28, 0.11), S2,
                  bev=0.012))
    for s in (-1, 1):
        out.append(bx(nm + "_r%d" % s, T @ Ts(s * wdt * 0.27, -0.18, hgt + 0.32, ry=s * 0.72),
                      (wdt * 0.80, dep + 0.82, 0.12), TL, bev=0.008))
    out.append(bx(nm + "_rg", T @ Ts(0, -0.18, hgt + 0.62), (0.22, dep + 0.86, 0.16), S2,
                  bev=0.012))
    return out


def roof_furniture(parts, MAT, rng):
    """Dormers and chimney stacks on the four wings: the roofs were large empty
    planes from the air, and a dormer row is what makes a roof read as inhabited."""
    S = MAT["stone_warm"]
    S2 = MAT["stone"]
    TL = MAT["tile"]
    GL = MAT["glass"]
    WD = MAT["wood_dark"]
    IR = MAT["iron"]
    # building -> (cx, cy, half span, ridge z, pitch tan, dormer ys, chimneys, tile)
    # the tile material must be the WING's own roof material: the first pass passed
    # the red tile for every wing and the chapel came out with red dormer caps on a
    # blue slate roof.
    wings = [
        ("hd_", -24.25, -5.0, 8.85, CY + 12.0 + 8.85 * math.tan(math.radians(46)), 46.0,
         (-12.0, -5.0, 2.0), ((-29.0, -12.0), (-19.0, 3.5)), MAT["tile"]),
        ("cd_", 21.10, -13.0, 5.60, CY + 13.0 + 5.60 * math.tan(math.radians(52)), 52.0,
         (-16.5, -9.5), (), MAT["slate"]),
        ("sd_", 33.30, 0.0, 5.80, CY + 5.4 + 5.80 * math.tan(math.radians(42)), 42.0,
         (-5.2, 5.2), (), MAT["tile"]),
        ("qd_", -24.00, 26.0, 6.50, CY + 10.5 + 6.50 * math.tan(math.radians(44)), 44.0,
         (23.4, 28.6), (), MAT["tile"]),
    ]
    for pre, cx, cy, hw, ridge, pitch, ys, chs, TLw in wings:
        tp = math.tan(math.radians(pitch))
        for s in (-1, 1):
            dx = hw * 0.55
            zs = ridge - dx * tp
            rz = math.pi * 0.5 if s < 0 else -math.pi * 0.5
            for k, y in enumerate(ys):
                if pre in ("hd_", "cd_") or k == 0 or s > 0:
                    parts += dormer("%sdm%d_%d" % (pre, s, k),
                                    Ts(cx + s * dx, y, zs - 0.62, rz=rz), S, S2, TLw, GL,
                                    WD,
                                    wdt=1.34 if pre != "sd_" else 1.10,
                                    hgt=1.56 if pre != "sd_" else 1.30)
        for k, (chx, chy) in enumerate(chs):
            zc = ridge - abs(chx - cx) * tp
            parts += H.chimney("%sch%d" % (pre, k), Ts(chx, chy, zc - 1.0), 3.4, S2,
                               pots=4)
    # ---- statues: fountain corners and either side of the keep stair
    for k, (sx, sy, rz) in enumerate((
            (1.0 + 4.6, 12.0 - 4.6, -math.pi * 0.25), (1.0 - 4.6, 12.0 + 4.6,
                                                       math.pi * 0.75),
            (1.0 - 4.6, 12.0 - 4.6, math.pi * 0.25), (1.0 + 4.6, 12.0 + 4.6,
                                                      -math.pi * 0.75))):
        parts += H.statue("st_f%d" % k, Ts(sx, sy, CY, rz=rz), 2.6, S2)
        parts.append(bx("st_fp%d" % k, Ts(sx, sy, CY + 0.10), (1.9, 1.9, 0.34), S, bev=0.03))
        parts.append(bx("st_fq%d" % k, Ts(sx, sy, CY + 0.30), (1.55, 1.55, 0.22), S2,
                        bev=0.03))
    for s in (-1, 1):
        parts += H.statue("st_k%d" % s, Ts(s * 5.6, -21.0 + 11.0 + 5.2, CY + 1.5, rz=0.0),
                          2.8, S2)
        parts.append(bx("st_kp%d" % s, Ts(s * 5.6, -4.8, CY + 0.55), (1.7, 1.7, 1.1), S,
                        bev=0.03))
        parts.append(bx("st_kq%d" % s, Ts(s * 5.6, -4.8, CY + 1.14), (1.9, 1.9, 0.16), S2,
                        bev=0.03))
    return parts


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------
def build(MAT, rng):
    """Return the list of objects making up the castle (origin-centred)."""
    parts = []
    build_base(parts, MAT)
    build_curtain(parts, MAT, rng)
    build_corner_towers(parts, MAT, rng)
    gatehouse(parts, MAT, rng)
    keep(parts, MAT, rng)
    great_hall(parts, MAT, rng)
    chapel(parts, MAT, rng)
    stable(parts, MAT, rng)
    guardhouse(parts, MAT, rng)
    courtyard(parts, MAT, rng)
    parts += paving(MAT, rng)
    parts += cobbles(MAT, rng)
    courtyard_bulk(parts, MAT, rng)
    garrison_yard(parts, MAT, rng)
    roof_furniture(parts, MAT, rng)
    # flatten any nested list a helper may have returned, then centre on origin
    flat = []
    for o in parts:
        if isinstance(o, (list, tuple)):
            flat.extend(o)
        elif o is not None:
            flat.append(o)
    # centre the footprint on the module origin in BOTH plan axes.  Measuring
    # the built geometry instead of trusting a hand-tuned constant is what keeps
    # the origin honest when the entrance sequence grows outwards.
    xs = [o.matrix_world @ Vector(c) for o in flat for c in o.bound_box]
    cx = (min(v.x for v in xs) + max(v.x for v in xs)) * 0.5
    cy = (min(v.y for v in xs) + max(v.y for v in xs)) * 0.5
    H.apply(flat, Ts(-cx, -cy, 0))
    # a couple of ground slabs are deliberately sunk 0.1 m to avoid z-fighting
    # with the caller's terrain; lift the whole model so the footprint sits
    # exactly on z = 0 as the API promises
    zlo = min((o.matrix_world @ Vector(c)).z for o in flat for c in o.bound_box)
    if zlo < 0.0:
        for o in flat:
            o.location.z -= zlo
        bpy.context.view_layer.update()
    return flat


def make_mats():
    """Preview materials - the caller supplies its own dict in engine use."""
    M = {}
    M["stone"] = K.mat_stone()
    M["stone_warm"] = K.mat_stone("stone_sand", base="#8d8168", dark="#5b5342",
                                  light="#a89b7f", scale=2.0)
    M["wood"] = K.mat_wood()
    M["wood_dark"] = K.mat_wood("timber_dark", base="#3a2517", light="#543823", scale=12)
    M["tile"] = K.mat_tile()
    M["tile_blue"] = K.mat_tile("roof_blue", base="#3f5566", dark="#2b3b49",
                                light="#557088")
    M["slate"] = K.mat_tile("roof_slate", base="#4a5560", dark="#333c46", light="#5f6d7a")
    M["glass"] = K.mat_glass()
    M["iron"] = K.mat_metal()
    M["gold"] = K.mat_gold()
    M["plaster"] = K.mat_plaster()
    M["banner_red"] = K.mat_cloth("banner_red", "#8e2b26")
    M["banner_blue"] = K.mat_cloth("banner_blue", "#26365e")
    M["banner_gold"] = K.mat_cloth("banner_gold", "#c9a227")
    # standing moat water: darker and greener than the kit's mirror-like
    # default, which reflected the sky and read as blue paint
    M["water"] = K.mat_water("moat_water", base="#2c3f38")
    return M


def stats(parts):
    lo, hi = H.bbox(parts)
    print("[castle] parts=%d tris=%d bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f) "
          "size=(%.1f,%.1f,%.1f)"
          % (len(parts), H.tri_count(parts), lo.x, lo.y, lo.z, hi.x, hi.y, hi.z,
             hi.x - lo.x, hi.y - lo.y, hi.z - lo.z), flush=True)
    return lo, hi


def fill_light():
    """H.setup_world's sun comes from -Y, so the +Y gate is backlit in every
    required view.  Add a cool sky-bounce sun from +Y for the gate shots."""
    lamp = bpy.data.lights.new("castle_fill", "SUN")
    lamp.energy = 2.35
    lamp.angle = math.radians(14.0)
    lamp.color = (0.86, 0.90, 1.0)
    ob = bpy.data.objects.new("castle_fill", lamp)
    ob.rotation_euler = (math.radians(-52.0), 0.0, math.radians(-28.0))
    bpy.context.scene.collection.objects.link(ob)
    return ob


def preview():
    H._clear()
    MAT = make_mats()
    # muted awnings for the market stalls (preview only: the caller's MAT may
    # not carry these, so stall() falls back to the banner cloth)
    MAT["cv_red"] = K.mat_cloth("canvas_red", "#8f3628")
    MAT["cv_gold"] = K.mat_cloth("canvas_gold", "#b1934f")
    MAT["cv_blue"] = K.mat_cloth("canvas_blue", "#3c5a70")
    rng = random.Random(11)
    parts = build(MAT, rng)
    lo, hi = stats(parts)
    H.diorama_floor(K.mat_flag("plateau", base="#7d7568", dark="#4a4438"), 320.0)
    H.setup_world()
    fill_light()
    H.setup_engine(samples=160, res=(1600, 900))
    H.three_views("castle", center=(0, 0, 26), size=(105, 105), dist=120)
    gy = GATE_YF + SHIFT_Y
    # the required gate close-up: eye height 2 m, 25 m off the drawbridge.
    # 24 mm cut the tower tops off, so this is 20 mm aimed at the window band.
    cam = H.camera("cam_gate", (7.5, gy + 25.0, 2.0), (0.0, gy - 4.0, 14.5), lens=20)
    H.render_to(os.path.join(OUT, "hd_castle_gate.png"), cam)
    # a second, wider gate shot from the causeway: reads the whole gatehouse
    cam3 = H.camera("cam_gate2", (16.0, gy + 52.0, 9.0), (0.0, gy - 2.0, 16.0), lens=35)
    H.render_to(os.path.join(OUT, "hd_castle_gate2.png"), cam3)
    # the entrance sequence as the player meets it: a proper approach shot from
    # the causeway, wide enough to hold the moat, the bridge, the barbican and
    # the gatehouse stack in one frame.  The old 38 mm shot cut the barbican's
    # head off and never showed the water at all.
    cama2 = H.camera("cam_app", (9.0, gy + 96.0, 7.0), (0.0, gy - 16.0, 13.0), lens=30)
    H.render_to(os.path.join(OUT, "hd_castle_approach.png"), cama2)
    # barbican close-up at eye height: arch, half-raised herse, shields, and the
    # lit passage behind it
    camr = H.camera("cam_road", (5.0, gy + 42.0, 2.3), (0.0, gy - 4.0, 11.0), lens=32)
    H.render_to(os.path.join(OUT, "hd_castle_barbican.png"), camr)
    # along the moat from the east: water, revetments and the bridge profile,
    # which is invisible from every head-on angle because the barbican hides it
    camm = H.camera("cam_moat", (56.0, gy + 10.0, 7.0), (6.0, gy + 4.0, 4.5), lens=30)
    H.render_to(os.path.join(OUT, "hd_castle_moat.png"), camm)
    # QA aerial from the city side: moat, island, bridge and wall-walk in one shot
    cama = H.camera("cam_air", (46.0, gy + 82.0, 48.0), (0.0, 18.0, 8.0), lens=42)
    H.render_to(os.path.join(OUT, "hd_castle_air.png"), cama)
    # my own +Y (city-facing) three-quarter, since H.three_views sits on -Y
    cam2 = H.camera("cam_front", (44.0, gy + 86.0, 34.0), (0.0, 4.0, 20.0), lens=45)
    H.render_to(os.path.join(OUT, "hd_castle_front.png"), cam2)
    # QA: the keep's south-east corner turret, to judge the corbel bell
    cam4 = H.camera("cam_keep", (27.0, 21.0, 7.0), (14.0, -9.0, 33.0), lens=48)
    H.render_to(os.path.join(OUT, "hd_castle_keep.png"), cam4)
    # honest view: exactly the same front shot with the preview fill light gone,
    # i.e. what the engine's own lighting will give us
    fl = bpy.data.objects.get("castle_fill")
    if fl is not None:
        fl.hide_render = True
        H.render_to(os.path.join(OUT, "hd_castle_front_nofill.png"), cam2)
        fl.hide_render = False
    print("[castle] done", flush=True)


if __name__ == "__main__":
    preview()
