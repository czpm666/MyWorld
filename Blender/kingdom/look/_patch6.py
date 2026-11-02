import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def cut(a, b, new, tag):
    global s
    i = s.index(a)
    j = s.index(b, i)
    s = s[:i] + new + s[j:]
    print("cut", tag)


# ---------------------------------------------------------------- floor: one mesh
i = s.index("    pw, pd = 1.02, 0.68")
j = s.index("    # a band of darker paving")
s = s[:i] + '''    pw, pd = 1.02, 0.68
    nx = int(round(2 * HX / pw))
    ny = int(round(2 * HY / pd))
    sx, sy = 2 * HX / nx, 2 * HY / ny
    verts, faces = [], []
    ztop, zbot = 0.0, -0.13
    for j2 in range(ny):
        off = 0.5 * sx if j2 % 2 else 0.0
        for i2 in range(nx + 1):
            x0 = -HX + i2 * sx - off
            x1 = x0 + sx
            if x1 <= -HX or x0 >= HX:
                continue
            x0 = max(x0, -HX) + 0.009
            x1 = min(x1, HX) - 0.009
            y0 = -HY + j2 * sy + 0.009
            y1 = -HY + (j2 + 1) * sy - 0.009
            b = len(verts)
            for zz in (zbot, ztop):
                verts.append((x0, y0, zz))
                verts.append((x1, y0, zz))
                verts.append((x1, y1, zz))
                verts.append((x0, y1, zz))
            faces.append((b + 0, b + 3, b + 2, b + 1))
            faces.append((b + 4, b + 5, b + 6, b + 7))
            faces.append((b + 0, b + 1, b + 5, b + 4))
            faces.append((b + 1, b + 2, b + 6, b + 5))
            faces.append((b + 2, b + 3, b + 7, b + 6))
            faces.append((b + 3, b + 0, b + 4, b + 7))
    ob = K.mesh_obj("ci_flags", verts, faces)
    K.assign(ob, _m(M, "stone_floor"))
    P.append(ob)
''' + s[j:]
print("cut floor")

# ---------------------------------------------------------------- armour
i = s.index("def build_armour(")
j = s.index("def build_guards(")
s = s[:i] + '''def build_armour(nm, T, M, face=1.0, halberd=True):
    """A knight's harness on a stand: narrow waisted plate, ~2.10 m overall."""
    P = []
    stl = _m(M, "steel")
    ir = _m(M, "iron")
    wd = _m(M, "wood_dark")
    le = _m(M, "leather")
    P.append(bx(nm + "_base", T @ Ts(0, 0, 0.05), (0.78, 0.78, 0.10),
                _m(M, "stone_dark"), bev=0.014))
    P.append(bx(nm + "_stand", T @ Ts(0, 0, 0.12), (0.34, 0.20, 0.06), ir, bev=0.006))
    P.append(bx(nm + "_post", T @ Ts(0, 0, 0.86), (0.10, 0.10, 1.48), wd))
    for s2 in (-1, 1):
        # legs: greave, knee cop, sabaton
        P.append(cyl(nm + "_greave", T @ Ts(0.0, s2 * 0.125, 0.52), 0.078, 0.56, stl,
                     seg=9))
        P.append(sph(nm + "_knee", T @ Ts(0.01, s2 * 0.125, 0.80), 0.090, stl,
                     seg=9, ring=5, squash=0.9))
        P.append(bx(nm + "_cuisse", T @ Ts(0.0, s2 * 0.125, 0.94), (0.20, 0.17, 0.22),
                    stl, bev=0.018))
        P.append(bx(nm + "_sabat", T @ Ts(0.055, s2 * 0.125, 0.215), (0.30, 0.15, 0.09),
                    stl, bev=0.014))
        # arm: vambrace, elbow, gauntlet
        P.append(cyl(nm + "_vamb", T @ Ts(0.015, s2 * 0.255, 1.34, rx=s2 * 0.10),
                     0.052, 0.38, stl, seg=8))
        P.append(sph(nm + "_elb", T @ Ts(0.02, s2 * 0.265, 1.16), 0.065, stl,
                     seg=8, ring=5))
        P.append(sph(nm + "_gaunt", T @ Ts(0.035, s2 * 0.270, 1.06), 0.070, stl,
                     seg=8, ring=6, squash=1.15))
        # pauldron over the shoulder
        P.append(sph(nm + "_pauld", T @ Ts(0.005, s2 * 0.215, 1.60), 0.125, stl,
                     seg=11, ring=7, squash=0.78))
        P.append(bx(nm + "_pauld_l", T @ Ts(0.0, s2 * 0.245, 1.53), (0.15, 0.09, 0.10),
                    stl, bev=0.020))
    # cuirass: waist, breast, back
    P.append(bx(nm + "_fauld", T @ Ts(0, 0, 1.03), (0.28, 0.40, 0.17), stl, bev=0.024))
    P.append(bx(nm + "_belt", T @ Ts(0, 0, 1.13), (0.29, 0.42, 0.06), le))
    P.append(sph(nm + "_breast", T @ Ts(0.01, 0, 1.42), 0.205, stl, seg=13, ring=9,
                 squash=1.42))
    P.append(bx(nm + "_ridge", T @ Ts(0.145, 0, 1.44), (0.06, 0.10, 0.46), stl,
                bev=0.016))
    # gorget, helm, visor, crest
    P.append(cyl(nm + "_gorget", T @ Ts(0, 0, 1.74), 0.098, 0.10, stl, seg=11))
    P.append(cyl(nm + "_helm", T @ Ts(0, 0, 1.88), 0.128, 0.19, stl, seg=13, r2=0.120))
    P.append(sph(nm + "_helm_t", T @ Ts(0, 0, 1.955), 0.128, stl, seg=13, ring=7,
                 squash=0.85))
    P.append(bx(nm + "_eyeg", T @ Ts(0.108, 0, 1.905), (0.05, 0.19, 0.030), ir))
    P.append(bx(nm + "_nasal", T @ Ts(0.122, 0, 1.875), (0.035, 0.045, 0.14), ir,
                bev=0.006))
    P.append(cyl(nm + "_plume", T @ Ts(0, 0, 2.06), 0.032, 0.20, _m(M, "cloth_red"),
                 seg=7, r2=0.012))
    if halberd:
        P.append(cyl(nm + "_shaft", T @ Ts(0.24, 0.30, 1.30), 0.028, 2.62, wd, seg=7))
        P.append(cyl(nm + "_spike", T @ Ts(0.24, 0.30, 2.74), 0.038, 0.30, stl, seg=7,
                     r2=0.005))
        P.append(prism_y(nm + "_axe", T @ Ts(0.24, 0.30, 2.52),
                         [(-0.24, 0.09), (0.09, 0.18), (0.12, -0.12), (-0.22, -0.09)],
                         0.045, stl, bev=0.005))
    return P


''' + s[j:]
print("cut armour")

