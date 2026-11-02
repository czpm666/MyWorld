"""
build_port.py - harbour town archetype (port_a / port_b / port_c).

    blender -b --factory-startup --python build_port.py -- --variant port_a

Town band (canonical LOCAL layout, entrance always at -Y):

    y -44.0 .. -35.0  approach road                        z 0.00
    y -35.0 .. -27.2  forecourt, two gate trees            z 0.00
    y -27.2 .. -26.2  three steps up
    y -26.2           town gate (5.0 m clear)
    y -27.2 .. -19.2  upper town on a stone terrace        z 0.45
    y -19.2 .. -18.0  three steps down
    y -18.0 ..  -5.2  main street, 4.8 m facade to facade  z 0.00
    y  -5.2 ..   6.8  market square, 12 x 12 m             z 0.00
    y   6.8 ..  21.2  cargo yard, one 2.5 m cart rut       z 0.00
    y  21.2 ..  25.55 quay promenade                       z 0.35
    y  26.0 ..        water (river(), untouched)

Every variant is the same skeleton with a different character; the rotation is
0 for all three so the entrance faces -Y in Unity space and the review cameras
frame the same composition for each variant.

Outputs per variant
  export/kingdom/port/<v>.fbx
  kingdom/<v>.blend
  renders/kingdom/<v>.png        1280x720 EEVEE overview
  renders/kingdom/<v>_player.png player camera (game pitch)
  renders/kingdom/<v>_eye.png    eye-level street view
  kingdom/port_measure_<v>.json  measured object / tri / material / bbox + self check
"""
import bpy
import json
import math
import os
import random
import sys
import time

from mathutils import Vector

BL = r"E:\My World\Blender"
KINGDOM = os.path.join(BL, "kingdom")
EXPORT_DIR = os.path.join(BL, "export", "kingdom", "port")
RENDER_DIR = os.path.join(BL, "renders", "kingdom")
for _p in (BL, KINGDOM):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import medkit as mk          # noqa: E402
import medbuild as mb        # noqa: E402
import portlib as P          # noqa: E402
from medkit import T_at, box, cyl, cone  # noqa: E402

BUCKETS = ("ground", "quay", "works", "boats", "buildings", "props", "foliage")

# The entrance of every variant must sit at Blender -Y, which is Unity -Z, so no
# variant may be rotated: the street, the gate and the harbour all line up on
# the world axis and the fixed review cameras frame the same composition.
VARIANT_ROT = {"port_a": 0.0, "port_b": 0.0, "port_c": 0.0}

# overview camera in LOCAL space: (location, target, lens)
VARIANT_CAM = {
    "port_a": ((-46.0, 58.0, 50.0), (0.0, 8.0, 2.0), 40.0),
    "port_b": ((-52.0, 54.0, 46.0), (0.0, 10.0, 2.0), 40.0),
    "port_c": ((-40.0, 60.0, 53.0), (0.0, 9.0, 2.0), 40.0),
}

# review cameras: fixed world positions, shared by all variants
CAM_PLAYER = ((0.0, -13.5, 17.3), (0.0, 0.5, 0.0), 40.0)
CAM_EYE = ((2.2, -9.0, 1.7), (0.0, 3.5, 2.2), 35.0)
CAM_TOP = ((0.0, 0.0, 108.0), (0.0, 0.0, 0.0), 30.0)

# ---------------------------------------------------------------------------
# town metrics (metres, canonical local space)
# ---------------------------------------------------------------------------
# cloth names -> render colour, seeded in build_town before any other prop
_CLOTH_HEX = {"banner_red": "#7d2e26", "banner_trim": "#7a5a24",
              "bloom": "#4c5a68", "sack": "#8a7c63"}
Y_FACE = 26.0
APP_Y = -44.0
FC_Y = -35.0                 # forecourt south edge (urban edge)
TERR_Y0 = -29.4              # terrace south retaining edge
TERR_Z = 0.45
STEP_Y = -21.6               # terrace north edge -> three steps down
ST_Y0 = -21.6                # main street starts here
PLZ_Y0, PLZ_Y1 = -10.0, 2.0  # 12 m deep market square
PLZ_X = 6.8                  # 13.6 m wide, meets both plinths
YARD_Y0, YARD_Y1 = 2.0, 21.2
QUAY_Y0, QUAY_Y1 = 21.2, 25.55
QUAY_Z = 0.35
BND_W = -13.2                # west town wall
BND_E = 15.6                 # east town wall (warehouse back)
ST_HW = 2.10                 # carriageway half width
FAC_X = 2.40                 # facade line -> street 4.8 m, setback 0.30
GATE_Y = -28.4
CORE_C = (0.0, -3.0)         # town centre of gravity, for the radial check


# ---------------------------------------------------------------------------
# scene assembly helpers
# ---------------------------------------------------------------------------
def _flat(seq, out):
    """Generators nest their return values; flatten to a list of objects."""
    if seq is None:
        return
    if isinstance(seq, bpy.types.Object):
        out.append(seq)
        return
    try:
        it = iter(seq)
    except TypeError:
        out.append(seq)
        return
    for x in it:
        _flat(x, out)


class Scene(object):
    def __init__(self, F):
        self.F = F
        self.g = dict((k, []) for k in BUCKETS)
        # self-check bookkeeping (footprints, not geometry)
        self.houses = []      # (tag, x0, x1, y0, y1, core)
        self.grass = []       # (x0, x1, y0, y1)
        self.walls = []       # (tag, x0, y0, x1, y1, anchored)
        self.piers = []       # (tag, length, y_head)
        self.levels = set([0.0])
        self.notes = {}

    def add(self, bucket, parts):
        added = []
        _flat(parts, added)
        # bevels are invisible at town scale and cost ~3x the triangles
        P.strip_bev(added)
        self.g[bucket].extend(added)

    def T(self, x, y, z=0.0, rz=0.0, ry=0.0, rx=0.0):
        """Variant-space transform: local layout coords -> world."""
        return self.F @ T_at(x, y, z, rz=rz, ry=ry, rx=rx)

    def house(self, tag, x0, x1, y0, y1, core=True):
        self.houses.append((tag, x0, x1, y0, y1, core))

    def wall(self, tag, x0, y0, x1, y1, anchored=True):
        self.walls.append((tag, x0, y0, x1, y1, anchored))

    def level(self, z):
        self.levels.add(round(z, 3))


def turf(sc, tag, x0, x1, y0, y1):
    """Rough pasture outside the town walls -- a thin layer on the plate."""
    m = mk.mat_foliage("grass_field", "#4d5c33", "#6b7842", 2.6)
    sc.grass.append((x0, x1, y0, y1))
    return [box(tag, sc.T((x0 + x1) * 0.5, (y0 + y1) * 0.5, 0.015),
                (x1 - x0, y1 - y0, 0.03), m)]


def row_fill(y0, y1, widths):
    """Lay `widths` out along [y0, y1] with equal gaps between neighbours.

    Returns specs (y_centre, W) plus the gap actually used, so the street
    frontage is always closed and the gap stays inside 0.4..1.5 m.
    """
    span = y1 - y0
    free = span - sum(widths)
    g = free / float(len(widths) - 1) if len(widths) > 1 else 0.0
    out, y = [], y0
    for i, W in enumerate(widths):
        out.append((round(y + W * 0.5, 3), W))
        y += W + (g if i < len(widths) - 1 else 0.0)
    return out, round(g, 3)


def house_row(sc, tag, side, x_line, specs, z=0.0, seed=0, deep=6.0, nfs=(2,),
              kws=None, win=3):
    """Row of houses whose FRONT sits on x_line.

    side = -1 (front faces +X, west row) or +1 (front faces -X, east row).
    specs: list of (y_centre, W).
    """
    out = []
    kws = kws or [{}] * len(specs)
    for i, (yc, W) in enumerate(specs):
        nF = nfs[i % len(nfs)]
        rz = -math.pi * 0.5 if side < 0 else math.pi * 0.5
        T = sc.T(x_line + side * deep * 0.5, yc, z, rz=rz)
        rng = random.Random(seed + i * 17)
        kw = dict(kws[i % len(kws)])
        out += P.house_port("%s%d" % (tag, i), T, W=W, D=deep, nF=nF,
                            pi=2 + (i * 3 + seed) % 4,
                            ti=(i * 2 + seed) % 5,
                            rng=rng, win_front=win if W > 4.0 else 2, **kw)
        x0 = min(x_line, x_line + side * deep)
        x1 = max(x_line, x_line + side * deep)
        sc.house("%s%d" % (tag, i), x0, x1, yc - W * 0.5, yc + W * 0.5)
    return out


def street_dressing(sc, seed, carts=(), racks=(), coils=(), fishcr=(), bags=()):
    rng = random.Random(seed)
    parts = []
    for i, (x, y, rz) in enumerate(carts):
        parts += P.cart_loaded("cart%d" % i, sc.T(x, y, 0.0, rz=rz), rng=rng)
    for i, (x, y, rz) in enumerate(racks):
        parts += P.net_rack("rack%d" % i, sc.T(x, y, 0.0, rz=rz))
    for i, (x, y) in enumerate(coils):
        parts += P.rope_coil("coil%d" % i, sc.T(x, y, 0.0))
    for i, (x, y, rz) in enumerate(fishcr):
        parts += P.fish_crate("fc%d" % i, sc.T(x, y, 0.0, rz=rz))
    for i, (x, y) in enumerate(bags):
        parts += mb.crate_stack("cs%d" % i, sc.T(x, y, 0.0), rng)
        parts += mb.barrel_cluster("bcl%d" % i, sc.T(x + 1.35, y - 0.4, 0.0), rng)
    return parts


