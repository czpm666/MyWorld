# -*- coding: utf-8 -*-
"""Round-3 patch: pointed arches, un-bury the throne aedicule, richer glass,
   heraldic tapestry + flags, better interior lighting."""
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


# ---------------------------------------------------------------------------
# p1: materials
# ---------------------------------------------------------------------------
t = load("_cint_p1.py")
t = rep(t, '''    M["stone"] = K.mat_stone("cint_stone", base="#a99d84", dark="#5f584a",
                             light="#c3b79a", scale=1.9)''',
        '''    M["stone"] = K.mat_stone("cint_stone", base="#9b8f76", dark="#4f4839",
                             light="#bcab8b", scale=1.9)''')
t = rep(t, '''    M["stone_light"] = K.mat_stone("cint_stone_l", base="#bdb094", dark="#786f5d",
                                   light="#d6caab", scale=2.4)''',
        '''    M["stone_light"] = K.mat_stone("cint_stone_l", base="#b3a689", dark="#6d6453",
                                   light="#cdc0a0", scale=2.4)''')
t = rep(t, '''    M["glass_gold"] = _lit_glass("cint_glass_g", "#8a6a24", "#ffd98a", 3.1, 0.55)
    M["glass_blue"] = _lit_glass("cint_glass_b", "#243a63", "#9dc0ff", 2.2, 0.55)
    M["glass_red"] = _lit_glass("cint_glass_r", "#6d1f22", "#ff9b7a", 2.4, 0.55)
    M["glass_pale"] = _lit_glass("cint_glass_p", "#7d8b93", "#e9f2ff", 4.2, 0.62)''',
        '''    M["glass_gold"] = _lit_glass("cint_glass_g", "#4a3410", "#f0b64a", 2.0, 0.26)
    M["glass_blue"] = _lit_glass("cint_glass_b", "#101c40", "#2f4f9e", 1.5, 0.24)
    M["glass_red"] = _lit_glass("cint_glass_r", "#3a0a0d", "#9e2b25", 1.5, 0.24)
    M["glass_pale"] = _lit_glass("cint_glass_p", "#4a5560", "#b9cfe4", 2.2, 0.34)''')
save("_cint_p1.py", t)
print("PATCHED p1", len(t))

# ---------------------------------------------------------------------------
# p3: arches + aedicule
# ---------------------------------------------------------------------------
t = load("_cint_p3.py")
# screen-wall arch: steeper point
t = rep(t, "    z_spr, z_apex = 6.20, 9.00\n", "    z_spr, z_apex = 6.10, 10.30\n")
# chancel arch: steeper point
t = rep(t, "    z_spr, z_apex = 6.60, 9.60\n", "    z_spr, z_apex = 5.60, 10.30\n")
# back wall aedicule: project into the room instead of into the masonry
for old, new in (
        ('sd,\n                   y0 + 0.01, y0 + 0.06, axis="y"))',
         'sd,\n                   y0 - 0.06, y0 - 0.01, axis="y"))'),
        ('Ts(s * 1.72, y0 + 0.20, 3.06)', 'Ts(s * 1.72, y0 - 0.20, 3.06)'),
        ('Ts(s * 1.72, y0 + 0.21, 5.27)', 'Ts(s * 1.72, y0 - 0.21, 5.27)'),
        ('Ts(s * 1.72, y0 + 0.21, 0.88)', 'Ts(s * 1.72, y0 - 0.21, 0.88)'),
        ('sl, n=14, keystone=True)', 'sl, n=14, keystone=True)'),
        ('nah, 1.80, 0.30, y0 + 0.02, y0 + 0.40,',
         'nah, 1.80, 0.30, y0 - 0.40, y0 - 0.02,'),
        ('Ts(0.0, y0 + 0.22, 0.86), (3.90, 0.46, 0.16)',
         'Ts(0.0, y0 - 0.22, 0.86), (3.90, 0.46, 0.16)'),
        ('sd, y0 + 0.01, y0 + 0.05, axis="y"))',
         'sd, y0 - 0.05, y0 - 0.01, axis="y"))'),
        ('0.24,\n                             y0 + 0.02, y0 + 0.20, sl, n=12, keystone=True)',
         '0.24,\n                             y0 - 0.20, y0 - 0.02, sl, n=12, keystone=True)'),
        ('Ts(xc + t * 0.94, y0 + 0.10, 2.60)', 'Ts(xc + t * 0.94, y0 - 0.10, 2.60)'),
        ('Ts(xc, y0 + 0.10, 1.34)', 'Ts(xc, y0 - 0.10, 1.34)'),
):
    if old != new:
        t = rep(t, old, new)
# the central statue would hide behind the throne: put the pair in the flanking
# niches instead, and hang the heraldic cloth over the throne
t = rep(t, '''    C.append(statue("bw_stat", Ts(0.0, y0 + 0.20, 0.94), 3.30, MAT, rng))''',
        '''    for s in (-1, 1):
        C.append(statue("bw_stat%d" % s, Ts(s * 2.72, y0 - 0.16, 1.42), 2.55,
                        MAT, rng))''')
save("_cint_p3.py", t)
print("PATCHED p3", len(t))
