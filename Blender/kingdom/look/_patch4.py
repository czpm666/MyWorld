import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

# 1. flags: one tone, the mortar joints carry the pattern
a = ('_ashlar("ci_flag", (0.185, 0.176, 0.160),\n'
     '                               (0.225, 0.212, 0.192), (0.070, 0.066, 0.060),')
b = ('_ashlar("ci_flag", (0.205, 0.194, 0.175),\n'
     '                               (0.212, 0.201, 0.181), (0.062, 0.058, 0.052),')
assert a in s, "flag"
s = s.replace(a, b)

# 2. fog and sun
s = s.replace('vol.inputs["Density"].default_value = 0.0052',
              'vol.inputs["Density"].default_value = 0.0045')
s = s.replace("sd.energy = 22.0", "sd.energy = 55.0")
s = s.replace("L.energy = 220.0", "L.energy = 150.0")
s = s.replace('L = bpy.data.lights.new("ci_well_lan", "POINT")\n    L.energy = 700.0',
              'L = bpy.data.lights.new("ci_well_lan", "POINT")\n    L.energy = 2200.0')

# 3. a torch beside the stair door, and its light
a = '    L = bpy.data.lights.new("ci_well_lan", "POINT")'
b = ('    for (aa, zz) in ((186.0, 0.10), (214.0, 0.10)):\n'
     '        a = math.radians(aa)\n'
     '        rr = ST_RIN - 0.20\n'
     '        P.append(cyl("ci_std_torch", Ts(ST_CX + rr * math.cos(a),\n'
     '                                        ST_CY + rr * math.sin(a), zz + 1.55),\n'
     '                     0.055, 1.90, _m(M, "wood_dark"), seg=8))\n'
     '        P.append(cyl("ci_std_cup", Ts(ST_CX + rr * math.cos(a),\n'
     '                                      ST_CY + rr * math.sin(a), zz + 2.56),\n'
     '                     0.15, 0.26, _m(M, "iron"), seg=10, r2=0.20))\n'
     '        P.append(sph("ci_std_fl", Ts(ST_CX + rr * math.cos(a),\n'
     '                                     ST_CY + rr * math.sin(a), zz + 2.78),\n'
     '                     0.20, _m(M, "fire"), seg=10, ring=6, squash=1.5))\n'
     '        L = bpy.data.lights.new("ci_std_light", "POINT")\n'
     '        L.energy = 900.0\n'
     '        L.shadow_soft_size = 0.16\n'
     '        L.color = (1.0, 0.46, 0.16)\n'
     '        o = bpy.data.objects.new("ci_std_light", L)\n'
     '        o.location = (ST_CX + rr * math.cos(a), ST_CY + rr * math.sin(a),\n'
     '                      zz + 2.86)\n'
     '        K.link(o)\n'
     '        P.append(o)\n'
     '    L = bpy.data.lights.new("ci_well_lan", "POINT")')
assert a in s
s = s.replace(a, b, 1)

# 4. new cameras
shots = '''        shots = [
            ("A_door", (HX - 2.6, 0.0, EYE), (-HX + 1.2, 0.0, 3.00), 28.0),
            ("B_throne", (-4.0, 2.30, 2.45), (-11.35, 0.10, 2.62), 33.0),
            ("C_feast", (5.2, -6.6, FZ0 + 1.70), (-9.4, 1.2, FZ0 + 2.4), 26.0),
            ("D_stair", (ST_CX + 2.30 * math.cos(math.radians(205.0)),
                         ST_CY + 2.30 * math.sin(math.radians(205.0)), 1.72),
             (ST_CX + 1.80 * math.cos(math.radians(292.0)),
              ST_CY + 1.80 * math.sin(math.radians(292.0)), 7.60), 14.0),
            ("E_torch", (ST_CX + 1.55 * math.cos(math.radians(283.0)),
                         ST_CY + 1.55 * math.sin(math.radians(283.0)), 2.72),
             (ST_CX + 3.15 * math.cos(math.radians(278.0)),
              ST_CY + 3.15 * math.sin(math.radians(278.0)), 3.36), 30.0),
            ("F_shaft", (-10.5, -5.5, 1.72), (6.0, 2.0, 7.0), 20.0),
        ]
'''
i = s.index("        shots = [")
j = s.index("    for (nm, loc, look, lens) in shots:")
s = s[:i] + shots + s[j:]

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED", s.count("\n") + 1)
