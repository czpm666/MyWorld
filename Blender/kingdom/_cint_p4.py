# ---------------------------------------------------------------------------
# p4: dais, throne, fittings, assembly, preview
# ---------------------------------------------------------------------------
STEP_RUN = (Y_DAIS - Y_STEP0) / N_STEP      # 0.32
STEP_H = Z_DAIS / N_STEP                    # 0.16


def rod(name, p0, p1, r, mat, seg=8):
    """A cylinder from p0 to p1 (both world points)."""
    p0 = Vector(p0)
    p1 = Vector(p1)
    d = p1 - p0
    L = max(d.length, 1e-4)
    q = d.to_track_quat('Z', 'Y')
    T = Matrix.Translation((p0 + p1) * 0.5) @ q.to_matrix().to_4x4()
    return cyl(name, T, r, L, mat, seg=seg)


# ---------------------------------------------------------------------------
# the dais: seven steps, a 10 x 6 platform, stepped cheek walls
# ---------------------------------------------------------------------------
def dais(C, MAT, rng):
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    dn = _m(MAT, "stone_dark")
    for i in range(N_STEP):
        h = (i + 1) * STEP_H
        ya = Y_STEP0 + i * STEP_RUN
        C.append(bx("dst%d" % i, Ts(0.0, (ya + Y_DAIS) * 0.5, h * 0.5),
                    (2.0 * STEP_HW, Y_DAIS - ya, h), sl, bev=0.012))
        # darker nosing on the tread edge
        C.append(bx("dsn%d" % i, Ts(0.0, ya + 0.045, h - 0.014),
                    (2.0 * STEP_HW, 0.09, 0.028), dn, bev=0.0))
        # stepped cheek walls, 0.44 above the tread
        for s in (-1, 1):
            C.append(bx("dch%d_%d" % (i, s),
                        Ts(s * (STEP_HW + 0.28), (ya + Y_DAIS) * 0.5,
                           (h + 0.46) * 0.5),
                        (0.56, Y_DAIS - ya, h + 0.46), sd, bev=0.015))
    # newel blocks at the foot of the cheeks
    for s in (-1, 1):
        C.append(bx("dnw%d" % s, Ts(s * (STEP_HW + 0.28), Y_STEP0 - 0.10, 0.34),
                    (0.78, 0.78, 0.68), sl, bev=0.02))
        C.append(frustum("dnc%d" % s, Ts(s * (STEP_HW + 0.28), Y_STEP0 - 0.10, 0.72),
                         (0.62, 0.62), (0.44, 0.44), 0.14, sd, bev=0.012))
        C.append(K.sphere("dno%d" % s, Ts(s * (STEP_HW + 0.28), Y_STEP0 - 0.10, 0.94),
                          0.19, _m(MAT, "gold"), seg=14))
    # platform
    C.append(bx("dpl", Ts(0.0, (Y_DAIS + Y_BACK) * 0.5, Z_DAIS * 0.5),
                (2.0 * DAIS_HW, Y_BACK - Y_DAIS, Z_DAIS), sl, bev=0.02))
    # moulded edge all round the platform
    C.append(bx("dpe", Ts(0.0, Y_DAIS - 0.07, Z_DAIS - 0.11),
                (2.0 * DAIS_HW + 0.18, 0.18, 0.16), sd, bev=0.015))
    C.append(bx("dpe2", Ts(0.0, Y_DAIS - 0.02, Z_DAIS - 0.02),
                (2.0 * DAIS_HW + 0.10, 0.10, 0.06), dn, bev=0.008))
    for s in (-1, 1):
        C.append(bx("dpes%d" % s, Ts(s * (DAIS_HW + 0.07), (Y_DAIS + Y_BACK) * 0.5,
                                     Z_DAIS - 0.11),
                    (0.18, Y_BACK - Y_DAIS, 0.16), sd, bev=0.015))
    # guard platforms at the head of the stairs
    for s in (-1, 1):
        C.append(bx("dgp%d" % s, Ts(s * 3.86, 19.42, Z_DAIS + 0.10),
                    (1.34, 1.34, 0.20), sd, bev=0.02))


