

# ===========================================================================
# PART D - the upper feast hall, and the stair tower that climbs to it
# ===========================================================================
FZ0 = Z_FEAST                 # 20.20  floor of the feast hall
FZ1 = Z_FEAST_TOP             # 28.40  its ceiling
FWT = 0.60                    # thickness of the upper storey walls
ST_SEG = 36
ST_DA = TAU / ST_SEG
ST_A0 = math.radians(200.0)   # the foot of the stair, facing into the hall
ST_STEP_A = math.radians(13.0)
ST_N = 112
ST_RISE = FZ0 / ST_N
ST_DB = (math.radians(190.0), math.radians(210.0))
ST_DT = (math.radians(206.0), math.radians(226.0))


def _pol(r, a):
    return (r * math.cos(a), r * math.sin(a))


def feast_poly(rad=0.0, n=18):
    """Plan of the upper storey: the room, with the tower bitten out."""
    P = [(-HX - rad, -HY - rad), (HX + rad, -HY - rad), (HX + rad, ST_CY)]
    for k in range(n + 1):
        a = (math.pi * 0.5) * k / n
        P.append((ST_CX + ST_R * math.cos(a), ST_CY + ST_R * math.sin(a)))
    P.append((-HX - rad, HY + rad))
    return P


def build_feast_floor(M, rng):
    P = []
    wf = _m(M, "wood_floor")
    st = _m(M, "stone_wall")
    # structural slab, top dressed with boards
    P.append(prism_z("ci_f_slab", Ts(0, 0, FZ0 - 0.24), feast_poly(), 0.48, st))
    P.append(prism_z("ci_f_deck", Ts(0, 0, FZ0 - 0.02), feast_poly(), 0.06, wf))
    # board joints, and the beam soffit showing under the edge
    for k in range(-14, 15):
        yy = k * 0.86
        if abs(yy) > HY - 0.3:
            continue
        xs = HX
        if yy > ST_CY - ST_R and yy < ST_CY + ST_R:
            xs = ST_CX - math.sqrt(max(0.0, ST_R ** 2 - (yy - ST_CY) ** 2))
        if xs < 0.5:
            continue
        P.append(bx("ci_f_joint", Ts(xs * 0.5, yy, FZ0 + 0.012),
                    (xs - 0.02, 0.024, 0.014), _m(M, "wood_dark")))
    return P


def _clip_x(yy):
    """Where an X-running ceiling member has to stop, short of the tower."""
    if abs(yy - ST_CY) >= ST_R:
        return HX
    return ST_CX - math.sqrt(max(0.0, ST_R ** 2 - (yy - ST_CY) ** 2))


def build_feast_ceiling(M, rng):
    P = []
    wb = _m(M, "wood_beam")
    wd = _m(M, "wood_dark")
    pl = _m(M, "plaster")
    P.append(prism_z("ci_f_ceil", Ts(0, 0, FZ1 + 0.12), feast_poly(), 0.24, pl))
    for yy in (-7.5, -4.5, -1.5, 1.5, 4.5, 7.5):
        xe = _clip_x(yy)
        if xe < -HX + 1.0:
            continue
        P.append(bx("ci_f_beam", Ts((-HX + xe) * 0.5, yy, FZ1 - 0.22),
                    (xe + HX, 0.34, 0.44), wb))
        # braces at the ends
        for sx in (-1, 1):
            xb = -HX + 0.1 if sx < 0 else xe - 0.1
            P.append(bx("ci_f_brace", Ts(xb - sx * 0.42, yy, FZ1 - 0.72),
                        (0.16, 0.20, 0.72), wd))
    # cornice
    for s in (1, -1):
        P.append(bx("ci_f_corn", Ts(0, s * (HY - 0.06), FZ1 - 0.10),
                    (2 * HX, 0.30, 0.26), wb))
    return P