def yard_pen(sc, tag, x, y, w, d, rng=None):
    """Fenced working yard: rails, log pile, crates and barrels, no idle grass."""
    rng = rng or random.Random(11)
    parts = []
    dirt = mk.mat_earth("earth_yard", "#5c4c3a", "#3f3527")
    parts.append(box(tag + "_lot", sc.T(x, y, 0.045), (w - 0.3, d - 0.3, 0.09), dirt))
    for sy in (-1, 1):
        parts += P.wall_run("%s_%d" % (tag, sy), sc.F, x - w * 0.5, y + sy * d * 0.5,
                            x + w * 0.5, y + sy * d * 0.5, h=1.05, t=0.11,
                            kind="fence")
        sc.wall("%s_%d" % (tag, sy), x - w * 0.5, y + sy * d * 0.5,
                x + w * 0.5, y + sy * d * 0.5, True)
    for sx in (-1, 1):
        parts += P.wall_run("%s_%d" % (tag, sx + 4), sc.F, x + sx * w * 0.5,
                            y - d * 0.5, x + sx * w * 0.5, y + d * 0.5,
                            h=1.05, t=0.11, kind="fence")
        sc.wall("%s_%d" % (tag, sx + 4), x + sx * w * 0.5, y - d * 0.5,
                x + sx * w * 0.5, y + d * 0.5, True)
    parts += P.woodpile(tag + "_lg", sc.T(x - w * 0.22, y + d * 0.18, 0.08))
    parts += mb.crate_stack(tag + "_cs", sc.T(x + w * 0.24, y - d * 0.18, 0.08), rng)
    parts += mb.barrel_cluster(tag + "_bc", sc.T(x + w * 0.10, y + d * 0.26, 0.08),
                               rng)
    return parts


# ---------------------------------------------------------------------------
# the canonical town
# ---------------------------------------------------------------------------
def build_town(sc, rng, cfg):
    """Build the shared dense harbour skeleton; cfg picks the character."""
    # seed the three cloth colours first, so no prop can claim those names
    # with a different colour (the material cache is keyed by name alone)
    for _cn, _ch in (("banner_red", "#7d2e26"), ("banner_trim", "#7a5a24"),
                     ("bloom", "#4c5a68"), ("sack", "#8a7c63")):
        mk.mat_cloth(_cn, _ch, 0.92)
    cob = P.m_cobble()
    cob2 = P.m_cobble2()
    flg = P.m_flag()
    slb = P.m_slab()
    stp = P.m_step()
    wall = P.m_wall()
    tim = P.m_timber()
    dirt = mk.mat_earth("earth_path", "#5e4e3b", "#43382a")

    # -- ground ------------------------------------------------------------
    sc.add("ground", P.ground_plate("grd", sc.F, cob))
    sc.add("quay", P.river("riv", sc.F, land_x=16.2))

    # pasture outside the walls; the town paves over everything inside
    sc.add("works", turf(sc, "turf_s", -60.0, 60.0, -60.0, TERR_Y0))
    sc.add("works", turf(sc, "turf_w", -60.0, BND_W, TERR_Y0, QUAY_Y0))
    sc.add("works", turf(sc, "turf_e", BND_E, 60.0, TERR_Y0, QUAY_Y0))
    sc.add("works", turf(sc, "turf_nw", -60.0, -20.0, QUAY_Y0, 25.8))
    sc.add("works", turf(sc, "turf_ne", 20.0, 60.0, QUAY_Y0, 25.8))

    # -- approach road + forecourt ----------------------------------------
    sc.add("works", P.paving("rd", sc.F, 5.6, 9.0, dirt, th=0.09,
                             cx=0.0, cy=APP_Y + 4.5))
    sc.add("works", P.paving("fc", sc.F, 19.2, 7.8, dirt, th=0.08,
                             cx=0.0, cy=TERR_Y0 - 3.9))
    sc.add("works", P.paving("fcf", sc.F, 9.6, 8.0, flg, th=0.10,
                             cx=0.0, cy=TERR_Y0 - 4.0,
                             border=slb, bw=0.18, bh=0.04))
    for sx in (-1, 1):
        sc.add("works", P.paving("rdk%d" % sx, sc.F, 0.5, 9.0, slb, th=0.11,
                                 cx=sx * 3.05, cy=APP_Y + 4.5))

    # -- upper town terrace (+0.45) ---------------------------------------
    sc.add("works", P.plinth("terr", sc.F @ T_at((BND_W + BND_E) * 0.5,
                                                 (TERR_Y0 + STEP_Y) * 0.5),
                             BND_E - BND_W, TERR_Y0 - STEP_Y, TERR_Z,
                             body=wall, top=flg))
    sc.level(TERR_Z)
    sc.add("works", P.stairs("terr_st", sc.F @ T_at(0, TERR_Y0, 0.0, rz=math.pi),
                             n=3, rise=0.15, run=0.32, width=5.6,
                             cheek_h=0.26, cheek_t=0.36))
    sc.add("works", P.stairs("st_dn", sc.F @ T_at(0, STEP_Y, 0.0),
                             n=3, rise=0.15, run=0.32, width=5.6,
                             cheek_h=0.26, cheek_t=0.36))

    # -- street / square / yard / quay paving -----------------------------
    st_d = abs(STEP_Y - PLZ_Y0)
    sc.add("works", P.paving("st", sc.F, ST_HW * 2.0, st_d, cob, th=0.10,
                             cx=0.0, cy=(STEP_Y + PLZ_Y0) * 0.5))
    for sx in (-1, 1):
        sc.add("works", P.paving("gut%d" % sx, sc.F, 0.30, st_d, slb, th=0.115,
                                 cx=sx * (ST_HW + 0.15),
                                 cy=(STEP_Y + PLZ_Y0) * 0.5))
    sc.add("works", P.paving("plz", sc.F, PLZ_X * 2.0, PLZ_Y1 - PLZ_Y0, slb,
                             th=0.12, cx=0.0, cy=(PLZ_Y0 + PLZ_Y1) * 0.5,
                             border=stp, bw=0.22, bh=0.05))
    sc.add("works", P.paving("yrd", sc.F, (BND_E - BND_W),
                             YARD_Y1 - YARD_Y0, cob2, th=0.09,
                             cx=(BND_W + BND_E) * 0.5,
                             cy=(YARD_Y0 + YARD_Y1) * 0.5))
    # one cart rut, 1.6 m wide, off the axis, square -> quay
    sc.add("works", P.paving("rut", sc.F, 1.6, YARD_Y1 - YARD_Y0, dirt, th=0.10,
                             cx=1.35, cy=(YARD_Y0 + YARD_Y1) * 0.5))
    sc.add("works", P.paving("qy", sc.F, 40.0, QUAY_Y1 - QUAY_Y0, flg, th=0.10,
                             cx=0.0, cy=(QUAY_Y0 + QUAY_Y1) * 0.5))
    for x0 in (-2.6, 8.2):
        sc.add("works", P.stairs("qst%d" % int(x0), sc.F @ T_at(x0, QUAY_Y0, -0.10),
                                 n=2, rise=0.175, run=0.30, width=4.4,
                                 cheek=False))
    sc.level(QUAY_Z)
    # sea wall coping: low stone lip along the water, opened at the gangways
    cx0 = -20.0
    gaps = [(16.6 - cx0, 19.4 - cx0), (5.2 - cx0, 7.2 - cx0), (-7.4 - cx0, -5.4 - cx0)]
    sc.add("works", P.wall_run("sea", sc.F, cx0, QUAY_Y1, 20.0, QUAY_Y1, h=0.30,
                               t=0.34, kind="stone", gaps=gaps))
    sc.wall("sea", cx0, QUAY_Y1, 20.0, QUAY_Y1, True)
    for gx in (6.2, -6.4):
        sc.add("works", P.gangway_steps("gws%d" % int(gx * 10),
                                        sc.F @ T_at(gx, QUAY_Y1 + 0.05, QUAY_Z - 0.10),
                                        n=5))

    # -- house rows (frontage closed, gaps from row_fill) -----------------
    low_w, g_lw = row_fill(ST_Y0, PLZ_Y0, cfg["w_low_w"])
    low_e, g_le = row_fill(ST_Y0, PLZ_Y0, cfg["w_low_e"])
    up_w, g_uw = row_fill(TERR_Y0, STEP_Y, cfg["w_up_w"])
    up_e, g_ue = row_fill(TERR_Y0, STEP_Y, cfg["w_up_e"])
    sc.add("buildings", house_row(sc, "uw", -1, -FAC_X, up_w, TERR_Z, 3,
                                  nfs=cfg["n_up_w"], kws=cfg.get("k_up_w")))
    sc.add("buildings", house_row(sc, "ue", +1, FAC_X, up_e, TERR_Z, 5,
                                  nfs=cfg["n_up_e"], kws=cfg.get("k_up_e")))
    sc.add("buildings", house_row(sc, "lw", -1, -FAC_X, low_w, 0.0, 7,
                                  nfs=cfg["n_low_w"], kws=cfg.get("k_low_w")))
    sc.add("buildings", house_row(sc, "le", +1, FAC_X, low_e, 0.0, 10,
                                  nfs=cfg["n_low_e"], kws=cfg.get("k_low_e")))
    sc.notes["gaps"] = [g_lw, g_le, g_uw, g_ue]
    sc.notes["streets"] = {"street": ST_Y0, "plaza": PLZ_Y0, "terrace": TERR_Y0}

    # -- town gate -------------------------------------------------------
    sc.add("buildings", P.town_gate("gate", sc.F @ T_at(0, GATE_Y, TERR_Z),
                                    clear=5.0))
    sc.notes["gate"] = [0.0, GATE_Y]

    # -- closed boundary: wall + gate + quay corner towers ----------------
    W = cfg["wall"]
    for sx, x1, nm in ((-1, BND_W, "w"), (1, BND_E, "e")):
        # south wall on the terrace, from the gate pier to the corner
        sc.add("works", P.wall_run("bnd_s%s" % nm, sc.F, sx * 3.05, GATE_Y,
                                   x1, GATE_Y, h=1.30, t=0.42, kind=W, mat=wall))
        sc.wall("bnd_s%s" % nm, sx * 3.05, GATE_Y, x1, GATE_Y, True)
        # terrace side wall
        sc.add("works", P.wall_run("bnd_t%s" % nm, sc.F, x1, GATE_Y, x1, STEP_Y,
                                   h=1.10, t=0.40, kind=W, mat=wall))
        sc.wall("bnd_t%s" % nm, x1, GATE_Y, x1, STEP_Y, True)
        # lower town side wall, all the way to the quay
        sc.add("works", P.wall_run("bnd_l%s" % nm, sc.F, x1, STEP_Y, x1, QUAY_Y0,
                                   h=1.10, t=0.40, kind=W, mat=wall))
        sc.wall("bnd_l%s" % nm, x1, STEP_Y, x1, QUAY_Y0, True)
        # quay corner tower closes the end of the run
        sc.add("works", P.plinth("tw%s" % nm, sc.F @ T_at(x1, QUAY_Y0), 1.9, 1.9,
                                 3.15, body=wall, top=stp, cope=0.20, cope_h=0.14))
        sc.add("props", P.lamp_post("twl%s" % nm, sc.F @ T_at(x1, QUAY_Y0, 3.30),
                                    h=1.9))
        # yard kerb between square and working yard (5.2 m opening on the axis)
        sc.add("works", P.wall_run("yrdk%s" % nm, sc.F, sx * 2.6, YARD_Y0,
                                   x1, YARD_Y0, h=0.36, t=0.30, kind="stone",
                                   mat=wall))
        sc.wall("yrdk%s" % nm, sx * 2.6, YARD_Y0, x1, YARD_Y0, True)

    # -- market square: fish market west, warehouse east ------------------
    fmx = (BND_W + PLZ_X * 0.5) * 0.5 - 1.4      # plinth centre, west
    sc.add("works", P.plinth("fmp", sc.F @ T_at(-10.0, -4.0), 6.4, 10.0, 0.45,
                             body=wall, top=flg))
    sc.level(0.45)
    sc.add("works", P.stairs("fms", sc.F @ T_at(-6.78, -4.0, 0.0, rz=-math.pi * 0.5),
                             n=3, rise=0.15, run=0.30, width=5.2,
                             cheek_h=0.10, cheek_t=0.24))
    sc.add("buildings", P.fish_market("fmk", sc.F @ T_at(-10.0, -4.0, 0.45,
                                                        rz=-math.pi * 0.5),
                                      w=7.0, d=5.4, pitch=32.0))
    sc.house("fmk", BND_W, -6.8, -9.0, 1.0)
    for (y0, y1, tg) in ((PLZ_Y0 + 0.05, -9.0, "n"), (1.0, PLZ_Y1, "s")):
        sc.add("works", P.wall_run("pwl" + tg, sc.F, -PLZ_X, y0, -PLZ_X, y1,
                                   h=1.05, t=0.34, kind="stone", mat=wall))
        sc.wall("pwl" + tg, -PLZ_X, y0, -PLZ_X, y1, True)
    sc.add("works", P.plinth("whp", sc.F @ T_at(11.0, -4.0), 8.4, 9.0, 0.90,
                             body=wall, top=flg))
    sc.level(0.90)
    sc.add("works", P.stairs("whs", sc.F @ T_at(6.80, -4.0, 0.0, rz=math.pi * 0.5),
                             n=6, rise=0.15, run=0.30, width=4.6,
                             cheek_h=0.12, cheek_t=0.26))
    sc.add("buildings", P.warehouse("wh", sc.F @ T_at(11.0, -4.0, 0.90,
                                                     rz=math.pi * 0.5),
                                    W=8.2, D=7.4, FH=3.1, pitch=36.0,
                                    pi=3, ti=1, rng=rng, hoist=True, annex=False))
    sc.house("wh", 7.2, BND_E, -8.5, 0.5)
    for (y0, y1, tg) in ((PLZ_Y0 + 0.05, -8.5, "n"), (0.5, PLZ_Y1, "s")):
        sc.add("works", P.wall_run("pwr" + tg, sc.F, PLZ_X, y0, PLZ_X, y1,
                                   h=1.05, t=0.34, kind="stone", mat=wall))
        sc.wall("pwr" + tg, PLZ_X, y0, PLZ_X, y1, True)

    # -- cargo yard: crane plinths + boat shed ----------------------------
    for sx in (-1, 1):
        sc.add("works", P.plinth("crp%d" % sx, sc.F @ T_at(sx * 3.9, 18.2),
                                 2.6, 4.0, 0.90, body=wall, top=flg))
        sc.add("works", P.stairs("crs%d" % sx,
                                 sc.F @ T_at(sx * 3.9, 16.2, 0.0, rz=math.pi),
                                 n=5, rise=0.18, run=0.30, width=2.4,
                                 cheek_h=0.10, cheek_t=0.22))
    sc.add("buildings", P.boat_shed("bshed", sc.F @ T_at(-10.2, 16.2, 0.0,
                                                         rz=-math.pi * 0.5),
                                    W=5.6, D=6.0))
    sc.house("bshed", BND_W, -7.2, 13.4, 19.0, core=False)
    # the boat shed's south face fills the right of the eye frame: board it up
    dbt = P.wood("wood_door_big", "#5a3f27", "#7a5936", 0.82)
    shb = P.wood("wood_shutter", "#6b4b2f", "#8a6239")
    for i, xx in enumerate((-12.4, -11.0)):
        sc.add("props", box("bsd%d" % i, sc.F @ T_at(xx, 13.33, 1.06),
                            (1.28, 0.10, 2.06), dbt, bev=0.008))
        for j in range(2):
            sc.add("props", box("bsbr%d%d" % (i, j),
                                sc.F @ T_at(xx, 13.28, 0.55 + j * 1.0),
                                (1.24, 0.05, 0.10), tim))
    sc.add("props", box("bswb", sc.F @ T_at(-8.1, 13.36, 2.16),
                        (0.92, 0.08, 0.80), shb, bev=0.01))
    sc.add("props", box("bswg", sc.F @ T_at(-8.1, 13.30, 2.16),
                        (0.76, 0.04, 0.64), shb, bev=0.0))
    sc.add("props", P.net_panel("bsn", sc.F @ T_at(-8.15, 13.28, 1.05),
                                w=1.9, h=1.15))
    stacks = []
    for i, xx in enumerate((-12.0, -9.6)):
        for j in range(4):
            stacks.append(box("bst%d%d" % (i, j),
                              sc.F @ T_at(xx, 12.60 - j * 0.34,
                                          0.20 + j * 0.20),
                              (1.9, 0.30, 0.19), tim, bev=0.008))
    sc.add("props", stacks)
    sc.add("props", P.crate_pile("bsc", sc.F @ T_at(-8.0, 11.35),
                                 nx=2, ny=2, nz=1, rng=random.Random(9)))
    # horizontal cladding + a faded harbour sign break up the flat gable wall
    for i, zz in enumerate((2.35, 3.15, 3.95)):
        sc.add("props", box("bsbt%d" % i, sc.F @ T_at(-10.2, 13.18, zz),
                            (5.5, 0.11, 0.26), mk.mat_wood("wood_timber", "#5a4530", "#7a6348"), bev=0.004))
    for i, xx in enumerate((-13.0, -7.4)):
        sc.add("props", box("bscb%d" % i, sc.F @ T_at(xx, 13.18, 2.9),
                            (0.20, 0.11, 5.4), mk.mat_wood("wood_timber", "#5a4530", "#7a6348"), bev=0.004))
    sc.add("props", box("bssg", sc.F @ T_at(-10.2, 13.20, 4.55),
                        (3.4, 0.10, 0.86), mk.mat_wood("wood_sign", "#6a4a2c", "#8a6238"), bev=0.01))
    sc.add("props", P.lamp_post("bslp", sc.F @ T_at(-6.9, 13.1, 0.0), h=2.9))
    return dict(cob=cob, flg=flg, slb=slb, stp=stp, wall=wall, tim=tim)