# ---------------------------------------------------------------------------
# the throne
# ---------------------------------------------------------------------------
def throne(C, MAT, rng):
    wd = _m(MAT, "wood_dark")
    wb = _m(MAT, "wood")
    au = _m(MAT, "gold")
    red = _m(MAT, "cloth_red")
    sd = _m(MAT, "stone_shadow")
    sl = _m(MAT, "stone_light")
    yc = 21.55
    SEAT = Z_DAIS + 0.62
    # stepped plinth
    C.append(bx("th_p0", Ts(0.0, yc, Z_DAIS + 0.075), (3.00, 2.40, 0.15), sl,
                bev=0.02))
    C.append(bx("th_p1", Ts(0.0, yc, Z_DAIS + 0.21), (2.66, 2.08, 0.12), sd,
                bev=0.015))
    C.append(bx("th_p2", Ts(0.0, yc, Z_DAIS + 0.29), (2.44, 1.90, 0.06), wd,
                bev=0.01))
    # seat
    C.append(bx("th_seat", Ts(0.0, yc + 0.10, SEAT - 0.16), (1.94, 1.08, 0.30),
                wd, bev=0.02))
    C.append(bx("th_cush", Ts(0.0, yc + 0.02, SEAT + 0.01), (1.62, 0.92, 0.10),
                red, bev=0.015))
    # tall back, pointed head
    back = [(-1.04, SEAT - 0.28), (1.04, SEAT - 0.28), (1.04, 3.90),
            (0.00, 4.66), (-1.04, 3.90)]
    C.append(prism("th_back", back, wd, yc + 0.52, yc + 0.88, axis="y", bev=0.02))
    # velvet panel let into the back
    vel = [(-0.86, SEAT - 0.10), (0.86, SEAT - 0.10), (0.86, 3.80),
           (0.00, 4.40), (-0.86, 3.80)]
    C.append(prism("th_vel", vel, red, yc + 0.47, yc + 0.53, axis="y"))
    # gold edging around the velvet
    for zz, ww in ((SEAT - 0.06, 1.76), (3.80, 1.76), (4.40, 0.10)):
        C.append(bx("th_gt%.2f" % zz, Ts(0.0, yc + 0.47, zz), (ww, 0.03, 0.05),
                    au, bev=0.0))
    for s in (-1, 1):
        C.append(bx("th_gs%d" % s, Ts(s * 0.885, yc + 0.47, 1.85),
                    (0.05, 0.03, 3.90), au, bev=0.0))
    # crocketed crown on the head of the back
    C.append(torus("th_crown", Ts(0.0, yc + 0.70, 4.42), 0.26, 0.045, au,
                   seg=18, ring=5))
    for s in (-1, 0, 1):
        C.append(K.cone("th_spk%d" % (s + 1),
                        Ts(s * 0.19, yc + 0.70, 4.62 + (0.10 if s == 0 else 0.0)),
                        0.055, 0.30 if s == 0 else 0.20, au, seg=8))
    # arm rests with lion heads
    for s in (-1, 1):
        C.append(bx("th_ap%d" % s, Ts(s * 0.98, yc - 0.16, SEAT + 0.36),
                    (0.26, 0.28, 0.72), wd, bev=0.02))
        C.append(bx("th_ar%d" % s, Ts(s * 0.98, yc + 0.14, SEAT + 0.66),
                    (0.26, 0.94, 0.22), wd, bev=0.02))
        C.append(bx("th_ac%d" % s, Ts(s * 0.98, yc - 0.16, SEAT + 0.76),
                    (0.34, 0.34, 0.10), au, bev=0.01))
        # lion head
        lh = Ts(s * 0.98, yc - 0.30, SEAT + 0.90)
        C.append(K.sphere("th_lh%d" % s, lh, 0.185, au, seg=14))
        C.append(bx("th_lm%d" % s, lh @ Ts(0.0, -0.15, -0.02), (0.15, 0.12, 0.11),
                    au, bev=0.01))
        C.append(K.sphere("th_le%d_0" % s, lh @ Ts(0.09, 0.02, 0.14), 0.045, au,
                          seg=8))
        C.append(K.sphere("th_le%d_1" % s, lh @ Ts(-0.09, 0.02, 0.14), 0.045, au,
                          seg=8))
        C.append(torus("th_lmane%d" % s, lh @ Ts(0.0, 0.10, 0.0, rx=math.pi * 0.5),
                       0.20, 0.05, wd, seg=14, ring=5))
    # footstool
    C.append(bx("th_fs0", Ts(0.0, yc - 0.98, Z_DAIS + 0.13), (1.28, 0.62, 0.26),
                wd, bev=0.02))
    C.append(bx("th_fs1", Ts(0.0, yc - 0.98, Z_DAIS + 0.30), (1.20, 0.56, 0.10),
                red, bev=0.012))


def candelabra(name, T, h, MAT, arms=3):
    """A standing candelabrum; T at the floor, h = total height."""
    au = _m(MAT, "brass")
    cnd = _m(MAT, "candle")
    fl = _m(MAT, "fire")
    out = []
    out.append(frustum(name + "_b", T @ Ts(0, 0, 0.04), (0.34, 0.34), (0.22, 0.22),
                       0.08, au, bev=0.01))
    out.append(cyl(name + "_s", T @ Ts(0, 0, h * 0.5), 0.045, h, au, seg=10,
                   r2=0.032))
    out.append(torus(name + "_k", T @ Ts(0, 0, h * 0.62), 0.075, 0.022, au,
                     seg=12, ring=4))
    span = 0.30 if arms > 1 else 0.0
    for j in range(arms):
        fx = 0.0 if arms == 1 else (-span + 2.0 * span * j / (arms - 1))
        out.append(cyl(name + "_c%d" % j, T @ Ts(fx, 0, h + 0.05), 0.055, 0.06, au,
                       seg=8))
        out.append(cyl(name + "_w%d" % j, T @ Ts(fx, 0, h + 0.30), 0.032, 0.42, cnd,
                       seg=8))
        out.append(K.cone(name + "_f%d" % j, T @ Ts(fx, 0, h + 0.57), 0.030, 0.13,
                          fl, seg=6))
    return out


