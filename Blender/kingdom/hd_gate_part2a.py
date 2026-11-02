# ==========================================================================
#  PART 2 -- rebuilt gate complex
#
#  Layout (local frame, +Y = out of the city):
#
#      y = +52 .. +31.4   road, moat far bank
#      y = +31 .. +23     MOAT (8 m), timber DRAWBRIDGE on the axis
#      y = +23 .. +9.4    BARBICAN WARD: front wall + 2 towers at y=23,
#                         side walls at x=+-8.3, the porch at the back
#      y = +9.25 .. -6.6  the gatehouse + forebuilding (the main gate)
#      y = -6.6 .. -46    city street
#
#  Every walking surface (city street, passage, ward, drawbridge, road) is at
#  the same level, z = +0.12, so no ramp, step or seam is needed anywhere.
# ==========================================================================

RO = R_PASS + 0.10          # real opening radius of the gate passage (2.85)
ZC = Z_SPRING + RO          # 7.10 crown
DECK = 0.12                 # the one walking level of the whole complex
CITY_Z = 0.06               # city street surface (a 6 cm threshold step)
BARB_FRONT = 23.0           # outer face of the barbican front wall
BARB_BACK = 9.40            # inner face of the barbican side walls
BARB_Z = 10.60              # barbican wall-walk level
BARB_T = 1.70               # barbican wall thickness
BARB_X = 8.30               # barbican wall centre line
BTOW_R = 3.30               # barbican tower radius
BTOW_TOP = 12.60            # barbican tower shaft top
MOAT_A = 23.00              # near edge of the moat (= barbican front)
MOAT_B = 31.00              # far edge of the moat
WATER_Z = -0.95
MOAT_BED = -2.60
BRIDGE_X = 3.05             # drawbridge half width
CURT_X1 = 30.60             # outer end of the curtain wall
ROAD_X = 4.20               # road half width
ROAD_END = 52.0
CITY_END = -46.0


