import sys, os, math, random
KING = r"E:\My World\Blender\kingdom"
sys.path.insert(0, KING)
os.chdir(KING)
import numpy as np
import spots as S

lay = S.load(); units = S.units_for(lay); print('units', len(units))
g = S.raster(units)
print('shape', g.shape, 'blocked frac %.3f' % g.mean())
clr = S.clearance(g)
print('clearance p50 %.2f p90 %.2f max %.2f' % (np.percentile(clr, 50), np.percentile(clr, 90), clr.max()))
n = g.shape[0]
cnt = {'clr': 0, 'run': 0, 'back': 0, 'lat': 0, 'fac': 0, 'ok': 0}
gr = S.Grid(units)
random.seed(1)
for _ in range(4000):
    x = random.uniform(-650, 650); y = random.uniform(-650, 650)
    rr = math.hypot(x, y)
    if rr > 660 or rr < 40:
        continue
    i = int((x + S.HALF) / S.RES); j = int((y + S.HALF) / S.RES)
    if not (2 <= i < n - 2 and 2 <= j < n - 2):
        continue
    c = clr[j, i]
    if not (1.6 <= c <= 9.0):
        continue
    cnt['clr'] += 1
    for k in range(8):
        ux, uy = math.cos(k * math.pi / 4), math.sin(k * math.pi / 4)
        run = S.clear_run(g, x, y, ux, uy)
        if run < 26:
            continue
        cnt['run'] += 1
        if S.clear_run(g, x, y, -ux, -uy, limit=8.0) < 3:
            continue
        cnt['back'] += 1
        lat = S.free_lateral(g, x, y, -uy, ux, limit=7.0)
        if lat < 1.8:
            continue
        cnt['lat'] += 1
        fac, nl, nr = S.wall_in_view(x, y, ux, uy, units, gr)
        if nl < 2 or nr < 2:
            continue
        cnt['fac'] += 1
        cnt['ok'] += 1
        break
print(cnt)
