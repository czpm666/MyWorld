# -*- coding: utf-8 -*-
"""One-shot surgery on _cint_p3.py: replace chancel() + back_wall() wholesale."""
import io

P = r"E:\My World\Blender\kingdom\_cint_p3.py"

NEW = r'''def chancel(C, E, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    glass = [_m(MAT, k) for k in ("glass_gold", "glass_blue", "glass_red")]
    woodb = _m(MAT, "wood_beam")
    y0, y1 = Y_CHOR, Y_CHOR + 1.0
    hw = 5.00
    z_spr, z_apex = 6.60, 9.60
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
                   y0 + 0.01, y0 + 0.06, axis="y"))
    for s in (-1, 1):
        C.append(bx("bw_nj%d" % s, Ts(s * 1.72, y0 + 0.20, 3.06),
                    (0.54, 0.40, 4.28), sl, bev=0.02))
        C.append(bx("bw_nc%d" % s, Ts(s * 1.72, y0 + 0.21, 5.27),
                    (0.72, 0.44, 0.18), sl, bev=0.015))
        C.append(bx("bw_nb%d" % s, Ts(s * 1.72, y0 + 0.21, 0.88),
                    (0.72, 0.44, 0.16), sl, bev=0.015))
    C += arch_ring_y("bw_nr", 0.0, 5.20, nah, 1.80, 0.30, y0 + 0.02, y0 + 0.40,
                     sl, n=14, keystone=True)
    C.append(bx("bw_ns", Ts(0.0, y0 + 0.22, 0.86), (3.90, 0.46, 0.16), sl, bev=0.02))
    C.append(statue("bw_stat", Ts(0.0, y0 + 0.20, 0.94), 3.30, MAT, rng))
    # ---- blind arcading to either side
    for s in (-1, 1):
        for j in range(2):
            xc = s * (2.72 + j * 2.45)
            C.append(prism("bw_bp%d_%d" % (s, j), hole_pts(0.80, 1.30, 4.00, 5.40, 12),
                           sd, y0 + 0.01, y0 + 0.05, axis="y"))
            C += arch_ring_y("bw_br%d_%d" % (s, j), xc, 4.00, 0.80, 1.40, 0.24,
                             y0 + 0.02, y0 + 0.20, sl, n=12, keystone=True)
            for t in (-1, 1):
                C.append(bx("bw_bj%d_%d_%d" % (s, j, t),
                            Ts(xc + t * 0.94, y0 + 0.10, 2.60),
                            (0.28, 0.20, 2.60), sl, bev=0.012))
            C.append(bx("bw_bsd%d_%d" % (s, j), Ts(xc, y0 + 0.10, 1.34),
                        (2.16, 0.20, 0.12), sl, bev=0.012))
    # ---- cornice + string course
    C.append(bx("bw_corn", Ts(0.0, y0 - 0.12, Z_CHOR_CEIL - 0.30),
                (2 * hw, 0.30, 0.26), sl, bev=0.025))
    C.append(bx("bw_str", Ts(0.0, y0 - 0.08, 7.90), (2 * hw, 0.20, 0.16), sl,
                bev=0.02))


'''

src = io.open(P, encoding="utf-8").read()
a = src.index("def chancel(C, E, MAT, rng):")
b = src.index("# ---------------------------------------------------------------------------\n# statues")
out = src[:a] + NEW + src[b:]
io.open(P, "w", encoding="utf-8", newline="\n").write(out)
print("PATCHED p3: %d -> %d chars" % (len(src), len(out)))
