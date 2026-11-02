import ast
import io

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

# ---------------------------------------------------------------- well lamps
a = """        P.append(bx("ci_st_lan_bar", Ts(ST_CX + 0.28 * math.cos(a),
                                       ST_CY + 0.28 * math.sin(a), 14.30),
                    (0.035, 0.035, 0.46), _m(M, "iron")))
    return P"""
b = """        P.append(bx("ci_st_lan_bar", Ts(ST_CX + 0.28 * math.cos(a),
                                       ST_CY + 0.28 * math.sin(a), 14.30),
                    (0.035, 0.035, 0.46), _m(M, "iron")))
    # three more lamps on long chains down the shaft: a 15 m open well with one
    # lamp at the very top reads as a black hole from the bottom of the stair
    for zz in WELL_LAMPS:
        P.append(cyl("ci_st_chain", Ts(ST_CX, ST_CY, (zz + 15.02) * 0.5),
                     0.020, 15.02 - zz, _m(M, "iron"), seg=6))
        P.append(cyl("ci_st_lamp_b", Ts(ST_CX, ST_CY, zz), 0.30, 0.16,
                     _m(M, "iron"), seg=12, r2=0.22))
        P.append(cyl("ci_st_lamp_f", Ts(ST_CX, ST_CY, zz + 0.11), 0.20, 0.22,
                     _m(M, "fire"), seg=12))
    return P"""
assert a in s
s = s.replace(a, b, 1)

# ------------------------------------------------------- lights: shaft + sconces
a = """    L = bpy.data.lights.new("ci_well_lan", "POINT")"""
dots = s.index(a)
b = """    for zz in WELL_LAMPS:
        L = bpy.data.lights.new("ci_st_lampL", "POINT")
        L.energy = 640.0
        L.shadow_soft_size = 0.30
        L.color = (1.0, 0.55, 0.24)
        o = bpy.data.objects.new("ci_st_lampL", L)
        o.location = (ST_CX, ST_CY, zz + 0.14)
        K.link(o)
        P.append(o)
    # wall sconces down both long walls of the feast hall: an 8 m high room lit
    # only by two hearths reads as a black box from the far end
    for sx in (-7.60, -0.40, 6.80):
        for s in (-1, 1):
            yy = s * (HY - 0.30)
            P.append(bx("ci_f_sc_br", Ts(sx, yy - s * 0.10, FZ0 + 2.16),
                        (0.07, 0.34, 0.07), _m(MAT, "iron")))
            P.append(cyl("ci_f_sc_sh", Ts(sx, yy - s * 0.24, FZ0 + 2.34),
                         0.038, 0.46, _m(MAT, "wood_dark"), seg=8))
            P.append(sph("ci_f_sc_fl", Ts(sx, yy - s * 0.24, FZ0 + 2.64),
                         0.085, _m(MAT, "fire"), seg=9, ring=6, squash=1.7))
            L = bpy.data.lights.new("ci_f_sc_light", "POINT")
            L.energy = 620.0
            L.shadow_soft_size = 0.16
            L.color = (1.0, 0.52, 0.20)
            o = bpy.data.objects.new("ci_f_sc_light", L)
            o.location = (sx, yy - s * 0.26, FZ0 + 2.70)
            K.link(o)
            P.append(o)
    L = bpy.data.lights.new("ci_well_lan", "POINT")"""
s = s[:dots] + b + s[dots + len(a):]

# ------------------------------------------------------------- constant
a = 'ST_TOP = Z_TOP + 0.6'
assert a in s
s = s.replace(a, a + '\nWELL_LAMPS = (13.40, 9.10, 4.70)   # hanging lamps down the stair well', 1)

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCH OK  lines=%d" % (s.count("\n") + 1))
