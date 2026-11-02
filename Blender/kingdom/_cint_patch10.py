# -*- coding: utf-8 -*-
"""Fix: porch arch orientation (envelope!), flag cloth placement, pole feet,
   seating metric, denser audit sampling."""
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
# porch blind arch was an X-normal ring built as a Y-normal one -> flew to x=-22.6
t = rep(t, '''        E += arch_ring_y("pz_br%d" % j, yc, 4.30, 0.86, 1.30, 0.24,
                         x0 - 0.24, x0 - 0.02, sl, n=12, keystone=True)''',
        '''        E += arch_ring_x("pz_br%d" % j, yc, 4.30, 0.86, 1.30, 0.24,
                         x0 - 0.24, x0 - 0.02, sl, n=12, keystone=True)''')
# flag cloth must hang on its pole, not 0.6 m inside the room
t = rep(t, '''        C += cloth("hw_fb%d" % s, Ts(px - s * 0.66, y0 - 0.86, 8.50,
                                    rz=-s * math.pi * 0.5),''',
        '''        C += cloth("hw_fb%d" % s, Ts(px - s * 0.02, y0 - 0.86, 8.50,
                                    rz=-s * math.pi * 0.5),''')
t = rep(t, '''            C.append(bx("hw_ff%d_%d" % (s, k),
                        Ts(px - s * 1.27, y0 - 0.83, 7.16 + k * 0.10),
                        (0.09, 0.03, 0.05), gm, bev=0.006))''',
        '''            C.append(bx("hw_ff%d_%d" % (s, k),
                        Ts(px - s * 0.02, y0 - 0.86 + (k - 2) * 0.26, 7.09),
                        (0.05, 0.10, 0.09), gm, bev=0.006))''')
# poles: foot sits just under the dais floor so the joint is a joint
t = rep(t, '''        C.append(cyl("hw_pol%d" % s, Ts(px, y0 - 0.78, 5.40), 0.072, 9.05, wd,
                     seg=10))''',
        '''        C.append(cyl("hw_pol%d" % s, Ts(px, y0 - 0.78, 5.50), 0.072, 8.80, wd,
                     seg=10))''')
save("_cint_p3.py", t)
print("PATCHED p3", len(t))

P = os.path.join(D, "_cint_test.py")
t = io.open(P, encoding="utf-8").read()
t = rep(t, "    if hi[2] <= 1.32 and 2.00 < lo[0] < 8.75 and hi[0] < 8.78:",
        "    if 0.34 <= hi[2] <= 1.32 and 2.00 < lo[0] < 8.75 and hi[0] < 8.78:")
t = rep(t, """    if len(vs) > 60:
        vs.sort(key=lambda c: c.z)
        sample = vs[::max(1, len(vs) // 60)][:60]""",
        """    if len(vs) > 150:
        vs.sort(key=lambda c: c.z)
        sample = vs[::max(1, len(vs) // 150)][:150]""")
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("PATCHED test", len(t))