# --------------------------------------------------------------------------
#  boolean helpers (real openings, real reveals)
# --------------------------------------------------------------------------
def _join(obs, name):
    obs = [o for o in obs if o is not None]
    if not obs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def _bool(target, cutter):
    """Apply one EXACT difference and drop the cutter."""
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    md = target.modifiers.new("cut", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.solver = "EXACT"
    md.object = cutter
    try:
        bpy.ops.object.modifier_apply(modifier=md.name)
    except RuntimeError as exc:
        print("[gate] boolean failed on %s: %s" % (target.name, exc), flush=True)
        target.modifiers.remove(md)
    return target


def _cut(targets, cutter, label=""):
    """Cut one cutter out of every target, then delete it."""
    for t in targets:
        if t is not None:
            _bool(t, cutter)
    if cutter is not None and cutter.name in bpy.data.objects:
        bpy.data.objects.remove(cutter, do_unlink=True)


def _rect_cutter(name, T, w, h, depth, out=0.35):
    """A box cut into a wall face: local +Y is out of the wall."""
    return box(name, T @ Ts(0, out - depth * 0.5, h * 0.5), (w, depth, h), None)


def _loop_cutter(name, T, w, h, depth, out=0.35):
    """A pointed opening cut into a wall face (T at the sill centre)."""
    return H.prism(name, T @ Ts(0, out - depth * 0.5, 0), pointed_loop(w, h),
                   depth, None, axis="y")


def _frame(x, y, z, ang):
    """Face frame: local +Y points outward at angle `ang`, local X tangential."""
    return Ts(x, y, z) @ RotZ(ang - PI * 0.5)


def _arch_ring_pts(r0, r1, a0=0.0, a1=PI, seg=44):
    pts = []
    for i in range(seg + 1):
        a = lerp(a0, a1, i / seg)
        pts.append((math.cos(a) * r1, math.sin(a) * r1))
    for i in range(seg + 1):
        a = lerp(a1, a0, i / seg)
        pts.append((math.cos(a) * r0, math.sin(a) * r0))
    return pts


def arch_order(name, T, r, MAT, n=23, w=0.55, depth=0.30, hood=True,
               keystone=True, a0=0.0, a1=PI):
    """A readable arch surround: backing ring, real voussoirs, hood, keystone.

    T is at the arch centre on the wall face, local +Y out.  The backing ring
    sits flush with the opening radius so no gap can ever show the dark vault
    through the joints (the sawtooth bug of the old build).
    """
    st, pale = MAT["stone"], MAT["stone_pale"]
    p = []
    # solid backing, buried in the wall
    p.append(H.prism(name + "_bk", T @ Ts(0, -0.06, 0), _arch_ring_pts(r - 0.02, r + w,
                   a0, a1), 0.24, st, axis="y"))
    # real voussoirs, each one a separate tapered stone
    p.append(voussoir_ring(name + "_vs", T @ Ts(0, depth * 0.5 - 0.03, 0),
                           r + 0.012, w - 0.024, n, pale, y=0.0, zc=0.0,
                           a0=a0, a1=a1, thick=depth, gap=0.014))
    # impost blocks at the springing
    for s in (-1, 1):
        if 0.0 < (a0 if s < 0 else a1) < PI:
            p.append(box(name + "_imp%d" % s,
                         T @ Ts(s * math.cos(a0 if s < 0 else a1) * (r + w * 0.5),
                                depth * 0.5, math.sin(a0 if s < 0 else a1) * (r + w * 0.5)),
                         (0.62, depth + 0.14, 0.34), pale, bev=0.015))
    if hood:
        p.append(H.prism(name + "_hd", T @ Ts(0, 0.10, 0),
                         _arch_ring_pts(r + w + 0.03, r + w + 0.32, a0, a1),
                         0.30, pale, axis="y"))
        p.append(H.prism(name + "_hd2", T @ Ts(0, 0.02, 0),
                         _arch_ring_pts(r + w - 0.02, r + w + 0.05, a0, a1),
                         0.14, st, axis="y"))
        # label stops
        for s in (-1, 1):
            aa = a0 if s < 0 else a1
            p.append(box(name + "_ls%d" % s,
                         T @ Ts(math.cos(aa) * (r + w + 0.17), 0.14,
                                math.sin(aa) * (r + w + 0.17)),
                         (0.34, 0.34, 0.50), pale, bev=0.02))
    if keystone:
        p.append(box(name + "_ks", T @ Ts(0, depth * 0.5 + 0.10, r + w * 0.5),
                     (0.46, depth + 0.20, 0.78), pale, bev=0.02))
        p.append(box(name + "_ksb", T @ Ts(0, depth * 0.5 + 0.06, r + w * 0.5),
                     (0.60, depth + 0.10, 0.94), st, bev=0.02))
    return p


def pointed_window(name, T, w, h, MAT, tracery=2, transom=0, depth=0.55,
                   hood=True, sill=True, seg=10, k=0.30):
    """Glazing, mullions, sill and mouldings for an already-cut pointed hole.

    T sits at the sill centre on the wall face, local +Y out.  The reveal
    walls are the boolean cut faces, so this is a real recess.
    """
    sw, pale, sd = MAT["stone_warm"], MAT["stone_pale"], MAT["stone_dark"]
    loop = pointed_loop(w, h, seg=seg, k=k)
    hw = w * 0.5
    p = []
    p.append(H.prism(name + "_bk", T @ Ts(0, -depth + 0.03, 0), loop, 0.03, sd, axis="y"))
    p.append(H.prism(name + "_gl", T @ Ts(0, -depth + 0.09, 0), loop, 0.035,
                     MAT["glass"], axis="y"))
    # leaded glazing bars, just in front of the glass
    for i in range(1, 4):
        z = h * i / 4.0
        p.append(box(name + "_gb%d" % i, T @ Ts(0, -depth + 0.125, z),
                     (w * 0.94, 0.012, 0.035), MAT["iron_dark"]))
    # stone mullions and a transom, standing inside the reveal
    n = max(1, int(tracery))
    for i in range(1, n):
        x = -hw + w * i / n
        p.append(box(name + "_m%d" % i, T @ Ts(x, -depth * 0.46, h * 0.5),
                     (0.11, depth * 0.86, h), pale, bev=0.01))
    for i in range(int(transom)):
        z = h * (0.42 + 0.30 * i)
        p.append(box(name + "_t%d" % i, T @ Ts(0, -depth * 0.46, z),
                     (w, depth * 0.86, 0.10), pale, bev=0.01))
    # dressed surround: jambs + architrave, proud of the wall
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (hw + 0.16), 0.10, h * 0.5),
                     (0.32, 0.24, h + 0.02), sw, bev=0.015))
    p.append(pointed_band(name + "_ar", T, w, h, 0.30, 0.02, 0.18, sw, seg=seg, k=k))
    if sill:
        p.append(box(name + "_sl", T @ Ts(0, 0.16, -0.12), (w + 0.84, 0.46, 0.19),
                     pale, bev=0.02))
        p.append(box(name + "_sd", T @ Ts(0, 0.30, -0.24), (w + 0.60, 0.14, 0.07), sd))
    if hood:
        p.append(pointed_band(name + "_hd", T, w + 0.54, h, 0.34, 0.16, 0.34, pale,
                              seg=seg, k=k))
        for s in (-1, 1):
            p.append(box(name + "_hs%d" % s, T @ Ts(s * (hw + 0.42), 0.30, h - 0.14),
                         (0.30, 0.34, 0.36), pale, bev=0.02))
    return p


