# -*- coding: utf-8 -*-
"""Round-3b patch: tapestries, heraldry, wall sconces, rood-screen medallions,
   and the reworked interior lighting."""
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


ADD = r'''

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
            fs.append((a, b, b + 1, a + 1))
    ob = K.mesh_obj(nm, vs, fs, smooth=True)
    K.assign(ob, mat)
    ob.data.transform(T)
    return [ob]


def tapestry(nm, T, w, h, MAT, rng, cloth_key="tapestry", cols=8, rows=6,
             border=True, rod=True):
    out = cloth(nm, T, w, h, _m(MAT, cloth_key), cols=cols, rows=rows)
    gm = _m(MAT, "cloth_gold")
    wd = _m(MAT, "wood_dark")
    if border:
        for sx, sz, bw, bh in ((0, 1, w, 0.13), (0, -1, w, 0.13),
                               (-1, 0, 0.13, h), (1, 0, 0.13, h)):
            out.append(bx("%s_bd%d%d" % (nm, sx, sz),
                          T @ Ts(sx * (w * 0.5 - bw * 0.5),
                                 -0.02,
                                 sz * (h * 0.5 - bh * 0.5)),
                          (bw, 0.035, bh), gm, bev=0.008))
    if rod:
        out.append(cyl("%s_rod" % nm, T @ Ts(0.0, 0.02, h * 0.5 + 0.09, rz=0.0,
                                             ry=math.pi * 0.5),
                       w * 0.5 + 0.16, 1.0, wd, seg=10))
        out[-1].data.transform(Matrix())
        for k in (-1, 0, 1):
            out.append(torus("%s_rg%d" % (nm, k),
                             T @ Ts(k * w * 0.30, 0.02, h * 0.5 + 0.03),
                             0.055, 0.016, _m(MAT, "iron"), seg=10, ring=4))
    return out


def heraldry(C, MAT, rng):
    """Great heraldic cloth over the throne, two flags flanking it."""
    y0 = Y_BACK
    gm = _m(MAT, "gold")
    wd = _m(MAT, "wood_dark")
    # ---- the big cloth, hung on a rod above the aedicule arch
    C += tapestry("hw_tap", Ts(0.0, y0 - 0.08, 9.10, rz=0.0), 4.60, 3.30, MAT,
                  rng, cloth_key="tapestry_blue", cols=10, rows=7)
    # ---- heraldic charge: crowned sword on a sun disc
    C.append(cyl("hw_disc", Ts(0.0, y0 - 0.16, 9.10, ry=math.pi * 0.5),
                 0.86, 0.05, _m(MAT, "cloth_gold"), seg=24))
    for k in range(12):
        a = k * math.pi / 6.0
        C.append(bx("hw_ray%d" % k,
                    Ts(math.sin(a) * 1.02, y0 - 0.13, 9.10 + math.cos(a) * 1.02,
                       rz=0.0),
                    (0.16, 0.05, 0.30, ), gm, bev=0.01))
        C.rotate if False else None
    C.append(bx("hw_sw", Ts(0.0, y0 - 0.17, 9.06), (0.15, 0.06, 1.44), gm,
                bev=0.01))
    C.append(bx("hw_gd", Ts(0.0, y0 - 0.17, 8.62), (0.62, 0.07, 0.10), gm,
                bev=0.01))
    C.append(bx("hw_pm", Ts(0.0, y0 - 0.17, 8.18), (0.10, 0.07, 0.34), gm,
                bev=0.01))
    C.append(torus("hw_cr", Ts(0.0, y0 - 0.17, 9.86, ry=math.pi * 0.5),
                   0.24, 0.045, gm, seg=16, ring=5))
    for k, xx in enumerate((-0.20, 0.0, 0.20)):
        C.append(K.cone("hw_cp%d" % k, Ts(xx, y0 - 0.17, 10.18), 0.075, 0.26,
                        gm, seg=8))
    # ---- two flags on poles flanking the dais
    for s in (-1, 1):
        px = s * 3.55
        C.append(cyl("hw_pol%d" % s, Ts(px, y0 - 0.72, 5.40), 0.075, 9.10, wd,
                     seg=10))
        C.append(sphere("hw_pf%d" % s, Ts(px, y0 - 0.72, 10.02), 0.16, gm,
                        seg=12, ring=8))
        C += cloth("hw_fb%d" % s, Ts(px + s * 0.60, y0 - 0.80, 8.55,
                                    rz=math.pi * 0.5),
                   1.22, 2.85, _m(MAT, "cloth_blue" if s > 0 else "cloth_red"),
                   cols=6, rows=8, wave=0.07, sag=0.14)
        for k in range(5):
            zz = 7.10 + k * 0.10
            C.append(bx("hw_ff%d_%d" % (s, k), Ts(px + s * 1.18, y0 - 0.80, zz),
                        (0.10, 0.03, 0.05), gm, bev=0.006))
    # ---- aisle cloths on the outer wall, one per bay
    for yc in AIS_WIN:
        for s in (-1, 1):
            E_ = []
            key = "tapestry" if ((yc * 100) % 2 > 1) else "tapestry_blue"
            E_ += tapestry("aw_tap%d_%d" % (int(yc * 10), s),
                           Ts(s * (X_IN - 0.09), yc, 4.85, rz=s * math.pi * 0.5),
                           3.30, 3.60, MAT, rng, cloth_key=key, cols=7, rows=6)
            C.extend(E_)


def sconces(E, MAT, rng):
    """Iron wall sconces on the nave face of every pier."""
    iron = _m(MAT, "iron")
    cm = _m(MAT, "candle")
    fm = _m(MAT, "fire")
    for py in PIERS:
        for z, dz in ((4.30, 1), (8.10, -1)):
            E.append(bx("sc_pl%d_%d" % (int(py * 10), int(z * 10)),
                        Ts(XNAVE - 0.04, py, z), (0.10, 0.34, 0.62), iron,
                        bev=0.012))
            E.append(rod("sc_ar%d_%d" % (int(py * 10), int(z * 10)),
                         (XNAVE - 0.10, py, z + 0.24),
                         (XNAVE + 0.42, py, z + 0.30), 0.028, iron, seg=6))
            E.append(cyl("sc_cp%d_%d" % (int(py * 10), int(z * 10)),
                         Ts(XNAVE + 0.42, py, z + 0.36), 0.115, 0.10, iron,
                         seg=10, r2=0.055))
            E.append(cyl("sc_cd%d_%d" % (int(py * 10), int(z * 10)),
                         Ts(XNAVE + 0.42, py, z + 0.62), 0.052, 0.44, cm, seg=8))
            E.append(K.cone("sc_fl%d_%d" % (int(py * 10), int(z * 10)),
                            Ts(XNAVE + 0.42, py, z + 0.91), 0.040, 0.13, fm,
                            seg=8))
'''

