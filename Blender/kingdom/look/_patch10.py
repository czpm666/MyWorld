import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def rep(a, b, tag, n=1):
    global s
    assert a in s, tag
    s = s.replace(a, b, n)
    print("rep", tag)


# soot for the inside of the firebox
rep('    M["fire"] = _emit("int_fire", "#ff6a12", 15.0)',
    '    M["soot"] = _ashlar("ci_soot", (0.022, 0.021, 0.020),\n'
    '                        (0.034, 0.032, 0.030), (0.012, 0.011, 0.010),\n'
    '                        bw=0.90, bh=0.40, grime=0.2, bump=0.1)\n'
    '    M["fire"] = _emit("int_fire", "#ff6a12", 15.0)', "soot")

rep('''    P.append(bx("ci_fp_back", T @ Ts(0, DP + 0.25, FZ0 + 3.0), (2 * HW + 0.9, 0.50, 6.0), sd))''',
    '''    P.append(bx("ci_fp_back", T @ Ts(0, DP + 0.20, FZ0 + 3.0), (2 * HW + 0.9, 0.50, 6.0), sd))
    P.append(bx("ci_fp_bk2", T @ Ts(0, DP - 0.01, FZ0 + (OH + 0.2) * 0.5),
                (2 * HW - 0.02, 0.06, OH + 0.2), _m(M, "soot")))
    for s3 in (-1, 1):
        P.append(bx("ci_fp_side", T @ Ts(s3 * (HW - 0.02), DP * 0.5, FZ0 + OH * 0.5),
                    (0.06, DP, OH), _m(M, "soot")))
    P.append(bx("ci_fp_top", T @ Ts(0, DP * 0.5, FZ0 + OH - 0.02),
                (2 * HW, DP, 0.06), _m(M, "soot")))''', "soot box")

i = s.index("    # ---- flame tongues: a tight cluster, so the hearth stays dark around it")
j = s.index("    return P", i)
s = s[:i] + '''    # ---- flame tongues: a tall cluster at the front of the firebox
    hot = _m(M, "fire_hot")
    for (xx, yy, hh, rr, mm) in ((-0.40, 0.34, 1.05, 0.105, fi),
                                 (-0.10, 0.42, 1.30, 0.120, fi),
                                 (0.22, 0.33, 1.10, 0.105, fi),
                                 (0.46, 0.44, 0.78, 0.085, fi),
                                 (-0.26, 0.28, 0.72, 0.085, hot),
                                 (0.04, 0.36, 0.95, 0.100, hot),
                                 (0.32, 0.30, 0.58, 0.070, hot),
                                 (-0.50, 0.26, 0.46, 0.055, hot)):
        P.append(cyl("ci_fp_flame", T @ Ts(xx, yy, FZ0 + 0.30), rr, hh, mm,
                     seg=7, r2=0.008))
''' + s[j:]
print("cut flames")

rep("""    L.energy = 1600.0
    L.shadow_soft_size = 0.45
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.55, 0.0, FZ0 + 0.62)""",
    """    L.energy = 1300.0
    L.shadow_soft_size = 0.45
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.20, 0.0, FZ0 + 0.55)""", "hearth light")

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED", s.count("\n") + 1)
