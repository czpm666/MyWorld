def side_wall(s, M, rng):
    """A long wall: bench, blind arcade of pointed niches, clerestory, plate.

    Local frame: +X runs along the wall, +Y points out of the room.
    """
    P = []
    n = "+y" if s > 0 else "-y"
    T = WF(0.0, s * HY, 0.0, n)
    U = HX + WT
    st = _m(M, "stone_wall")
    sl = _m(M, "stone_light")
    sc = _m(M, "stone_course")
    sd = _m(M, "stone_dark")
    PZ = 0.46
    SPR, RISE = 5.10, 2.10
    # ---- outer leaf of the wall and the plinth
    P.append(bx("ci_wall_out", T @ Ts(0, (PZ + WT) * 0.5, 4.60),
                (2 * U, WT - PZ, 9.20), st))
    P.append(bx("ci_plinth", T @ Ts(0, (WT - 0.07) * 0.5, 0.10),
                (2 * U, WT + 0.07, 0.20), sd, bev=0.012))
    # ---- piers, with a bundle of engaged shafts on the room face
    for x0 in BAYX:
        P.append(bx("ci_pier", T @ Ts(x0, PZ * 0.5, 4.60), (0.92, PZ, 9.20), st))
        P.append(cyl("ci_pier_sh", T @ Ts(x0, -0.075, 4.85), 0.185, 8.40, sl, seg=14))
        for dx in (-0.30, 0.30):
            P.append(cyl("ci_pier_sh2", T @ Ts(x0 + dx, -0.045, 4.85), 0.098, 8.40,
                         sl, seg=10))
        P.append(bx("ci_pier_base", T @ Ts(x0, -0.09, 0.31), (0.98, 0.50, 0.62), sc,
                    bev=0.014))
        P.append(bx("ci_pier_cap", T @ Ts(x0, -0.075, 7.42), (1.00, 0.48, 0.24), sc,
                    bev=0.014))
    # ---- the arcade: arch heads, archivolts, niche linings, stone seats
    for i in range(NBAY):
        u0, u1 = BAYX[i] + 0.46, BAYX[i + 1] - 0.46
        hs = (u1 - u0) * 0.5
        uc = (u0 + u1) * 0.5
        P.append(spandrel("ci_arc_span", T @ Ts(0, PZ * 0.5, 0), u0, u1, SPR, RISE,
                          9.20, PZ, st, nseg=10))
        P.append(ring_voussoir("ci_arc_ring", T @ Ts(0, 0.04, 0), hs, SPR, RISE, 0.26,
                               0.20, sl, nseg=10, bev=0.008))
        P.append(bx("ci_arc_line", T @ Ts(uc, PZ - 0.03, 2.40), (2 * hs, 0.06, 4.64), sd))
        for s2 in (-1, 1):
            P.append(bx("ci_arc_jamb", T @ Ts(uc + s2 * (hs - 0.05), 0.02, 2.40),
                        (0.10, 0.10, 4.60), sl, bev=0.008))
        P.append(bx("ci_arc_seat", T @ Ts(uc, -0.16, 0.255), (2 * hs - 0.20, 0.50, 0.51),
                    sc))
        P.append(bx("ci_arc_seat_t", T @ Ts(uc, -0.17, 0.53), (2 * hs - 0.16, 0.52, 0.06),
                    sl, bev=0.012))
    # ---- string course at the clerestory sill
    P.append(bx("ci_sill", T @ Ts(0, WT * 0.5 - 0.10, 9.40),
                (2 * U, WT + 0.20, 0.40), sc, bev=0.016))
    # ---- clerestory
    for i in range(NBAY):
        b0, b1 = BAYX[i], BAYX[i + 1]
        u0, u1 = b0 + 0.62, b1 - 0.62
        hs = (u1 - u0) * 0.5
        uc = (u0 + u1) * 0.5
        P.append(bx("ci_cl_jamb", T @ Ts((b0 + u0) * 0.5, WT * 0.5, 11.80),
                    (u0 - b0, WT, 4.40), st))
        P.append(bx("ci_cl_jamb", T @ Ts((u1 + b1) * 0.5, WT * 0.5, 11.80),
                    (b1 - u1, WT, 4.40), st))
        P.append(spandrel("ci_cl_span", T @ Ts(0, WT * 0.5, 0), u0, u1, 11.90, 1.50,
                          Z_PLATE, WT, st, nseg=7))
        P.append(ring_voussoir("ci_cl_ring", T @ Ts(0, 0.02, 0), hs, 11.90, 1.50, 0.24,
                               0.30, sl, nseg=7, bev=0.010))
        for sx in (-1, 1):
            P.append(bx("ci_cl_order", T @ Ts(uc + sx * (hs + 0.12), 0.02, 10.75),
                        (0.24, 0.30, 2.30), sl, bev=0.010))
        P.append(bx("ci_cl_seat", T @ Ts(uc, WT * 0.5, 9.74),
                    (2 * hs + 0.10, WT - 0.28, 0.16), sl, bev=0.012))
        P.extend(glazed_window("ci_cl", T, uc, WT * 0.5, 9.80, hs, 11.90, 1.50, rng))
    # ---- wall plate and cornice
    P.append(bx("ci_plate", T @ Ts(0, 0.02, Z_PLATE + 0.17), (2 * U, 0.34, 0.34),
                _m(M, "wood_beam")))
    P.append(bx("ci_cornice", T @ Ts(0, -0.08, Z_PLATE - 0.10), (2 * U, 0.30, 0.20),
                sc, bev=0.012))
    return P