def arrow_loop(name, T, MAT, h=1.25, w=0.20, depth=0.42):
    """Dark slot, crosslet and sill for an already-cut arrow loop."""
    pale, sd = MAT["stone_pale"], MAT["stone_dark"]
    p = [box(name + "_d", T @ Ts(0, -depth + 0.04, h * 0.5),
             (w * 0.92, 0.035, h * 0.94), sd)]
    p.append(box(name + "_c", T @ Ts(0, 0.015, h * 0.52), (w * 1.55, 0.05, 0.10), pale))
    p.append(box(name + "_c2", T @ Ts(0, 0.015, h * 0.52), (0.10, 0.05, h * 1.15), pale))
    p.append(box(name + "_s", T @ Ts(0, 0.06, -0.06), (w + 0.46, 0.22, 0.13),
                 pale, bev=0.012))
    return p


def ashlar_panel(name, T, w, h, mat, rng, bw=1.42, bh=0.64, proud=0.055):
    """One ashlar panel object (a list) that can be booleaned afterwards."""
    return ashlar(name, T, w, h, mat, rng, bw=bw, bh=bh, proud=proud)


def ring_ashlar(name, T, r, z0, z1, mat_a, mat_b, rng, n=40, course=0.72,
                thick=0.06):
    """All ashlar courses on a drum, joined into one object (for booleaning)."""
    obs = []
    z = z0
    i = 0
    while z < z1 - 0.1:
        hh = min(course, z1 - z)
        obs += ring_stones(name + "_c%d" % i, T, r, z, n, hh, mat_a, mat_b, rng,
                           thick=thick, gap=0.03)
        z += hh
        i += 1
    return _join(obs, name + "_ash")


def gable_roof(name, T, w, d, h, tile, deck, ov=0.42):
    """A small gabled roof: ridge along local X, slopes to +-Y, slate slabs."""
    out = []
    hw, hd = w * 0.5, d * 0.5
    out.append(H.wedge(name + "_core", T, w, d, h, deck))
    L = math.hypot(hd + ov, h)
    ang = math.atan2(h, hd + ov)
    for s in (-1, 1):
        out.append(box(name + "_sl%d" % s,
                       T @ Ts(0, s * (hd + ov) * 0.5, h * 0.5 + 0.09, rx=-s * ang),
                       (w + 2 * ov, L, 0.16), tile, bev=0.012))
    out.append(box(name + "_rd", T @ Ts(0, 0, h + 0.16), (w + 2 * ov + 0.1, 0.34, 0.20),
                   tile, bev=0.012))
    return out


