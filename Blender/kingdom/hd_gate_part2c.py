# --------------------------------------------------------------------------
#  curtain walls and their end turrets
# --------------------------------------------------------------------------
def build_curtain(MAT, rng, side):
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron = MAT["stone_pale"], MAT["iron_dark"]
    x0, x1 = 19.80, CURT_X1          # the inner end is buried in the tower drum
    cx = (x0 + x1) * 0.5
    ln = x1 - x0
    h = WALL_H
    body = box("cw_body%d" % side, Ts(side * cx, 0, h * 0.5), (ln, WALL_T, h), st,
               bev=0.02)
    p.append(body)
    p.append(box("cw_pl%d" % side, Ts(side * cx, 0, 0.45), (ln, WALL_T + 0.30, 0.90),
                 sd, bev=0.025))
    # ashlar on both faces
    pan = {}
    for s in (-1, 1):
        T = _frame(side * cx, s * WALL_T * 0.5, 0.90, PI * 0.5 if s > 0 else 1.5 * PI)
        pan[s] = ashlar("cw_as%d_%d" % (side, s), T, ln - 0.10, h - 1.05, sw, rng,
                        bw=1.40, bh=0.62)[0]
        p.append(pan[s])
        p.append(box("cw_sc%d_%d" % (side, s), Ts(side * cx, s * (WALL_T * 0.5 + 0.06),
                                                  6.95), (ln - 0.10, 0.20, 0.24), pale,
                     bev=0.02))
        p.append(box("cw_sc2%d_%d" % (side, s), Ts(side * cx, s * (WALL_T * 0.5 + 0.02),
                                                   6.78), (ln - 0.10, 0.10, 0.14), sd))
    # arrow loops on the road face: real cuts through the panel and the body
    for i in range(3):
        x = cx - 3.4 + i * 3.4
        T = _frame(side * x, WALL_T * 0.5, 8.55, PI * 0.5)
        c = _rect_cutter("cw_lc%d_%d" % (side, i), T, 0.26, 1.35, 0.62)
        _cut([body, pan[1]], c)
        p += arrow_loop("cw_lp%d_%d" % (side, i),
                        _frame(side * x, WALL_T * 0.5, 8.55, PI * 0.5), MAT, depth=0.42)
    # wall walk and parapets
    p.append(box("cw_walk%d" % side, Ts(side * cx, 0, h + 0.07),
                 (ln - 0.04, WALL_T + 0.20, 0.14), pale, bev=0.02))
    p.append(box("cw_par%d" % side, Ts(side * cx, WALL_T * 0.5 + 0.12, h + 0.55),
                 (ln - 0.06, 0.44, 0.82), st, bev=0.02))
    p.append(box("cw_cop%d" % side, Ts(side * cx, WALL_T * 0.5 + 0.12, h + 1.00),
                 (ln - 0.02, 0.56, 0.12), pale, bev=0.015))
    p += crenel_line("cw_mer%d" % side, Ts(side * cx, WALL_T * 0.5 + 0.12, h + 1.06),
                     ln - 0.20, st, merlon=0.92, gap=0.52, h=1.05, depth=0.50)
    p.append(box("cw_par2%d" % side, Ts(side * cx, -(WALL_T * 0.5 + 0.09), h + 0.50),
                 (ln - 0.06, 0.40, 0.72), st, bev=0.02))
    p.append(box("cw_cop2%d" % side, Ts(side * cx, -(WALL_T * 0.5 + 0.09), h + 0.90),
                 (ln - 0.02, 0.52, 0.12), pale, bev=0.015))

    # ---- end turret ------------------------------------------------------
    tx = side * (CURT_X1 - 0.35)
    p.append(H.lathe("cw_tpl%d" % side,
                     [(0.0, 0.0), (2.95, 0.0), (2.95, 0.55), (2.72, 1.05),
                      (2.58, 1.10)], st, seg=44, T=Ts(tx, 0, 0),
                     close_bottom=True, close_top=False))
    shaft = cyl("cw_tsh%d" % side, Ts(tx, 0, 7.35), 2.58, 12.60, st, seg=44)
    p.append(shaft)
    ash = ring_ashlar("cw_tas%d" % side, Ts(tx, 0, 0), 2.58, 1.10, 12.60, sw, pale,
                      rng, n=16, course=0.62, thick=0.05)
    p.append(ash)
    for i in range(2):
        ang = math.radians(20.0 + 70.0 * i)
        c = _rect_cutter("cw_tlc%d_%d" % (side, i), face_T(tx, 0, 9.30, ang, 2.58),
                         0.22, 1.10, 0.70)
        _cut([shaft, ash], c)
        p += arrow_loop("cw_tlp%d_%d" % (side, i), face_T(tx, 0, 9.30, ang, 2.60),
                        MAT, h=1.10, w=0.20, depth=0.44)
    p.append(corbel_ring("cw_tcor%d" % side, Ts(tx, 0, 0), 2.58, 12.60, 18, sw,
                         out=0.55, h=0.75, w=0.34, taper=0.30))
    p.append(ring_wall("cw_tgal%d" % side, Ts(tx, 0, 0), 2.40, 3.12, 13.30, 14.02, sw,
                       seg=44))
    p.append(ring_wall("cw_tpar%d" % side, Ts(tx, 0, 0), 2.86, 3.16, 14.02, 14.86, st,
                       seg=44))
    p.append(rcrenel("cw_tmer%d" % side, Ts(tx, 0, 0), 3.01, 14.86, 12, merlon=0.72,
                     gap=0.42, h=0.86, depth=0.46, mat=st))
    p.append(H.lathe("cw_troof%d" % side, [(2.98, 14.30), (0.02, 17.70)], MAT["slate"],
                     seg=44, T=Ts(tx, 0, 0), close_bottom=False, close_top=True))
    p.append(sphere("cw_tball%d" % side, Ts(tx, 0, 17.86), 0.16, MAT["gold"], seg=10,
                    ring=6))
    p.append(cyl("cw_tfin%d" % side, Ts(tx, 0, 18.20), 0.055, 0.90, iron, seg=8))
    return p