def yard_shed(sc, tag, T, W=4.4, D=3.0, FH=2.4, pi=3, ti=4):
    """Open-fronted lean-to store used in the working yards."""
    Wm = P.m_wall()
    Tm = P.m_timber()
    parts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(mk.box(tag + "_p%d%d" % (sx, sy),
                                T @ T_at(sx * (W / 2 - 0.16), sy * (D / 2 - 0.16), FH * 0.5),
                                (0.22, 0.22, FH), Tm))
    parts.append(mk.box(tag + "_b", T @ T_at(0, -D / 2 + 0.12, FH * 0.5),
                        (W, 0.18, FH), Wm))
    for sx in (-1, 1):
        parts.append(mk.box(tag + "_s%d" % sx, T @ T_at(sx * (W / 2 - 0.09), 0, FH * 0.52),
                            (0.18, D, FH * 1.04), Wm))
    parts.append(mk.gable_roof(tag + "_rf", T @ T_at(0, 0, FH), W + 0.5, D + 0.5, 0.0,
                              33.0, P.tile(ti), Tm, ov_side=0.40, ov_gable=0.40))
    return parts

def periphery(sc, rng):
    """Fill the plate margin between the town wall and the plate edge.

    Nothing here is allowed to be an empty apron: every band is a working yard
    (cooperage / net-drying / cart yard / smallholding) enclosed by a 1.2-1.4 m
    wall whose ends land on the town wall, a pier, or the plate-edge curtain.
    """
    W = P.m_wall()
    SL = P.m_slab()
    TM = P.m_timber()
    fb_leaf_a = mk.mat_foliage("leaf_broad_hi", "#3d4f26", "#5c7038", 3.2)
    ZH = 1.28

    # --- plate-edge curtain: reads as the town boundary from any angle ------
    for sx in (-1, 1):
        sc.add("works", P.wall_run("curt%d" % sx, sc.F, sx * 43.6, -43.6,
                                   sx * 43.6, 23.2, h=1.42, t=0.55, mat=W))
    sc.add("works", P.wall_run("curtn", sc.F, -43.6, -43.6, 43.6, -43.6,
                               h=1.42, t=0.55, mat=W))

    # --- east: cooperage yard (x 16..31, y -8..10) --------------------------
    sc.add("works", P.wall_run("ey_s", sc.F, 16.0, -8.0, 31.0, -8.0, h=ZH, t=0.38, mat=W))
    sc.add("works", P.wall_run("ey_n", sc.F, 16.0, 10.0, 31.0, 10.0, h=ZH, t=0.38, mat=W))
    sc.add("works", P.wall_run("ey_e", sc.F, 31.0, -8.0, 31.0, 10.0, h=ZH, t=0.38,
                               mat=W, gaps=((7.2, 9.4),)))
    for sy in (-1, 1):
        sc.add("works", P.plinth("ey_gp%d" % sy, sc.F @ T_at(31.0, -0.2 + sy * 1.5),
                                 0.62, 0.62, 1.55, body=W, top=SL))
    sc.add("works", P.paving("ey_gd", sc.F, 14.4, 17.4,
                                 mk.mat_earth("earth_yard", "#5b4f3d", "#3d342a"),
                                 th=0.05, cx=23.5, cy=1.0))
    sc.add("props", P.crate_pile("ey_c1", sc.F @ T_at(19.4, 6.4, 0.02), 3, 2, 2,
                                 rng=random.Random(410)))
    sc.add("props", P.crate_pile("ey_c2", sc.F @ T_at(24.6, -5.2, 0.02), 2, 3, 2,
                                 rng=random.Random(411)))
    sc.add("props", P.crate_pile("ey_c3", sc.F @ T_at(28.2, 3.2, 0.02), 2, 2, 1,
                                 rng=random.Random(412)))
    for i, (bx, by) in enumerate(((18.2, -3.4), (18.9, -2.2), (17.9, -1.0),
                                  (23.2, 8.2), (24.1, 7.4), (22.4, 8.6),
                                  (28.0, -6.0), (28.9, -5.0))):
        sc.add("props", mb.barrel("ey_b%d" % i, sc.F @ T_at(bx, by, 0.02),
                                  r=0.30, h=0.84, rng=random.Random(420 + i)))
    # cooper's lean-to: gable roof on four posts, open on the town side
    sc.add("buildings", yard_shed(sc, "ey_sh", sc.F @ T_at(26.6, 7.0, 0.02, rz=math.pi),
                                W=4.6, D=3.2, FH=2.5, pi=3, ti=4))
    sc.add("props", P.woodpile("ey_wp", sc.F @ T_at(17.4, 8.4, 0.05), L=2.6))

    # --- west: net-drying + fish-drying yard (x -31..-14.5, y -8..10) -------
    sc.add("works", P.wall_run("wy_s", sc.F, -31.0, -8.0, -14.6, -8.0, h=ZH, t=0.38, mat=W))
    sc.add("works", P.wall_run("wy_n", sc.F, -31.0, 10.0, -14.6, 10.0, h=ZH, t=0.38, mat=W))
    sc.add("works", P.wall_run("wy_w", sc.F, -31.0, -8.0, -31.0, 10.0, h=ZH, t=0.38,
                               mat=W, gaps=((6.8, 9.0),)))
    for sy in (-1, 1):
        sc.add("works", P.plinth("wy_gp%d" % sy, sc.F @ T_at(-31.0, 0.9 + sy * 1.5),
                                 0.62, 0.62, 1.55, body=W, top=SL))
    sc.add("works", P.paving("wy_gd", sc.F, 16.0, 17.4,
                                 mk.mat_earth("earth_yard", "#5b4f3d", "#3d342a"),
                                 th=0.05, cx=-22.8, cy=1.0))
    for i, (nx, ny) in enumerate(((-28.0, 6.6), (-25.2, 6.6), (-28.0, 3.0), (-25.2, 3.0),
                                  (-28.0, -0.6), (-25.2, -0.6))):
        sc.add("props", P.net_rack("wy_nr%d" % i, sc.F @ T_at(nx, ny, 0.02, rz=math.pi * 0.5),
                                   w=3.0, h=2.0))
    # fish-drying frames: three trestles with slats and pale fish
    for i, fx in enumerate((-20.2, -17.8)):
        for j, fy in enumerate((-5.4, -1.2, 3.0)):
            sc.add("props", box("wy_fd%d%d" % (i, j), sc.F @ T_at(fx, fy, 0.62),
                                (0.10, 2.6, 1.24), TM))
            sc.add("props", box("wy_fs%d%d" % (i, j), sc.F @ T_at(fx, fy, 1.20),
                                (0.72, 2.6, 0.10), TM))
            sc.add("props", box("wy_ff%d%d" % (i, j), sc.F @ T_at(fx, fy, 1.06),
                                (0.56, 2.3, 0.16), P.fish_mat()))
    for i, (rx, ry) in enumerate(((-22.4, 8.4), (-29.2, -5.6), (-16.4, 8.2), (-22.0, -6.2))):
        sc.add("props", P.rope_coil("wy_rc%d" % i, sc.F @ T_at(rx, ry, 0.03, rz=rng.uniform(0, 3))))
    sc.add("buildings", yard_shed(sc, "wy_sh", sc.F @ T_at(-27.4, -5.6, 0.02, rz=-math.pi * 0.5),
                                W=4.2, D=3.0, FH=2.4, pi=2, ti=3))

    # --- north: cart yard + smallholding (y -36..-43.4) ---------------------
    sc.add("works", P.wall_run("ny_s", sc.F, -20.0, -36.4, 20.0, -36.4, h=ZH, t=0.38,
                               mat=W, gaps=((18.0, 22.0),)))
    for sx in (-1, 1):
        sc.add("works", P.plinth("ny_gp%d" % sx, sc.F @ T_at(sx * 1.1, -36.4),
                                 0.60, 0.60, 1.50, body=W, top=SL))
    sc.add("works", P.paving("ny_gd", sc.F, 38.0, 6.6,
                                 mk.mat_earth("earth_yard", "#5b4f3d", "#3d342a"),
                                 th=0.05, cx=0.0, cy=-39.9))
    for i, (cx, cy, crz) in enumerate(((-13.0, -39.4, 0.4), (-8.6, -41.2, -0.3),
                                       (11.4, -40.0, 2.9))):
        sc.add("props", mb.cart("ny_ct%d" % i, sc.F @ T_at(cx, cy, 0.02, rz=crz), rng=random.Random(430 + i)))
    for i, (hx, hy) in enumerate(((-17.4, -41.6), (-15.0, -42.4), (16.2, -39.0))):
        sc.add("props", mk.cyl("ny_hay%d" % i, sc.F @ T_at(hx, hy, 0.0), 0.92, 1.5,
                               mk.mat_foliage("leaf_hay", "#8a7231", "#a89040", 3.0), seg=12))
        sc.add("props", mk.cone("ny_hc%d" % i, sc.F @ T_at(hx, hy, 1.5), 1.05, 0.75,
                                mk.mat_foliage("leaf_hay", "#8a7231", "#a89040", 3.0), seg=12))
    for i, (wx, wy) in enumerate(((5.4, -41.8), (7.2, -42.6))):
        sc.add("props", P.woodpile("ny_wp%d" % i, sc.F @ T_at(wx, wy, 0.05), L=2.4))
    sc.add("props", P.trough("ny_tg", sc.F @ T_at(-3.6, -40.6, 0.04, rz=math.pi * 0.5)))
    sc.add("props", P.veg_bed("ny_vb1", sc.F @ T_at(19.6, -40.2, 0.03), 5.0, 3.4))
    sc.add("props", P.veg_bed("ny_vb2", sc.F @ T_at(-24.6, -39.6, 0.03), 5.0, 3.4))
    sc.add("props", P.chicken_coop("ny_cc", sc.F @ T_at(24.4, -38.6, 0.02),
                                   rng=random.Random(440)))

    # --- outer bands: orchard rows + ploughed strips -----------------------
    for row, (ox, oy) in enumerate(((36.0, -4.0), (-36.0, -2.0), (34.0, -26.0))):
        for k in range(2):
            for m in range(2 if row < 2 else 1):
                sc.add("foliage", mb.tree("pb_t%d%d%d" % (row, k, m),
                                         sc.F @ T_at(ox + m * 3.7 - 1.85, oy + k * 3.9 - 1.95, 0.02),
                                         h=4.2, rng=random.Random(450 + row * 9 + k * 3 + m),
                                         leaf_mat=fb_leaf_a, species="broad"))
        sc.add("foliage", mk.sphere("pb_hb%d" % row, sc.F @ T_at(ox + 3.4, oy - 1.2, 0.5),
                                    0.85, fb_leaf_a, seg=10, ring=6, squash=0.7))
        sc.add("foliage", mk.sphere("pb_hb2%d" % row, sc.F @ T_at(ox - 3.6, oy + 1.4, 0.45),
                                    0.72, fb_leaf_a, seg=10, ring=6, squash=0.7))
    # --- hedgerow patchwork: worked land right up to the plate curtain -----
    HG = P.m_hedge()
    for hy in (-15.0, -27.0, 15.0, 23.0):
        sc.add("works", P.wall_run("hgw%d" % int(hy), sc.F, 16.2, hy, 43.2, hy,
                                   h=1.15, t=0.55, kind="hedge"))
        sc.add("works", P.wall_run("hge%d" % int(hy), sc.F, -43.2, hy, -16.2, hy,
                                   h=1.15, t=0.55, kind="hedge"))
    for hx in (-30.0, 30.0):
        sc.add("works", P.wall_run("hgv%d" % int(hx), sc.F, hx, -35.8, hx, 23.0,
                                   h=1.15, t=0.55, kind="hedge",
                                   gaps=((-8.4, 10.6),) if hx > 0 else ((6.4, 9.0),)))

    # ploughed strips sit inside those paddocks
    plots = ((26.0, -21.0, 11.0, 5.4), (36.6, -21.0, 9.0, 5.4),
             (-26.0, -21.0, 11.0, 5.4), (-36.6, -21.0, 9.0, 5.4),
             (26.0, 18.6, 11.0, 5.4), (36.6, 18.6, 9.0, 5.4),
             (-26.0, 18.6, 11.0, 5.4), (-36.6, -31.0, 9.0, 5.4),
             (0.0, -47.0, 26.0, 6.0), (0.0, 47.4, 26.0, 5.0))
    for i, (fx, fy, fw, fh) in enumerate(plots):
        sc.add("works", mk.box("pb_fd%d" % i, sc.F @ T_at(fx, fy, 0.04),
                               (fw, fh, 0.08), mk.mat_earth("earth_garden", "#4a3d2e", "#332a1f")))
        nrow = max(3, int(fw / 1.05))
        for k in range(nrow):
            sc.add("works", mk.box("pb_fr%d_%d" % (i, k),
                                   sc.F @ T_at(fx - fw * 0.5 + 0.55 + k * 1.05, fy, 0.13),
                                   (0.44, fh - 1.0, 0.14),
                                   mk.mat_foliage("leaf_crop", "#5c6a33", "#7d8a46", 3.0)))
    # field furniture: hayshed, haystack rows, troughs, a second orchard
    sc.add("buildings", yard_shed(sc, "hb1", sc.F @ T_at(39.0, -31.0, 0.02), W=5.0, D=3.6,
                                  FH=2.6, pi=2, ti=4))
    sc.add("buildings", yard_shed(sc, "hb2", sc.F @ T_at(-39.0, -31.0, 0.02, rz=math.pi),
                                  W=4.6, D=3.2, FH=2.4, pi=3, ti=3))
    for i, (hx, hy) in enumerate(((33.4, -8.6), (35.2, -9.8), (-33.8, -6.4),
                                  (-35.4, -7.6), (-33.0, 27.0))):
        sc.add("props", mk.cyl("pb_hs%d" % i, sc.F @ T_at(hx, hy, 0.0), 0.88, 1.45,
                               mk.mat_foliage("leaf_hay", "#8a7231", "#a89040", 3.0), seg=10))
        sc.add("props", mk.cone("pb_hc%d" % i, sc.F @ T_at(hx, hy, 1.45), 1.0, 0.72,
                                mk.mat_foliage("leaf_hay", "#8a7231", "#a89040", 3.0), seg=10))
    for i, (tx, ty) in enumerate(((32.0, 12.6), (-32.0, 12.6), (32.0, -33.0))):
        sc.add("props", P.trough("pb_tg%d" % i, sc.F @ T_at(tx, ty, 0.04, rz=0.0)))
    for row, (ox, oy) in enumerate(((38.4, 30.2), (-38.4, 31.6))):
        sc.add("foliage", mk.sphere("pb_ob%d" % row, sc.F @ T_at(ox, oy, 0.62),
                                    1.05, fb_leaf_a, seg=10, ring=6, squash=0.72))


