import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def rep(a, b, tag, n=1):
    global s
    assert a in s, tag
    s = s.replace(a, b, n)
    print("rep", tag)


# ---- lights must follow the module when build() is placed
rep('''    H.apply(P, T)
    return P''',
    '''    H.apply(P, T)
    for ob in P:
        if ob is not None and ob.type != "MESH":
            ob.matrix_world = T @ ob.matrix_world
    return P''', "light transform")

# ---- flames: fewer, smaller, so the firebox reads
rep('''    for (xx, yy, hh, rr, mm) in ((-0.40, 0.34, 1.05, 0.105, fi),
                                 (-0.10, 0.42, 1.30, 0.120, fi),
                                 (0.22, 0.33, 1.10, 0.105, fi),
                                 (0.46, 0.44, 0.78, 0.085, fi),
                                 (-0.26, 0.28, 0.72, 0.085, hot),
                                 (0.04, 0.36, 0.95, 0.100, hot),
                                 (0.32, 0.30, 0.58, 0.070, hot),
                                 (-0.50, 0.26, 0.46, 0.055, hot)):''',
    '''    for (xx, yy, hh, rr, mm) in ((-0.46, 0.30, 0.50, 0.055, fi),
                                 (-0.20, 0.40, 0.62, 0.062, fi),
                                 (0.16, 0.32, 0.54, 0.058, fi),
                                 (0.42, 0.42, 0.40, 0.048, fi),
                                 (-0.05, 0.34, 0.34, 0.040, hot),
                                 (0.28, 0.28, 0.28, 0.034, hot)):''', "flames")

rep('M["fire"] = _emit("int_fire", "#ff6a12", 15.0)',
    'M["fire"] = _emit("int_fire", "#ff6a12", 9.0)', "fire str")
rep('M["fire_hot"] = _emit("int_fire_hot", "#ffd08a", 34.0)',
    'M["fire_hot"] = _emit("int_fire_hot", "#ffd08a", 20.0)', "hot str")

# ---- hero framing: just inside the great door, on the axis
i = s.index("        shots = [")
j = s.index("    for (nm, loc, look, lens) in shots:")
s = s[:i] + '''        shots = [
            ("A_door", (11.4, 0.0, EYE), (-11.70, 0.0, 3.40), 34.0),
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
