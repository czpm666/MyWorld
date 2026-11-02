def build_fireplace(M, rng):
    """A hooded hearth on the -X wall of the feast hall, with a real fire."""
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    st = _m(M, "stone_wall")
    sc = _m(M, "stone_course")
    sd = _m(M, "stone_dark")
    fi = _m(M, "fire")
    em = _m(M, "ember")
    ir = _m(M, "iron")
    wd = _m(M, "wood_dark")
    HW = 1.25           # half width of the hearth opening
    DP = 0.95           # depth into the wall
    OH = 1.75           # opening height
    # ---- stone surround: cheeks, back, lintel, stepped hood to the ceiling
    P.append(bx("ci_fp_back", T @ Ts(0, DP + 0.25, FZ0 + 3.0), (2 * HW + 0.9, 0.50, 6.0), sd))
    for s2 in (-1, 1):
        P.append(bx("ci_fp_cheek", T @ Ts(s2 * (HW + 0.34), DP * 0.5, FZ0 + 3.0),
                    (0.68, DP + 0.5, 6.0), st, bev=0.016))
        P.append(bx("ci_fp_pil", T @ Ts(s2 * (HW + 0.02), -0.05, FZ0 + (OH + 0.55) * 0.5),
                    (0.50, 0.22, OH + 0.55), sc, bev=0.014))
        P.append(bx("ci_fp_pc", T @ Ts(s2 * (HW + 0.02), -0.10, FZ0 + OH + 0.50),
                    (0.62, 0.32, 0.24), sc, bev=0.012))
    P.append(bx("ci_fp_lint", T @ Ts(0, DP * 0.5, FZ0 + OH + 0.26),
                (2 * HW + 1.4, DP + 0.55, 0.44), sc, bev=0.016))
    P.append(bx("ci_fp_lint2", T @ Ts(0, -0.10, FZ0 + OH + 0.06),
                (2 * HW + 1.1, 0.30, 0.16), sd, bev=0.010))
    for k in range(4):
        w = (2 * HW + 1.25) - k * 0.42
        P.append(bx("ci_fp_hood%d" % k,
                    T @ Ts(0, DP * 0.5 + 0.10 * k, FZ0 + OH + 0.72 + k * 0.60),
                    (w, DP + 0.15, 0.64), st if k % 2 else sc, bev=0.014))
    # ---- hearth floor, soot, kerb, andirons
    P.append(bx("ci_fp_floor", T @ Ts(0, DP * 0.5, FZ0 + 0.075), (2 * HW, DP, 0.15), sd,
                bev=0.012))
    P.append(bx("ci_fp_kerb", T @ Ts(0, -0.13, FZ0 + 0.16), (2 * HW + 0.8, 0.34, 0.32), sc,
                bev=0.014))
    for s2 in (-1, 1):
        P.append(bx("ci_fp_fd", T @ Ts(s2 * 0.62, DP * 0.42, FZ0 + 0.30),
                    (0.10, 0.34, 0.46), ir, bev=0.010))
        P.append(cyl("ci_fp_fdt", T @ Ts(s2 * 0.62, DP * 0.42, FZ0 + 0.54), 0.055, 0.20,
                     ir, seg=8))
    # ---- a stack of logs, three courses
    for k in range(6):
        yy = DP * 0.46 + rng.uniform(-0.20, 0.20)
        zz = FZ0 + 0.20 + 0.15 * (k // 2)
        P.append(cyl("ci_fp_log", T @ Ts(rng.uniform(-0.55, 0.55), yy, zz,
                                        ry=math.pi * 0.5),
                     0.095, 1.45, wd, seg=8))
    for k in range(14):
        P.append(sph("ci_fp_coal", T @ Ts(rng.uniform(-0.95, 0.95),
                                          DP * 0.42 + rng.uniform(-0.22, 0.22),
                                          FZ0 + 0.17), rng.uniform(0.06, 0.13), em, 8, 5, 0.5))
    # ---- flame tongues, two staggered rows so the fire has depth
    for k in range(11):
        xx = -1.02 + 0.204 * k
        h = rng.uniform(0.70, 1.55)
        yy = DP * 0.40 + (0.18 if k % 2 else -0.06) + rng.uniform(-0.05, 0.05)
        P.append(prism_y("ci_fp_flame", T @ Ts(xx + rng.uniform(-0.05, 0.05), yy,
                                              FZ0 + 0.26),
                         [(-0.15, 0.0), (0.15, 0.0), (0.07, h * 0.50), (0.0, h),
                          (-0.07, h * 0.44)], 0.16, fi))
    return P