# ---------------------------------------------------------------------------
# shared dressing
# ---------------------------------------------------------------------------
def dress(sc, rng, cfg):
    """Square story groups, quay furniture, yard cargo, boats, trees."""
    cob, slb, tim, wall = P.m_cobble(), P.m_slab(), P.m_timber(), P.m_wall()

    # --- market square ---------------------------------------------------
    # everything sits inside the wedge the fixed player camera can actually
    # see (|x| <= 4.5 at the square's near half), leaving a 2.4 m walking
    # lane down the axis from the street to the yard.
    # clutter in the square's middle band so the frame is never empty paving
    sc.add("props", P.crate_pile("pz1", sc.F @ T_at(-2.8, 2.6, 0.12),
                                 nx=2, ny=2, nz=1, rng=random.Random(41)))
    sc.add("props", P.crate_pile("pz2", sc.F @ T_at(2.6, 4.6, 0.12),
                                 nx=2, ny=1, nz=2, rng=random.Random(43)))
    for i, (fx, fy, frz) in enumerate(((-2.2, 5.4, 0.4), (1.9, 6.2, -0.3))):
        sc.add("props", P.fish_crate("pzf%d" % i,
                                     sc.F @ T_at(fx, fy, 0.12, rz=frz)))
    sc.add("props", P.well_group("plz_well", sc.F @ T_at(-3.7, -4.0, 0.12),
                                 rng=random.Random(21)))
    sc.add("props", P.notice_board("plz_nb", sc.F @ T_at(4.1, -3.6, 0.12)))
    sc.add("props", cyl("plz_pole", sc.F @ T_at(4.8, 1.6, 1.9), 0.06, 3.6,
                        tim, seg=8))
    sc.add("props", box("plz_flag", sc.F @ T_at(5.25, 1.6, 3.30),
                        (0.86, 0.03, 0.56), mk.mat_cloth("banner_red", "#7d2e26")))
    for i, (x, y, rz, cn) in enumerate(((-4.4, -2.6, math.pi * 0.5, "banner_red"),
                                        (4.4, -4.4, -math.pi * 0.5, "banner_trim"),
                                        (4.2, -1.0, -math.pi * 0.5, "bloom"))):
        sc.add("props", P.stall("stl%d" % i, sc.F @ T_at(x, y, 0.12, rz=rz),
                                w=2.3, d=1.5, cloth=mk.mat_cloth(cn, _CLOTH_HEX[cn])))
    # two canopy trees in stone planting pits, framing the square
    fol = []
    for i, (x, y) in enumerate(((-5.8, -9.0), (5.8, -9.2))):
        sc.add("works", P.paving("pit%d" % i, sc.F, 1.7, 1.7,
                                 mk.mat_earth("earth_garden", "#4a3d2e", "#332a1f"),
                                 th=0.055, cx=x, cy=y))
        fol += mb.tree("ptree%d" % i, sc.F @ T_at(x, y, 0.06), h=6.4,
                       rng=random.Random(230 + i),
                       leaf_mat=mk.mat_foliage("leaf_broad_hi", "#3f5a2c",
                                               "#5e7d3c", 5.0), species="broad")
        fol += P.bush("pbush%d" % i, sc.F @ T_at(x + 0.9, y - 0.7, 0.06), r=0.5)
    sc.add("foliage", fol)
    sc.add("props", street_dressing(
        sc, 31,
        carts=[(2.0, -8.4, 1.25)],
        racks=[(-6.2, -5.2, math.pi * 0.5)],
        coils=[(-6.2, -1.0), (6.2, -6.0)],
        fishcr=[(-1.0, -4.0, 0.4), (1.6, -2.2, 1.1), (-1.8, -7.8, 0.2),
                (2.4, -5.2, 0.9)],
        bags=[(2.8, -6.0), (-2.4, -9.4)]))
    sc.add("props", P.laundry_line("laun", sc.F @ T_at(-6.4, -2.2, 0.12,
                                                       rz=math.pi * 0.5), L=2.6))
    sc.add("props", P.woodpile("plz_wp", sc.F @ T_at(6.2, 1.2, 0.12), L=2.0, h=0.95))
    sc.add("props", P.veg_bed("plz_vb", sc.F @ T_at(-6.2, 1.0, 0.05), 2.0, 1.2))
    # --- cargo yard: pave, fill, keep x 5..9 clear as the warehouse lane --
    for i, (x, y, nx, ny, nz) in enumerate(cfg["piles"]):
        sc.add("props", P.crate_pile("yl%d" % i, sc.F @ T_at(x, y, 0.09),
                                     nx=nx, ny=ny, nz=nz,
                                     rng=random.Random(700 + i)))
        if i % 2 == 0:
            sc.add("props", mb.barrel_cluster("yb%d" % i,
                                              sc.F @ T_at(x + 1.5, y - 1.2, 0.09),
                                              rng=random.Random(720 + i)))
    # south end of the working yard: more cargo, a second cart, a tarp stack
    for i, (x, y, nz) in enumerate(((-6.4, 4.6, 2), (12.0, 4.8, 3),
                                    (13.8, 7.4, 2))):
        sc.add("props", P.crate_pile("ys%d" % i, sc.F @ T_at(x, y, 0.09),
                                     nx=2, ny=2, nz=nz,
                                     rng=random.Random(760 + i)))
    sc.add("props", street_dressing(
        sc, 61,
        carts=[(4.7, 10.8, 0.1), (-4.3, 8.2, 3.0)],
        racks=[(13.4, 11.6, -math.pi * 0.5), (-6.6, 10.4, math.pi * 0.5)],
        coils=[(2.9, 20.6), (-2.9, 10.9), (10.2, 8.2)],
        fishcr=[(2.2, 4.6, 0.2), (-2.2, 4.7, 0.8), (11.8, 20.9, 0.3)],
        bags=[(12.4, 8.9)]))
    # plank walkway over the rut, and a timber stack against the east wall
    sc.add("props", box("deck", sc.F @ T_at(0.15, 12.2, 0.19), (3.0, 6.0, 0.08),
                        mat=P.wood("wood_platform")))
    sc.add("props", box("planks", sc.F @ T_at(13.9, 12.6, 0.86), (2.4, 4.0, 0.30),
                        tim))
    sc.add("props", box("planks2", sc.F @ T_at(13.9, 12.6, 1.12), (2.2, 3.6, 0.22),
                        tim))
    sc.add("props", box("planks3", sc.F @ T_at(13.9, 15.4, 0.72), (2.2, 2.4, 0.28),
                        tim))
    sc.add("props", P.net_rack("yrd_nr", sc.F @ T_at(-6.4, 20.4, 0.0,
                                                    rz=math.pi * 0.5), w=3.0))
    sc.add("props", [yard_pen(sc, "yp_e", 12.6, 18.6, 4.6, 4.6,
                              rng=random.Random(77))])
    # boat up on trestles, inside the yard, off the street
    sc.add("boats", P.boat("hauled", sc.F @ T_at(-4.9, 14.0, -0.30, rz=1.57),
                           L=4.8, B=1.6, D=0.9, cargo=False, mast=False,
                           furled=False))
    for i, (x, y) in enumerate(((-4.9, 12.6), (-4.9, 15.4))):
        sc.add("props", box("trs%d" % i, sc.F @ T_at(x, y, 0.26),
                            (1.5, 0.24, 0.52), tim))

    # --- quay ------------------------------------------------------------
    for i, x in enumerate((-14.0, -8.4, -2.2, 5.0, 11.0, 16.0)):
        sc.add("props", P.bollard("bl%d" % i, sc.F @ T_at(x, QUAY_Y1 - 0.72, QUAY_Z),
                                  h=0.62, r=0.16))
    for i, x in enumerate((-11.2, -4.6, 3.2, 13.2)):
        sc.add("props", P.lamp_post("lp%d" % i, sc.F @ T_at(x, 21.7, QUAY_Z),
                                    h=3.0))
    sc.add("props", street_dressing(
        sc, 41,
        carts=[(-9.4, 23.2, 0.2)],
        racks=[(12.4, 23.0, 0.0)],
        coils=[(-4.2, 23.0), (3.6, 24.2), (9.8, 23.4)],
        fishcr=[(-2.6, 22.9, 0.3), (-3.4, 23.9, 1.0), (10.4, 24.0, 0.6),
                (4.6, 23.1, -0.3)],
        bags=[(6.2, 22.4)]))

    # --- piers, boats ----------------------------------------------------
    for i, (px, plen, pw) in enumerate(cfg["piers"]):
        sc.add("quay", P.pier("pier%d" % i, sc.F @ T_at(px, 0.0, 0.0),
                              length=plen, width=pw, deck_z=0.62, y0=Y_FACE))
        sc.piers.append(("pier%d" % i, plen, Y_FACE + plen))
    for i, (bx, by, brz, bl) in enumerate(cfg["boats"]):
        sc.add("boats", P.boat("bt%d" % i, sc.F @ T_at(bx, by, -0.50, rz=brz),
                               L=bl, B=2.4, D=1.25, cargo=(i % 2 == 0),
                               mast=True, furled=True))

    # --- trees: back yards inside the walls, gate pair, orchard ----------
    fol = []
    leaf_a = mk.mat_foliage("leaf_broad_hi", "#3f5a2c", "#5e7d3c", 5.0)
    leaf_b = mk.mat_foliage("leaf_poplar_hi", "#4b5f2c", "#6d8340", 4.5)
    for i, _tv in enumerate(cfg["trees"]):
        x, y, h, s = _tv[:4]
        tz = _tv[4] if len(_tv) > 4 else 0.0
        fol += mb.tree("tr%d" % i, sc.F @ T_at(x, y, tz), h=h,
                       rng=random.Random(200 + i),
                       leaf_mat=leaf_a if i % 3 else leaf_b, species=s)
        fol += P.bush("tb%d" % i, sc.F @ T_at(x + 0.8, y - 0.7, tz), r=0.46,
                      mat=leaf_a)
    # entrance: two symmetric gate trees, two stone gate posts where the dirt
    # road turns into the flagstone forecourt (the paving material change)
    for sx in (-1, 1):
        fol += mb.tree("gtr%d" % sx, sc.F @ T_at(sx * 5.9, TERR_Y0 - 3.6, 0.0),
                       h=6.8, rng=random.Random(301 + sx), leaf_mat=leaf_a,
                       species="broad")
        fol += P.bush("gbush%d" % sx, sc.F @ T_at(sx * 5.1, TERR_Y0 - 2.6, 0.0),
                      r=0.58, mat=leaf_a)
        sc.add("works", P.plinth("gpost%d" % sx,
                                 sc.F @ T_at(sx * 3.9, TERR_Y0 - 6.0), 0.66, 0.66,
                                 1.60, body=wall, top=slb, cope=0.12, cope_h=0.10))
        sc.add("props", P.lamp_post("gpl%d" % sx,
                                    sc.F @ T_at(sx * 3.9, TERR_Y0 - 6.0, 1.70),
                                    h=1.5))
    # orchard grid on the approach, well outside the core
    for ix in range(3):
        for iy in range(3):
            fol += mb.tree("orc%d_%d" % (ix, iy),
                           sc.F @ T_at(cfg["orchard"][0] + ix * 6.2,
                                       cfg["orchard"][1] - iy * 5.0, 0.02),
                           h=4.4 + (ix + iy) % 3 * 0.5,
                           rng=random.Random(400 + ix * 7 + iy),
                           leaf_mat=mk.mat_foliage("leaf_fruit", "#4f6b30",
                                                   "#7d9448", 4.0),
                           species="broad")
    sc.add("foliage", fol)


