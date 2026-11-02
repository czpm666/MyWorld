# ---------------------------------------------------------------------------
# glazing, mouldings, wall panels
# ---------------------------------------------------------------------------
def frustum(name, T, s0, s1, h, mat, bev=0.0):
    """Box frustum: section s0 at z=0, s1 at z=h (both (x, y) sizes)."""
    a0, b0 = s0[0] * 0.5, s0[1] * 0.5
    a1, b1 = s1[0] * 0.5, s1[1] * 0.5
    v = [(-a0, -b0, 0), (a0, -b0, 0), (a0, b0, 0), (-a0, b0, 0),
         (-a1, -b1, h), (a1, -b1, h), (a1, b1, h), (-a1, b1, h)]
    f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
         (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = K.mesh_obj(name, [tuple((T @ Vector(p))) for p in v], f)
    if mat:
        K.assign(ob, mat)
    if bev:
        K.bevel(ob, bev, 2, 40.0)
    return ob


def arch_halfw(hs, rise, dz, n=48):
    """Half width of a two-centred arch at height dz above its springing."""
    if dz <= 0.0:
        return hs
    if dz >= rise:
        return 0.0
    pts = arch_pts(hs, rise, n)
    for i in range(len(pts) - 1):
        (x0, z0), (x1, z1) = pts[i], pts[i + 1]
        if (z0 - dz) * (z1 - dz) <= 0.0 and abs(z1 - z0) > 1e-9:
            t = (dz - z0) / (z1 - z0)
            return abs(x0 + (x1 - x0) * t)
    return 0.0


def arch_ring_x(name, yc, z_spring, hs, rise, ring, x0, x1, mat, n=14,
                bev=0.012, keystone=True):
    """Voussoirs on an X-normal wall (polygon in y,z; extruded along x)."""
    ring = max(0.02, ring)
    pts = [(yc + x, z_spring + z) for (x, z) in arch_pts(hs, rise, n)]
    nrm = arch_normals([(p[0] - yc, p[1] - z_spring) for p in pts])
    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        q0 = (p0[0] + nrm[i][0] * ring, p0[1] + nrm[i][1] * ring)
        q1 = (p1[0] + nrm[i + 1][0] * ring, p1[1] + nrm[i + 1][1] * ring)
        out.append(prism("%s_vs%02d" % (name, i), [p0, p1, q1, q0], mat,
                         x0, x1, axis="x", bev=bev))
    if keystone:
        zc = z_spring + rise
        w = max(0.30, abs(pts[len(pts) // 2 + 1][0] - pts[len(pts) // 2 - 1][0]) * 0.7)
        out.append(prism("%s_key" % name,
                         [(yc - w * 0.5, zc - 0.16), (yc + w * 0.5, zc - 0.16),
                          (yc + w * 0.36, zc + ring * 1.15),
                          (yc - w * 0.36, zc + ring * 1.15)],
                         mat, x0 - 0.05, x1 + 0.05, axis="x", bev=0.02))
    return out


def arch_ring_y(name, xc, z_spring, hs, rise, ring, y0, y1, mat, n=14,
                bev=0.012, keystone=True):
    """Voussoirs on a Y-normal wall (polygon in x,z; extruded along y)."""
    pts = [(xc + x, z_spring + z) for (x, z) in arch_pts(hs, rise, n)]
    nrm = arch_normals([(p[0] - xc, p[1] - z_spring) for p in pts])
    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        q0 = (p0[0] + nrm[i][0] * ring, p0[1] + nrm[i][1] * ring)
        q1 = (p1[0] + nrm[i + 1][0] * ring, p1[1] + nrm[i + 1][1] * ring)
        out.append(prism("%s_vs%02d" % (name, i), [p0, p1, q1, q0], mat,
                         y0, y1, axis="y", bev=bev))
    if keystone:
        zc = z_spring + rise
        w = max(0.30, abs(pts[len(pts) // 2 + 1][0] - pts[len(pts) // 2 - 1][0]) * 0.7)
        out.append(prism("%s_key" % name,
                         [(xc - w * 0.5, zc - 0.16), (xc + w * 0.5, zc - 0.16),
                          (xc + w * 0.36, zc + ring * 1.15),
                          (xc - w * 0.36, zc + ring * 1.15)],
                         mat, y0 - 0.05, y1 + 0.05, axis="y", bev=0.02))
    return out


def glaze_x(name, yc, w, z_bot, z_apex, x_in, x_out, glass, rng,
            frame_mat=None, mullion=True, transom=True, sill=True, rows=5,
            arows=4, cols=3, iron=None):
    """Glazed pointed window in an X-normal wall, inner face at x_in."""
    iron = iron or frame_mat
    hs = w * 0.5
    rise = min(hs * 1.30, (z_apex - z_bot) * 0.62)
    z_spring = z_apex - rise
    out = []
    xg = x_in + (x_out - x_in) * 0.58
    # ---- panes
    zb = z_bot
    for i in range(rows):
        za = zb + (z_spring - z_bot) * i / rows
        zz = zb + (z_spring - z_bot) * (i + 1) / rows
        for j in range(cols):
            y0 = yc - hs + 2 * hs * j / cols
            y1 = yc - hs + 2 * hs * (j + 1) / cols
            out.append(prism("%s_gl%d_%d" % (name, i, j),
                             [(y0, za), (y1, za), (y1, zz), (y0, zz)],
                             glass[int(rng.random() * len(glass)) % len(glass)],
                             xg, xg + 0.03, axis="x"))
    for i in range(arows):
        za = z_spring + rise * i / arows
        zz = z_spring + rise * (i + 1) / arows
        hw = arch_halfw(hs, rise, (za - z_spring) + 0.02)
        hw = max(0.06, min(hs, hw))
        for j in range(cols):
            y0 = yc - hw + 2 * hw * j / cols
            y1 = yc - hw + 2 * hw * (j + 1) / cols
            out.append(prism("%s_ga%d_%d" % (name, i, j),
                             [(y0, za), (y1, za), (y1, zz), (y0, zz)],
                             glass[int(rng.random() * len(glass)) % len(glass)],
                             xg, xg + 0.03, axis="x"))
    # ---- iron armature
    if mullion:
        out.append(bx("%s_mull" % name, Ts(x_in + 0.10, yc, (z_bot + z_spring + rise * 0.35) * 0.5),
                      (0.16, 0.15, (z_spring + rise * 0.35) - z_bot), iron, bev=0.012))
    if transom:
        zt = z_bot + (z_spring - z_bot) * 0.62
        out.append(bx("%s_tr" % name, Ts(x_in + 0.10, yc, zt),
                      (0.14, 2 * hs + 0.52, 0.11), iron, bev=0.01))
    # ---- stone surround on the inner face
    if sill:
        out.append(prism("%s_sill" % name,
                         [(yc - hs - 0.26, z_bot - 0.10), (yc + hs + 0.26, z_bot - 0.10),
                          (yc + hs + 0.26, z_bot + 0.10), (yc - hs - 0.26, z_bot + 0.10)],
                         frame_mat, x_in - 0.14, x_in + 0.34, axis="x", bev=0.02))
        for s in (-1, 1):
            y0 = yc + s * (hs + 0.02)
            y1 = yc + s * (hs + 0.26)
            out.append(prism("%s_jam%d" % (name, s), [(min(y0, y1), z_bot),
                                                      (max(y0, y1), z_bot),
                                                      (max(y0, y1), z_spring),
                                                      (min(y0, y1), z_spring)],
                             frame_mat, x_in - 0.10, x_in + 0.30, axis="x", bev=0.014))
        out += arch_ring_x("%s_ar" % name, yc, z_spring, hs + 0.14,
                           rise + 0.14, 0.26, x_in - 0.10, x_in + 0.30,
                           frame_mat, n=12, keystone=False)
    return out


def glaze_y(name, xc, w, z_bot, z_apex, y_in, y_out, glass, rng,
            frame_mat=None, mullion=True, transom=True, sill=True, rows=5,
            arows=4, cols=3, iron=None):
    """Glazed pointed window in a Y-normal wall, inner face at y_in."""
    iron = iron or frame_mat
    hs = w * 0.5
    rise = min(hs * 1.30, (z_apex - z_bot) * 0.62)
    z_spring = z_apex - rise
    out = []
    yg = y_in + (y_out - y_in) * 0.58
    for i in range(rows):
        za = z_bot + (z_spring - z_bot) * i / rows
        zz = z_bot + (z_spring - z_bot) * (i + 1) / rows
        for j in range(cols):
            x0 = xc - hs + 2 * hs * j / cols
            x1 = xc - hs + 2 * hs * (j + 1) / cols
            out.append(prism("%s_gl%d_%d" % (name, i, j),
                             [(x0, za), (x1, za), (x1, zz), (x0, zz)],
                             glass[int(rng.random() * len(glass)) % len(glass)],
                             yg, yg + 0.03, axis="y"))
    for i in range(arows):
        za = z_spring + rise * i / arows
        zz = z_spring + rise * (i + 1) / arows
        hw = max(0.06, min(hs, arch_halfw(hs, rise, (za - z_spring) + 0.02)))
        for j in range(cols):
            x0 = xc - hw + 2 * hw * j / cols
            x1 = xc - hw + 2 * hw * (j + 1) / cols
            out.append(prism("%s_ga%d_%d" % (name, i, j),
                             [(x0, za), (x1, za), (x1, zz), (x0, zz)],
                             glass[int(rng.random() * len(glass)) % len(glass)],
                             yg, yg + 0.03, axis="y"))
    if mullion:
        out.append(bx("%s_mull" % name, Ts(xc, y_in + 0.10, (z_bot + z_spring + rise * 0.35) * 0.5),
                      (0.15, 0.16, (z_spring + rise * 0.35) - z_bot), iron, bev=0.012))
    if transom:
        zt = z_bot + (z_spring - z_bot) * 0.62
        out.append(bx("%s_tr" % name, Ts(xc, y_in + 0.10, zt),
                      (2 * hs + 0.16, 0.14, 0.11), iron, bev=0.01))
    if sill:
        out.append(prism("%s_sill" % name,
                         [(xc - hs - 0.26, z_bot - 0.10), (xc + hs + 0.26, z_bot - 0.10),
                          (xc + hs + 0.26, z_bot + 0.10), (xc - hs - 0.26, z_bot + 0.10)],
                         frame_mat, y_in - 0.14, y_in + 0.34, axis="y", bev=0.02))
        for s in (-1, 1):
            x0 = xc + s * (hs + 0.02)
            x1 = xc + s * (hs + 0.26)
            out.append(prism("%s_jam%d" % (name, s), [(min(x0, x1), z_bot),
                                                      (max(x0, x1), z_bot),
                                                      (max(x0, x1), z_spring),
                                                      (min(x0, x1), z_spring)],
                             frame_mat, y_in - 0.10, y_in + 0.30, axis="y", bev=0.014))
        out += arch_ring_y("%s_ar" % name, xc, z_spring, hs + 0.14, rise + 0.14,
                           0.26, y_in - 0.10, y_in + 0.30, frame_mat, n=12,
                           keystone=False)
    return out


# ---------------------------------------------------------------------------
# floor
# ---------------------------------------------------------------------------
def floor(parts, MAT, rng):
    st = [_m(MAT, "stone_floor"), _m(MAT, "stone"), _m(MAT, "stone_dark")]
    x0, x1 = -13.8, 13.8
    y0, y1 = -25.0, 25.0
    fw = 1.55
    nx = int(math.ceil((x1 - x0) / fw))
    ny = int(math.ceil((y1 - y0) / fw))
    for i in range(nx):
        for j in range(ny):
            ax = x0 + i * fw
            ay = y0 + j * fw
            sx = min(fw, x1 - ax) - 0.035
            sy = min(fw, y1 - ay) - 0.035
            if sx < 0.2 or sy < 0.2:
                continue
            mat = st[(i * 7 + j * 3 + int(rng.random() * 2)) % 3] if (i + j) % 5 == 0 \
                else st[(i * 3 + j * 5) % 2]
            parts.append(bx("fl_%02d_%02d" % (i, j),
                            Ts(ax + sx * 0.5 + 0.017, ay + sy * 0.5 + 0.017, -0.11),
                            (sx, sy, 0.22), mat))
    # a dark border course 1 m inside the walls makes the flags read as a floor
    for (ax, ay, sx, sy) in ((0.0, -24.0, 26.4, 0.9), (0.0, 24.0, 26.4, 0.9),
                             (-12.9, 0.0, 0.9, 47.1), (12.9, 0.0, 0.9, 47.1)):
        parts.append(bx("fl_border", Ts(ax, ay, 0.0), (sx, sy, 0.03),
                        _m(MAT, "stone_dark"), bev=0.01))


# ---------------------------------------------------------------------------
# aisle: outer wall, vault, end wall
# ---------------------------------------------------------------------------
AIS_WIN = [-20.80] + [PIERS[i] + BAY * 0.5 for i in range(NBAY)]


def outer_wall(E, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_dark")
    fr = _m(MAT, "stone_light")
    x0, x1 = X_IN, HALL_W * 0.5
    y0, y1 = -26.0, Y_CHOR
    ww = 1.55
    glass = [_m(MAT, k) for k in ("glass_gold", "glass_blue", "glass_pale")]
    # band below the sills
    E.append(prism("ow_low", [(y0, 0.0), (y1, 0.0), (y1, Z_AIS_SILL),
                              (y0, Z_AIS_SILL)], st, x0, x1, axis="x"))
    # window band: wall between the openings, plus the arched head of each
    segs = []
    cur = y0
    for yc in sorted(AIS_WIN):
        segs.append((cur, yc - ww * 0.5))
        cur = yc + ww * 0.5
    segs.append((cur, y1))
    for i, (a, b) in enumerate(segs):
        if b - a > 0.02:
            E.append(prism("ow_seg%02d" % i, [(a, Z_AIS_SILL), (b, Z_AIS_SILL),
                                             (b, Z_AIS_TOP), (a, Z_AIS_TOP)],
                           st, x0, x1, axis="x"))
    z_spring = Z_AIS_TOP - ww * 0.5 * 1.30
    for i, yc in enumerate(sorted(AIS_WIN)):
        hs = ww * 0.5
        hw = hs
        E.append(prism("ow_head%02d" % i,
                       [(yc - hw, z_spring)] +
                       [(yc + x, z_spring + z) for (x, z) in arch_pts(hs, Z_AIS_TOP - z_spring, 12)
                        if abs(x) < hw - 1e-6] +
                       [(yc + hw, z_spring), (yc + hw, Z_AIS_TOP), (yc - hw, Z_AIS_TOP)],
                       st, x0, x1, axis="x"))
        E += glaze_x("ow_w%d" % i, yc, hs * 2 - 0.12, Z_AIS_SILL, Z_AIS_TOP,
                     x0, x1, glass, rng, frame_mat=sl, rows=4, arows=3, cols=2)
    # band above the windows
    E.append(prism("ow_top", [(y0, Z_AIS_TOP), (y1, Z_AIS_TOP), (y1, Z_VAULT_SPRING),
                              (y0, Z_VAULT_SPRING)], st, x0, x1, axis="x"))
    # plinth / dado / string courses on the inner face
    E.append(bx("ow_plinth", Ts(x0 - 0.06, (y0 + y1) * 0.5, 0.45),
                (0.14, y1 - y0, 0.90), sd, bev=0.02))
    E.append(bx("ow_plinth_cap", Ts(x0 - 0.10, (y0 + y1) * 0.5, 0.94),
                (0.22, y1 - y0, 0.10), sl, bev=0.02))
    E.append(bx("ow_dado", Ts(x0 - 0.04, (y0 + y1) * 0.5, 1.16),
                (0.10, y1 - y0, 0.36), sl, bev=0.015))
    E.append(bx("ow_str", Ts(x0 - 0.08, (y0 + y1) * 0.5, Z_AIS_SILL - 0.06),
                (0.18, y1 - y0, 0.16), sl, bev=0.02))
    E.append(bx("ow_corn1", Ts(x0 - 0.10, (y0 + y1) * 0.5, Z_VAULT_SPRING - 0.28),
                (0.20, y1 - y0, 0.22), sl, bev=0.02))
    E.append(bx("ow_corn2", Ts(x0 - 0.16, (y0 + y1) * 0.5, Z_VAULT_SPRING - 0.09),
                (0.30, y1 - y0, 0.14), sl, bev=0.025))
    # pilasters on the bay divisions
    for i, py in enumerate(PIERS + [-24.4]):
        if py > y1:
            continue
        E.append(bx("ow_pil%d" % i, Ts(x0 - 0.09, py, Z_VAULT_SPRING * 0.5 + 0.4),
                    (0.22, 0.86, Z_VAULT_SPRING - 0.8), st, bev=0.02))
        E.append(bx("ow_pilcap%d" % i, Ts(x0 - 0.14, py, Z_VAULT_SPRING - 0.42),
                    (0.32, 1.02, 0.22), sl, bev=0.02))
        E.append(bx("ow_pilbase%d" % i, Ts(x0 - 0.14, py, 1.42),
                    (0.32, 1.02, 0.26), sl, bev=0.02))


def aisle_vault(E, MAT, rng):
    """Pointed barrel over the aisle, springing from both walls at 7.6."""
    st = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_dark")
    hs = AISLE_W * 0.5
    rise = 2.60
    prof = arch_pts(hs, rise, 20)
    xs = [XAIS + hs + x for (x, z) in prof]
    zs = [Z_VAULT_SPRING + z for (x, z) in prof]
    rows = []
    ylist = [Y_SCREEN]
    ylist += [p for p in PIERS]
    ylist += [Y_CHOR]
    for yy in sorted(set([round(v, 3) for v in ylist])):
        rows.append([(x, yy, z) for (x, z) in zip(xs, zs)])
    E.append(quad_strip("avault", rows, st))
    # transverse ribs on the bay joints
    for i, py in enumerate(PIERS + [Y_CHOR]):
        E.append(prism("avrib%d" % i, [(XAIS + hs + x - 0.02, Z_VAULT_SPRING + z - 0.16)
                                      for (x, z) in prof],
                       sd, py - 0.16, py + 0.16, axis="y", bev=0.012))
    # a wall rib where the vault meets the outer wall
    E.append(bx("av_wr", Ts(X_IN - 0.10, (Y_SCREEN + Y_CHOR) * 0.5, Z_VAULT_SPRING + 0.06),
                (0.24, Y_CHOR - Y_SCREEN, 0.26), sd, bev=0.02))
    E.append(bx("av_wr2", Ts(XAIS + 0.06, (Y_SCREEN + Y_CHOR) * 0.5, Z_VAULT_SPRING + 0.06),
                (0.22, Y_CHOR - Y_SCREEN, 0.24), sd, bev=0.02))


def aisle_end(E, MAT, rng):
    """Transverse wall closing the aisle at the chancel, with a blind arch."""
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_shadow")
    y0, y1 = Y_CHOR, Y_CHOR + 1.6
    hw = AISLE_W * 0.5 - 0.34
    cx = (XAIS + X_IN) * 0.5
    z_spr, z_apex = 4.10, 6.30
    z_top = Z_VAULT_CROWN + 0.8
    for s in (-1, 1):
        a, b = (XAIS, cx - hw) if s < 0 else (cx + hw, X_IN)
        E.append(prism("ae_side%d" % s, [(a, 0.0), (b, 0.0), (b, z_top), (a, z_top)],
                       st, y0, y1, axis="y"))
    E.append(prism("ae_head",
                   [(cx - hw, z_spr)] +
                   [(cx + x, z_spr + z) for (x, z) in arch_pts(hw, z_apex - z_spr, 12)
                    if abs(x) < hw - 1e-6] +
                   [(cx + hw, z_spr), (cx + hw, z_top), (cx - hw, z_top)],
                   st, y0, y1, axis="y"))
    # recessed dark panel + arch ring so the aisle does not just stop dead
    E.append(prism("ae_back", [(cx + x, z) for (x, z) in
                               hole_pts(hw, 0.0, z_spr, z_apex, 12)], sd,
                   y0 + 0.28, y0 + 0.34, axis="y"))
    E += arch_ring_y("ae_ring", cx, z_spr, hw, z_apex - z_spr, 0.26,
                     y0 - 0.08, y0 + 0.06, sl, n=12, keystone=True)


# ---------------------------------------------------------------------------
# arcade: piers, arches, clerestory, high windows
# ---------------------------------------------------------------------------
def pier(E, MAT, py, rng, nm):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_dark")
    wd = _m(MAT, "wood_dark")
    cx = XARC
    # plinth and base mouldings
    E.append(bx(nm + "_pl", Ts(cx, py, 0.14), (1.34, 2.00, 0.28), sd, bev=0.02))
    E.append(bx(nm + "_pl2", Ts(cx, py, 0.30), (1.28, 1.94, 0.08), sl, bev=0.015))
    E.append(bx(nm + "_base", Ts(cx, py, 0.49), (1.20, 1.84, 0.30), st, bev=0.025))
    E.append(frustum(nm + "_basef", Ts(cx, py, 0.64), (1.22, 1.86), (1.16, 1.80),
                     0.12, sl, bev=0.015))
    # shaft
    E.append(bx(nm + "_shaft", Ts(cx, py, (0.76 + 6.90) * 0.5),
                (1.10, 1.52, 6.90 - 0.76), st, bev=0.02))
    # four engaged colonnettes (clustered pier read)
    for k, (ox, oy) in enumerate(((0.0, -0.76), (0.0, 0.76),
                                  (-0.55, 0.0), (0.55, 0.0))):
        E.append(cyl(nm + "_col%d" % k, Ts(cx + ox, py + oy, (0.78 + 6.86) * 0.5),
                     0.155, 6.86 - 0.78, sl, seg=12, bev=0.0))
        E.append(cyl(nm + "_colb%d" % k, Ts(cx + ox, py + oy, 0.84), 0.19, 0.18,
                     sd, seg=12))
        E.append(cyl(nm + "_colc%d" % k, Ts(cx + ox, py + oy, 6.80), 0.21, 0.16,
                     sl, seg=12))
    # necking, bell, acanthus leaves, abacus
    E.append(bx(nm + "_neck", Ts(cx, py, 6.98), (1.14, 1.56, 0.12), sd, bev=0.015))
    E.append(frustum(nm + "_bell", Ts(cx, py, 7.04), (1.16, 1.58), (1.46, 1.92),
                     0.44, sl, bev=0.015))
    leaf = [(0.0, 0.0), (0.08, 0.16), (0.006, 0.30), (0.0, 0.45),
            (-0.006, 0.30), (-0.08, 0.16)]
    for k, (dxa, dya, r0) in enumerate(((1, 0, 0.55), (-1, 0, 0.55),
                                        (0, 1, 0.765), (0, -1, 0.765))):
        ang = math.atan2(dya, dxa)
        for s in (-1, 1):
            mx = cx + dxa * r0 - dya * s * 0.40
            my = py + dya * r0 + dxa * s * 0.40
            E.append(prism(nm + "_lf%d_%d" % (k, s), leaf, sd, -0.045, 0.05,
                           axis="x", T=Ts(mx, my, 7.02, rz=ang)))
    E.append(bx(nm + "_abacus", Ts(cx, py, 7.55), (1.50, 1.96, 0.18), sl, bev=0.02))
    E.append(bx(nm + "_abacus2", Ts(cx, py, 7.66), (1.38, 1.84, 0.06), st, bev=0.012))
    # a little carved band on the nave face of the abacus
    E.append(bx(nm + "_carve", Ts(XNAVE + 0.02, py, 7.55), (0.03, 1.60, 0.10),
                wd, bev=0.008))


def arcade(E, MAT, rng):
    st = _m(MAT, "stone")
    sl = _m(MAT, "stone_light")
    sd = _m(MAT, "stone_dark")
    sh = _m(MAT, "stone_shadow")
    fr = _m(MAT, "stone_light")
    glass = [_m(MAT, k) for k in ("glass_gold", "glass_blue", "glass_red",
                                  "glass_pale")]
    for i, py in enumerate(PIERS):
        pier(E, MAT, py, rng, "pr%d" % i)
    x0, x1 = XNAVE, XAIS
    for i in range(NBAY):
        yc = PIERS[i] + BAY * 0.5
        # arch ring, projecting a little on both faces
        E += arch_ring_x("ar%d" % i, yc, Z_CAP, HS_ARC, RISE_ARC, 0.46,
                         x0 - 0.06, x1 + 0.06, sl, n=14, keystone=True)
        # spandrel panel: bay rectangle with the arch extrados bitten out
        E.append(prism("sp%d" % i,
                       spandrel_pts(BAY * 0.5, Z_CAP - 0.02, Z_CLER_SILL,
                                    HS_ARC + 0.46, Z_CAP, RISE_ARC + 0.46, 14),
                       st, x0, x1, axis="x"))
        # clerestory window: jamb strips + head, glass, surround
        ehw = 1.88
        z_top = Z_CLER_TOP
        w_apex = 15.62
        rise = 1.30 * 1.60
        z_spring = w_apex - rise
        for s in (-1, 1):
            a = yc + s * ehw
            b = yc + s * (BAY * 0.5)
            E.append(prism("cw_j%d_%d" % (i, s),
                           [(min(a, b), Z_CLER_SILL), (max(a, b), Z_CLER_SILL),
                            (max(a, b), z_top), (min(a, b), z_top)], st, x0, x1,
                           axis="x"))
        E.append(prism("cw_h%d" % i,
                       [(yc - ehw, z_spring)] +
                       [(yc + x, z_spring + z) for (x, z) in
                        arch_pts(1.60 + 0.28, w_apex - z_spring + 0.28, 12)
                        if abs(x) < ehw - 1e-6] +
                       [(yc + ehw, z_spring), (yc + ehw, z_top), (yc - ehw, z_top)],
                       st, x0, x1, axis="x"))
        E += glaze_x("cw%d" % i, yc, 3.20, Z_CLER_SILL, w_apex, x0, x1, glass, rng,
                     frame_mat=fr, rows=5, arows=4, cols=3)
        # a hood mould tying the window into the wall
        E += arch_ring_x("cwh%d" % i, yc, z_spring, 1.60 + 0.30, rise + 0.30, 0.22,
                         x0 - 0.06, x0 + 0.16, sl, n=12, keystone=True)
    # continuous course over the arcade and under the wall plate
    E.append(bx("arc_str", Ts(XNAVE - 0.12, (Y_SCREEN + Y_CHOR) * 0.5, Z_CLER_SILL - 0.09),
                (0.30, Y_CHOR - Y_SCREEN, 0.18), sl, bev=0.02))
    E.append(bx("arc_corn1", Ts(XNAVE - 0.10, (Y_SCREEN + Y_CHOR) * 0.5, Z_PLATE - 0.34),
                (0.24, Y_CHOR - Y_SCREEN, 0.20), sl, bev=0.02))
    E.append(bx("arc_corn2", Ts(XNAVE - 0.16, (Y_SCREEN + Y_CHOR) * 0.5, Z_PLATE - 0.18),
                (0.36, Y_CHOR - Y_SCREEN, 0.14), sl, bev=0.02))
    # aisle-side string course (the vault springs off it)
    E.append(bx("ais_corn", Ts(XAIS + 0.10, (Y_SCREEN + Y_CHOR) * 0.5, Z_PLATE - 0.20),
                (0.24, Y_CHOR - Y_SCREEN, 0.20), sl, bev=0.02))
    # wall pier above each arcade pier (the truss seats on it)
    for i, py in enumerate(PIERS):
        E.append(bx("cl_pil%d" % i, Ts(XNAVE - 0.04, py, (Z_CLER_SILL + Z_PLATE) * 0.5),
                    (0.12, 0.42, Z_PLATE - Z_CLER_SILL), sl, bev=0.012))
    return