# ---------------------------------------------------------------------------
# floor coverings
# ---------------------------------------------------------------------------
def carpets(C, MAT, rng):
    red = _m(MAT, "carpet_red")
    blue = _m(MAT, "carpet_blue")
    gold = _m(MAT, "cloth_gold")
    y0, y1 = -23.60, Y_STEP0 - 0.10
    C.append(bx("cp_run", Ts(0.0, (y0 + y1) * 0.5, 0.012), (4.40, y1 - y0, 0.024),
                red))
    for s in (-1, 1):
        C.append(bx("cp_brd%d" % s, Ts(s * 2.12, (y0 + y1) * 0.5, 0.013),
                    (0.14, y1 - y0, 0.026), gold))
    for yy in (y0 + 0.16, y1 - 0.16):
        C.append(bx("cp_end%.2f" % yy, Ts(0.0, yy, 0.013), (4.40, 0.14, 0.026),
                    gold))
    # a woven medallion band down the middle
    for j in range(9):
        yy = y0 + 1.4 + j * 3.9
        if yy > y1 - 1.0:
            break
        C.append(bx("cp_med%d" % j, Ts(0.0, yy, 0.014), (1.40, 1.90, 0.028), blue))
        C.append(bx("cp_medb%d" % j, Ts(0.0, yy, 0.015), (1.10, 1.60, 0.030),
                    gold))
        C.append(bx("cp_medc%d" % j, Ts(0.0, yy, 0.016), (0.94, 1.44, 0.032), red))
    # dais carpet
    C.append(bx("cp_dais", Ts(0.0, 20.60, Z_DAIS + 0.012), (7.60, 4.40, 0.024),
                blue))
    for s in (-1, 1):
        C.append(bx("cp_dbd%d" % s, Ts(s * 3.66, 20.60, Z_DAIS + 0.013),
                    (0.14, 4.40, 0.026), gold))
    for yy in (18.46, 22.74):
        C.append(bx("cp_ded%.2f" % yy, Ts(0.0, yy, Z_DAIS + 0.013), (7.60, 0.14, 0.026),
                    gold))
    C.append(bx("cp_step", Ts(0.0, 17.20, STEP_H * 7.05 / 7.0), (3.30, 1.60, 0.015),
                red))


# ---------------------------------------------------------------------------
# hanging lamps: chains from the tie beams to an iron corona of candles
# ---------------------------------------------------------------------------
def chandelier(C, MAT, rng, yc, R=1.42, z_ring=10.90):
    iron = _m(MAT, "iron")
    au = _m(MAT, "brass")
    cnd = _m(MAT, "candle")
    fl = _m(MAT, "fire")
    tag = int(round((yc + 40.0) * 10))
    # three chains gathered at a hook on the tie beam
    for k in range(3):
        a = TAU * k / 3.0 + 0.35
        p0 = Vector((R * math.cos(a), yc + R * math.sin(a), z_ring + 0.06))
        p1 = Vector((0.0, yc, Z_PLATE - 0.02))
        C.append(rod("ch_c%d_%d" % (tag, k), p0, p1, 0.024, iron, seg=6))
    # hook + hub
    C.append(bx("ch_hk%d" % tag, Ts(0.0, yc, Z_PLATE - 0.06), (0.16, 0.10, 0.14),
                iron))
    C.append(cyl("ch_hub%d" % tag, Ts(0.0, yc, z_ring - 0.02), 0.09, 0.26, iron,
                 seg=12))
    for k in range(4):
        a2 = TAU * k / 4.0 + 0.42
        C.append(rod("ch_br%d_%d" % (tag, k),
                     (R * math.cos(a2), yc + R * math.sin(a2), z_ring),
                     (0.0, yc, z_ring - 0.20), 0.018, iron, seg=5))
    C.append(K.sphere("ch_kn%d" % tag, Ts(0.0, yc, z_ring - 0.16), 0.13, au,
                      seg=12))
    C.append(rod("ch_tip%d" % tag, (0.0, yc, z_ring - 0.26), (0.0, yc, z_ring - 0.72),
                 0.022, iron, seg=6))
    # iron corona
    C.append(torus("ch_rg%d" % tag, Ts(0.0, yc, z_ring), R, 0.055, iron, seg=32,
                   ring=6))
    C.append(torus("ch_rg2%d" % tag, Ts(0.0, yc, z_ring + 0.16), R * 0.52, 0.032,
                   iron, seg=24, ring=4))
    for k in range(8):
        a = TAU * k / 8.0 + 0.2
        C.append(rod("ch_sp%d_%d" % (tag, k),
                     (R * math.cos(a), yc + R * math.sin(a), z_ring),
                     (R * 0.52 * math.cos(a), yc + R * 0.52 * math.sin(a),
                      z_ring + 0.16), 0.018, iron, seg=5))
    # candles round the ring
    n = 12
    for k in range(n):
        a = TAU * k / n
        px = (R - 0.03) * math.cos(a)
        py = yc + (R - 0.03) * math.sin(a)
        C.append(cyl("ch_cp%d_%d" % (tag, k), Ts(px, py, z_ring + 0.10), 0.085,
                     0.11, au, seg=8))
        C.append(cyl("ch_cd%d_%d" % (tag, k), Ts(px, py, z_ring + 0.43), 0.037,
                     0.56, cnd, seg=8))
        C.append(K.cone("ch_fl%d_%d" % (tag, k), Ts(px, py, z_ring + 0.76), 0.032,
                        0.15, fl, seg=6))


