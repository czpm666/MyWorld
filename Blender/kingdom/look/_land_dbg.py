import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
KROOT = os.path.dirname(HERE)
sys.path[:0] = [KROOT, HERE]
import numpy as np
import _land_stub
_land_stub.install()
import hd_landscape as L

L._river_arrays(L._SEED)
R = L._RIV
px, py, w = R["px"], R["py"], R["wl"]
inH = (np.abs(px) <= L.HARBOUR_X + 40.0) & (np.abs(py - L.HARBOUR_Y) < 120.0)
for k in (236, 237, 238, 239, 240):
    print(k, "px %.1f py %.1f inH %s w %.3f" % (px[k], py[k], inH[k], w[k]))
print("w in 178..190:", np.round(w[178:191], 3))
print("w in 276..288:", np.round(w[276:289], 3))