# ---------------------------------------------------------------- chandelier rings
a = '''    P.append(cyl("ci_ch_ring", Ts(cx, cy, cz), 1.36, 0.10, ir, seg=28, r2=1.36))
    P.append(cyl("ci_ch_ring2", Ts(cx, cy, cz - 0.34), 1.06, 0.07, ir, seg=28))'''
b = '''    for k in range(26):
        aa = TAU * k / 26.0
        chord = 2.0 * 1.34 * math.tan(math.pi / 26.0) * 1.05
        P.append(bx("ci_ch_ring", Ts(cx + 1.34 * math.cos(aa), cy + 1.34 * math.sin(aa),
                                     cz, rz=aa), (0.055, chord, 0.10), ir, bev=0.004))
    for k in range(20):
        aa = TAU * k / 20.0
        chord = 2.0 * 1.04 * math.tan(math.pi / 20.0) * 1.05
        P.append(bx("ci_ch_ring2", Ts(cx + 1.04 * math.cos(aa), cy + 1.04 * math.sin(aa),
                                      cz - 0.34, rz=aa), (0.045, chord, 0.07), ir,
                    bev=0.004))'''
assert a in s
s = s.replace(a, b)

# ---------------------------------------------------------------- torch niches
i = s.index("    # ---- torches in niches up the shaft")
j = s.index("    # ---- the lantern at the head of the shaft")
s = s[:i] + '''    # ---- torches on iron brackets in shallow niches up the shaft
    rn = ri - 0.02
    rf = ri - 0.17
    for k in range(9):
        i2 = 6 + k * 12
        a = ST_A0 + i2 * ST_STEP_A
        z = ST_RISE * (i2 + 1) + 1.70
        P.append(bx("ci_st_niche", Ts(cx + rn * math.cos(a), cy + rn * math.sin(a), z,
                                      rz=a), (0.07, 0.56, 0.94), sd))
        for da in (-1, 1):
            aa = a + da * 0.32 / rn
            P.append(bx("ci_st_nch_c", Ts(cx + (rn - 0.05) * math.cos(aa),
                                          cy + (rn - 0.05) * math.sin(aa), z, rz=aa),
                        (0.15, 0.09, 1.00), sl, bev=0.008))
        P.append(bx("ci_st_nch_h", Ts(cx + (rn - 0.03) * math.cos(a),
                                      cy + (rn - 0.03) * math.sin(a), z + 0.55, rz=a),
                    (0.20, 0.72, 0.13), sl, bev=0.010))
        P.append(bx("ci_st_brack", Ts(cx + rf * math.cos(a), cy + rf * math.sin(a),
                                      z - 0.06, rz=a), (0.26, 0.07, 0.07), ir))
        P.append(cyl("ci_st_torch", Ts(cx + rf * math.cos(a), cy + rf * math.sin(a),
                                       z - 0.04), 0.044, 0.72, wd, seg=8))
        P.append(sph("ci_st_flame", Ts(cx + rf * math.cos(a), cy + rf * math.sin(a),
                                       z + 0.38), 0.115, _m(M, "fire"), 8, 5, 1.9))
''' + s[j:]
print("cut niche")