def build_stair(MAT, rng, side):
    """A solid straight flight down the city face of the curtain wall."""
    p = []
    sw, sd, pale = MAT["stone_warm"], MAT["stone_dark"], MAT["stone_pale"]
    x = side * 27.60
    w = 1.94
    y_top = -WALL_T * 0.5 - 0.12
    n = 42
    rise = 12.60 / n
    run = 14.0 / n
    for i in range(n):
        yy = y_top - run * (i + 0.5)
        zz = rise * (i + 1)
        p.append(box("st_s%d_%d" % (side, i), Ts(x, yy, zz * 0.5),
                     (w, run + 0.02, zz), sw, bev=0.006))
    # the face of the flight, stepped back into a battered mass
    p.append(box("st_bk%d" % side, Ts(x, y_top - 14.10, 1.40),
                 (w - 0.06, 0.30, 2.80), sd, bev=0.01))
    # raking side walls (built as short levels so they never float)
    for s in (-1, 1):
        for i in range(0, n, 2):
            yy = y_top - run * (i + 1)
            zz = rise * (i + 2)
            p.append(box("st_pw%d_%d_%d" % (side, s, i),
                         Ts(x + s * (w * 0.5 - 0.10), yy, zz * 0.5 + 0.55),
                         (0.30, run * 2.1, zz + 1.10), sw, bev=0.01))
    # newel and a lantern at the bottom
    p.append(cyl("st_new%d" % side, Ts(x, y_top + 0.30, 13.35), 0.36, 1.70, pale, seg=14))
    p.append(sphere("st_nb%d" % side, Ts(x, y_top + 0.30, 14.32), 0.32, pale, seg=12,
                    ring=7))
    p.append(H.lantern_post("st_lp%d" % side, Ts(x + side * 1.55,
                                                y_top - 14.6, 0.06), 2.70,
                            MAT["iron_dark"], MAT["glow"]))
    return p


# --------------------------------------------------------------------------
#  the barbican: a closed ward in front of the gate
# --------------------------------------------------------------------------
BARB_GATE_W = 5.00
BARB_GATE_R = 2.50
BARB_GATE_SPRING = 3.30