# ---------------------------------------------------------------------------
# variant A -- fishing hamlet: timber, fence plots, treadwheel crane
# ---------------------------------------------------------------------------
def layout_a(sc, rng):
    cfg = dict(
        wall="fence",
        w_low_w=[3.6, 3.4, 3.4], w_low_e=[3.4, 3.6, 3.4],
        w_up_w=[3.8, 3.6], w_up_e=[3.6, 3.8],
        n_low_w=(2, 2, 1), n_low_e=(2, 3, 1),
        n_up_w=(2, 2), n_up_e=(2, 2),
        k_low_w=[dict(hoist=True, sign=True), dict(sign=False), dict(sign=True)],
        k_low_e=[dict(sign=True), dict(cargo=True), dict(sign=False)],
        k_up_w=[dict(sign=True), dict(sign=False)],
        k_up_e=[dict(sign=False), dict(hoist=True)],
        piers=[(-5.6, 5.2, 3.2), (5.2, 5.0, 3.0)],
        boats=[(-7.1, 29.0, 0.0, 6.6), (6.7, 29.2, 0.0, 6.4),
               (0.2, 33.6, 0.35, 6.0)],
        piles=[(-6.0, 9.0, 2, 2, 2), (-9.6, 9.6, 2, 2, 3),
               (11.2, 8.6, 2, 2, 2), (13.4, 10.6, 1, 2, 2),
               (11.6, 13.6, 2, 2, 2), (13.4, 16.0, 2, 1, 2),
               (11.0, 19.0, 2, 2, 2), (13.6, 20.4, 1, 2, 2),
               (-6.2, 20.6, 2, 2, 2)],
        trees=[(-10.9, -19.4, 7.2, "broad", 0.0), (10.9, -19.6, 6.6, "broad", 0.0),
               (-10.9, -15.2, 6.8, "broad", 0.0), (10.9, -14.8, 7.0, "poplar", 0.0),
               (-10.8, -11.2, 6.4, "broad", 0.0), (11.0, -11.0, 7.4, "broad", 0.0),
               (-10.9, -27.2, 6.6, "poplar", 0.45), (10.9, -26.8, 6.8, "broad", 0.45)],
        orchard=(-22.0, -38.0),
    )
    build_town(sc, rng, cfg)
    dress(sc, rng, cfg)
    # landmark: 15.5 m timber treadwheel crane bridging the street axis
    sc.add("buildings", P.harbour_crane("crane", sc.F @ T_at(0, 18.2, 0.90),
                                        h=14.6, base_x=3.35, base_y=1.95,
                                        top_x=1.50, top_y=1.30, z_deck=7.00,
                                        reach=7.4, wheel=True))
    sc.notes["landmark"] = ["harbour crane", 15.5, 0.0, 18.2]
    # outskirt plots, all inside the walls
    sc.add("props", P.veg_bed("vg1", sc.F @ T_at(10.9, -12.6, 0.05), 2.4, 1.5))
    sc.add("props", P.veg_bed("vg2", sc.F @ T_at(10.9, -10.8, 0.05), 2.4, 1.5))
    sc.add("props", P.chicken_coop("cc1", sc.F @ T_at(-11.4, -20.6, 0.05),
                                   rng=random.Random(88)))
    sc.add("props", P.woodpile("wp1", sc.F @ T_at(10.8, -26.2, 0.50), L=2.4))
    fol = []
    fol += mb.tree("bg1", sc.F @ T_at(12.4, -24.0, 0.45), h=4.6,
                   rng=random.Random(501),
                   leaf_mat=mk.mat_foliage("leaf_fruit", "#4f6b30", "#7d9448", 4.0),
                   species="broad")
    fol += mb.tree("bg2", sc.F @ T_at(-11.8, -26.6, 0.45), h=4.2,
                   rng=random.Random(502),
                   leaf_mat=mk.mat_foliage("leaf_fruit", "#4f6b30", "#7d9448", 4.0),
                   species="broad")
    sc.add("foliage", fol)
    sc.add("props", box("hay1", sc.F @ T_at(13.6, -28.0, 0.50), (2.4, 2.0, 1.10),
                        mk.mat_foliage("leaf_hay", "#a08c4e", "#c0aa66")))


