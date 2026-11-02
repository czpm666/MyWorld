import sys, time
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import numpy as np
t0 = time.time()
import hd_landscape as L
L._river_arrays(1337)
print("import+arrays", round(time.time()-t0, 2))

t0 = time.time()
h = L.heights(np.linspace(-3600, 3600, 361), np.linspace(-3600, 3600, 361)) if False else None
xs = np.linspace(-3600, 3600, 361)
X, Y = np.meshgrid(xs, xs, indexing="xy")
Z = L.heights(X, Y)
print("heights 361^2", round(time.time()-t0, 2), "s  min/max", round(Z.min(),1), round(Z.max(),1))

# radial profile every 30 deg
print("r      N      E      S      W     NE     NW     SE     SW")
for rr in (700, 900, 1200, 1600, 2100, 2600, 3100, 3600, 4400, 5400, 6800, 8800, 12000):
    row = []
    for deg in (90, 0, 270, 180, 45, 135, 315, 225):
        a = np.radians(deg)
        row.append(L.h1(rr*np.cos(a), rr*np.sin(a)))
    print("%6d" % rr, " ".join("%6.0f" % v for v in row))

# river crossings
for nm, x, y in (("west bridge", -1000, 0), ("south bridge", 0, -905),
                 ("harbour", 0, -352), ("river up", -2320, 430)):
    wl, d, hw = L._water_level(x, y)
    print("%-12s terr=%7.2f  wl=%7.2f  d=%6.1f hw=%5.1f" % (nm, L.h1(x,y), wl, d, hw))

# flatness check
for rr in (0, 300, 600, 690, 700, 800, 900, 940):
    a = np.linspace(0, 2*np.pi, 16, endpoint=False)
    z = L.heights(rr*np.cos(a), rr*np.sin(a))
    print("flat r=%4d  min %.3f max %.3f" % (rr, z.min(), z.max()))
print("total", round(time.time()-t0,2))