# ---------------------------------------------------------------- torch lights
a = '''        rr = ST_R - 0.28
        L = bpy.data.lights.new("ci_st_light", "POINT")
        L.energy = 470.0
        L.shadow_soft_size = 0.12
        L.color = fire
        o = bpy.data.objects.new("ci_st_light", L)
        o.location = (ST_CX + rr * math.cos(a), ST_CY + rr * math.sin(a), z + 2.05)'''
b = '''        rr = ST_RIN - 0.16
        L = bpy.data.lights.new("ci_st_light", "POINT")
        L.energy = 520.0
        L.shadow_soft_size = 0.13
        L.color = fire
        o = bpy.data.objects.new("ci_st_light", L)
        o.location = (ST_CX + rr * math.cos(a), ST_CY + rr * math.sin(a), z + 2.08)'''
assert a in s
s = s.replace(a, b)

# ---------------------------------------------------------------- hearth light
a = '''    L.energy = 3200.0
    L.shadow_soft_size = 0.55
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.85, 0.0, FZ0 + 0.95)'''
b = '''    L.energy = 4200.0
    L.shadow_soft_size = 0.50
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.55, 0.0, FZ0 + 0.80)'''
assert a in s
s = s.replace(a, b)
a = '''    # chandelier
    L = bpy.data.lights.new("ci_ch_light", "POINT")'''
b = '''    L = bpy.data.lights.new("ci_fp_in", "POINT")
    L.energy = 900.0
    L.shadow_soft_size = 0.30
    L.color = fire
    o = bpy.data.objects.new("ci_fp_in", L)
    o.location = (-HX - 0.30, 0.0, FZ0 + 0.60)
    K.link(o)
    P.append(o)
    # chandelier
    L = bpy.data.lights.new("ci_ch_light", "POINT")'''
assert a in s
s = s.replace(a, b)

# ---------------------------------------------------------------- stone floor look
a = '''                               bw=1.02, bh=0.68, ms=0.016, rough=0.52, bump=0.42,
                               grime=0.5)'''
b = '''                               bw=1.02, bh=0.68, ms=0.016, rough=0.80, bump=0.18,
                               grime=0.5)'''
assert a in s
s = s.replace(a, b)

# ---------------------------------------------------------------- cameras
i = s.index("        shots = [")
j = s.index("    for (nm, loc, look, lens) in shots:")
s = s[:i] + '''        shots = [
            ("A_door", (HX - 2.6, 0.0, EYE), (-HX + 1.2, 0.0, 3.00), 28.0),
            ("B_throne", (-4.0, 2.30, 2.45), (-11.35, 0.10, 2.62), 33.0),
            ("C_feast", (-6.2, -6.3, FZ0 + 1.68), (-12.6, -0.20, FZ0 + 2.05), 30.0),
            ("D_stair", (ST_CX + 0.34, ST_CY + 0.24, 9.60),
             (ST_CX - 2.30, ST_CY - 2.20, 4.30), 16.0),
            ("E_torch", (ST_CX + 1.60 * math.cos(math.radians(278.0)),
                         ST_CY + 1.60 * math.sin(math.radians(278.0)), 2.60),
             (ST_CX + 2.86 * math.cos(math.radians(278.0)),
              ST_CY + 2.86 * math.sin(math.radians(278.0)), 3.05), 35.0),
            ("F_shaft", (-10.5, -5.5, 1.72), (6.0, 2.0, 7.0), 20.0),
        ]
''' + s[j:]

# ---------------------------------------------------------------- fire strength
s = s.replace("strn = 16.0", "strn = 34.0")

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED", s.count("\n") + 1)
