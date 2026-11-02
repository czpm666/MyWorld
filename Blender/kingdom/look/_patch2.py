import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

n520 = s.count("L.energy = 520.0")
n240 = s.count("L.energy = 240.0")
print("520 x%d  240 x%d" % (n520, n240))
assert n520 == 1 and n240 == 1
s = s.replace("L.energy = 520.0", "L.energy = 220.0")
s = s.replace("L.energy = 240.0", "L.energy = 470.0")

subs = [
    ('_emit("int_fire", "#ff8a2a", 62.0)', '_emit("int_fire", "#ff8a2a", 16.0)'),
    ('mats = ["stone_floor"] * 9 + ["stone_light"]', 'mats = ["stone_floor"] * 10'),
    ('_ashlar("ci_marble", (0.420, 0.400, 0.360),\n'
     '                          (0.470, 0.450, 0.405), (0.300, 0.285, 0.255),',
     '_ashlar("ci_marble", (0.330, 0.315, 0.286),\n'
     '                          (0.372, 0.355, 0.320), (0.232, 0.220, 0.198),'),
    ('    P += build_feast_props(M, rng)\n    if lights:',
     '    P += build_feast_props(M, rng)\n    P += build_seals(M)\n    if lights:'),
]
for a, b in subs:
    assert a in s, a[:50]
    s = s.replace(a, b)

seals = io.open(r"E:\My World\Blender\kingdom\look\_new_seals.py",
                encoding="utf-8", newline="").read()
mk = "def build(KM, MAT, origin=(0.0, 0.0)"
i = s.index(mk)
s = s[:i] + seals + s[i:]

a = '    L = bpy.data.lights.new("ci_st_lampL", "POINT")'
b = ('    L = bpy.data.lights.new("ci_well_lan", "POINT")\n'
     '    L.energy = 700.0\n'
     '    L.shadow_soft_size = 0.26\n'
     '    L.color = (1.0, 0.78, 0.48)\n'
     '    o = bpy.data.objects.new("ci_well_lan", L)\n'
     '    o.location = (ST_CX, ST_CY, 14.32)\n'
     '    K.link(o)\n'
     '    P.append(o)\n'
     '    L = bpy.data.lights.new("ci_st_lampL", "POINT")')
assert a in s
s = s.replace(a, b, 1)
ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED", s.count("\n") + 1)