# ---------------------------------------------------------------------------
# braziers
# ---------------------------------------------------------------------------
def brazier(C, MAT, rng, x, y, nm):
    iron = _m(MAT, "iron")
    coal = _m(MAT, "coal")
    fl = _m(MAT, "fire")
    C.append(frustum(nm + "_bowl", Ts(x, y, 1.02), (0.40, 0.40), (0.76, 0.76),
                     0.32, iron, bev=0.012))
    C.append(torus(nm + "_rim", Ts(x, y, 1.33), 0.74, 0.038, iron, seg=20, ring=4))
    for k in range(3):
        a = TAU * k / 3.0 + 0.5
        C.append(rod(nm + "_leg%d" % k,
                     (x + 0.18 * math.cos(a), y + 0.18 * math.sin(a), 1.04),
                     (x + 0.84 * math.cos(a), y + 0.84 * math.sin(a), 0.035),
                     0.040, iron, seg=6))
    C.append(cyl(nm + "_coals", Ts(x, y, 1.36), 0.66, 0.10, coal, seg=14))
    for k in range(5):
        a = TAU * k / 5.0 + 0.3
        rr = 0.34 if k % 2 else 0.16
        C.append(K.cone(nm + "_fl%d" % k,
                        Ts(x + rr * math.cos(a), y + rr * math.sin(a),
                           1.30 + 0.10 * (k % 2)), 0.085, 0.34, fl, seg=6))


# ---------------------------------------------------------------------------
# furniture
# ---------------------------------------------------------------------------
def long_table(C, MAT, rng, x, y, L, nm, cloth=True):
    wd = _m(MAT, "wood")
    wdd = _m(MAT, "wood_dark")
    wht = _m(MAT, "cloth_white")
    gold = _m(MAT, "cloth_gold")
    w = 1.14
    C.append(bx(nm + "_top", Ts(x, y, 0.775), (w, L, 0.09), wd, bev=0.012))
    C.append(bx(nm + "_apr", Ts(x, y, 0.700), (w - 0.16, L - 0.18, 0.13), wdd,
                bev=0.01))
    nl = max(2, int(L / 1.9) + 1)
    for j in range(nl):
        yy = y - L * 0.5 + 0.32 + (L - 0.64) * j / (nl - 1)
        for s in (-1, 1):
            C.append(cyl(nm + "_lg%d_%d" % (j, s), Ts(x + s * (w * 0.5 - 0.14), yy,
                                                     0.36), 0.062, 0.72, wdd,
                         seg=8, r2=0.05))
            C.append(cyl(nm + "_lgc%d_%d" % (j, s), Ts(x + s * (w * 0.5 - 0.14), yy,
                                                      0.68), 0.082, 0.07, wdd,
                         seg=8))
    if cloth:
        C.append(bx(nm + "_cl", Ts(x, y, 0.795), (w + 0.10, L + 0.08, 0.025), wht,
                    bev=0.005))
        C.append(bx(nm + "_cle", Ts(x, y, 0.735), (w + 0.10, L + 0.08, 0.10), wht))
        for s in (-1, 1):
            C.append(bx(nm + "_cb%d" % s, Ts(x + s * (w * 0.5 + 0.05), y, 0.760),
                        (0.02, L + 0.08, 0.06), gold))
    return


def bench(C, MAT, x, y, L, nm):
    wd = _m(MAT, "wood")
    wdd = _m(MAT, "wood_dark")
    C.append(bx(nm + "_s", Ts(x, y, 0.44), (0.42, L, 0.07), wd, bev=0.01))
    for j in range(max(2, int(L / 2.4) + 1)):
        yy = y - L * 0.5 + 0.05 + (L - 0.10) * j / (max(2, int(L / 2.4) + 1) - 1)
        for s in (-1, 1):
            C.append(bx(nm + "_l%d_%d" % (j, s), Ts(x + s * 0.15, yy, 0.23),
                        (0.07, 0.14, 0.46), wdd, bev=0.008))
    C.append(bx(nm + "_st", Ts(x, y, 0.28), (0.36, L - 0.30, 0.06), wdd))


def chair(C, MAT, x, y, nm, rz=0.0):
    wd = _m(MAT, "wood_dark")
    red = _m(MAT, "cloth_red")
    T = Ts(x, y, 0.0, rz=rz)
    C.append(bx(nm + "_s", T @ Ts(0, 0, 0.46), (0.52, 0.50, 0.08), wd, bev=0.01))
    C.append(bx(nm + "_c", T @ Ts(0, 0.01, 0.52), (0.44, 0.42, 0.06), red))
    for s in (-1, 1):
        for t in (-1, 1):
            C.append(bx(nm + "_l%d%d" % (s, t), T @ Ts(s * 0.20, t * 0.19, 0.22),
                        (0.055, 0.055, 0.44), wd))
    C.append(bx(nm + "_b", T @ Ts(0, -0.23, 0.86), (0.52, 0.07, 0.72), wd,
                bev=0.012))
    C.append(bx(nm + "_bp", T @ Ts(0, -0.19, 0.72), (0.40, 0.03, 0.50), red))
    C.append(K.sphere(nm + "_f", T @ Ts(0.22, -0.225, 1.245), 0.045, wd, seg=8))