def layout_b(sc, rng):
    cfg = dict(
        wall="stone",
        w_low_w=[3.7, 3.5, 3.3], w_low_e=[3.5, 3.7, 3.3],
        w_up_w=[3.8, 3.6], w_up_e=[3.6, 3.8],
        n_low_w=(3, 2, 1), n_low_e=(2, 3, 1),
        n_up_w=(3, 2), n_up_e=(2, 3),
        k_low_w=[dict(sign=True, stone_ground=True), dict(sign=False, stone_ground=True),
                 dict(sign=True, cargo=True, stone_ground=True)],
        k_low_e=[dict(sign=True, stone_ground=True), dict(cargo=True, stone_ground=True),
                 dict(sign=False, stone_ground=True)],
        k_up_w=[dict(sign=True), dict(sign=False)],
        k_up_e=[dict(sign=False), dict(sign=True)],
        piers=[(-5.4, 5.0, 3.2), (5.0, 4.8, 2.8)],
        boats=[(-7.2, 29.2, 0.0, 6.8), (6.6, 28.9, 0.0, 7.2),
               (0.0, 34.2, 0.0, 5.8)],
        piles=[(-6.2, 9.0, 2, 3, 2), (-10.0, 12.0, 2, 2, 2),
               (11.4, 8.8, 2, 2, 3), (13.6, 12.0, 1, 2, 2),
               (11.0, 13.8, 2, 2, 2), (13.4, 16.2, 2, 2, 2),
               (10.8, 19.2, 2, 2, 3), (13.6, 20.6, 1, 2, 2),
               (-6.0, 20.4, 2, 2, 2)],
        trees=[(-10.9, -19.2, 6.8, "broad", 0.0), (10.9, -19.8, 7.0, "broad", 0.0),
               (-11.0, -15.0, 6.6, "broad", 0.0), (10.9, -14.6, 7.2, "poplar", 0.0),
               (-10.8, -11.0, 6.6, "broad", 0.0), (11.0, -11.4, 7.0, "broad", 0.0),
               (10.6, -27.0, 6.4, "poplar", 0.45), (-10.6, -24.0, 6.8, "broad", 0.45)],
        orchard=(20.0, -38.0),
    )
    build_town(sc, rng, cfg)
    dress(sc, rng, cfg)
    # landmark: 15.4 m mast cluster on a stepped stone standing, on the axis.
    # (No lighthouse / breakwater: this town sits on an inland lake shore.)
    sc.add("works", P.plinth("mpl", sc.F @ T_at(0.0, 18.2), 4.4, 3.6, 0.62,
                             body=P.m_wall(), top=P.m_flag()))
    sc.add("works", P.stairs("mst", sc.F @ T_at(0.0, 16.4, 0.0, rz=math.pi),
                             n=4, rise=0.155, run=0.30, width=2.6,
                             cheek_h=0.10, cheek_t=0.22))
    sc.level(0.62)
    sc.add("buildings", P.mast_cluster("masts", sc.F @ T_at(0.0, 18.2, 0.62),
                                       h=15.4, rng=random.Random(11)))
    sc.notes["landmark"] = ["mast cluster", 16.02, 0.0, 18.2]
    for sx in (-1, 1):
        sc.add("props", P.crate_pile("cpc%d" % sx,
                                     sc.F @ T_at(sx * 3.9, 17.4, 0.90),
                                     nx=2, ny=2, nz=1,
                                     rng=random.Random(31 + sx)))
    sc.add("buildings", P.crane_gantry("gant", sc.F @ T_at(-7.0, 23.2, QUAY_Z),
                                       h=5.2, reach=4.6, span=1.9, hook_drop=2.2))
    sc.add("props", P.loading_platform("ldp", sc.F @ T_at(11.0, 10.6, 0.09),
                                       w=7.2, d=1.9, h=0.88))
    sc.add("props", P.veg_bed("vg1", sc.F @ T_at(10.9, -12.4, 0.05), 2.4, 1.5))
    sc.add("props", P.woodpile("wp1", sc.F @ T_at(-11.4, -14.6, 0.05), L=2.4))
    # variant character (stone trading port): a market cross + weigh-beam post
    sc.add("props", P.plinth("mxc_b", sc.F @ T_at(-2.4, 0.9), 1.24, 1.24, 0.30,
                             body=P.m_wall(), top=P.m_step()))
    sc.add("props", box("mxc_s", sc.F @ T_at(-2.4, 0.9, 1.40), (0.24, 0.24, 2.20),
                        P.m_wall(), bev=0.01))
    sc.add("props", box("mxc_a", sc.F @ T_at(-2.4, 0.9, 2.42), (1.52, 0.19, 0.19),
                        P.m_timber(), bev=0.01))
    sc.add("props", box("mxc_g", sc.F @ T_at(-3.02, 0.9, 1.96), (0.34, 0.07, 0.46),
                        mk.mat_wood("wood_sign", "#6a4a2c", "#8a6238"), bev=0.008))
    for i, (bx, by, br, bh) in enumerate(((-4.9, 1.4, 0.30, 0.82), (-4.9, 0.5, 0.30, 0.82),
                                          (-4.6, 1.0, 0.30, 0.82), (4.4, 1.9, 0.28, 0.78))):
        sc.add("props", mb.barrel("mbc%d" % i, sc.F @ T_at(bx, by, 0.12), r=br, h=bh,
                                  rng=random.Random(300 + i)))
    sc.add("props", P.chicken_coop("cc1", sc.F @ T_at(12.2, -26.4, 0.50),
                                   rng=random.Random(188)))


