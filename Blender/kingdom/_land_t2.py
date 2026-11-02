import sys
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import numpy as np
import hd_landscape as L
L._river_arrays(1337)
for rr in (600, 690, 700, 800, 900):
    a = np.linspace(0, 2*np.pi, 16, endpoint=False)
    x = rr*np.cos(a); y = rr*np.sin(a)
    z = L.heights(x, y)
    j = int(np.argmin(z))
    d, i = L._poly_dist(np.array([x[j]]), np.array([y[j]]), L._RIV["px"], L._RIV["py"])
    print("r=%4d min %7.3f at (%7.1f,%7.1f)  river d=%6.1f wl=%7.2f" % (
        rr, z[j], x[j], y[j], d[0], L._RIV["wl"][i[0]]))
print("lake", [round(v,1) for v in L._RIV["lake"]])
print("wl profile samples:", np.round(L._RIV["wl"][::40], 1))