def feast_wall(s, M, rng):
    """Upper storey wall: wainscot, plaster, timber posts, leaded lights."""
    P = []
    n = "+x" if s > 0 else "-x"
    T = WF(s * HX, 0.0, 0.0, n) if s > 0 else WF(-HX, 0.0, 0.0, n)
    pl = _m(M, "plaster")
    wb = _m(M, "wood_beam")
    wd = _m(M, "wood_dark")
    sl = _m(M, "stone_course")
    # the frame here runs +X along +Y for both ends, so build in (y, z)
    # room is y in [-HY, HY]
    H = FZ1 - FZ0
    # wainscot
    P.append(bx("ci_f_wsc", T @ Ts(0, 0.10, FZ0 + 0.70), (2 * HY, 0.22, 1.40), wb))
    P.append(bx("ci_f_wsc_c", T @ Ts(0, 0.02, FZ0 + 1.44), (2 * HY, 0.30, 0.12), wd,
                bev=0.012))
    for k in range(-9, 10):
        yy = k * 1.0
        P.append(bx("ci_f_stile", T @ Ts(yy, 0.05, FZ0 + 0.70), (0.10, 0.20, 1.34), wd))
    # plaster field
    P.append(bx("ci_f_pl", T @ Ts(0, FWT * 0.5, FZ0 + H * 0.5), (2 * HY, FWT, H), pl))
    # timber posts
    for yy in (-HY, -HY + 4.5, -HY + 9.0, -HY + 13.5, HY):
        P.append(bx("ci_f_post", T @ Ts(yy, -0.06, FZ0 + H * 0.5), (0.30, 0.34, H), wb))
    P.append(bx("ci_f_plate", T @ Ts(0, -0.02, FZ1 - 0.30), (2 * HY, 0.30, 0.34), wb))
    return P


def feast_long_wall(s, M, rng):
    """Upper storey long wall: piers, plaster, and four tall craft windows."""
    P = []
    n = "+y" if s > 0 else "-y"
    T = WF(0.0, s * HY, 0.0, n)
    U = HX
    pl = _m(M, "plaster")
    wb = _m(M, "wood_beam")
    wd = _m(M, "wood_dark")
    st = _m(M, "stone_wall")
    sl = _m(M, "stone_light")
    H = FZ1 - FZ0
    SP, RR = FZ0 + 4.15, 0.80
    # wainscot, and the band above the window heads
    P.append(bx("ci_f_lwsc", T @ Ts(0, 0.16, FZ0 + 0.77), (2 * U, 0.32, 1.54), wb))
    P.append(bx("ci_f_lwsc_c", T @ Ts(0, 0.10, FZ0 + 1.57), (2 * U, 0.40, 0.12), wd,
                bev=0.012))
    P.append(bx("ci_f_lwtop", T @ Ts(0, FWT * 0.5, FZ0 + (5.05 + H) * 0.5),
                (2 * U, FWT, H - 5.05), pl))
    P.append(bx("ci_f_lwplate", T @ Ts(0, -0.04, FZ1 - 0.30), (2 * U, 0.32, 0.34), wb))
    bw = 2 * U / 4.0
    for i in range(4):
        xc = -U + (i + 0.5) * bw
        hs = 1.50
        z0 = FZ0 + 1.60
        u0, u1 = xc - hs - 0.30, xc + hs + 0.30
        # solid piers either side of each window
        for (a0, a1) in ((-U + i * bw, u0), (u1, -U + (i + 1) * bw)):
            if a1 - a0 < 0.06:
                continue
            P.append(bx("ci_f_wpier", T @ Ts((a0 + a1) * 0.5, FWT * 0.5,
                                            FZ0 + (1.54 + 5.05) * 0.5),
                        (a1 - a0, FWT, 5.05 - 1.54), st))
        P.append(spandrel("ci_f_wspan", T @ Ts(0, FWT * 0.5, 0), u0, u1, SP, RR,
                          FZ0 + 5.05, FWT, pl, nseg=7))
        P.extend(glazed_window("ci_f_w", T, xc, 0.06, z0, hs, SP, RR, rng))
    return P