def armour_stand(C, MAT, x, y, nm, rz=0.0):
    iron = _m(MAT, "iron")
    st = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_dark")
    T = Ts(x, y, 0.0, rz=rz)
    C.append(bx(nm + "_pl", T @ Ts(0, 0, 0.06), (0.72, 0.72, 0.12), sd, bev=0.015))
    C.append(cyl(nm + "_po", T @ Ts(0, 0, 0.85), 0.055, 1.62, iron, seg=8))
    C.append(frustum(nm + "_to", T @ Ts(0, 0, 1.44), (0.34, 0.22), (0.46, 0.27),
                     0.56, iron, bev=0.012))
    C.append(frustum(nm + "_sk", T @ Ts(0, 0, 1.26), (0.44, 0.28), (0.36, 0.24),
                     0.30, iron, bev=0.012))
    for s in (-1, 1):
        C.append(K.sphere(nm + "_sh%d" % s, T @ Ts(s * 0.36, 0, 1.66), 0.17, iron,
                          seg=12))
        C.append(bx(nm + "_ar%d" % s, T @ Ts(s * 0.44, 0.02, 1.38), (0.12, 0.13, 0.56),
                    iron, bev=0.01))
    C.append(K.sphere(nm + "_hm", T @ Ts(0, 0, 1.90), 0.19, iron, seg=14))
    C.append(bx(nm + "_vz", T @ Ts(0, 0.09, 1.88), (0.20, 0.10, 0.10), iron))
    # a sword planted point-down, hands resting on the hilt
    C.append(rod(nm + "_sw", (T @ Vector((0.0, 0.20, 1.98))),
                 (T @ Vector((0.0, 0.20, 1.10))), 0.026, iron, seg=6))
    C.append(bx(nm + "_gd", T @ Ts(0, 0.20, 2.02), (0.30, 0.05, 0.05), iron))
    C.append(K.sphere(nm + "_pm", T @ Ts(0, 0.20, 2.09), 0.045, _m(MAT, "gold"),
                      seg=8))
    for s in (-1, 1):
        C.append(bx(nm + "_fd%d" % s, T @ Ts(s * 0.17, 0, 0.22), (0.20, 0.30, 0.20),
                    iron, bev=0.01))


def halberd_rack(C, MAT, x, y, nm, rz=0.0, n=4):
    wd = _m(MAT, "wood")
    iron = _m(MAT, "iron")
    T = Ts(x, y, 0.0, rz=rz)
    C.append(bx(nm + "_r1", T @ Ts(0, 0, 1.42), (0.09, 1.90, 0.10), wd, bev=0.01))
    C.append(bx(nm + "_r2", T @ Ts(0, 0, 0.30), (0.09, 1.90, 0.10), wd, bev=0.01))
    for s in (-1, 1):
        C.append(bx(nm + "_bp%d" % s, T @ Ts(0, s * 0.86, 0.85), (0.12, 0.12, 1.70),
                    wd, bev=0.01))
    for k in range(n):
        yy = -0.72 + 1.44 * k / (n - 1)
        C.append(rod(nm + "_sh%d" % k, (x + 0.10, y + yy, 0.24),
                     (x + 0.16, y + yy, 2.24), 0.028, wd, seg=6))
        # head: axe blade + spike
        C.append(prism(nm + "_ax%d" % k, [(x + 0.16, 2.06), (x + 0.16, 2.24),
                                          (x + 0.10, 2.30), (x + 0.10, 2.02)],
                       iron, y + yy - 0.02, y + yy + 0.02, axis="y"))
        C.append(K.cone(nm + "_sp%d" % k, Ts(x + 0.16, y + yy, 2.36), 0.035, 0.26,
                        iron, seg=6))


def flag(C, MAT, x, y, nm, h=6.4, rz=0.0):
    wd = _m(MAT, "wood_dark")
    gold = _m(MAT, "cloth_gold")
    iron = _m(MAT, "iron")
    T = Ts(x, y, 0.0, rz=rz)
    C.append(frustum(nm + "_b", T @ Ts(0, 0, 0.11), (0.62, 0.62), (0.40, 0.40),
                     0.22, _m(MAT, "stone_dark"), bev=0.015))
    C.append(rod(nm + "_p", (x, y, 0.20), (x, y, h), 0.055, wd, seg=8))
    C.append(K.sphere(nm + "_f", T @ Ts(0, 0, h + 0.10), 0.10, gold, seg=10))
    # a long swallow-tailed banner hanging from a cross bar
    C.append(bx(nm + "_cb", T @ Ts(0, 0.0, h - 0.40), (0.06, 1.30, 0.06), wd))
    C.append(quad_strip(nm + "_bn", [
        [T @ Vector((-0.03, 0.60, h - 0.44)), T @ Vector((-0.03, 0.0, h - 0.42)),
         T @ Vector((-0.03, -0.60, h - 0.44))],
        [T @ Vector((-0.03, 0.60, h - 2.30)), T @ Vector((-0.03, 0.0, h - 2.60)),
         T @ Vector((-0.03, -0.60, h - 2.30))],
    ], _m(MAT, "cloth_blue")))
    C.append(quad_strip(nm + "_bn2", [
        [T @ Vector((0.03, 0.60, h - 0.44)), T @ Vector((0.03, 0.0, h - 0.42)),
         T @ Vector((0.03, -0.60, h - 0.44))],
        [T @ Vector((0.03, 0.60, h - 2.30)), T @ Vector((0.03, 0.0, h - 2.60)),
         T @ Vector((0.03, -0.60, h - 2.30))],
    ], _m(MAT, "cloth_blue")))
    for s in (-1, 1):
        C.append(bx(nm + "_rb%d" % s, T @ Ts(0, s * 0.56, h - 0.42),
                    (0.10, 0.10, 0.14), iron))