def build_barbican(MAT, rng):
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron = MAT["stone_pale"], MAT["iron_dark"]

    # ---- side walls ------------------------------------------------------
    for s in (-1, 1):
        x = s * BARB_X
        ln = BARB_FRONT - 6.45
        cy = (6.45 + BARB_FRONT) * 0.5
        p.append(box("bb_sw%d" % s, Ts(x, cy, BARB_Z * 0.5), (BARB_T, ln, BARB_Z), st,
                     bev=0.02))
        p.append(box("bb_sp%d" % s, Ts(x, cy, 0.45), (BARB_T + 0.28, ln, 0.90), sd,
                     bev=0.025))
        for f in (-1, 1):
            p.append(ashlar("bb_sa%d_%d" % (s, f),
                            Ts(x + f * BARB_T * 0.5, cy, 0.88) @ RotZ(-f * PI * 0.5),
                            ln - 0.08, BARB_Z - 1.02, sw, rng, bw=1.30, bh=0.58))
            p.append(box("bb_ssc%d_%d" % (s, f),
                         Ts(x + f * (BARB_T * 0.5 + 0.05), cy, 6.60),
                         (0.18, ln - 0.10, 0.22), pale, bev=0.02))
        p.append(box("bb_swk%d" % s, Ts(x, cy, BARB_Z + 0.07),
                     (BARB_T + 0.16, ln, 0.14), pale, bev=0.02))
        p.append(box("bb_spar%d" % s, Ts(x, cy, BARB_Z + 0.55),
                     (BARB_T + 0.10, ln - 0.06, 0.82), st, bev=0.02))
        p.append(box("bb_scop%d" % s, Ts(x, cy, BARB_Z + 0.98),
                     (BARB_T + 0.22, ln - 0.02, 0.12), pale, bev=0.015))
        p += crenel_line("bb_smer%d" % s, Ts(x, cy, BARB_Z + 1.04), ln - 0.20, st,
                         merlon=0.88, gap=0.50, h=1.02, depth=0.52, axis="y")
        for i in range(3):
            yy = 9.2 + i * 3.4
            p += arrow_loop("bb_sl%d_%d" % (s, i),
                            _frame(x + s * BARB_T * 0.5, yy, 8.10,
                                   PI * 0.5 if s > 0 else 1.5 * PI), MAT, depth=0.42)

    # ---- front wall with the barbican gate -------------------------------
    fw = H.prism("bb_fw", Ts(0, (BARB_FRONT + 21.30) * 0.5, 0),
                 arch_notch_poly(9.15, BARB_Z, BARB_GATE_R + 0.02,
                                 BARB_GATE_SPRING, seg=34), BARB_T, st, axis="y")
    p.append(fw)
    for f, yy, ang in ((1, BARB_FRONT, PI * 0.5), (-1, 21.30, 1.5 * PI)):
        T = _frame(0, yy, 0.0, ang)
        ob = ashlar("bb_fa%d" % f, T, 18.30, BARB_Z, sw, rng, bw=1.38, bh=0.60)[0]
        _cut([ob], _rect_cutter("bb_fmc%d" % f, T, 5.36, 6.10, 1.10))
        p.append(ob)
        p.append(box("bb_fpl%d" % f, Ts(0, yy + f * 0.13, 0.45),
                     (18.30, 0.26, 0.90), sd, bev=0.02))
        p.append(box("bb_fsc%d" % f, Ts(0, yy + f * 0.09, 6.72),
                     (18.30, 0.20, 0.24), pale, bev=0.02))
    p.append(box("bb_fwk", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 0.07),
                 (18.30, BARB_T + 0.16, 0.14), pale, bev=0.02))
    p.append(box("bb_fpar", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 0.55),
                 (18.30, BARB_T + 0.10, 0.82), st, bev=0.02))
    p.append(box("bb_fcop", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 0.98),
                 (18.30, BARB_T + 0.22, 0.12), pale, bev=0.015))
    p += crenel_line("bb_fmer", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 1.04),
                     18.10, st, merlon=0.90, gap=0.52, h=1.04, depth=0.54)
    p += arch_order("bb_ar", Ts(0, BARB_FRONT + 0.01, BARB_GATE_SPRING),
                    BARB_GATE_R, MAT, n=19, w=0.46, depth=0.26, hood=True)
    p += arch_order("bb_ar2", Ts(0, 21.29, BARB_GATE_SPRING), BARB_GATE_R, MAT,
                    n=19, w=0.40, depth=0.20, hood=False, keystone=False)
    p += portcullis("bb_pc", Ts(0, (BARB_FRONT + 21.30) * 0.5, 0), 4.70, 2.15, 5.55,
                    MAT, n=9)
    p.append(box("bb_gf", Ts(0, (BARB_FRONT + 21.30) * 0.5, DECK * 0.5),
                 (BARB_GATE_W + 0.10, BARB_T + 0.02, DECK), MAT["cobble"], bev=0.01))
    p += coat_of_arms("bb_coa", Ts(0, BARB_FRONT + 0.02, 7.55), 1.10, MAT)
    for s in (-1, 1):
        p += wall_banner("bb_ban%d" % s, Ts(s * 5.85, BARB_FRONT + 0.10, 8.85), 1.35,
                         3.60, MAT["banner_red"] if s < 0 else MAT["banner_blue"],
                         MAT["gold"], iron)
        p += torch("bb_tch%d" % s, Ts(s * 2.62, 22.05, 3.30), MAT, -s)

    # ---- the two corner towers -------------------------------------------
    for s in (-1, 1):
        tx, ty = s * BARB_X, 22.60
        p.append(H.lathe("bt_pl%d" % s,
                         [(0.0, -2.60), (BTOW_R + 0.42, -2.60), (BTOW_R + 0.42, 0.60),
                          (BTOW_R + 0.10, 1.10), (BTOW_R, 1.16)], st, seg=44,
                         T=Ts(tx, ty, 0), close_bottom=True, close_top=False))
        shaft = cyl("bt_sh%d" % s, Ts(tx, ty, 6.88), BTOW_R, 11.44, st, seg=44)
        p.append(shaft)
        ash = ring_ashlar("bt_as%d" % s, Ts(tx, ty, 0), BTOW_R, 1.16, BTOW_TOP, sw,
                          pale, rng, n=18, course=0.60, thick=0.05)
        p.append(ash)
        for i in range(3):
            ang = math.radians(30.0 + 60.0 * i)
            c = _rect_cutter("bt_lc%d_%d" % (s, i),
                             face_T(tx, ty, 8.30, ang, BTOW_R), 0.24, 1.20, 0.72)
            _cut([shaft, ash], c)
            p += arrow_loop("bt_lp%d_%d" % (s, i), face_T(tx, ty, 8.30, ang, BTOW_R),
                            MAT, h=1.20, w=0.22, depth=0.44)
        p.append(corbel_ring("bt_co%d" % s, Ts(tx, ty, 0), BTOW_R, BTOW_TOP, 20, sw,
                             out=0.62, h=0.80, w=0.36, taper=0.30))
        p.append(ring_wall("bt_ga%d" % s, Ts(tx, ty, 0), BTOW_R - 0.15, BTOW_R + 0.58,
                           BTOW_TOP + 0.55, BTOW_TOP + 1.30, sw, seg=44))
        p.append(ring_wall("bt_pa%d" % s, Ts(tx, ty, 0), BTOW_R + 0.30, BTOW_R + 0.60,
                           BTOW_TOP + 1.30, BTOW_TOP + 2.16, st, seg=44))
        p.append(rcrenel("bt_me%d" % s, Ts(tx, ty, 0), BTOW_R + 0.45, BTOW_TOP + 2.16,
                         13, merlon=0.74, gap=0.44, h=0.92, depth=0.48, mat=st))
        p.append(ring_wall("bt_wk%d" % s, Ts(tx, ty, 0), 0.0, BTOW_R - 0.10,
                           BTOW_TOP + 0.55, BTOW_TOP + 0.62, MAT["slate"], seg=44))
        p.append(flag("bt_fl%d" % s, Ts(tx, ty, BTOW_TOP + 1.35), 0.08, 1.60, 1.00,
                      MAT["banner_red"], MAT["gold"], iron))

    # ---- the ward --------------------------------------------------------
    p += flagstones("bb_floor", Ts(0, 0, DECK), 2 * (BARB_X - BARB_T * 0.5),
                    9.15, 21.35, MAT["cobble"], rng, cw=1.25, cl=1.00, h=0.16)
    for s in (-1, 1):
        p.append(box("bb_al%d" % s, Ts(s * 6.98, 7.95, DECK * 0.5),
                     (0.98, 2.70, DECK), MAT["cobble"], bev=0.01))
    # a well
    p.append(cyl("bb_well", Ts(-5.30, 13.30, 0.55), 0.95, 1.10, sd, seg=18))
    p.append(ring_wall("bb_wellr", Ts(-5.30, 13.30, 0), 0.60, 0.95, 1.10, 1.22, pale,
                       seg=18))
    for i in range(2):
        p.append(cyl("bb_wlp%d" % i, Ts(-5.30 + (-1) ** i * 0.85, 13.30, 1.95), 0.06,
                     1.70, MAT["wood_dark"], seg=8))
    p.append(box("bb_wlb", Ts(-5.30, 13.30, 2.72), (1.90, 0.14, 0.14),
                 MAT["wood_dark"]))
    p.append(box("bb_wlh", Ts(-5.30, 13.30, 2.40), (0.10, 0.10, 0.70), iron))
    for i, (xx, yy) in enumerate(((6.10, 11.20), (6.10, 12.30), (5.20, 18.40))):
        p.append(H.barrel("bb_br%d" % i, Ts(xx, yy, DECK), 0.32, 0.86, MAT["wood"], iron))
    for i, (xx, yy) in enumerate(((-6.20, 11.00), (-5.10, 19.20))):
        p.append(H.crate("bb_cr%d" % i, Ts(xx, yy, DECK), 0.70, MAT["wood"]))
    p.append(H.cart("bb_cart", Ts(3.60, 16.60, DECK, rz=PI * 0.12), MAT["wood"],
                    MAT["iron"], L=2.4, W=1.2))
    for i, (xx, yy) in enumerate(((-7.00, 15.00), (7.00, 15.00))):
        p.append(H.lantern_post("bb_lp%d" % i, Ts(xx, yy, DECK), 2.90,
                                MAT["iron_dark"], MAT["glow"]))
    return p


