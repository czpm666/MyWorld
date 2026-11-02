import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

shots = '''        shots = [
            ("A_door", (HX - 2.6, 0.0, EYE), (-HX + 1.2, 0.0, 3.90), 26.0),
            ("B_throne", (-4.0, 2.30, 2.45), (-11.35, 0.10, 2.62), 33.0),
            ("C_feast", (5.2, -6.6, FZ0 + 1.70), (-9.4, 1.2, FZ0 + 2.4), 26.0),
            ("D_stair", (ST_CX + 0.05, ST_CY + 0.05, 1.30),
             (ST_CX - 0.25, ST_CY - 0.18, 14.6), 12.0),
            ("E_torch", (8.06, 4.01, 2.20), (9.91, 2.21, 3.31), 30.0),
            ("F_shaft", (-7.6, 6.6, 1.72), (6.2, -7.2, 9.4), 22.0),
        ]
'''
i = s.index("        shots = [")
j = s.index("    for (nm, loc, look, lens) in shots:")
s = s[:i] + shots + s[j:]
s = s.replace('vol.inputs["Density"].default_value = 0.0034',
              'vol.inputs["Density"].default_value = 0.0052')
ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("SHOTS PATCHED", s.count("\n") + 1)
