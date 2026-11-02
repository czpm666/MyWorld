"""Print the ground vertex-colour statistics without opening Blender."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import _land_stub  # noqa: E402

_land_stub.install()

import hd_landscape as L  # noqa: E402

L._river_arrays(1337)

for r in (1000.0, 1200.0, 1500.0, 2000.0, 2600.0):
    for deg in (0.0, 45.0, 90.0, 135.0, 180.0):
        a = np.radians(deg)
        x = np.array([r * np.cos(a)])
        y = np.array([r * np.sin(a)])
        z = L.heights(x, y)
        c = L._ground_col(x, y, z, np.zeros(1), np.zeros(1), 1337)
        print("r=%6.0f deg=%5.1f z=%7.2f  col=(%.3f %.3f %.3f)"
              % (r, deg, float(z[0]), c[0, 0], c[0, 1], c[0, 2]))

# and the flat apron right outside the wall, where the render looked blank
xs = np.linspace(-1400, 1400, 41)
X, Y = np.meshgrid(xs, xs)
Z = L.heights(X, Y)
C = L._ground_col(X, Y, Z, np.zeros_like(Z), np.zeros_like(Z), 1337)
d = np.hypot(X, Y)
near = (d > 980) & (d < 1400)
print("\napron band: n=%d  mean=(%.3f %.3f %.3f)  min=%.3f max=%.3f"
      % (near.sum(), C[near, 0].mean(), C[near, 1].mean(), C[near, 2].mean(),
         C[near, :3].min(), C[near, :3].max()))
print("sd at (0,1100) = %.1f" % float(L._city_sd(np.array([0.0]),
                                                 np.array([1100.0]))[0]))