def guard(C, MAT, x, y, nm, rz=0.0):
    """An armoured halberdier, feet on the floor."""
    iron = _m(MAT, "iron")
    cbl = _m(MAT, "cloth_blue")
    gold = _m(MAT, "gold")
    T = Ts(x, y, 0.0, rz=rz)
    for s in (-1, 1):
        C.append(cyl(nm + "_lg%d" % s, T @ Ts(s * 0.13, 0, 0.44), 0.10, 0.88, iron,
                     seg=8))
    C.append(frustum(nm + "_sk", T @ Ts(0, 0, 0.86), (0.40, 0.30), (0.34, 0.26),
                     0.32, cbl, bev=0.01))
    C.append(frustum(nm + "_to", T @ Ts(0, 0, 1.16), (0.36, 0.24), (0.46, 0.27),
                     0.52, iron, bev=0.012))
    for s in (-1, 1):
        C.append(K.sphere(nm + "_sh%d" % s, T @ Ts(s * 0.36, 0, 1.60), 0.16, iron,
                          seg=12))
        if s > 0:
            p0 = T @ Vector((0.38, 0.0, 1.56))
            p1 = T @ Vector((0.58, -0.03, 1.28))
        else:
            p0 = T @ Vector((-0.38, 0.0, 1.56))
            p1 = T @ Vector((-0.34, -0.10, 1.02))
        C.append(rod(nm + "_ar%d" % s, p0, p1, 0.085, iron, seg=6))
    C.append(K.sphere(nm + "_hd", T @ Ts(0, 0, 1.80), 0.145, _m(MAT, "stone_light"),
                      seg=12))
    C.append(cyl(nm + "_hm", T @ Ts(0, 0, 1.86), 0.185, 0.20, iron, seg=12))
    C.append(K.cone(nm + "_cr", T @ Ts(0, 0, 1.99), 0.06, 0.12, gold, seg=8))
    C.append(rod(nm + "_hb", (x + 0.60, y, 0.02), (x + 0.60, y, 2.62), 0.032,
                 _m(MAT, "wood"), seg=6))
    C.append(prism(nm + "_ha", [(x + 0.60, 2.38), (x + 0.60, 2.60),
                                (x + 0.44, 2.66), (x + 0.44, 2.32)], iron,
                   y - 0.02, y + 0.02, axis="y"))
    C.append(K.cone(nm + "_hs", Ts(x + 0.60, y, 2.76), 0.04, 0.26, iron, seg=6))


