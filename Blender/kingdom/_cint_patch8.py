# -*- coding: utf-8 -*-
"""Round-3: p4 only (calls + lighting)."""
import io
import os

D = r"E:\My World\Blender\kingdom"
P = os.path.join(D, "_cint_p4.py")
t = io.open(P, encoding="utf-8").read()


def rep(t, old, new, n=1):
    if t.count(old) != n:
        raise SystemExit("marker %dx: %r" % (t.count(old), old[:70]))
    return t.replace(old, new)


t = rep(t, "    back_wall(C, MAT, rng)\n",
        "    back_wall(C, MAT, rng)\n    heraldry(C, E, MAT, rng)\n"
        "    sconces(E, MAT, rng)\n")
t = rep(t, '''    _sun("SUN", (-0.54, 0.40, -0.74), energy=5.0, angle=1.0)
    # ---- interior fill
    _area("FILL_NAVE", (0.0, 3.0, 13.60), (10.0, 8.0), 2400.0, (0.0, 0.0, 0.0))
    _area("FILL_ENTRY", (0.0, -13.50, 12.40), (8.0, 6.0), 1500.0, (0.0, 0.0, 0.0))
    _area("FILL_DAIS", (0.0, 14.00, 13.20), (7.0, 6.0), 1800.0,
          (math.radians(18.0), 0.0, 0.0), color=(1.0, 0.90, 0.78))''',
        '''    _sun("SUN", (-0.62, -0.26, -0.72), energy=9.5, angle=0.55)
    # ---- interior fill (kept low so the shafts read)
    _area("FILL_NAVE", (0.0, 3.0, 15.10), (7.0, 6.0), 900.0, (0.0, 0.0, 0.0),
          color=(1.0, 0.93, 0.84))
    _area("FILL_ENTRY", (0.0, -14.20, 14.20), (6.0, 5.0), 520.0, (0.0, 0.0, 0.0),
          color=(1.0, 0.93, 0.86))
    _area("FILL_DAIS", (0.0, 15.60, 14.40), (6.0, 5.0), 700.0,
          (math.radians(14.0), 0.0, 0.0), color=(1.0, 0.90, 0.78))
    # ---- uplights so the timber roof is not a black hole
    _area("UP_NAVE", (0.0, 1.0, 9.40), (12.0, 14.0), 950.0,
          (math.pi, 0.0, 0.0), color=(1.0, 0.90, 0.78))
    _area("UP_CHOR", (0.0, 17.60, 9.80), (8.0, 6.0), 420.0,
          (math.pi, 0.0, 0.0), color=(1.0, 0.88, 0.74))''')
t = rep(t, 'box.data.materials.append(_volume_mat())',
        'box.data.materials.append(_volume_mat(0.0072, 0.62))')
t = rep(t, '''    bg.inputs[0].default_value = (0.52, 0.66, 0.86, 1.0)
    bg.inputs[1].default_value = 1.15''',
        '''    bg.inputs[0].default_value = (0.44, 0.60, 0.86, 1.0)
    bg.inputs[1].default_value = 0.85''')
t = rep(t, '''        ("f_diag", (-6.90, -11.60, 1.72), (0.60, 10.00, 4.40), 30.0),''',
        '''        ("f_diag", (-6.90, -11.60, 1.72), (0.60, 10.00, 4.40), 30.0),
        ("g_roof", (0.0, 3.40, 1.70), (0.0, 8.60, 16.40), 17.0),''')
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("PATCHED p4", len(t))