_GLASS_ORDER = ("glass_blue", "glass_blue", "glass_blue", "glass_gold",
                "glass_red", "glass_green", "glass_pale", "glass_gold")


def glazed_window(nm, T, uc, vc, z0, hs, spring, rise, rng):
    """Leaded stained glass in an arched opening: one mesh, per-face material."""
    uniq = []
    for n in _GLASS_ORDER:
        if n not in uniq:
            uniq.append(n)
    mats = [_m({}, n) for n in uniq]
    idx = {n: i for i, n in enumerate(uniq)}
    cols = [idx[n] for n in _GLASS_ORDER]
    P = []
    verts, faces, mi = [], [], []
    inset = 0.016

    def pane(x0, x1, zz0, zz1, ci):
        if x1 - x0 < 0.04 or zz1 - zz0 < 0.04:
            return
        b = len(verts)
        for (xx, zz) in ((x0 + inset, zz0 + inset), (x1 - inset, zz0 + inset),
                         (x1 - inset, zz1 - inset), (x0 + inset, zz1 - inset)):
            verts.append(T @ Vector((xx, vc, zz)))
        faces.append((b, b + 1, b + 2, b + 3))
        mi.append(ci)

    # rectangular lights
    pw = 0.25
    ncol = max(4, int(round(2.0 * hs / pw)))
    pw = 2.0 * hs / ncol
    ph = 0.30
    nrow = max(3, int(round((spring - z0) / ph)))
    ph = (spring - z0) / nrow
    for r in range(nrow):
        for c in range(ncol):
            if c == 0 or c == ncol - 1:
                ci = idx["glass_red"] if (r % 2) else idx["glass_pale"]
            elif c == ncol // 2:
                ci = idx["glass_gold"]
            else:
                ci = cols[(r * 5 + c * 3 + (r * c) % 7) % len(cols)]
            pane(uc - hs + c * pw, uc - hs + (c + 1) * pw,
                 z0 + r * ph, z0 + (r + 1) * ph, ci)
    # the arch head, three courses narrowing with the curve
    for k in range(5):
        zz = spring + rise * (k + 0.5) / 5.4
        hw = arch_halfwidth(hs, spring, rise, zz) - 0.05
        if hw < 0.10:
            break
        n = max(1, int(2 * hw / 0.30))
        for c in range(n):
            x0 = uc - hw + 2 * hw * c / n
            x1 = uc - hw + 2 * hw * (c + 1) / n
            pane(x0, x1, zz - rise / 10.8, zz + rise / 10.8,
                 idx["glass_gold"] if (c + k) % 3 else idx["glass_blue"])
    ob = K.mesh_obj(nm + "_glass", verts, faces)
    K.assign(ob, *mats)
    for p, m in zip(ob.data.polygons, mi):
        p.material_index = m
    P.append(ob)
    # stone mullions and a transom
    ms = _m({}, "stone_light")
    for c in (1, 2):
        P.append(bx(nm + "_mull", T @ Ts(uc - hs + c * 2 * hs / 3.0, vc - 0.015,
                                        (z0 + spring) * 0.5 + 0.05),
                    (0.11, 0.09, spring - z0 + 0.10), ms, bev=0.006))
    P.append(bx(nm + "_trans", T @ Ts(uc, vc - 0.015, z0 + (spring - z0) * 0.62),
                (2 * hs, 0.07, 0.10), ms, bev=0.006))
    return P