# ---------------------------------------------------------------------------
# the entrance porch
# ---------------------------------------------------------------------------
def narthex(C, E, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    wb = _m(MAT, "wood_beam")
    y0, y1 = Y_S + 1.60, Y_SCREEN - 1.70          # -24.4 .. -18.9
    XW = HALL_W * 0.5
    # flat boarded ceiling at the wall plate
    C.append(bx("nx_ceil", Ts(0.0, (y0 + y1) * 0.5, Z_PLATE + 0.26),
                (2.0 * X_IN, y1 - y0, 0.52), wb, bev=0.02))
    for j in range(4):
        yy = y0 + 0.86 + j * 1.30
        C.append(bx("nx_bm%d" % j, Ts(0.0, yy, Z_PLATE - 0.17),
                    (2.0 * X_IN, 0.30, 0.36), wb, bev=0.015))
        for s in (-1, 1):
            C.append(frustum("nx_cb%d_%d" % (j, s), Ts(s * (X_IN - 0.30), yy,
                                                       Z_PLATE - 0.52),
                             (0.34, 0.40), (0.52, 0.56), 0.34, sl, bev=0.012))
    # side walls above the aisle eaves (the outer wall stops at the vault spring)
    E.append(prism("nx_sw", [(y0, Z_VAULT_SPRING - 0.30), (y1, Z_VAULT_SPRING - 0.30),
                             (y1, Z_PLATE + 0.52), (y0, Z_PLATE + 0.52)],
                   st, X_IN, XW, axis="x"))
    E.append(bx("nx_str", Ts(X_IN - 0.10, (y0 + y1) * 0.5, Z_PLATE - 0.52),
                (0.22, y1 - y0, 0.20), sl, bev=0.02))
    E.append(bx("nx_pil", Ts(X_IN - 0.16, y0 + 0.10, (Z_VAULT_SPRING + Z_PLATE) * 0.5),
                (0.32, 0.70, Z_PLATE - Z_VAULT_SPRING - 0.6), st, bev=0.02))
    # stub tying the screen wall to the arcade line
    E.append(prism("nx_stub", [(8.40, 0.0), (9.90, 0.0), (9.90, Z_PLATE),
                               (8.40, Z_PLATE)], st, y0, Y_SCREEN, axis="y"))
    # wall closing the void over the east end of the aisle vault
    prof = arch_pts(AISLE_W * 0.5, 2.60, 16)
    pts = [(XAIS + AISLE_W * 0.5 + x, Z_VAULT_SPRING + z) for (x, z) in prof]
    pts += [(X_IN, Z_PLATE + 0.52), (XAIS, Z_PLATE + 0.52)]
    E.append(prism("nx_ae", pts, st, Y_SCREEN - 0.36, Y_SCREEN, axis="y"))
    E += arch_ring_y("nx_ar", XAIS + AISLE_W * 0.5, Z_VAULT_SPRING, AISLE_W * 0.5,
                     2.60, 0.24, Y_SCREEN - 0.44, Y_SCREEN - 0.14, sl, n=14,
                     keystone=True)


# ---------------------------------------------------------------------------
# everything else that furnishes the nave
# ---------------------------------------------------------------------------
def furnishings(C, E, MAT, rng):
    # ---- throne, candelabra, guards
    throne(C, MAT, rng)
    C += candelabra("cdl0", Ts(-1.86, 21.90, Z_DAIS), 1.86, MAT, arms=3)
    C += candelabra("cdl1", Ts(1.86, 21.90, Z_DAIS), 1.86, MAT, arms=3)
    for s in (-1, 1):
        guard(C, MAT, s * 3.86, 19.42, "gd0_%d" % s, rz=math.pi if s > 0 else 0.0)
        guard(C, MAT, s * 3.10, Y_STEP0 - 1.10, "gd1_%d" % s, rz=math.pi * 0.5 * s)
    # ---- chandeliers on the pier axes
    for i in (1, 3, 5):
        chandelier(C, MAT, rng, PIERS[i])
    # ---- braziers beside the stairs and by the screen
    for s in (-1, 1):
        brazier(C, MAT, rng, s * 5.90, 15.10, "bz0_%d" % s)
        brazier(C, MAT, rng, s * 5.90, -15.40, "bz1_%d" % s)
    # ---- banquet tables down both sides of the nave
    for s in (-1, 1):
        for j, (yy, ll) in enumerate(((-11.35, 8.4), (-2.10, 7.2), (7.20, 7.2))):
            xx = s * 5.30
            long_table(C, MAT, rng, xx, yy, ll, "tb%d_%d" % (j, s))
            bench(C, MAT, xx - 0.86, yy, ll - 0.5, "bn%d_%da" % (j, s))
            bench(C, MAT, xx + 0.86, yy, ll - 0.5, "bn%d_%db" % (j, s))
            for k, tz in enumerate((-0.30, 0.30)):
                C += candelabra("tcd%d_%d_%d" % (j, s, k),
                                Ts(xx, yy + ll * tz, 0.815), 0.68, MAT, arms=1)
    # ---- head table on the platform, flanked by chairs
    long_table(C, MAT, rng, 3.30, 22.20, 1.5, "hbt", cloth=True)
    C.append(bx("hbt_cp", Ts(3.30, 22.20, 0.83), (1.30, 1.60, 0.02),
                _m(MAT, "cloth_blue"), bev=0.0))
    # ---- armour stands and halberd racks along the arcade
    for s in (-1, 1):
        for j, yy in enumerate((-13.90, 0.60, 12.20)):
            armour_stand(C, MAT, s * 8.24, yy, "am%d_%d" % (j, s),
                         rz=math.pi * (0.5 if s > 0 else -0.5))
        halberd_rack(C, MAT, s * 8.46, -7.80, "hr%d" % 0, rz=0.0, n=4)
        halberd_rack(C, MAT, s * 8.46, 3.20, "hr%d" % 1, rz=0.0, n=4)
        flag(C, MAT, s * 8.34, -5.30, "fg%d_0" % s)
        flag(C, MAT, s * 8.34, 7.90, "fg%d_1" % s)
    # ---- chairs along the walls of the aisle
    for s in (-1, 1):
        for j, yy in enumerate((-9.4, -4.6, 0.2, 5.0, 9.8)):
            chair(C, MAT, s * 12.30, yy, "ch%d_%d" % (j, s),
                  rz=math.pi if s > 0 else 0.0)
    # ---- banners in the porch
    for s in (-1, 1):
        C += banner("nx_bn%d" % s, Ts(s * 4.60, -21.60, Z_PLATE - 0.20), 1.10, 3.10,
                    MAT, rng, mat=_m(MAT, "cloth_blue"))


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------
def _mirror_copy(objs):
    M = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
    out = []
    for ob in objs:
        me = ob.data.copy()
        me.transform(M)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.update()
        nb = bpy.data.objects.new(ob.name + "_m", me)
        bpy.context.collection.objects.link(nb)
        out.append(nb)
    return out


def _flat(seq, out):
    """Some helpers hand back a list of parts; accept either."""
    for it in seq:
        if isinstance(it, (list, tuple)):
            _flat(it, out)
        elif it is not None:
            out.append(it)
    return out


def build(MAT, rng):
    C, E = [], []
    floor(C, MAT, rng)
    arcade(E, MAT, rng)
    outer_wall(E, MAT, rng)
    aisle_vault(E, MAT, rng)
    aisle_end(E, MAT, rng)
    screen_wall(C, MAT, rng)
    south_wall(C, MAT, rng)
    narthex(C, E, MAT, rng)
    chancel(C, E, MAT, rng)
    back_wall(C, MAT, rng)
    heraldry(C, E, MAT, rng)
    sconces(E, MAT, rng)
    detail(C, E, MAT, rng)
    roof(C, E, MAT, rng)
    dais(C, MAT, rng)
    carpets(C, MAT, rng)
    furnishings(C, E, MAT, rng)
    C = _flat(C, [])
    E = _flat(E, [])
    out = list(C) + list(E)
    out.extend(_mirror_copy(E))
    return out


def footprint():
    return (HALL_W, HALL_L)


def height():
    return Z_RIDGE + 0.35


# ---------------------------------------------------------------------------
# preview
# ---------------------------------------------------------------------------
def _volume_mat(density=0.014, aniso=0.55):
    m = bpy.data.materials.new("VOL_AIR")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.location = (0, 0)
    pv.inputs["Density"].default_value = density
    pv.inputs["Anisotropy"].default_value = aniso
    pv.inputs["Color"].default_value = (1.0, 0.965, 0.915, 1.0)
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    return m


def _sun(name, direction, energy=4.6, angle=1.1, color=(1.0, 0.945, 0.855)):
    li = bpy.data.lights.new(name, "SUN")
    li.energy = energy
    li.angle = math.radians(angle)
    li.color = color
    ob = bpy.data.objects.new(name, li)
    bpy.context.collection.objects.link(ob)
    ob.rotation_euler = Vector(direction).normalized().to_track_quat('-Z', 'Y').to_euler()
    return ob


def _area(name, loc, size, energy, rot, color=(1.0, 0.92, 0.84)):
    li = bpy.data.lights.new(name, "AREA")
    li.energy = energy
    li.shape = "RECTANGLE"
    li.size, li.size_y = size
    li.color = color
    ob = bpy.data.objects.new(name, li)
    ob.location = loc
    ob.rotation_euler = rot
    bpy.context.collection.objects.link(ob)
    return ob


def _point(name, loc, energy, color=(1.0, 0.72, 0.40), radius=0.25):
    li = bpy.data.lights.new(name, "POINT")
    li.energy = energy
    li.color = color
    li.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, li)
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    return ob