# --------------------------------------------------------------------------
#  the twin drum towers
# --------------------------------------------------------------------------
def build_tower(MAT, rng, side):
    p = []
    cx = side * TOW_X
    cy = 0.0
    tag = "twR" if side > 0 else "twL"
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale = MAT["stone_pale"]
    iron = MAT["iron_dark"]
    # ---- plinth and shaft ------------------------------------------------
    p.append(H.lathe(tag + "_plinth",
                     [(0.0, 0.0), (8.62, 0.0), (8.62, 0.52), (8.28, 1.02),
                      (8.02, 1.16)], st, seg=96, T=Ts(cx, cy, 0),
                     close_bottom=True, close_top=False))
    p.append(cyl(tag + "_shaft", Ts(cx, cy, 13.6), 8.0, 25.3, st, seg=96))
    ash = ring_ashlar(tag + "_ash", Ts(cx, cy, 0), 8.0, 1.16, 24.6, sw, pale, rng,
                      n=40, course=0.72, thick=0.06)
    p.append(ash)

    # ---- real openings ---------------------------------------------------
    cutters = []
    # three tall windows on the outward quarter
    for i, ang in enumerate((52.0, 80.0, 108.0)):
        T = _frame(cx, cy, 17.1, math.radians(ang))
        # the frame has to stand on the drum surface, not at the centre
        T = face_T(cx, cy, 17.1, math.radians(ang), 8.0)
        cutters.append(_loop_cutter(tag + "_wc%d" % i, T, 1.55, 2.15, 1.20))
    # arrow loops, two rows
    loop_specs = []
    for row, z in enumerate((4.6, 9.0, 13.2)):
        for j, ang in enumerate((28.0, 68.0, 112.0, 152.0)):
            loop_specs.append((ang, z))
            T = face_T(cx, cy, z, math.radians(ang), 8.0)
            cutters.append(_rect_cutter(tag + "_lc%d_%d" % (row, j), T, 0.24, 1.32, 0.90))
    # the city-side door
    Td = face_T(cx, cy, 0.10, math.radians(270.0), 8.0)
    cutters.append(_loop_cutter(tag + "_dc", Td, 1.55, 2.05, 1.10))
    cutter = _join(cutters, tag + "_cut")
    _cut([ash, p[1], p[0]], cutter)

    # ---- windows and loops ----------------------------------------------
    for i, ang in enumerate((52.0, 80.0, 108.0)):
        T = face_T(cx, cy, 17.1, math.radians(ang), 8.06)
        p += pointed_window(tag + "_w%d" % i, T, 1.55, 2.15, MAT, tracery=2,
                            transom=0, depth=0.58, hood=True)
    for row, z in enumerate((4.6, 9.0, 13.2)):
        for j, ang in enumerate((28.0, 68.0, 112.0, 152.0)):
            T = face_T(cx, cy, z, math.radians(ang), 8.05)
            p += arrow_loop(tag + "_l%d_%d" % (row, j), T, MAT, depth=0.44)
    # the city door: timber leaf, iron straps, steps
    Td = face_T(cx, cy, 0.10, math.radians(270.0), 8.06)
    p += _arched_door(tag + "_door", Td, 1.55, 2.05, MAT, depth=0.34, steps=2)

    # ---- string courses --------------------------------------------------
    for k, z in enumerate((7.95, 15.15, 20.95)):
        p.append(H.lathe(tag + "_sc%d" % k,
                         [(8.0, 0.0), (8.20, 0.0), (8.20, 0.20), (8.06, 0.30),
                          (8.0, 0.30)], sw, seg=96, T=Ts(cx, cy, z),
                         close_bottom=False, close_top=False))

    # ---- bartizan on the outward face ------------------------------------
    ang = PI * 0.5
    bx, by = cx + math.cos(ang) * 8.35, cy + math.sin(ang) * 8.35
    p.append(H.lathe(tag + "_btc",
                     [(0.30, -1.55), (0.92, -0.35), (1.12, 0.0), (1.12, 0.18)],
                     sw, seg=24, T=Ts(bx, by, 22.55), close_bottom=True,
                     close_top=False))
    p.append(cyl(tag + "_btd", Ts(bx, by, 23.9), 1.12, 2.55, sw, seg=24))
    for i in range(3):
        Tb = face_T(bx, by, 23.2 + i * 0.7, math.radians(90.0), 1.12)
        p += arrow_loop(tag + "_btl%d" % i, Tb, MAT, h=0.9, w=0.16, depth=0.30)
    p.append(H.lathe(tag + "_btr",
                     [(1.30, 25.16), (1.30, 25.30), (0.10, 27.55)], MAT["slate"],
                     seg=24, T=Ts(bx, by, 0), close_bottom=False, close_top=True))
    p.append(sphere(tag + "_btf", Ts(bx, by, 27.72), 0.13, MAT["gold"], seg=10, ring=6))

    # ---- machicolation head ---------------------------------------------
    p.append(corbel_ring(tag + "_corb", Ts(cx, cy, 0), 8.0, 24.60, 44, sw,
                         out=1.18, h=1.30, w=0.46, taper=0.30))
    p.append(ring_wall(tag + "_gal", Ts(cx, cy, 0), 7.30, 9.08, 25.90, 27.30, sw,
                       seg=96))
    p.append(ring_wall(tag + "_gal2", Ts(cx, cy, 0), 8.98, 9.10, 25.88, 27.42, pale,
                       seg=96))
    p.append(ring_wall(tag + "_par", Ts(cx, cy, 0), 8.56, 9.12, 27.30, 28.62, st,
                       seg=96))
    p.append(rcrenel(tag + "_mer", Ts(cx, cy, 0), 8.84, 28.62, 36, merlon=0.92,
                     gap=0.52, h=1.24, depth=0.56, mat=st))
    # walk floor ring (inside the parapet, outside the roof kerb)
    p.append(ring_wall(tag + "_walk", Ts(cx, cy, 0), 6.55, 8.62, 27.28, 27.42, pale,
                       seg=96))
    p.append(ring_wall(tag + "_kerb", Ts(cx, cy, 0), 6.44, 6.62, 27.38, 27.95, sw,
                       seg=96))

    # ---- steep conical roof ---------------------------------------------
    roof = [(0.0, 35.30), (6.68, 27.55)]
    p.append(H.lathe(tag + "_roof", roof, MAT["slate"], seg=96, T=Ts(cx, cy, 0),
                     close_bottom=False, close_top=True))
    p.append(ring_wall(tag + "_eave", Ts(cx, cy, 0), 6.62, 7.05, 27.34, 27.62, sd,
                       seg=96))
    # four hips up the cone
    for i in range(4):
        a = PI * 0.25 + i * PI * 0.5
        L = math.hypot(6.55, 7.7)
        p.append(box(tag + "_rib%d" % i,
                     Ts(cx + math.cos(a) * 3.28, cy + math.sin(a) * 3.28, 31.4,
                        rz=a - PI * 0.5, rx=-math.atan2(7.75, 6.55)),
                     (0.16, L, 0.10), sd, bev=0.01))
    # lucarne on the front slope
    lx, ly = cx, cy + 5.05
    p.append(box(tag + "_luc", Ts(lx, ly, 29.05), (1.30, 1.10, 1.55), sw, bev=0.02))
    p.append(H.prism(tag + "_lug",
                     Ts(lx, ly + 0.55, 29.82),
                     [(-0.78, 0.0), (0.78, 0.0), (0.0, 0.85)], 1.16, MAT["slate"],
                     axis="y"))
    p.append(box(tag + "_luw", Ts(lx, ly + 0.56, 29.02), (0.52, 0.06, 0.72),
                 MAT["glass"]))
    p.append(box(tag + "_lus", Ts(lx, ly + 0.60, 28.63), (0.80, 0.18, 0.09), pale))
    # finial, vane and flag
    p.append(cyl(tag + "_fin", Ts(cx, cy, 35.62), 0.075, 1.30, iron, seg=10))
    p.append(sphere(tag + "_fbl", Ts(cx, cy, 36.35), 0.17, MAT["gold"], seg=12, ring=7))
    p.append(box(tag + "_vn", Ts(cx + 0.32, cy, 35.95), (0.58, 0.03, 0.22), MAT["gold"]))
    p += flag(tag + "_flag", Ts(cx, cy, 36.45), 0.10, 2.05, 1.15,
              MAT["banner_red"], MAT["gold"], iron)

    # ---- ground-floor plinth details ------------------------------------
    for i in range(8):
        a = math.radians(22.5 + 45.0 * i)
        Tb = face_T(cx, cy, 0.35, a, 8.55)
        p.append(box(tag + "_bs%d" % i, Tb @ Ts(0, 0.10, 0.35),
                     (1.10, 0.26, 0.70), sd, bev=0.015))
    return p


