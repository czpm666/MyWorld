# -*- coding: utf-8 -*-
"""Fix: heraldic disc/crown faced the wrong way (ry -> rx), bench legs reach
   the seat, chandelier hub becomes a supported finial with cross braces."""
import io
import os

D = r"E:\My World\Blender\kingdom"


def load(fn):
    return io.open(os.path.join(D, fn), encoding="utf-8").read()


def save(fn, t):
    io.open(os.path.join(D, fn), "w", encoding="utf-8", newline="\n").write(t)


def rep(t, old, new, n=1):
    if t.count(old) != n:
        raise SystemExit("marker %dx: %r" % (t.count(old), old[:70]))
    return t.replace(old, new)


t = load("_cint_p3.py")
t = rep(t, '''    C.append(cyl("hw_disc", Ts(0.0, y0 - 0.16, 9.16, ry=math.pi * 0.5),
                 0.80, 0.045, _m(MAT, "cloth_gold"), seg=24))''',
        '''    C.append(cyl("hw_disc", Ts(0.0, y0 - 0.16, 9.16, rx=math.pi * 0.5),
                 0.80, 0.045, _m(MAT, "cloth_gold"), seg=24,
                 bev=0.0))''')
t = rep(t, '''    C.append(torus("hw_cr", Ts(0.0, y0 - 0.18, 9.90, ry=math.pi * 0.5),
                   0.23, 0.045, gm, seg=16, ring=5))''',
        '''    C.append(torus("hw_cr", Ts(0.0, y0 - 0.18, 9.90, rx=math.pi * 0.5),
                   0.23, 0.045, gm, seg=16, ring=5))''')
save("_cint_p3.py", t)
print("PATCHED p3", len(t))

t = load("_cint_p4.py")
t = rep(t, '''            C.append(bx(nm + "_l%d_%d" % (j, s), Ts(x + s * 0.15, yy, 0.20),
                        (0.07, 0.14, 0.40), wdd, bev=0.008))''',
        '''            C.append(bx(nm + "_l%d_%d" % (j, s), Ts(x + s * 0.15, yy, 0.23),
                        (0.07, 0.14, 0.46), wdd, bev=0.008))''')
t = rep(t, '''    C.append(cyl("ch_hub%d" % tag, Ts(0.0, yc, z_ring + 0.24), 0.11, 0.36, iron,
                 seg=12))''',
        '''    C.append(cyl("ch_hub%d" % tag, Ts(0.0, yc, z_ring - 0.02), 0.09, 0.26, iron,
                 seg=12))
    for k in range(4):
        a2 = TAU * k / 4.0 + 0.42
        C.append(rod("ch_br%d_%d" % (tag, k),
                     (R * math.cos(a2), yc + R * math.sin(a2), z_ring),
                     (0.0, yc, z_ring - 0.20), 0.018, iron, seg=5))''')
save("_cint_p4.py", t)
print("PATCHED p4", len(t))