def _world():
    w = bpy.data.worlds.new("SKY_AFTERNOON")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.44, 0.60, 0.86, 1.0)
    bg.inputs[1].default_value = 0.85
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w


def preview():
    H._clear()
    sc = bpy.context.scene
    MAT = make_mats()
    rng = random.Random(20261030)
    objs = build(MAT, rng)
    print("BUILD objects:", len(objs), "tris:", H.tri_count(objs))
    _world()
    # ---- afternoon sun, coming in through the south-east clerestory
    _sun("SUN", (-0.62, -0.26, -0.72), energy=9.5, angle=0.55)
    # ---- interior fill (kept low so the shafts read)
    _area("FILL_NAVE", (0.0, 3.0, 15.10), (7.0, 6.0), 900.0, (0.0, 0.0, 0.0),
          color=(1.0, 0.93, 0.84))
    _area("FILL_ENTRY", (0.0, -14.20, 14.20), (6.0, 5.0), 520.0, (0.0, 0.0, 0.0),
          color=(1.0, 0.93, 0.86))
    _area("FILL_DAIS", (0.0, 15.60, 14.40), (6.0, 5.0), 700.0,
          (math.radians(14.0), 0.0, 0.0), color=(1.0, 0.90, 0.78))
    # ---- uplights so the timber roof is not a black hole
    _area("UP_NAVE", (0.0, 1.0, 9.40), (12.0, 14.0), 950.0,
          (math.pi, 0.0, 0.0), color=(1.0, 0.90, 0.78))
    _area("UP_CHOR", (0.0, 17.60, 9.80), (8.0, 6.0), 420.0,
          (math.pi, 0.0, 0.0), color=(1.0, 0.88, 0.74))
    # ---- practicals
    for i in (1, 3, 5):
        _point("CH_L%d" % i, (0.0, PIERS[i], 11.90), 220.0, (1.0, 0.70, 0.36), 0.5)
    for s in (-1, 1):
        _point("BZ0_%d" % s, (s * 5.90, 15.10, 1.55), 90.0, (1.0, 0.52, 0.18), 0.3)
        _point("BZ1_%d" % s, (s * 5.90, -15.40, 1.55), 90.0, (1.0, 0.52, 0.18), 0.3)
        _point("CD_%d" % s, (s * 1.86, 21.90, Z_DAIS + 1.95), 45.0,
               (1.0, 0.66, 0.34), 0.18)
    # ---- volumetric air so the shafts read
    vol = _m(MAT, "stone")  # dummy, replaced right after
    box = K.box("VOL", Ts(0.0, 0.0, 8.85), (18.4, 50.6, 17.70), vol)
    box.data.materials.clear()
    box.data.materials.append(_volume_mat(0.0072, 0.62))

    H.setup_engine(samples=128, res=(1600, 900), gpu=True)
    sc.cycles.use_denoising = True
    try:
        sc.view_settings.look = "AgX - Punchy"
    except Exception:
        pass

    shots = [
        ("a_entry", (0.0, -23.30, 1.70), (0.0, 6.00, 2.90), 22.0),
        ("b_nave", (0.0, -1.20, 1.70), (0.0, 17.00, 3.30), 27.0),
        ("c_dais", (0.0, 11.20, 1.70), (0.0, 21.60, 2.55), 34.0),
        ("d_back", (0.0, 20.20, Z_DAIS + 1.70), (0.0, -24.00, 3.40), 22.0),
        ("e_aisle", (11.55, -14.60, 1.70), (11.55, 6.00, 2.60), 22.0),
        ("f_diag", (-6.90, -11.60, 1.72), (0.60, 10.00, 4.40), 30.0),
        ("g_roof", (0.0, 3.40, 1.70), (0.0, 8.60, 16.40), 17.0),
    ]
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    paths = []
    for nm, loc, tgt, lens in shots:
        cam = H.camera("CAM_" + nm, loc, tgt, lens=lens)
        p = os.path.join(OUT, "%s.png" % nm)
        H.render_to(p, cam)
        paths.append(p)
        print("RENDER", p)
    return paths


if __name__ == "__main__":
    preview()
