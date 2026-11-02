import sys, os, math, json
KING = r"E:\My World\Blender\kingdom"
sys.path.insert(0, KING)
os.chdir(KING)
import numpy as np
import spots as S

lay = S.load()
units = S.units_for(lay)
g = S.raster(units)
clr = S.clearance(g)
print('blocked frac %.3f' % g.mean())

picks = json.load(open(os.path.join(KING, 'look', 'spots.json'), encoding='utf-8'))['picks']
for p in picks[:5]:
    x, y = p['x'], p['y']
    i = int((x + S.HALF) / S.RES); j = int((y + S.HALF) / S.RES)
    print('pick %6.1f,%6.1f  clr %.2f  w %.1f run %.1f  blocked=%d' %
          (x, y, clr[j, i], p['w'], p['run'], g[j, i]))
    near = []
    for u in units:
        d = math.hypot(u['x'] - x, u['y'] - y)
        if d < 9.0:
            near.append((round(d, 1), u['kind'], u['ring']))
    near.sort()
    print('   units within 9 m:', near[:8])