t = load("_cint_p3.py")
if "def heraldry" not in t:
    t = t.rstrip("\n") + ADD + "\n"
save("_cint_p3.py", t)
print("APPENDED p3", len(t))

# ---------------------------------------------------------------------------
# p4: call the new passes + rework the lighting
# ---------------------------------------------------------------------------
t = load("_cint_p4.py")
t = rep(t, "    back_wall(C)\n", "    back_wall(C)\n    heraldry(C, MAT, rng)\n"
                                "    sconces(E, MAT, rng)\n")
t = rep(t, '''    _sun("SUN", (-0.54, 0.40, -0.74), energy=5.0, angle=1.0)
    # ---- interior fill
    _area("FILL_NAVE", (0.0, 3.0, 13.60), (10.0, 8.0), 2400.0, (0.0, 0.0, 0.0))
    _area("FILL_ENTRY", (0.0, -13.50, 12.40), (8.0, 6.0), 1500.0, (0.0, 0.0, 0.0))
    _area("FILL_DAIS", (0.0, 14.00, 13.20), (7.0, 6.0), 1800.0,
          (math.radians(18.0), 0.0, 0.0), color=(1.0, 0.90, 0.78))''',
        '''    _sun("SUN", (-0.62, -0.26, -0.72), energy=9.5, angle=0.55)
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
          (math.pi, 0.0, 0.0), color=(1.0, 0.88, 0.74))''')
t = rep(t, '''    box = K.box("VOL", Ts(0.0, 0.0, 8.85), (18.4, 50.6, 17.70), vol)
    box.data.materials.clear()
    box.data.materials.append(_volume_mat())''',
        '''    box = K.box("VOL", Ts(0.0, 0.0, 8.85), (18.4, 50.6, 17.70), vol)
    box.data.materials.clear()
    box.data.materials.append(_volume_mat(0.0072, 0.62))''')
t = rep(t, '''    bg.inputs[0].default_value = (0.52, 0.66, 0.86, 1.0)
    bg.inputs[1].default_value = 1.15''',
        '''    bg.inputs[0].default_value = (0.44, 0.60, 0.86, 1.0)
    bg.inputs[1].default_value = 0.85''')
t = rep(t, '''        ("f_diag", (-6.90, -11.60, 1.72), (0.60, 10.00, 4.40), 30.0),''',
        '''        ("f_diag", (-6.90, -11.60, 1.72), (0.60, 10.00, 4.40), 30.0),
        ("g_roof", (0.0, 3.40, 1.70), (0.0, 8.60, 16.40), 17.0),''')
save("_cint_p4.py", t)
print("PATCHED p4", len(t))