def build_fireplace(M, rng):
    """A hooded hearth on the -X wall of the feast hall, with fire and smoke."""
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    st = _m(M, "stone_wall")
    sc = _m(M, "stone_course")
    sd = _m(M, "stone_dark")
    fi = _m(M, "fire")
    em = _m(M, "ember")
    ir = _m(M, "iron")
    wd = _m(M, "wood_dark")
    HW = 2.30           # half width of the hearth
    DP = 1.15           # depth into the wall
    OH = 2.55           # opening height
    # stone cheeks, back, lintel and the hood above
    P.append(bx("ci_fp_back", T @ Ts(0, DP + 0.20, FZ0 + 2.6), (2 * HW + 0.5, 0.40, 5.4), sd))
    for s2 in (-1, 1):
        P.append(bx("ci_fp_cheek", T @ Ts(s2 * (HW + 0.30), DP * 0.5, FZ0 + 2.6),
                    (0.60, DP + 0.4, 5.4), st, bev=0.016))
        P.append(bx("ci_fp_pil", T @ Ts(s2 * (HW + 0.02), -0.06, FZ0 + 1.25),
                    (0.44, 0.16, 2.5), sc, bev=0.014))
    P.append(bx("ci_fp_lint", T @ Ts(0, DP * 0.5, FZ0 + OH + 0.30),
                (2 * HW + 1.2, DP + 0.5, 0.50), sc, bev=0.016))
    # the hood, stepping out to the ceiling
    for k in range(4):
        w = (2 * HW + 1.1) - k * 0.55
        P.append(bx("ci_fp_hood%d" % k, T @ Ts(0, DP * 0.5 + 0.16 * k, FZ0 + OH + 0.75 + k * 0.62),
                    (w, DP + 0.1, 0.66), st if k % 2 else sc, bev=0.014))
    # hearth floor, soot back, fire basket
    P.append(bx("ci_fp_floor", T @ Ts(0, DP * 0.5, FZ0 + 0.09), (2 * HW, DP, 0.18), sd,
                bev=0.014))
    P.append(bx("ci_fp_kerb", T @ Ts(0, -0.10, FZ0 + 0.20), (2 * HW + 0.7, 0.36, 0.40), sc,
                bev=0.014))
    for s2 in (-1, 1):
        P.append(bx("ci_fp_iron", T @ Ts(s2 * 0.66, DP * 0.55 - 0.10, FZ0 + 0.42),
                    (0.09, 1.10, 0.60), ir))
    # logs
    for k in range(5):
        yy = DP * 0.5 + rng.uniform(-0.34, 0.34)
        zz = FZ0 + 0.26 + 0.11 * (k % 3)
        P.append(cyl("ci_fp_log", T @ Ts(rng.uniform(-0.7, 0.7), yy, zz,
                                        rz=rng.uniform(0.0, 1.2), ry=math.pi * 0.5),
                     0.085, 1.5, wd, seg=7))
    # embers and flame tongues
    for k in range(9):
        P.append(sph("ci_fp_coal", T @ Ts(rng.uniform(-1.0, 1.0), DP * 0.5 + rng.uniform(-0.3, 0.3),
                                         FZ0 + 0.22), rng.uniform(0.07, 0.14), em, 8, 5, 0.5))
    for k in range(7):
        xx = -1.0 + 0.33 * k
        h = rng.uniform(0.55, 1.15)
        P.append(prism_y("ci_fp_flame", T @ Ts(xx + rng.uniform(-0.06, 0.06),
                                              DP * 0.5 + rng.uniform(-0.2, 0.2), FZ0 + 0.30),
                         [(-0.13, 0.0), (0.13, 0.0), (0.05, h * 0.55), (0.0, h),
                          (-0.06, h * 0.5)], 0.13, fi))
    return P


def _smoke_mat():
    m = bpy.data.materials.get("ci_smoke_vol")
    if m:
        return m
    m = bpy.data.materials.new("ci_smoke_vol")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.34, 0.32, 0.30, 1.0)
    vol.inputs["Density"].default_value = 0.55
    vol.inputs["Anisotropy"].default_value = 0.35
    vol.inputs["Absorption Color"].default_value = (0.10, 0.09, 0.08, 1.0)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return m


