import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

i = s.index("        shots = [")
j = s.index("    for (nm, loc, look, lens) in shots:")
j2 = s.index("\n", j)
loop = s[j:j2]
assert "for (nm, loc, look, lens) in shots:" in loop

s = s[:i] + '''        shots = [
            ("A_door", (11.4, 0.0, EYE), (-11.70, 0.0, 3.40), 34.0, 0.0022),
            ("B_throne", (-4.0, 2.30, 2.45), (-11.35, 0.10, 2.62), 33.0, 0.0022),
            ("C_feast", (-4.6, -6.0, FZ0 + 1.68), (-12.6, 0.0, FZ0 + 2.00), 24.0,
             0.0022),
            ("D_stair", (ST_CX + 0.34, ST_CY + 0.24, 9.60),
             (ST_CX - 2.30, ST_CY - 2.20, 4.30), 16.0, 0.0030),
            ("E_torch", (ST_CX + 1.05 * math.cos(math.radians(278.0)),
                         ST_CY + 1.05 * math.sin(math.radians(278.0)), 2.66),
             (ST_CX + 2.76 * math.cos(math.radians(278.0)),
              ST_CY + 2.76 * math.sin(math.radians(278.0)), 2.98), 24.0, 0.0030),
            ("F_shaft", (-10.5, -5.5, 1.72), (6.0, 2.0, 7.0), 20.0, 0.0080),
        ]
''' + s[j:]

# per-shot fog
a = "    for (nm, loc, look, lens) in shots:"
b = ("    sc.view_settings.exposure = 0.55\n"
     "    for (nm, loc, look, lens, dens) in shots:\n"
     "        vol.inputs[\"Density\"].default_value = dens")
assert a in s
s = s.replace(a, b, 1)

s2 = io.open(p, encoding="utf-8", newline="").read()
ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED")
