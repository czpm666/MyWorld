def build_throne(M, rng):
    """Three steps up, a tall narrow high-backed seat, gold, cloth of estate.

    The silhouette is deliberately vertical: a 1.38 m wide back standing 3.2 m
    over the dais, so it cannot be mistaken for an altar or a wall panel.
    """
    P = []
    T = Ts(THR_X, THR_Y, Z_DAIS)
    st = _m(M, "stone_light")
    sd = _m(M, "stone_dark")
    mb = _m(M, "marble")
    gd = _m(M, "gold")
    br = _m(M, "brass")
    rd = _m(M, "cloth_red")
    cd = _m(M, "cloth_gold")
    # ---- plinth, footpace
    P.append(bx("ci_thr_pl", T @ Ts(0.04, 0, 0.11), (1.96, 2.16, 0.22), sd, bev=0.018))
    P.append(bx("ci_thr_pl_g", T @ Ts(0.04, 0, 0.235), (2.00, 2.20, 0.05), gd, bev=0.008))
    P.append(bx("ci_thr_fp", T @ Ts(0.02, 0, 0.315), (1.78, 1.98, 0.16), mb, bev=0.012))
    # ---- seat block, cushion
    P.append(bx("ci_thr_seat", T @ Ts(-0.20, 0, 0.65), (1.06, 1.14, 0.50), mb, bev=0.018))
    P.append(bx("ci_thr_seat_ap", T @ Ts(0.26, 0, 0.66), (0.07, 1.06, 0.40), st, bev=0.008))
    P.append(bx("ci_thr_seat_g", T @ Ts(0.295, 0, 0.55), (0.035, 1.02, 0.13), gd, bev=0.006))
    P.append(bx("ci_thr_cus", T @ Ts(-0.22, 0, 0.955), (0.98, 1.06, 0.13), rd, bev=0.045))
    P.append(bx("ci_thr_fringe", T @ Ts(-0.22, 0, 0.888), (1.02, 1.10, 0.035), cd))
    # ---- the tall narrow back
    P.append(bx("ci_thr_back", T @ Ts(-0.72, 0, 1.80), (0.34, 1.38, 2.80), mb, bev=0.018))
    # velvet inset, gold frame, roundel
    P.append(bx("ci_thr_vel", T @ Ts(-0.545, 0, 1.92), (0.05, 1.04, 1.92), rd, bev=0.010))
    for s2 in (-1, 1):
        P.append(bx("ci_thr_vel_fr", T @ Ts(-0.535, s2 * 0.555, 1.92),
                    (0.06, 0.10, 2.02), gd, bev=0.008))
    P.append(bx("ci_thr_vel_ft", T @ Ts(-0.535, 0, 2.90), (0.06, 1.20, 0.10), gd, bev=0.008))
    P.append(bx("ci_thr_vel_fb", T @ Ts(-0.535, 0, 0.96), (0.06, 1.20, 0.10), gd, bev=0.008))
    P.append(cyl("ci_thr_round", T @ Ts(-0.515, 0, 2.28, ry=math.pi * 0.5), 0.31, 0.05,
                 gd, seg=20))
    P.append(cyl("ci_thr_round2", T @ Ts(-0.505, 0, 2.28, ry=math.pi * 0.5), 0.22, 0.05,
                 rd, seg=20))
    # ---- crest rail, gable canopy, orb, finials
    P.append(bx("ci_thr_crest", T @ Ts(-0.72, 0, 3.245), (0.42, 1.46, 0.13), gd, bev=0.010))
    P.append(bx("ci_thr_crest2", T @ Ts(-0.72, 0, 3.13), (0.44, 1.50, 0.08), st, bev=0.010))
    P.append(prism_y("ci_thr_can", T @ Ts(-0.72, 0, 0),
                     [(-1.00, 3.31), (-1.00, 3.45), (-0.50, 3.86), (0.0, 4.02),
                      (0.50, 3.86), (1.00, 3.45), (1.00, 3.31)], 0.36, st, bev=0.012))
    P.append(bx("ci_thr_can_g", T @ Ts(-0.72, 0, 3.40), (0.40, 1.92, 0.07), gd, bev=0.006))
    P.append(sph("ci_thr_orb", T @ Ts(-0.72, 0, 4.16), 0.135, gd, seg=14, ring=8))
    for s2 in (-1, 1):
        P.append(cyl("ci_thr_pin", T @ Ts(-0.72, s2 * 0.80, 3.62), 0.078, 0.62, st, seg=10))
        P.append(cyl("ci_thr_pint", T @ Ts(-0.72, s2 * 0.80, 4.06), 0.11, 0.26, gd, seg=10,
                     r2=0.016))
    # ---- arms, lion heads, arm supports
    for s2 in (-1, 1):
        P.append(bx("ci_thr_arm", T @ Ts(0.02, s2 * 0.66, 1.36), (1.10, 0.22, 0.26),
                    mb, bev=0.014))
        P.append(bx("ci_thr_arm_g", T @ Ts(0.02, s2 * 0.66, 1.505), (1.04, 0.18, 0.05),
                    gd, bev=0.006))
        P.append(bx("ci_thr_arm_s", T @ Ts(-0.24, s2 * 0.66, 1.12), (0.20, 0.20, 0.36),
                    mb, bev=0.010))
        P.append(sph("ci_thr_lion", T @ Ts(0.55, s2 * 0.66, 1.40), 0.135, gd,
                     seg=14, ring=8, squash=0.92))
        P.append(bx("ci_thr_lion_e", T @ Ts(0.64, s2 * 0.66, 1.43), (0.05, 0.13, 0.07),
                    _m(M, "iron")))
    # ---- footstool
    P.append(bx("ci_thr_fst", T @ Ts(0.86, 0, 0.325), (0.62, 0.98, 0.15), st, bev=0.014))
    P.append(bx("ci_thr_fst_g", T @ Ts(0.86, 0, 0.405), (0.66, 1.02, 0.035), gd, bev=0.006))
    P.append(bx("ci_thr_fst_c", T @ Ts(0.86, 0, 0.445), (0.54, 0.90, 0.05), rd, bev=0.020))
    # ---- cloth of estate behind, and its hood
    Th = WF(-HX + 0.045, 0.0, 0.0, "-x") @ Ts(0, 0, 5.34, rz=math.pi)
    P.append(hang_rail("ci_thr_rail", Th @ Ts(0, -0.05, 0), 3.02, br, r=0.05))
    P.append(cloth_panel("ci_thr_hang", Th, 2.98, 4.28, rd,
                         folds=11, amp=0.115, sag=0.07, rows=22, cols=15, thick=0.016))
    P.append(bx("ci_thr_hang_g", Th @ Ts(0, 0.02, -4.22), (2.98, 0.09, 0.11), cd))
    for s2 in (-1, 1):
        P.append(bx("ci_thr_hang_s", Th @ Ts(s2 * 1.46, -0.04, -2.14),
                    (0.09, 0.10, 4.28), cd))
    P.append(bx("ci_thr_hood", T @ Ts(-1.60, 0, 5.40), (1.02, 3.24, 0.20),
                _m(M, "wood_beam"), bev=0.014))
    P.append(bx("ci_thr_hood2", T @ Ts(-1.16, 0, 5.54), (0.16, 3.06, 0.34),
                _m(M, "wood_dark"), bev=0.012))
    for s2 in (-1, 1):
        P.append(bx("ci_thr_hood_br", T @ Ts(-1.30, s2 * 1.24, 4.84),
                    (0.16, 0.16, 1.20), _m(M, "wood_dark")))
    return P