def layout_c(sc, rng):
    cfg = dict(
        wall="stone",
        w_low_w=[3.5, 3.6, 3.5], w_low_e=[3.6, 3.4, 3.6],
        w_up_w=[3.7, 3.7], w_up_e=[3.6, 3.8],
        n_low_w=(2, 3, 1), n_low_e=(3, 3, 1),
        n_up_w=(2, 3), n_up_e=(3, 2),
        k_low_w=[dict(sign=True, cargo=True), dict(hoist=True), dict(sign=False)],
        k_low_e=[dict(sign=True), dict(cargo=True), dict(sign=False)],
        k_up_w=[dict(sign=False), dict(sign=True)],
        k_up_e=[dict(sign=True), dict(sign=False)],
        piers=[(-5.8, 5.2, 3.2), (5.6, 5.2, 3.2)],
        boats=[(-7.3, 29.0, 0.02, 7.0), (6.9, 29.2, -0.02, 7.2),
               (0.2, 34.8, 0.25, 6.2)],
        piles=[(-6.4, 9.2, 2, 2, 2), (-9.8, 12.4, 2, 2, 3),
               (11.2, 9.0, 2, 2, 2), (13.4, 11.2, 2, 1, 2),
               (11.4, 14.0, 2, 2, 2), (13.4, 16.6, 1, 2, 3),
               (11.0, 19.2, 2, 2, 2), (-6.0, 19.8, 2, 2, 2)],
        trees=[(-10.9, -23.0, 7.0, "poplar"), (10.9, -21.2, 6.8, "broad"),
               (-11.0, -11.8, 7.4, "broad"), (10.9, -14.8, 7.0, "broad"),
               (-10.8, -7.6, 6.4, "poplar"), (11.0, -7.4, 7.2, "broad"),
               (10.6, -19.0, 6.6, "broad"), (-10.6, -17.2, 7.0, "poplar")],
        orchard=(-22.0, -38.0),
    )
    build_town(sc, rng, cfg)
    dress(sc, rng, cfg)
    # landmark: 15.9 m mast cluster + derrick on the axis plinths
    sc.add("buildings", P.mast_cluster("masts", sc.F @ T_at(0.0, 18.2, 0.90),
                                       h=15.0, rng=rng))
    sc.add("buildings", P.crane_jib("djib", sc.F @ T_at(2.6, 20.2, 0.90, rz=-0.5),
                                    h=7.4, reach=5.4, drop=1.8))
    sc.notes["landmark"] = ["mast cluster", 15.9, 0.0, 18.2]
    # clifftop character: heavy sea-wall buttresses along the quay edge
    for i, x in enumerate((-12.4, -6.0, 6.0, 12.4)):
        sc.add("props", box("bt%d" % i, sc.F @ T_at(x, QUAY_Y0 + 0.4, 0.55),
                            (1.5, 1.2, 1.10), P.m_wall()))
    sc.add("props", P.veg_bed("vg1", sc.F @ T_at(-11.4, -12.2, 0.05), 2.4, 1.5))
    sc.add("props", P.chicken_coop("cc1", sc.F @ T_at(11.6, -20.4, 0.05),
                                   rng=random.Random(288)))
    sc.add("props", P.woodpile("wp1", sc.F @ T_at(-11.4, -26.2, 0.50), L=2.6))
    # variant character (clifftop quay): a beacon brazier on the square + buttresses
    sc.add("props", P.plinth("bcn", sc.F @ T_at(3.2, 0.2), 1.34, 1.34, 0.42,
                             body=P.m_wall(), top=P.m_step()))
    for i, (bx, by) in enumerate(((-0.34, -0.34), (0.34, -0.34), (-0.34, 0.34), (0.34, 0.34))):
        sc.add("props", box("bcn_p%d" % i, sc.F @ T_at(3.2 + bx, 0.2 + by, 0.86),
                            (0.12, 0.12, 0.52), P.m_iron(), bev=0.006))
    sc.add("props", box("bcn_b", sc.F @ T_at(3.2, 0.2, 1.06), (0.96, 0.96, 0.34),
                        P.m_iron(), bev=0.01))
    sc.add("props", box("bcn_f", sc.F @ T_at(3.2, 0.2, 1.20), (0.62, 0.62, 0.26),
                        mk.mat_glass("glass_lamp"), bev=0.01))
    for i, sx in enumerate((-1, 1)):
        sc.add("props", box("btm%d" % i, sc.F @ T_at(sx * 3.55, -9.30, 0.80),
                            (1.30, 0.95, 1.60), P.m_wall(), bev=0.015))
        sc.add("props", box("btc%d" % i, sc.F @ T_at(sx * 3.55, -9.30, 1.68),
                            (1.46, 1.08, 0.16), P.m_step(), bev=0.01))


LAYOUTS = {"port_a": layout_a, "port_b": layout_b, "port_c": layout_c}


# ---------------------------------------------------------------------------
# self check
# ---------------------------------------------------------------------------
def town_check(sc):
    """Numeric self check against TOWN_DESIGN_LA.md section 1/2."""
    gx, gy = CORE_C
    rad = 0.0
    xs, ys = [], []
    for (tag, x0, x1, y0, y1, core) in sc.houses:
        if not core:
            continue
        xs += [x0, x1]
        ys += [y0, y1]
        for px in (x0, x1):
            for py in (y0, y1):
                rad = max(rad, math.hypot(px - gx, py - gy))
    # landmark and gate count as core too (they sit on the street axis)
    for (nm, h, lx, ly) in (sc.notes.get("landmark") or [None, 0, 0, 0],):
        if nm:
            rad = max(rad, math.hypot(lx - gx, ly - gy))
    for (lx, ly) in (sc.notes.get("gate") or [0, 0],):
        if ly:
            rad = max(rad, math.hypot(lx - gx, ly - gy))
    # hard surface: sample the core disc, skip water
    hard = soft = 0
    for i in range(200):
        a = (i * 2.399963) % (math.pi * 2.0)
        r = math.sqrt((i + 0.5) / 200.0) * 23.0
        px = gx + math.cos(a) * r
        py = gy + math.sin(a) * r
        if py > QUAY_Y1 + 0.2:
            continue
        if any(x0 <= px <= x1 and y0 <= py <= y1 for (x0, x1, y0, y1) in sc.grass):
            soft += 1
        else:
            hard += 1
    ratio = hard / float(hard + soft) if (hard + soft) else 0.0
    loose = [w for w in sc.walls if not w[5]]
    pier_r = max([math.hypot(0.0 - gx, yh - gy) for (_, _, yh) in sc.piers] or [0.0])
    out = dict(
        core_center=[round(gx, 2), round(gy, 2)],
        core_radius=round(rad, 2),
        core_diameter=round(rad * 2.0, 2),
        house_count=len([h for h in sc.houses if h[5]]),
        street_width=round(FAC_X * 2.0, 2),
        setback=round(FAC_X - ST_HW, 2),
        gaps=[round(g, 2) for g in sc.notes.get("gaps", [])],
        levels=sorted(sc.levels),
        level_count=len(sc.levels),
        hard_surface_ratio=round(ratio, 3),
        isolated_fences=len(loose),
        fence_runs=len(sc.walls),
        piers=[[t, round(L, 2), round(y, 2)] for (t, L, y) in sc.piers],
        pier_max_len=round(max([L for (_, L, _) in sc.piers] or [0.0]), 2),
        pier_max_radius=round(pier_r, 2),
        landmark=list(sc.notes.get("landmark", [])),
        gate=list(sc.notes.get("gate", [])),
    )
    return out