# --------------------------------------------------------------------------
#  the drawbridge
# --------------------------------------------------------------------------
def build_drawbridge(MAT, rng):
    """A timber bridge lying down: level with the ward, the gate and the road."""
    p = []
    wood, wd, iron = MAT["wood"], MAT["wood_dark"], MAT["iron_dark"]
    w = BRIDGE_X * 2
    y0, y1 = 22.80, 31.15
    for s in (-1, 1):
        p.append(box("db_bm%d" % s, Ts(s * (BRIDGE_X - 0.22), (y0 + y1) * 0.5, DECK - 0.30),
                     (0.34, y1 - y0, 0.42), wd, bev=0.015))
    n = 9
    for i in range(n):
        yy = y0 + 0.5 + i * (y1 - y0 - 1.0) / (n - 1)
        p.append(box("db_j%d" % i, Ts(0, yy, DECK - 0.16), (w - 0.10, 0.24, 0.16), wd))
    n = 26
    for i in range(n):
        yy = y0 + 0.16 + i * (y1 - y0 - 0.32) / (n - 1)
        p.append(box("db_pk%d" % i, Ts(0, yy, DECK - 0.0475),
                     (w - 0.04, (y1 - y0 - 0.32) / (n - 1) - 0.035, 0.095), wood,
                     bev=0.006))
    for k in range(4):
        yy = y0 + 1.2 + k * 2.2
        p.append(box("db_st%d" % k, Ts(0, yy, DECK + 0.008), (w - 0.30, 0.14, 0.028),
                     iron))
        for j in range(6):
            p.append(cyl("db_bt%d_%d" % (k, j),
                         Ts(-w * 0.42 + j * w * 0.168, yy, DECK + 0.026), 0.036, 0.03,
                         iron, seg=6))
    for s in (-1, 1):
        p.append(box("db_rail%d" % s, Ts(s * (BRIDGE_X - 0.12), (y0 + y1) * 0.5,
                                         DECK + 0.42), (0.14, y1 - y0, 0.13), wd))
        for i in range(5):
            yy = y0 + 0.7 + i * 2.0
            p.append(box("db_post%d_%d" % (s, i),
                         Ts(s * (BRIDGE_X - 0.12), yy, DECK + 0.21),
                         (0.14, 0.14, 0.42), wd))
    # chain anchors at the corners, chains up to the barbican towers
    for s in (-1, 1):
        p.append(box("db_anc%d" % s, Ts(s * (BRIDGE_X - 0.45), y0 + 0.55, DECK + 0.06),
                     (0.42, 0.42, 0.12), iron, bev=0.01))
        p.append(torus("db_ar%d" % s, Ts(s * (BRIDGE_X - 0.45), y0 + 0.55, DECK + 0.16)
                       @ RotX(PI * 0.5), 0.13, 0.035, iron, seg=10, ring=5))
        p += chain("db_ch%d" % s,
                   Vector((s * (BRIDGE_X - 0.45), y0 + 0.55, DECK + 0.20)),
                   Vector((s * 5.15, 22.75, 8.10)), 0.55, iron, links=24, R=0.095,
                   r=0.032)
        p.append(torus("db_tr%d" % s, Ts(s * 5.10, 22.72, 8.10) @ RotZ(PI * 0.5)
                       @ RotX(PI * 0.5), 0.16, 0.04, iron, seg=10, ring=5))
    # the far abutment
    p.append(box("db_ab", Ts(0, 31.45, -0.30), (w + 1.30, 0.90, 0.86),
                 MAT["stone_dark"], bev=0.03))
    p.append(box("db_ab2", Ts(0, 31.45, 0.16), (w + 1.10, 0.80, 0.10),
                 MAT["stone_pale"], bev=0.02))
    return p