# --------------------------------------------------------------------------
#  arched door in an already-cut opening
# --------------------------------------------------------------------------
def _arched_door(name, T, w, h, MAT, depth=0.32, steps=0, double=False,
                 arched=True):
    """Timber leaf + frame for a cut opening.  T at the sill, +Y out."""
    wood, wd = MAT["wood"], MAT["wood_dark"]
    iron = MAT["iron_dark"]
    sw, pale = MAT["stone_warm"], MAT["stone_pale"]
    p = []
    hw = w * 0.5
    p.append(box(name + "_leaf", T @ Ts(0, -depth, h * 0.5), (w - 0.10, 0.13, h - 0.06),
                 wood, bev=0.012))
    # planks
    n = 5
    for i in range(n + 1):
        x = -hw + w * i / n
        p.append(box(name + "_pl%d" % i, T @ Ts(x, -depth + 0.075, h * 0.5),
                     (0.035, 0.02, h - 0.12), wd))
    for k in range(3):
        z = h * (0.20 + 0.28 * k)
        p.append(box(name + "_bd%d" % k, T @ Ts(0, -depth + 0.09, z),
                     (w * 0.94, 0.035, 0.13), iron))
        for s in (-1, 0, 1):
            p.append(cyl(name + "_bv%d_%d" % (k, s),
                         T @ Ts(s * w * 0.38, -depth + 0.11, z) @ RotX(PI * 0.5),
                         0.035, 0.03, iron, seg=8))
    if arched:
        p.append(voussoir_ring(name + "_vs", T @ Ts(0, -0.02, 0), hw + 0.02, 0.30, 9,
                               pale, y=0.0, zc=h, thick=0.30))
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (hw + 0.14), 0.06, h * 0.5),
                     (0.30, 0.22, h + 0.05), sw, bev=0.012))
    for i in range(steps):
        p.append(box(name + "_st%d" % i, T @ Ts(0, 0.30 + i * 0.30, -0.07 - i * 0.0),
                     (w + 0.50, 0.34, 0.16), pale, bev=0.012))
    return p
