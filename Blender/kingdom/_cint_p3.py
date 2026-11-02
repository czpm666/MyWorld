# ---------------------------------------------------------------------------
# roof: wall plates, tie-beam trusses, rafters, boarded deck
# ---------------------------------------------------------------------------
PLATE_TOP = 16.90             # top of the timber wall plate
EAVE_X = 9.45                 # outer edge of the wall plate = eave line


def roof(C, E, MAT, rng):
    wb = _m(MAT, "wood_beam")
    wd = _m(MAT, "wood_dark")
    # ---- timber wall plates running the full length of both walls
    for s in (1,):
        E.append(bx("plate", Ts(9.10, 0.0, (Z_PLATE + PLATE_TOP) * 0.5),
                    (0.70, HALL_L, PLATE_TOP - Z_PLATE), wd, bev=0.02))
    # ---- boarded deck, one slope per side, meeting on the ridge at x = 0
    E.append(prism("deck", [(0.0, Z_RIDGE), (EAVE_X, PLATE_TOP),
                            (EAVE_X, PLATE_TOP + 0.14), (0.0, Z_RIDGE + 0.14)],
                   _m(MAT, "wood_beam"), Y_S, Y_N, axis="y"))
    # ---- common rafters
    y = Y_S + 0.28
    k = 0
    while y < Y_N - 0.2:
        E.append(bx("rf%03d" % k, Ts(4.70, y, 19.00, ry=math.radians(24.28)),
                    (10.05, 0.20, 0.26), wb, bev=0.0))
        y += 0.56
        k += 1
    # ---- trusses on the arcade piers
    for i, py in enumerate(PIERS):
        # tie beam: spans the nave, seated on both wall plates
        C.append(bx("tie%d" % i, Ts(0.0, py, PLATE_TOP + 0.21),
                    (18.90, 0.36, 0.42), wb, bev=0.02))
        # king post
        C.append(bx("king%d" % i, Ts(0.0, py, (PLATE_TOP + 0.42 + 21.05) * 0.5),
                    (0.22, 0.24, 21.05 - PLATE_TOP - 0.42), wb, bev=0.015))
        # collar
        C.append(bx("col%d" % i, Ts(0.0, py, 18.35), (6.60, 0.22, 0.26), wb,
                    bev=0.015))
        # queen struts and braces (one half, mirrored later)
        E.append(bx("qs%d" % i, Ts(3.30, py, (18.48 + 19.62) * 0.5),
                    (0.18, 0.20, 19.62 - 18.48), wb, bev=0.012))
        E.append(bx("br%d" % i, Ts(4.70, py, (17.32 + 18.22) * 0.5,
                                   ry=math.radians(20.6)),
                    (2.56, 0.18, 0.20), wb, bev=0.012))
        # a carved corbel where the tie meets the wall
        E.append(frustum("corb%d" % i, Ts(8.55, py, 15.84), (0.44, 0.56),
                         (0.62, 0.80), 0.56, _m(MAT, "stone_light"), bev=0.02))
        # banners hanging from the tie beam, one either side of the crown
        E += banner("bn%d" % i, Ts(6.85, py, PLATE_TOP), 1.30, 3.30, MAT, rng)
    # ---- ridge beam
    C.append(bx("ridge", Ts(0.0, 0.0, Z_RIDGE - 0.17), (0.34, HALL_L, 0.26),
                wd, bev=0.02))


def banner(name, T, w, h, MAT, rng, mat=None):
    """Cloth banner under a beam: rod bolted to the soffit, cloth hanging from it."""
    m = mat or _m(MAT, "cloth_red")
    out = []
    out.append(bx(name + "_rod", T @ Ts(0.0, 0.0, -0.05),
                  (w + 0.24, 0.06, 0.06), _m(MAT, "wood_dark")))
    for s in (-1, 1):
        out.append(bx(name + "_br%d" % s, T @ Ts(s * w * 0.42, 0.0, -0.05),
                      (0.05, 0.05, 0.16), _m(MAT, "iron")))
    # cloth: two rows so it has a gentle sag, swallow-tail foot
    rows = []
    for (zz, sw) in ((0.0, 1.0), (h * 0.55, 1.0), (h * 0.92, 1.0)):
        rows.append([T @ Vector((-w * 0.5 * sw, 0.02 * math.sin(zz), zz)),
                     T @ Vector((0.0, 0.09, zz)),
                     T @ Vector((w * 0.5 * sw, 0.02 * math.sin(zz), zz))])
    out.append(quad_strip(name + "_cl", rows, m))
    for s in (-1, 1):
        out.append(quad_strip(name + "_tail%d" % s,
                              [[T @ Vector((s * w * 0.5, 0.0, h * 0.92)),
                                T @ Vector((s * w * 0.18, 0.06, h * 0.92))],
                               [T @ Vector((s * w * 0.5, 0.0, h)),
                                T @ Vector((s * w * 0.30, 0.06, h * 1.06))]], m))
    return out