def build_smoke(M):
    """A soft plume of smoke over the hearth: a volume, so it really reads."""
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    sm = _smoke_mat()
    rings = []
    for k in range(7):
        t = k / 6.0
        z = FZ0 + 0.55 + t * 2.6
        r = 0.30 + t * 0.42
        yy = 0.55 + t * 0.30
        ring = []
        for j in range(10):
            a = TAU * j / 10.0
            ring.append(Vector((r * math.cos(a), yy + r * 0.7 * math.sin(a), z)))
        rings.append(ring)
    ob = loft("ci_smoke", T, rings, sm, closed=True, cap0=False, cap1=False)
    P.append(ob)
    return P


def build_feast_tables(M, rng):
    P = []
    wb = _m(M, "wood")
    wd = _m(M, "wood_dark")
    cl = _m(M, "cloth_white")
    for s2 in (-1, 1):
        yc = s2 * 3.05
        x0, x1 = -9.6, 1.4
        L = x1 - x0
        # top, two boards
        for k in (-1, 1):
            P.append(bx("ci_t_top", Ts((x0 + x1) * 0.5, yc + k * 0.34, FZ0 + 0.76),
                        (L, 0.66, 0.09), wb, bev=0.008))
        P.append(bx("ci_t_rail", Ts((x0 + x1) * 0.5, yc, FZ0 + 0.68), (L - 0.5, 1.32, 0.10), wd))
        # trestles
        for k in range(3):
            xt = x0 + 0.9 + k * (L - 1.8) / 2.0
            P.append(bx("ci_t_leg", Ts(xt, yc, FZ0 + 0.36), (0.16, 0.20, 0.72), wd))
            P.append(bx("ci_t_foot", Ts(xt, yc, FZ0 + 0.05), (0.24, 1.14, 0.10), wd, bev=0.010))
            P.append(bx("ci_t_brace", Ts(xt, yc, FZ0 + 0.30), (0.12, 1.00, 0.14), wd,
                        bev=0.008))
        # benches either side
        for k in (-1, 1):
            yb = yc + k * 1.14
            P.append(bx("ci_t_bench", Ts((x0 + x1) * 0.5, yb, FZ0 + 0.46),
                        (L - 1.2, 0.34, 0.08), wb, bev=0.008))
            for j in range(3):
                xt = x0 + 1.2 + j * (L - 2.4) / 2.0
                P.append(bx("ci_t_bleg", Ts(xt, yb, FZ0 + 0.23), (0.12, 0.30, 0.46), wd))
        # a runner of linen and a couple of platters
        P.append(bx("ci_t_cloth", Ts((x0 + x1) * 0.5, yc, FZ0 + 0.815),
                    (L - 0.8, 0.66, 0.012), cl))
        for j in range(5):
            xt = x0 + 1.4 + j * (L - 2.8) / 4.0
            P.append(cyl("ci_t_plate", Ts(xt, yc + 0.10, FZ0 + 0.825), 0.19, 0.026,
                         _m(M, "brass"), seg=14))
            P.append(cyl("ci_t_mug", Ts(xt + 0.42, yc - 0.22, FZ0 + 0.86), 0.055, 0.16,
                         _m(M, "iron"), seg=10))
        for j in range(2):
            xt = x0 + 2.6 + j * 3.4
            P.append(cyl("ci_t_cand", Ts(xt, yc - 0.04, FZ0 + 0.88), 0.035, 0.22,
                         _m(M, "candle"), seg=8))
            P.append(cyl("ci_t_cstick", Ts(xt, yc - 0.04, FZ0 + 0.79), 0.09, 0.03,
                         _m(M, "brass"), seg=10))
    # a dresser against the -Y wall
    P.append(bx("ci_dr_body", Ts(-4.0, -HY + 0.42, FZ0 + 0.85), (3.2, 0.72, 1.30), wd))
    P.append(bx("ci_dr_top", Ts(-4.0, -HY + 0.42, FZ0 + 1.52), (3.4, 0.86, 0.10), wb,
                bev=0.012))
    for k in range(6):
        P.append(cyl("ci_dr_jug", Ts(-5.2 + k * 0.46, -HY + 0.40, FZ0 + 1.66), 0.11, 0.28,
                     _m(M, "brass") if k % 2 else _m(M, "iron"), seg=10))
    return P


