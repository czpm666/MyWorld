import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def rep(a, b, tag, n=1):
    global s
    assert a in s, tag
    s = s.replace(a, b, n)
    print("rep", tag)


rep('M["fire"] = _emit("int_fire", "#ff8a2a", 34.0)',
    'M["fire"] = _emit("int_fire", "#ff8a2a", 20.0)', "fire")

# ---- flames as tongues of fire, not flat cards
i = s.index("    # ---- flame tongues, two staggered rows so the fire has depth")
j = s.index("    return P", i)
s = s[:i] + '''    # ---- flame tongues: cones, so the fire reads from any angle
    for k in range(13):
        xx = -1.06 + 0.176 * k
        h = rng.uniform(0.55, 1.25)
        yy = DP * 0.40 + (0.16 if k % 2 else -0.07) + rng.uniform(-0.05, 0.05)
        rr = rng.uniform(0.075, 0.115)
        P.append(cyl("ci_fp_flame", T @ Ts(xx + rng.uniform(-0.04, 0.04), yy,
                                          FZ0 + 0.20),
                     rr, h, fi, seg=7, r2=0.010))
    for k in range(5):
        xx = -0.6 + 0.30 * k
        P.append(cyl("ci_fp_flame2", T @ Ts(xx, DP * 0.40 + rng.uniform(-0.1, 0.1),
                                           FZ0 + 0.16),
                     0.055, rng.uniform(0.24, 0.40), fi, seg=6, r2=0.006))
''' + s[j:]
print("cut flames")

rep("""        rr = ST_RIN - 0.16
        L = bpy.data.lights.new("ci_st_light", "POINT")
        L.energy = 520.0
        L.shadow_soft_size = 0.13""",
    """        rr = ST_RIN - 0.42
        L = bpy.data.lights.new("ci_st_light", "POINT")
        L.energy = 340.0
        L.shadow_soft_size = 0.20""", "torch light")

rep("""    L.energy = 4200.0
    L.shadow_soft_size = 0.50
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.55, 0.0, FZ0 + 0.80)""",
    """    L.energy = 3000.0
    L.shadow_soft_size = 0.55
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.62, 0.0, FZ0 + 1.00)""", "hearth light")

rep("sd.energy = 55.0", "sd.energy = 130.0", "sun")
rep('vol.inputs["Density"].default_value = 0.0045',
    'vol.inputs["Density"].default_value = 0.0055', "fog")
rep("L.energy = 2600.0", "L.energy = 3400.0", "throne key")

rep('''                              bw=1.18, bh=0.47, grime=0.42)''',
    '''                              bw=1.40, bh=0.50, grime=0.26, bump=0.16)''', "wall ashlar")

i = s.index("        shots = [")
j = s.index("    for (nm, loc, look, lens) in shots:")
s = s[:i] + '''        shots = [
            ("A_door", (6.0, 0.0, EYE), (-HX + 1.2, 0.0, 2.90), 40.0),
            ("B_throne", (-4.0, 2.30, 2.45), (-11.35, 0.10, 2.62), 33.0),
            ("C_feast", (-4.6, -6.0, FZ0 + 1.68), (-12.6, 0.0, FZ0 + 2.00), 24.0),
            ("D_stair", (ST_CX + 0.34, ST_CY + 0.24, 9.60),
             (ST_CX - 2.30, ST_CY - 2.20, 4.30), 16.0),
            ("E_torch", (ST_CX + 1.05 * math.cos(math.radians(278.0)),
                         ST_CY + 1.05 * math.sin(math.radians(278.0)), 2.66),
             (ST_CX + 2.76 * math.cos(math.radians(278.0)),
              ST_CY + 2.76 * math.sin(math.radians(278.0)), 2.98), 24.0),
            ("F_shaft", (-10.5, -5.5, 1.72), (6.0, 2.0, 7.0), 20.0),
        ]
''' + s[j:]

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED", s.count("\n") + 1)