# ---------------------------------------------------------------------------
# screen wall between the narthex and the nave
# ---------------------------------------------------------------------------
def screen_wall(C, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    glass = [_m(MAT, k) for k in ("glass_gold", "glass_blue", "glass_red",
                                  "glass_pale")]
    y0, y1 = Y_SCREEN - 1.70, Y_SCREEN       # -18.9 .. -17.2
    hw = 4.40
    z_spr, z_apex = 6.10, 10.30
    z_w0, z_w1 = 11.60, 15.40
    # side panels
    for s in (-1, 1):
        a, b = (s * hw, s * XNAVE)
        C.append(prism("sw_side%d" % s, [(min(a, b), 0.0), (max(a, b), 0.0),
                                         (max(a, b), Z_PLATE), (min(a, b), Z_PLATE)],
                       st, y0, y1, axis="y"))
        # blind arcade on the narthex face
        for j in range(3):
            xc = s * (hw + 0.62 + j * 1.24)
            C.append(prism("sw_ba%d_%d" % (s, j),
                           [(xc + x, z) for (x, z) in
                            hole_pts(0.44, 1.10, 3.05, 3.95, 10)],
                           sd, y0 - 0.02, y0 + 0.06, axis="y"))
            C += arch_ring_y("sw_br%d_%d" % (s, j), xc, 3.05, 0.44, 0.90, 0.16,
                             y0 - 0.10, y0 + 0.06, sl, n=10, keystone=False)
        # statue niche on the nave face (a shallow aedicule)
        xn = s * (hw + 0.62)
        C.append(prism("sw_ni%d" % s,
                       [(xn + x, z) for (x, z) in
                        hole_pts(0.62, 1.55, 3.35, 4.45, 10)], sd,
                       y1 + 0.01, y1 + 0.05, axis="y"))
        C += arch_ring_y("sw_nr%d" % s, xn, 3.35, 0.62, 1.10, 0.22,
                         y1 + 0.04, y1 + 0.22, sl, n=10, keystone=True)
        for t in (-1, 1):
            C.append(bx("sw_nj%d_%d" % (s, t), Ts(xn + t * 0.74, y1 + 0.11, 2.45),
                        (0.26, 0.22, 1.90), sl, bev=0.015))
        C.append(bx("sw_nb%d" % s, Ts(xn, y1 + 0.11, 1.49), (1.76, 0.22, 0.14),
                    sl, bev=0.015))
        C.append(statue("sw_st%d" % s, Ts(xn, y1 + 0.16, 1.56), 2.45, MAT, rng))
    # arch head: spandrel from the extrados up to the window sill
    C.append(prism("sw_head",
                   spandrel_pts(hw + 0.50, z_apex - 0.02, z_w0, hw + 0.50,
                                z_spr, z_apex - z_spr + 0.50, 14),
                   st, y0, y1, axis="y"))
    # window band above the arch: jambs, head, glass
    for s in (-1, 1):
        a, b = (s * 2.60, s * hw)
        C.append(prism("sw_wj%d" % s, [(min(a, b), z_w0), (max(a, b), z_w0),
                                       (max(a, b), Z_PLATE), (min(a, b), Z_PLATE)],
                       st, y0, y1, axis="y"))
    z_wr = z_w1 - 2.60 * 1.05
    C.append(prism("sw_wh",
                   [(-2.60, z_wr)] +
                   [(-2.60 + x, z_wr + z) for (x, z) in
                    arch_pts(2.60, z_w1 - z_wr, 12) if abs(x) < 2.60 - 1e-6] +
                   [(2.60, z_wr), (2.60, Z_PLATE), (-2.60, Z_PLATE)],
                   st, y0, y1, axis="y"))
    C += glaze_y("sw_w", 0.0, 5.10, z_w0, z_w1, y1, y0, glass, rng,
                 frame_mat=sl, iron=_m(MAT, "iron"), rows=5, arows=4, cols=4)
    # the great arch itself
    C += arch_ring_y("sw_ar", 0.0, z_spr, hw, z_apex - z_spr, 0.50, y0 - 0.08,
                     y1 + 0.06, sl, n=16, keystone=True)
    # imposts at the springing
    for s in (-1, 1):
        C.append(bx("sw_imp%d" % s, Ts(s * (hw + 0.20), (y0 + y1) * 0.5, z_spr - 0.22),
                    (0.44, y1 - y0 + 0.22, 0.30), sl, bev=0.02))


# ---------------------------------------------------------------------------
# entrance wall with the great door
# ---------------------------------------------------------------------------
def south_wall(C, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    wd = _m(MAT, "wood_dark")
    iron = _m(MAT, "iron")
    br = _m(MAT, "brass")
    glass = [_m(MAT, k) for k in ("glass_gold", "glass_blue", "glass_pale")]
    y0, y1 = Y_S, Y_S + 1.6
    hw = 2.10
    z_spr, z_apex = 5.40, 7.10
    z_w0, z_w1 = 8.80, 14.60
    for s in (-1, 1):
        a, b = (s * hw, s * (HALL_W * 0.5))
        C.append(prism("nt_side%d" % s, [(min(a, b), 0.0), (max(a, b), 0.0),
                                         (max(a, b), Z_PLATE), (min(a, b), Z_PLATE)],
                       st, y0, y1, axis="y"))
        # pilasters + a string course give the entrance wall some scale
        for j, xx in enumerate((hw + 1.10, hw + 3.30, hw + 5.60, hw + 7.90)):
            if xx > 14.4:
                continue
            C.append(bx("nt_p%d_%d" % (s, j), Ts(s * xx, y1 + 0.10, 6.20),
                        (0.56, 0.22, 12.40), st, bev=0.02))
            C.append(bx("nt_pc%d_%d" % (s, j), Ts(s * xx, y1 + 0.16, 12.46),
                        (0.72, 0.30, 0.24), sl, bev=0.02))
            C.append(bx("nt_pb%d_%d" % (s, j), Ts(s * xx, y1 + 0.16, 1.30),
                        (0.74, 0.30, 0.30), sl, bev=0.02))
    # head over the door: solid from the extrados up to the window sill
    C.append(prism("nt_head",
                   spandrel_pts(hw + 0.62, z_apex - 0.02, z_w0, hw + 0.62,
                                z_spr, z_apex - z_spr + 0.62, 14),
                   st, y0, y1, axis="y"))
    # window band above the door
    for s in (-1, 1):
        a, b = (s * 2.44, s * (hw + 0.62))
        C.append(prism("nt_wj%d" % s, [(min(a, b), z_w0), (max(a, b), z_w0),
                                       (max(a, b), Z_PLATE), (min(a, b), Z_PLATE)],
                       st, y0, y1, axis="y"))
    z_wr = z_w1 - 2.10 * 1.10
    C.append(prism("nt_wh",
                   [(-2.44, z_wr)] +
                   [(-2.44 + x, z_wr + z) for (x, z) in
                    arch_pts(2.44, z_w1 - z_wr, 12) if abs(x) < 2.44 - 1e-6] +
                   [(2.44, z_wr), (2.44, Z_PLATE), (-2.44, Z_PLATE)],
                   st, y0, y1, axis="y"))
    C += glaze_y("nt_w", 0.0, 4.76, z_w0, z_w1, y1, y0, glass, rng,
                 frame_mat=sl, iron=iron, rows=4, arows=4, cols=4)
    C += arch_ring_y("nt_dr", 0.0, z_spr, hw, z_apex - z_spr, 0.62, y1 - 0.02,
                     y1 + 0.10, sl, n=14, keystone=True)
    # door leaves, closed
    for s in (-1, 1):
        C.append(bx("nt_leaf%d" % s, Ts(s * hw * 0.5, y1 - 0.14,
                                        (z_spr - 0.16) * 0.5),
                    (hw, 0.20, z_spr - 0.16), wd, bev=0.02))
        for j in range(4):
            C.append(bx("nt_band%d_%d" % (s, j), Ts(s * hw * 0.5,
                                                    y1 - 0.24, 0.55 + j * 1.25),
                        (hw - 0.16, 0.05, 0.13), iron, bev=0.008))
        for j in range(2):
            C.append(bx("nt_hinge%d_%d" % (s, j), Ts(s * (hw - 0.22), y1 - 0.24,
                                                     1.05 + j * 2.55),
                        (0.30, 0.06, 0.10), iron))
    C.append(torus("nt_ring", Ts(0.30, y1 - 0.30, 2.10, rz=math.pi * 0.5),
                   0.16, 0.028, br, seg=16, ring=5))
    # a carved tympanum band and the lintel above the leaves
    C.append(bx("nt_lint", Ts(0.0, y1 - 0.10, z_spr + 0.06), (2 * hw + 0.30, 0.34, 0.14),
                sl, bev=0.02))


# ---------------------------------------------------------------------------
# chancel: cross wall, flat ceiling, side windows, back wall
# ---------------------------------------------------------------------------
Z_CHOR_CEIL = 11.20


def chancel(C, E, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    glass = [_m(MAT, k) for k in ("glass_gold", "glass_blue", "glass_red")]
    woodb = _m(MAT, "wood_beam")
    y0, y1 = Y_CHOR, Y_CHOR + 1.0
    hw = 5.00
    z_spr, z_apex = 5.60, 10.30
    # ---- cross wall pierced by the chancel arch
    for s in (-1, 1):
        a, b = (s * hw, s * (XNAVE + 0.55))
        C.append(prism("ch_side%d" % s, [(min(a, b), 0.0), (max(a, b), 0.0),
                                         (max(a, b), Z_CHOR_CEIL),
                                         (min(a, b), Z_CHOR_CEIL)],
                       st, y0, y1, axis="y"))
    C.append(prism("ch_head",
                   spandrel_pts(hw + 0.50, z_apex - 0.02, Z_CHOR_CEIL, hw + 0.50,
                                z_spr, z_apex - z_spr + 0.50, 14),
                   st, y0, y1, axis="y"))
    C += arch_ring_y("ch_ar", 0.0, z_spr, hw, z_apex - z_spr, 0.50, y0 - 0.10,
                     y1 + 0.08, sl, n=16, keystone=True)
    for s in (-1, 1):
        C.append(bx("ch_imp%d" % s, Ts(s * (hw + 0.22), (y0 + y1) * 0.5, z_spr - 0.24),
                    (0.46, y1 - y0 + 0.26, 0.32), sl, bev=0.02))
    # ---- wall above the chancel ceiling, sealing the roof space
    C.append(prism("ch_up", [(-XNAVE, Z_CHOR_CEIL), (XNAVE, Z_CHOR_CEIL),
                             (XNAVE, PLATE_TOP), (-XNAVE, PLATE_TOP)],
                   st, y0, y1, axis="y"))
    # ---- flat coffered ceiling + cross beams
    C.append(bx("ch_ceil", Ts(0.0, (y1 + Y_BACK) * 0.5, Z_CHOR_CEIL + 0.22),
                (2 * XNAVE, Y_BACK - y1, 0.44), sl, bev=0.02))
    for j in range(4):
        yy = y1 + 0.90 + j * 1.72
        C.append(bx("ch_cb%d" % j, Ts(0.0, yy, Z_CHOR_CEIL - 0.11),
                    (17.40, 0.34, 0.22), woodb, bev=0.015))
    # ---- chancel side walls (in +X, mirrored later) with two tall lancets
    X0, X1 = XNAVE, XAIS
    W0, W1 = 4.50, 10.40          # glazing zone
    SPR = 8.00                    # springing of the lancets
    hwl = 1.30
    ycs = (19.05, 22.75)
    jam = [(Y_CHOR + 1.0, ycs[0] - hwl), (ycs[0] + hwl, ycs[1] - hwl),
           (ycs[1] + hwl, Y_BACK)]
    # z 0 .. 4.50
    E.append(prism("ch_w0", [(jam[0][0], 0.0), (Y_BACK, 0.0), (Y_BACK, W0),
                             (jam[0][0], W0)], st, X0, X1, axis="x"))
    # z 4.50 .. 8.00 : the three piers between / beside the openings
    for i, (ya, yb) in enumerate(jam):
        E.append(prism("ch_w1_%d" % i, [(ya, W0), (yb, W0), (yb, SPR), (ya, SPR)],
                       st, X0, X1, axis="x"))
    # z 8.00 .. 10.40 : piers + the two arch heads
    for i, (ya, yb) in enumerate(jam):
        E.append(prism("ch_w2_%d" % i, [(ya, SPR), (yb, SPR), (yb, W1), (ya, W1)],
                       st, X0, X1, axis="x"))
    for j, yc in enumerate(ycs):
        head = [(yc + u, z) for (u, z) in
                spandrel_pts(hwl, SPR, W1, hwl, SPR, W1 - SPR, 14)]
        E.append(prism("ch_sh%d" % j, head, st, X0, X1, axis="x"))
        E += arch_ring_x("ch_wr%d" % j, yc, SPR, hwl, W1 - SPR, 0.28,
                         X0 - 0.06, X1 + 0.06, sl, n=12, keystone=True)
        E += glaze_x("ch_w%d" % j, yc, 2 * hwl, W0, W1, X0, X1, glass, rng,
                     frame_mat=sl, iron=_m(MAT, "iron"),
                     rows=4, arows=3, cols=2)
    # z 10.40 .. 11.70
    E.append(prism("ch_w3", [(Y_CHOR + 1.0, W1), (Y_BACK, W1),
                             (Y_BACK, Z_CHOR_CEIL + 0.50), (Y_CHOR + 1.0,
                                                            Z_CHOR_CEIL + 0.50)],
                   st, X0, X1, axis="x"))
    # string course + cornice on the chancel wall
    E.append(bx("ch_str", Ts((X0 + X1) * 0.5, (Y_CHOR + 1.0 + Y_BACK) * 0.5, W0 - 0.10),
                (X1 - X0 + 0.12, Y_BACK - Y_CHOR - 1.0, 0.18), sl, bev=0.02))
    E.append(bx("ch_cor", Ts((X0 + X1) * 0.5 - 0.04, (Y_CHOR + 1.0 + Y_BACK) * 0.5,
                             Z_CHOR_CEIL - 0.24),
                (X1 - X0 + 0.20, Y_BACK - Y_CHOR - 1.0, 0.24), sl, bev=0.025))


def back_wall(C, MAT, rng):
    """East-end wall: the throne aedicule, blind arcading, cornice."""
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    y0 = Y_BACK
    hw = XNAVE + 0.55
    # body of the wall
    C.append(prism("bw", [(-hw, 0.0), (hw, 0.0), (hw, Z_CHOR_CEIL + 0.4),
                          (-hw, Z_CHOR_CEIL + 0.4)], st, y0, y0 + 1.6, axis="y"))
    # ---- the throne aedicule: dark recess panel + frame projecting 0.40
    nah = 1.45
    C.append(prism("bw_np", hole_pts(nah, 0.90, 5.20, 7.00, 12), sd,
                   y0 - 0.06, y0 - 0.01, axis="y"))
    for s in (-1, 1):
        C.append(bx("bw_nj%d" % s, Ts(s * 1.72, y0 - 0.20, 3.06),
                    (0.54, 0.40, 4.28), sl, bev=0.02))
        C.append(bx("bw_nc%d" % s, Ts(s * 1.72, y0 - 0.21, 5.27),
                    (0.72, 0.44, 0.18), sl, bev=0.015))
        C.append(bx("bw_nb%d" % s, Ts(s * 1.72, y0 - 0.21, 0.88),
                    (0.72, 0.44, 0.16), sl, bev=0.015))
    C += arch_ring_y("bw_nr", 0.0, 5.20, nah, 1.80, 0.30, y0 - 0.40, y0 - 0.02,
                     sl, n=14, keystone=True)
    C.append(bx("bw_ns", Ts(0.0, y0 - 0.22, 0.86), (3.90, 0.46, 0.16), sl, bev=0.02))
    for s in (-1, 1):
        C.append(statue("bw_stat%d" % s, Ts(s * 2.72, y0 - 0.16, 1.42), 2.55,
                        MAT, rng))
    # ---- blind arcading to either side
    for s in (-1, 1):
        for j in range(2):
            xc = s * (2.72 + j * 2.45)
            C.append(prism("bw_bp%d_%d" % (s, j),
                           [(xc + x, z) for (x, z) in
                            hole_pts(0.80, 1.30, 4.00, 5.40, 12)],
                           sd, y0 - 0.05, y0 - 0.01, axis="y"))
            C += arch_ring_y("bw_br%d_%d" % (s, j), xc, 4.00, 0.80, 1.40, 0.24,
                             y0 - 0.20, y0 - 0.02, sl, n=12, keystone=True)
            for t in (-1, 1):
                C.append(bx("bw_bj%d_%d_%d" % (s, j, t),
                            Ts(xc + t * 0.94, y0 - 0.10, 2.60),
                            (0.28, 0.20, 2.60), sl, bev=0.012))
            C.append(bx("bw_bsd%d_%d" % (s, j), Ts(xc, y0 - 0.10, 1.34),
                        (2.16, 0.20, 0.12), sl, bev=0.012))
    # ---- cornice + string course
    C.append(bx("bw_corn", Ts(0.0, y0 - 0.12, Z_CHOR_CEIL - 0.30),
                (2 * hw, 0.30, 0.26), sl, bev=0.025))
    C.append(bx("bw_str", Ts(0.0, y0 - 0.08, 7.90), (2 * hw, 0.20, 0.16), sl,
                bev=0.02))


# ---------------------------------------------------------------------------
# statues
# ---------------------------------------------------------------------------
def statue(name, T, h, MAT, rng, mat=None, mat2=None):
    """A robed standing figure on a small plinth; T is the base centre."""
    m = mat or _m(MAT, "stone_light")
    m2 = mat2 or _m(MAT, "stone_dark")
    out = []
    ph = h * 0.08
    out.append(bx(name + "_p", T @ Ts(0, 0, ph * 0.5), (h * 0.34, h * 0.34, ph),
                  m2, bev=0.015))
    # robe: lathe from the hem to the shoulders
    rows = []
    seg = 12
    for i in range(7):
        t = i / 6.0
        r = (h * 0.115) * (1.0 - 0.55 * t) * (1.0 + 0.10 * math.sin(t * 7.0))
        if i < 4:
            r *= 1.0 + 0.16 * (1.0 - t / 0.66)
        z = ph + (h * 0.62) * t
        row = [T @ Vector((r * math.cos(TAU * k / seg), r * math.sin(TAU * k / seg), z))
               for k in range(seg)]
        rows.append(row)
    out.append(quad_strip(name + "_robe", rows, m, closed=True))
    # shoulders, head, a simple crown or helm
    zs = ph + h * 0.62
    out.append(K.sphere(name + "_sh", T @ Ts(0, 0, zs + h * 0.03),
                        h * 0.115, m, seg=12))
    out.append(K.sphere(name + "_hd", T @ Ts(0, 0, zs + h * 0.15), h * 0.075, m,
                        seg=12))
    out.append(cyl(name + "_cr", T @ Ts(0, 0, zs + h * 0.205), h * 0.075,
                   h * 0.045, _m(MAT, "gold"), seg=12))
    # arms folded across the chest
    for s in (-1, 1):
        out.append(bx(name + "_ar%d" % s, T @ Ts(s * h * 0.10, -h * 0.02, zs - h * 0.01,
                                                 ry=s * math.radians(24.0)),
                      (h * 0.09, h * 0.09, h * 0.30), m, bev=0.01))
    return out

# ---------------------------------------------------------------------------
# cloth: tapestries, heraldry, sconces  (round 3)
# ---------------------------------------------------------------------------
def cloth(nm, T, w, h, mat, cols=8, rows=6, wave=0.055, sag=0.10):
    """Hanging cloth with folds.  Local +Y = out of the wall."""
    vs = []
    for i in range(cols + 1):
        u = -1.0 + 2.0 * i / cols
        for j in range(rows + 1):
            v = j / float(rows)
            y = wave * math.sin(u * 3.9 + 0.6) * (0.55 + 0.45 * v)
            y += wave * 0.60 * math.sin(u * 9.1 + 1.7)
            z = -h * 0.5 + h * v - sag * (1.0 - u * u) * v * v
            vs.append((u * w * 0.5, y, z))
    fs = []
    for i in range(cols):
        for j in range(rows):
            a = i * (rows + 1) + j
            b = a + (rows + 1)
            fs.append((a, a + 1, b + 1, b))
    ob = K.mesh_obj(nm, vs, fs, smooth=True)
    K.assign(ob, mat)
    ob.data.transform(T)
    return [ob]


def tapestry(nm, T, w, h, MAT, rng, cloth_key="tapestry", cols=7, rows=6,
             border=True, rod=True):
    out = cloth(nm, T, w, h, _m(MAT, cloth_key), cols=cols, rows=rows)
    gm = _m(MAT, "cloth_gold")
    wd = _m(MAT, "wood_dark")
    if border:
        for sx, sz, bw, bh in ((0, 1, w, 0.13), (0, -1, w, 0.13),
                               (-1, 0, 0.13, h), (1, 0, 0.13, h)):
            out.append(bx("%s_bd%d%d" % (nm, sx, sz),
                          T @ Ts(sx * (w * 0.5 - bw * 0.5), 0.035,
                                 sz * (h * 0.5 - bh * 0.5)),
                          (bw, 0.035, bh), gm, bev=0.008))
    if rod:
        out.append(cyl("%s_rod" % nm, T @ Ts(0.0, 0.02, h * 0.5 + 0.04,
                                             ry=math.pi * 0.5),
                       0.055, w + 0.34, wd, seg=10))
        for k in (-1, 0, 1):
            out.append(torus("%s_rg%d" % (nm, k),
                             T @ Ts(k * w * 0.30, 0.03, h * 0.5 + 0.04),
                             0.058, 0.016, _m(MAT, "iron"), seg=10, ring=4))
    return out


def heraldry(C, E, MAT, rng):
    """Great heraldic cloth over the throne, two flags flanking it."""
    y0 = Y_BACK
    gm = _m(MAT, "gold")
    wd = _m(MAT, "wood_dark")
    C += tapestry("hw_tap", Ts(0.0, y0 - 0.09, 9.16), 4.60, 3.30, MAT, rng,
                  cloth_key="tapestry_blue", cols=10, rows=7)
    C.append(cyl("hw_disc", Ts(0.0, y0 - 0.16, 9.16, rx=math.pi * 0.5),
                 0.80, 0.045, _m(MAT, "cloth_gold"), seg=24,
                 bev=0.0))
    for k in range(12):
        a = k * math.pi / 6.0
        C.append(bx("hw_ray%d" % k,
                    Ts(math.sin(a) * 0.93, y0 - 0.15, 9.16 + math.cos(a) * 0.93,
                       ry=a),
                    (0.15, 0.05, 0.30), gm, bev=0.01))
    C.append(bx("hw_sw", Ts(0.0, y0 - 0.18, 9.12), (0.14, 0.06, 1.40), gm,
                bev=0.012))
    C.append(bx("hw_gd", Ts(0.0, y0 - 0.18, 8.70), (0.60, 0.07, 0.09), gm,
                bev=0.012))
    C.append(bx("hw_pm", Ts(0.0, y0 - 0.18, 8.30), (0.09, 0.07, 0.30), gm,
                bev=0.012))
    C.append(torus("hw_cr", Ts(0.0, y0 - 0.18, 9.90, rx=math.pi * 0.5),
                   0.23, 0.045, gm, seg=16, ring=5))
    for k, xx in enumerate((-0.19, 0.0, 0.19)):
        C.append(K.cone("hw_cp%d" % k, Ts(xx, y0 - 0.18, 10.20), 0.072, 0.25,
                        gm, seg=8))
    for s in (-1, 1):
        px = s * 3.62
        C.append(cyl("hw_pol%d" % s, Ts(px, y0 - 0.78, 5.50), 0.072, 8.80, wd,
                     seg=10))
        C.append(K.sphere("hw_pf%d" % s, Ts(px, y0 - 0.78, 9.93), 0.15, gm,
                        seg=12, ring=8))
        C += cloth("hw_fb%d" % s, Ts(px - s * 0.02, y0 - 0.86, 8.50,
                                    rz=-s * math.pi * 0.5),
                   1.26, 2.80, _m(MAT, "cloth_blue" if s > 0 else "cloth_red"),
                   cols=6, rows=8, wave=0.075, sag=0.14)
        for k in range(5):
            C.append(bx("hw_ff%d_%d" % (s, k),
                        Ts(px - s * 0.02, y0 - 0.86 + (k - 2) * 0.26, 7.09),
                        (0.05, 0.10, 0.09), gm, bev=0.006))
    for i, yc in enumerate(AIS_WIN):
        key = "tapestry" if (i % 2) else "tapestry_blue"
        E += tapestry("aw_tap%d" % i, Ts(X_IN - 0.06, yc, 4.90,
                                         rz=math.pi * 0.5),
                      3.30, 3.60, MAT, rng, cloth_key=key, cols=7, rows=6)


def sconces(E, MAT, rng):
    """Iron wall sconces flanking every pier on the nave side."""
    iron = _m(MAT, "iron")
    cm = _m(MAT, "candle")
    fm = _m(MAT, "fire")
    for i, py in enumerate(PIERS):
        for z in (4.35, 8.15):
            nm = "sc%d_%d" % (i, int(z * 10))
            E.append(bx(nm + "_pl", Ts(XNAVE - 0.05, py, z), (0.11, 0.34, 0.66),
                        iron, bev=0.012))
            E.append(rod(nm + "_ar", (XNAVE - 0.09, py, z + 0.26),
                         (XNAVE - 0.56, py, z + 0.32), 0.028, iron, seg=6))
            E.append(cyl(nm + "_cp", Ts(XNAVE - 0.56, py, z + 0.38), 0.115, 0.10,
                         iron, seg=10, r2=0.055))
            E.append(cyl(nm + "_cd", Ts(XNAVE - 0.56, py, z + 0.64), 0.052, 0.44,
                         cm, seg=8))
            E.append(K.cone(nm + "_fl", Ts(XNAVE - 0.56, py, z + 0.93), 0.040,
                            0.13, fm, seg=8))

# ---------------------------------------------------------------------------
# detail pass: dais balustrade, aisle benches, arch orders, porch arcade,
#               roof purlins
# ---------------------------------------------------------------------------
def detail(C, E, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    wb = _m(MAT, "wood_beam")
    # ---- 1. balustrade flanking the throne steps
    for s in (-1, 1):
        a0, a1 = (4.14, 4.54) if s > 0 else (-4.54, -4.14)
        E.append(prism("dl%d_p" % s,
                       [(Y_STEP0, 0.02), (Y_DAIS, 1.14), (Y_DAIS, 2.02),
                        (Y_STEP0, 0.90)], st, a0, a1, axis="x", bev=0.015))
        E.append(prism("dl%d_c" % s,
                       [(Y_STEP0 - 0.08, 0.88), (Y_DAIS + 0.04, 2.00),
                        (Y_DAIS + 0.04, 2.14), (Y_STEP0 - 0.08, 1.02)],
                       sl, a0 - 0.05, a1 + 0.05, axis="x", bev=0.012))
        E.append(bx("dl%d_n" % s, Ts(s * 4.34, Y_STEP0 - 0.46, 0.70),
                    (0.46, 0.46, 1.40), st, bev=0.022))
        E.append(bx("dl%d_nc" % s, Ts(s * 4.34, Y_STEP0 - 0.46, 1.44),
                    (0.58, 0.58, 0.12), sl, bev=0.02))
        E.append(K.sphere("dl%d_lh" % s, Ts(s * 4.34, Y_STEP0 - 0.46, 1.63),
                          0.185, st, seg=14, ring=10))
        E.append(bx("dl%d_ls" % s, Ts(s * 4.34, Y_STEP0 - 0.62, 1.58),
                    (0.17, 0.14, 0.13), st, bev=0.02))
        for e in (-1, 1):
            E.append(bx("dl%d_le%d" % (s, e),
                        Ts(s * 4.34 + e * 0.13, Y_STEP0 - 0.46, 1.77),
                        (0.07, 0.05, 0.10), st, bev=0.015))
        ym = (Y_DAIS + 23.90) * 0.5
        E.append(bx("dl%d_pp" % s, Ts(s * 4.82, ym, 1.55),
                    (0.28, 23.90 - Y_DAIS, 0.86), st, bev=0.02))
        E.append(bx("dl%d_pc" % s, Ts(s * 4.82, ym, 2.04),
                    (0.38, 23.90 - Y_DAIS + 0.12, 0.12), sl, bev=0.015))
        for k in range(5):
            E.append(bx("dl%d_pq%d" % (s, k),
                        Ts(s * 4.82, Y_DAIS + 0.55 + k * 1.24, 1.99),
                        (0.42, 0.34, 0.15), sl, bev=0.012))
    for k in range(N_STEP):
        yy = Y_STEP0 + (k + 1) * STEP_RUN
        E.append(bx("dl_ns%d" % k, Ts(0.0, yy - 0.055, 0.09 + k * STEP_H),
                    (2 * STEP_HW - 0.10, 0.11, 0.05), sl, bev=0.008))
    # ---- 2. stone benches under the aisle windows
    for i, yc in enumerate(AIS_WIN):
        E.append(bx("ab%d_s" % i, Ts(X_IN - 0.36, yc, 0.19), (0.66, 3.06, 0.38),
                    st, bev=0.02))
        E.append(bx("ab%d_c" % i, Ts(X_IN - 0.31, yc, 0.44), (0.74, 3.20, 0.11),
                    sl, bev=0.015))
    # ---- 3. second (outer) order on the nave arcade arches
    for i in range(NBAY):
        yc = PIERS[i] + BAY * 0.5
        E += arch_ring_x("ar2_%d" % i, yc, Z_CAP, HS_ARC + 0.52, RISE_ARC + 0.52,
                         0.20, XNAVE - 0.14, XNAVE + 0.04, sl, n=14,
                         keystone=True)
    # ---- 4. blind arcade on the porch side walls
    for j, yc in enumerate((-22.55, -20.05)):
        x0 = X_IN - 0.02
        E.append(prism("pz_bp%d" % j, [(yc + u, z) for (u, z) in
                                       hole_pts(0.86, 1.05, 4.30, 5.60, 12)],
                       sd, x0 - 0.06, x0 - 0.01, axis="x"))
        E += arch_ring_x("pz_br%d" % j, yc, 4.30, 0.86, 1.30, 0.24,
                         x0 - 0.24, x0 - 0.02, sl, n=12, keystone=True)
        for e in (-1, 1):
            E.append(bx("pz_bj%d_%d" % (j, e),
                        Ts(X_IN - 0.13, yc + e * 1.02, 2.62),
                        (0.26, 0.30, 3.20), sl, bev=0.015))
        E.append(bx("pz_bs%d" % j, Ts(X_IN - 0.13, yc, 0.96),
                    (0.26, 2.30, 0.16), sl, bev=0.015))
    # ---- 5. roof purlins + ridge beam
    E.append(bx("rf_rg", Ts(0.0, 0.0, Z_RIDGE - 0.17), (0.30, 51.80, 0.34), wb,
                bev=0.01))
    for xp in (1.6, 3.2, 4.8, 6.4, 8.0):
        z = Z_RIDGE - 0.455 * xp - 0.19
        E.append(bx("rf_pu%d" % int(xp * 10), Ts(xp, 0.0, z), (0.22, 51.80, 0.24),
                    wb, bev=0.01))