def build_chandelier(M, rng):
    P = []
    ir = _m(M, "iron")
    cx, cy = -1.0, 0.0
    cz = FZ1 - 4.30
    P.append(cyl("ci_ch_ring", Ts(cx, cy, cz), 1.36, 0.10, ir, seg=28, r2=1.36))
    P.append(cyl("ci_ch_ring2", Ts(cx, cy, cz - 0.34), 1.06, 0.07, ir, seg=28))
    for k in range(8):
        a = TAU * k / 8.0
        xx, yy = cx + 1.20 * math.cos(a), cy + 1.20 * math.sin(a)
        P.append(cyl("ci_ch_arm", Ts(xx, yy, cz + 0.16), 0.030, 0.34, ir, seg=6))
        P.append(cyl("ci_ch_cup", Ts(xx, yy, cz + 0.34), 0.085, 0.06, ir, seg=10))
        P.append(cyl("ci_ch_cand", Ts(xx, yy, cz + 0.52), 0.042, 0.34, _m(M, "candle"),
                     seg=8))
    for k in range(3):
        a = TAU * k / 3.0 + 0.4
        top = Vector((cx, cy, FZ1 - 0.14))
        bot = Vector((cx + 1.10 * math.cos(a), cy + 1.10 * math.sin(a), cz + 0.05))
        P.append(cyl("ci_ch_chain", Ts(top.x, top.y, (top.z + bot.z) * 0.5), 0.014,
                     top.z - bot.z, ir, seg=5))
    P.append(cyl("ci_ch_hub", Ts(cx, cy, cz + 0.30), 0.12, 0.20, ir, seg=10))
    return P


def build_barrels(M, rng):
    P = []
    wd = _m(M, "wood")
    ir = _m(M, "iron")
    spots = [(-11.3, -6.9, 0.0), (-10.4, -7.5, 0.0), (-11.5, -5.8, 0.0),
             (-11.0, -7.2, 0.86), (-9.4, -6.4, 0.4)]
    for (xx, yy, up) in spots:
        if up > 0.2:
            T = Ts(xx, yy, FZ0 + up)
            P.append(cyl("ci_bar", T, 0.40, 0.86, wd, seg=16, r2=0.36))
            for zz in (-0.26, 0.0, 0.26):
                P.append(cyl("ci_bar_hoop", T @ Ts(0, 0, zz), 0.405, 0.05, ir, seg=16,
                             r2=0.385))
        else:
            T = Ts(xx, yy, FZ0 + 0.43)
            P.append(cyl("ci_bar", T, 0.40, 0.86, wd, seg=16, r2=0.36))
            for zz in (-0.26, 0.0, 0.26):
                P.append(cyl("ci_bar_hoop", T @ Ts(0, 0, zz), 0.405, 0.05, ir, seg=16,
                             r2=0.385))
    return P


def build_hound(nm, T, M, rng, mat_scale=1.0):
    P = []
    fu = _m(M, "leather")
    P.append(sph(nm + "_body", T @ Ts(0, 0, 0.46), 0.30, fu, 12, 8, 1.9))
    P.append(sph(nm + "_chest", T @ Ts(0.30, 0, 0.48), 0.24, fu, 12, 8, 1.15))
    P.append(cyl(nm + "_neck", T @ Ts(0.48, 0, 0.60, ry=-0.7), 0.13, 0.34, fu, seg=10))
    P.append(sph(nm + "_head", T @ Ts(0.62, 0, 0.70), 0.145, fu, 12, 8, 1.15))
    P.append(sph(nm + "_snout", T @ Ts(0.76, 0, 0.66), 0.085, fu, 10, 6, 1.5))
    for s2 in (-1, 1):
        P.append(bx(nm + "_ear", T @ Ts(0.58, s2 * 0.09, 0.80), (0.07, 0.05, 0.13), fu))
        for xs in (0.28, -0.24):
            P.append(cyl(nm + "_leg", T @ Ts(xs, s2 * 0.15, 0.22), 0.045, 0.42, fu, seg=7))
            P.append(bx(nm + "_paw", T @ Ts(xs + 0.03, s2 * 0.15, 0.035), (0.13, 0.09, 0.07), fu))
    P.append(cyl(nm + "_tail", T @ Ts(-0.44, 0, 0.58, ry=1.0), 0.035, 0.42, fu, seg=6))
    return P


