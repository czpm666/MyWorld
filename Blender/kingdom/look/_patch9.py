import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def rep(a, b, tag, n=1):
    global s
    assert a in s, tag
    s = s.replace(a, b, n)
    print("rep", tag)


# a hot core material next to the orange body of the flame
rep('    M["fire"] = _emit("int_fire", "#ff8a2a", 20.0)',
    '    M["fire"] = _emit("int_fire", "#ff6a12", 15.0)\n'
    '    M["fire_hot"] = _emit("int_fire_hot", "#ffd08a", 34.0)', "fire mats")

# tightly clustered tongues, dark firebox around them
i = s.index("    # ---- flame tongues: cones, so the fire reads from any angle")
j = s.index("    return P", i)
s = s[:i] + '''    # ---- flame tongues: a tight cluster, so the hearth stays dark around it
    hot = _m(M, "fire_hot")
    for (xx, yy, hh, rr, mm) in ((-0.34, 0.42, 0.92, 0.105, fi),
                                 (-0.06, 0.50, 1.05, 0.115, fi),
                                 (0.22, 0.40, 0.86, 0.100, fi),
                                 (0.44, 0.52, 0.62, 0.085, fi),
                                 (-0.20, 0.34, 0.58, 0.080, hot),
                                 (0.06, 0.42, 0.70, 0.090, hot),
                                 (0.30, 0.36, 0.46, 0.070, hot),
                                 (-0.42, 0.30, 0.38, 0.060, hot)):
        P.append(cyl("ci_fp_flame", T @ Ts(xx, yy, FZ0 + 0.16), rr, hh, mm,
                     seg=7, r2=0.008))
''' + s[j:]
print("cut flames")

rep("""    L.energy = 3000.0
    L.shadow_soft_size = 0.55
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.62, 0.0, FZ0 + 1.00)""",
    """    L.energy = 1600.0
    L.shadow_soft_size = 0.45
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.55, 0.0, FZ0 + 0.62)""", "hearth light")

rep("""    L = bpy.data.lights.new("ci_fp_in", "POINT")
    L.energy = 900.0""",
    """    L = bpy.data.lights.new("ci_fp_in", "POINT")
    L.energy = 380.0""", "hearth inside")

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED", s.count("\n") + 1)