# ---------------------------------------------------------------------------
# join / measure / export
# ---------------------------------------------------------------------------
def join_groups(sc, prefix):
    objs = []
    for key in BUCKETS:
        parts = sc.g[key]
        if not parts:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        for ob in parts:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.convert(target="MESH")
        if len(bpy.context.selected_objects) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        ob.name = "%s_%s" % (prefix, key)
        ob.data.name = ob.name
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        objs.append(ob)
    return objs


def dedupe_materials(objs):
    """mat_glass()/mat_gold() build a fresh material per call; collapse those
    back onto one material per base name before export."""
    keep = {}
    for ob in objs:
        for slot in ob.material_slots:
            m = slot.material
            if m is not None:
                keep.setdefault(m.name.split(".")[0], m)
    for ob in objs:
        me = ob.data
        slots = [s.material for s in ob.material_slots]
        tgt, index = [], []
        for m in slots:
            k = keep[m.name.split(".")[0]] if m is not None else None
            if k not in tgt:
                tgt.append(k)
            index.append(tgt.index(k))
        if all(a is b for a, b in zip(tgt, slots)):
            continue
        per_poly = [index[p.material_index] for p in me.polygons]
        me.materials.clear()
        for m in tgt:
            me.materials.append(m)
        for p, i in zip(me.polygons, per_poly):
            p.material_index = i


def measure(objs):
    tris = faces = 0
    mats = set()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    detail = {}
    for ob in objs:
        me = ob.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        faces += len(me.polygons)
        detail[ob.name] = [len(me.polygons), len(me.loop_triangles)]
        for m in me.materials:
            if m:
                mats.add(m.name)
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return dict(objects=len(objs), triangles=tris, polygons=faces,
                materials=len(mats),
                bbox_min=[round(v, 2) for v in lo],
                bbox_max=[round(v, 2) for v in hi],
                size=[round(hi[i] - lo[i], 2) for i in range(3)],
                detail=detail,
                mat_names=sorted(mats))


def export_fbx(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
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
                                 use_mesh_modifiers=True, axis_forward="-Z",
                                 axis_up="Y")


# ---------------------------------------------------------------------------
# render rig (mirrors build_town.py)
# ---------------------------------------------------------------------------
def backdrop(sc):
    """Render-only continuation of the ground and river past the 120 m box.

    Added after the FBX export so the shipped asset stays inside the footprint;
    removed again before the .blend is saved.
    """
    objs = []
    m = mk.mat_foliage("back_grass", "#4a5a30", "#66743c", 2.4)
    hg = mk.mat_foliage("back_hedge", "#3a4a26", "#556a33", 5.0)
    g = mk.mat_earth("earth_back", base="#5e5844", dark="#43402f", scale=6.0,
                     patch=0.55)
    wm = P.water_mat()
    st = P.stone()
    for (cx, cy, w, d) in ((0.0, 115.0, 340.0, 110.0),
                           (0.0, -115.0, 340.0, 110.0)):
        objs.append(mk.box("apron", sc.T(cx, cy, -0.55), (w, d, 0.53), m))
    for sx in (-1, 1):
        objs.append(mk.box("apron", sc.T(sx * 115.0, -17.0, -0.55),
                           (110.0, 86.0, 0.53), m))
        objs.append(mk.box("apron", sc.T(sx * 115.0, 56.0, -0.55),
                           (110.0, 8.0, 0.53), m))
        objs.append(mk.box("apron_water", sc.T(sx * 115.0, 39.0, -0.90),
                           (110.0, 26.0, 0.60), wm))
        objs.append(mk.box("apron_quay", sc.T(sx * 115.0, 25.7, -1.25),
                           (110.0, 1.7, 2.70), st))
        objs.append(mk.box("apron_quay", sc.T(sx * 115.0, 52.3, -1.25),
                           (110.0, 1.7, 2.70), st))
    hrng = random.Random(31)
    for i in range(14):
        hx = hrng.uniform(-190.0, 190.0)
        hy = hrng.choice((-1, 1)) * hrng.uniform(78.0, 168.0)
        hl = hrng.uniform(18.0, 52.0)
        objs.append(mk.box("apron_hedge", sc.T(hx, hy, 0.60),
                           (hl, 1.1, 1.20), hg))
    for i in range(10):
        px = hrng.uniform(-180.0, 180.0)
        py = hrng.choice((-1, 1)) * hrng.uniform(84.0, 160.0)
        objs.append(mk.box("apron_plot", sc.T(px, py, 0.012),
                           (hrng.uniform(14.0, 30.0), hrng.uniform(7.0, 13.0), 0.03),
                           g))
    leaf = mk.mat_foliage("horizon_leaf", "#2f4a2c", "#476b36", 4.0)
    tr = P.wood()
    hrng = random.Random(99)
    for i in range(78):
        ang = math.pi * 2.0 * i / 78.0 + hrng.uniform(-0.03, 0.03)
        rr = hrng.uniform(84.0, 165.0)
        hx = math.cos(ang) * rr
        hy = math.sin(ang) * rr
        if abs(hx) < 76.0 and abs(hy) < 76.0:
            continue
        hh = hrng.uniform(6.0, 12.0)
        objs.append(mk.sphere("htree", sc.T(hx, hy, hh * 0.60), hh * 0.34, leaf,
                              seg=7, ring=5, squash=1.15))
        objs.append(mk.cyl("htrunk", sc.T(hx, hy, hh * 0.22), 0.22, hh * 0.44,
                           tr, seg=6))
    return objs


def setup_lighting(rot):
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        if ob.type in {"LIGHT", "CAMERA"}:
            bpy.data.objects.remove(ob, do_unlink=True)
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    nt = sc.world.node_tree
    bg = None
    for n in nt.nodes:
        if n.type == "BACKGROUND":
            bg = n
            break
    if bg is not None:
        bg.inputs["Color"].default_value = (0.44, 0.58, 0.76, 1.0)
        bg.inputs["Strength"].default_value = 0.72

    sd = bpy.data.lights.new("Sun", type="SUN")
    sd.energy = 3.1
    sd.angle = math.radians(5.0)
    sd.color = (1.0, 0.94, 0.83)
    sun = bpy.data.objects.new("Sun", sd)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(34.0) + rot)

    fd = bpy.data.lights.new("Fill", type="AREA")
    fd.energy = 480.0
    fd.size = 26.0
    fd.color = (0.82, 0.88, 1.0)
    fill = bpy.data.objects.new("Fill", fd)
    bpy.context.collection.objects.link(fill)
    R = mk.T_at(0, 0, 0, rz=rot).to_3x3()
    fill_loc = R @ Vector((18.0, 30.0, 22.0))
    fill.location = fill_loc
    fill.rotation_euler = (Vector((0, 0, 0)) - fill_loc).to_track_quat(
        "-Z", "Y").to_euler()
    return sun


def setup_render(res=(1280, 720), samples=64):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    for attr, val in (("taa_render_samples", samples), ("use_raytracing", True),
                      ("use_shadows", True), ("shadow_ray_count", 4),
                      ("shadow_step_count", 12)):
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass


def setup_camera(loc, target, lens=50.0):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    co = bpy.data.objects.new("Cam", cd)
    bpy.context.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat(
        "-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    return co


def render_to(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    variant = "port_a"
    for i, a in enumerate(argv):
        if a == "--variant" and i + 1 < len(argv):
            variant = argv[i + 1]
        elif a.startswith("--variant="):
            variant = a.split("=", 1)[1]
    if variant not in LAYOUTS:
        raise SystemExit("unknown variant %r" % variant)

    t0 = time.time()
    rot = VARIANT_ROT[variant]
    mk.reset_scene()
    mk._MAT_CACHE.clear()
    F = T_at(0, 0, 0, rz=rot)
    sc = Scene(F)
    rng = random.Random(sum(ord(c) for c in variant) * 7)
    LAYOUTS[variant](sc, rng)
    periphery(sc, rng)
    print("[port] %s built in %.1fs: %s" % (
        variant, time.time() - t0,
        ", ".join("%s=%d" % (k, len(v)) for k, v in sc.g.items())))

    check = town_check(sc)
    print("[port] %s check: %s" % (variant, json.dumps(check)))

    objs = join_groups(sc, variant)
    dedupe_materials(objs)
    stats = measure(objs)
    stats["variant"] = variant
    stats["check"] = check
    print("[port] %s measured: %s" % (variant, json.dumps(stats)))

    os.makedirs(EXPORT_DIR, exist_ok=True)
    fbx = os.path.join(EXPORT_DIR, "%s.fbx" % variant)
    export_fbx(objs, fbx)
    print("[port] wrote %s (%.1f KB)" % (fbx, os.path.getsize(fbx) / 1024.0))

    setup_lighting(rot)
    setup_render()
    apron = backdrop(sc)
    cam_loc, cam_tgt, lens = VARIANT_CAM[variant]
    R3 = mk.T_at(0, 0, 0, rz=rot).to_3x3()
    setup_camera(R3 @ Vector(cam_loc), R3 @ Vector(cam_tgt), lens)
    png = os.path.join(RENDER_DIR, "%s.png" % variant)
    t1 = time.time()
    render_to(png)
    print("[port] rendered %s in %.1fs" % (png, time.time() - t1))

    # the two review cameras asked for by the layout brief
    for tag, (cl, ct, lz) in (("player", CAM_PLAYER), ("eye", CAM_EYE),
                                 ("top", CAM_TOP)):
        setup_camera(cl, ct, lz)
        pp = os.path.join(RENDER_DIR, "%s_%s.png" % (variant, tag))
        render_to(pp)
        print("[port] rendered %s" % pp)

    os.makedirs(KINGDOM, exist_ok=True)
    for ob in apron:
        bpy.data.objects.remove(ob, do_unlink=True)
    for _ in range(3):
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True,
                               do_recursive=True)
    blend = os.path.join(KINGDOM, "%s.blend" % variant)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("[port] saved %s" % blend)

    js = os.path.join(KINGDOM, "port_measure_%s.json" % variant)
    with open(js, "w") as fh:
        json.dump(stats, fh, indent=1)
    print("[port] total %.1fs" % (time.time() - t0))


main()