def build_feast_props(M, rng):
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    # two hounds asleep on the hearth
    P += build_hound("ci_hound1", Ts(-9.4, 1.30, FZ0, rz=0.5), M, rng)
    P += build_hound("ci_hound2", Ts(-9.7, -1.45, FZ0, rz=-0.35), M, rng)
    # a pair of standing iron candle stands by the hearth
    ir = _m(M, "iron")
    for s2 in (-1, 1):
        P.append(cyl("ci_stand", T @ Ts(s2 * 2.9, -0.8, FZ0 + 0.9), 0.055, 1.8, ir, seg=8))
        P.append(cyl("ci_stand_b", T @ Ts(s2 * 2.9, -0.8, FZ0 + 0.06), 0.22, 0.06, ir,
                     seg=12))
        P.append(cyl("ci_stand_c", T @ Ts(s2 * 2.9, -0.8, FZ0 + 1.86), 0.10, 0.06, ir,
                     seg=10))
        P.append(cyl("ci_stand_can", T @ Ts(s2 * 2.9, -0.8, FZ0 + 2.06), 0.048, 0.36,
                     _m(M, "candle"), seg=8))
    return P


# ---------------------------------------------------------------------------
# the stair tower
# ---------------------------------------------------------------------------
def build_stair_tower(M, rng):
    """A corner turret: helical treads round an open well, lit by torches."""
    P = []
    st = _m(M, "stone_wall")
    sl = _m(M, "stone_light")
    sd = _m(M, "stone_dark")
    sc = _m(M, "stone_course")
    ir = _m(M, "iron")
    cx, cy = ST_CX, ST_CY
    ri, ro = ST_RIN + 0.30, ST_R          # inner face of the wall
    # ---- the wall itself, in segments, with doorways left open
    verts, faces = [], []

    def in_span(a, sp):
        return sp[0] - 1e-6 <= a + 1e-6 and a < sp[1] - 1e-6

    for i in range(ST_SEG):
        a0 = ST_A0 + i * ST_DA
        a1 = a0 + ST_DA
        for (z0, z1) in ((0.0, FZ0), (FZ0, Z_TOP)):
            if z0 == 0.0 and in_span(a0, ST_DB):
                continue
            if z0 > 0.0 and in_span(a0, ST_DT):
                continue
            b = len(verts)
            for (r, a, z) in ((ri, a0, z0), (ro, a0, z0), (ro, a1, z0), (ri, a1, z0)):
                verts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
            for (r, a, z) in ((ri, a0, z1), (ro, a0, z1), (ro, a1, z1), (ri, a1, z1)):
                verts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
            faces.append((b + 0, b + 3, b + 2, b + 1))       # underside
            faces.append((b + 4, b + 5, b + 6, b + 7))       # head
            faces.append((b + 0, b + 1, b + 5, b + 4))       # jamb a0
            faces.append((b + 3, b + 7, b + 6, b + 2))       # jamb a1
            faces.append((b + 0, b + 4, b + 6, b + 2))       # inner face
            faces.append((b + 1, b + 3, b + 7, b + 5))       # outer face
    ob = K.mesh_obj("ci_st_wall", verts, faces)
    K.assign(ob, st)
    P.append(ob)
    # ---- door surrounds, bottom and top
    for (ac, z0) in ((0.5 * (ST_DB[0] + ST_DB[1]), 0.0),
                     (0.5 * (ST_DT[0] + ST_DT[1]), FZ0)):
        for da in (-1, 1):
            aa = ac + da * math.radians(10.0)
            P.append(bx("ci_st_jamb", Ts(cx + (ri + 0.02) * math.cos(aa),
                                        cy + (ri + 0.02) * math.sin(aa), z0 + 1.30,
                                        rz=aa + math.pi * 0.5),
                        (0.30, 0.34, 2.60), sc, bev=0.014))
        aa = ac
        P.append(bx("ci_st_lint", Ts(cx + (ri + 0.02) * math.cos(aa),
                                    cy + (ri + 0.02) * math.sin(aa), z0 + 2.62,
                                    rz=aa + math.pi * 0.5),
                    (0.90, 0.36, 0.30), sc, bev=0.014))
    # ---- helical treads, one mesh
    verts, faces = [], []
    r0, r1 = ST_WELL, ST_R - 0.16
    for i in range(ST_N):
        a0 = ST_A0 + i * ST_STEP_A - ST_STEP_A * 0.5
        a1 = a0 + ST_STEP_A
        zt = ST_RISE * (i + 1)
        zb = zt - 0.17
        b = len(verts)
        for (r, a) in ((r0, a0), (r1, a0), (r1, a1), (r0, a1)):
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a), zt))
        for (r, a) in ((r0, a0), (r1, a0), (r1, a1), (r0, a1)):
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a), zb))
        faces.append((b + 0, b + 1, b + 2, b + 3))           # tread
        faces.append((b + 4, b + 7, b + 6, b + 5))           # soffit
        faces.append((b + 1, b + 5, b + 6, b + 2))           # outer cheek
        faces.append((b + 0, b + 3, b + 7, b + 4))           # inner cheek
        faces.append((b + 2, b + 6, b + 7, b + 3))           # riser
    ob = K.mesh_obj("ci_st_treads", verts, faces)
    K.assign(ob, sl)
    P.append(ob)
    # ---- the helical balustrade round the well (the open shaft)
    rings = []
    n = ST_N * 2
    for i in range(n + 1):
        a = ST_A0 + i * (ST_STEP_A * ST_N / n)
        z = ST_RISE * (i * ST_N / n) + 0.02
        ring = []
        for (r, dz) in ((ST_WELL - 0.30, 0.0), (ST_WELL, 0.0),
                        (ST_WELL, 1.02), (ST_WELL - 0.30, 1.02)):
            ring.append(Vector((cx + r * math.cos(a), cy + r * math.sin(a), z + dz)))
        rings.append(ring)
    P.append(loft("ci_st_rail", Ts(0, 0, 0), rings, sc, closed=True, smooth=False))
    # ---- torches in niches up the shaft
    for k in range(9):
        i = 6 + k * 12
        a = ST_A0 + i * ST_STEP_A
        z = ST_RISE * (i + 1)
        rr = ST_R - 0.10
        pm = Vector((cx + rr * math.cos(a), cy + rr * math.sin(a), z + 1.75))
        P.append(bx("ci_st_niche", Ts(pm.x, pm.y, pm.z, rz=a),
                    (0.52, 0.24, 0.78), sd, bev=0.010))
        P.append(bx("ci_st_brack", Ts(pm.x, pm.y, pm.z - 0.10, rz=a),
                    (0.10, 0.42, 0.10), ir))
        P.append(cyl("ci_st_torch", Ts(pm.x, pm.y, pm.z - 0.05, rz=a), 0.05, 0.62,
                     _m(M, "wood_dark"), seg=7))
        P.append(sph("ci_st_flame", Ts(pm.x, pm.y, pm.z + 0.34), 0.11, _m(M, "fire"),
                     8, 5, 1.7))
    # ---- the lantern at the head of the shaft
    P.append(cyl("ci_st_cap", Ts(cx, cy, Z_TOP + 0.10), ri + 0.06, 0.20, sd, seg=28))
    P.append(sph("ci_st_lamp", Ts(cx, cy, Z_TOP - 0.55), 0.26, _m(M, "candle"), 10, 6, 1.0))
    return P
