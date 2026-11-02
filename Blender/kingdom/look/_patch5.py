import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

# 1. well lamps: no shadow, brighter -- the core should glow and light the treads
a = '''        L = bpy.data.lights.new("ci_st_lampL", "POINT")
        L.energy = 640.0
        L.shadow_soft_size = 0.30
        L.color = (1.0, 0.55, 0.24)'''
b = '''        L = bpy.data.lights.new("ci_st_lampL", "POINT")
        L.energy = 1800.0
        L.shadow_soft_size = 0.30
        L.use_shadow = False
        L.color = (1.0, 0.55, 0.24)'''
assert a in s
s = s.replace(a, b, 1)

# 2. feast hall room fill: two big shadowless panels under the ceiling
a = '''    return P


def build_seals(M):'''
b = '''    # a big soft panel under the feast ceiling: eight window fills aimed
    # sideways leave the middle of an 8 m high room in the dark
    for xf in (-6.0, 4.0):
        L = bpy.data.lights.new("ci_f_roomfill", "AREA")
        L.energy = 5200.0
        L.size = 7.0
        L.size_y = 4.5
        L.color = (1.0, 0.90, 0.78)
        L.use_shadow = False
        o = bpy.data.objects.new("ci_f_roomfill", L)
        o.location = (xf, 0.0, FZ1 - 0.55)
        K.link(o)
        P.append(o)
    return P


def build_seals(M):'''
assert a in s
s = s.replace(a, b, 1)

# 3. let the per-shot fill factor dial the new lamps too
a = '''             "ci_f_winfill", "ci_f_sc_light")'''
b = '''             "ci_f_winfill", "ci_f_sc_light", "ci_f_roomfill")'''
assert a in s
s = s.replace(a, b, 1)

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCH OK")
