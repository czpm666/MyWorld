# -*- coding: utf-8 -*-
"""Round-3 detail pass: dais balustrade, aisle benches, arch orders,
   porch blind arcade, roof purlins; plus joint fixes from the audit."""
import io
import os

D = r"E:\My World\Blender\kingdom"


def load(fn):
    return io.open(os.path.join(D, fn), encoding="utf-8").read()


def save(fn, t):
    io.open(os.path.join(D, fn), "w", encoding="utf-8", newline="\n").write(t)


def rep(t, old, new, n=1):
    if t.count(old) != n:
        raise SystemExit("marker %dx: %r" % (t.count(old), old[:70]))
    return t.replace(old, new)


# ---------------------------------------------------------------- p2: transoms
t = load("_cint_p2.py")
t = rep(t, '            (0.14, 2 * hs + 0.16, 0.11), iron, bev=0.01))',
        '            (0.14, 2 * hs + 0.52, 0.11), iron, bev=0.01))')
save("_cint_p2.py", t)
print("PATCHED p2", len(t))

# ---------------------------------------------------------------- p3: joints
t = load("_cint_p3.py")
t = rep(t, '''                          T @ Ts(sx * (w * 0.5 - bw * 0.5), 0.02,''',
        '''                          T @ Ts(sx * (w * 0.5 - bw * 0.5), 0.035,''')
t = rep(t, '''        out.append(cyl("%s_rod" % nm, T @ Ts(0.0, 0.03, h * 0.5 + 0.10,''',
        '''        out.append(cyl("%s_rod" % nm, T @ Ts(0.0, 0.02, h * 0.5 + 0.04,''')
t = rep(t, '''                    Ts(math.sin(a) * 0.98, y0 - 0.15, 9.16 + math.cos(a) * 0.98,''',
        '''                    Ts(math.sin(a) * 0.93, y0 - 0.15, 9.16 + math.cos(a) * 0.93,''')
t = rep(t, '''        C.append(K.sphere("hw_pf%d" % s, Ts(px, y0 - 0.78, 10.00), 0.15, gm,''',
        '''        C.append(K.sphere("hw_pf%d" % s, Ts(px, y0 - 0.78, 9.93), 0.15, gm,''')
t = rep(t, '''                        Ts(px - s * 1.24, y0 - 0.86, 7.20 + k * 0.10),''',
        '''                        Ts(px - s * 1.27, y0 - 0.83, 7.16 + k * 0.10),''')
t = rep(t, '''        E += tapestry("aw_tap%d" % i, Ts(X_IN - 0.10, yc, 4.90,''',
        '''        E += tapestry("aw_tap%d" % i, Ts(X_IN - 0.06, yc, 4.90,''')

ADD = r'''

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
        E += arch_ring_y("pz_br%d" % j, yc, 4.30, 0.86, 1.30, 0.24,
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
'''

t = t.rstrip("\n") + ADD + "\n"
save("_cint_p3.py", t)
print("APPENDED p3", len(t))

# ---------------------------------------------------------------- p4: call it
t = load("_cint_p4.py")
t = rep(t, "    sconces(E, MAT, rng)\n",
        "    sconces(E, MAT, rng)\n    detail(C, E, MAT, rng)\n")
save("_cint_p4.py", t)
print("PATCHED p4", len(t))

# ---------------------------------------------------------------- test: audit
P = os.path.join(D, "_cint_test.py")
t = io.open(P, encoding="utf-8").read()
t = rep(t, "    if lo[2] <= 1.10 and hi[2] >= 0.30 and 1.80 < lo[0] < 8.75 and hi[0] < 8.78:",
        "    if hi[2] <= 1.32 and 2.00 < lo[0] < 8.75 and hi[0] < 8.78:")
t = rep(t, '''    vs = [mw @ v.co for v in o.data.vertices]
    if not vs:
        continue
    vs.sort(key=lambda c: c.z)
    if len(vs) > 26:
        sample = vs[:8] + vs[-8:] + vs[len(vs) // 2 - 5:len(vs) // 2 + 5]
    else:
        sample = vs''',
        '''    me2 = o.data
    me2.calc_loop_triangles()
    vs = [mw @ v.co for v in me2.vertices]
    vs += [mw @ ((me2.vertices[lt.vertices[0]].co
                  + me2.vertices[lt.vertices[1]].co
                  + me2.vertices[lt.vertices[2]].co) / 3.0)
           for lt in me2.loop_triangles[:40]]
    if not vs:
        continue
    if len(vs) > 60:
        vs.sort(key=lambda c: c.z)
        sample = vs[::max(1, len(vs) // 60)][:60]
    else:
        sample = vs''')
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("PATCHED test", len(t))
