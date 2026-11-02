import sys, os, math
KING = r"E:\My World\Blender\kingdom"
sys.path.insert(0, KING)
os.chdir(KING)
import numpy as np
import spots as S

lay = S.load()
u = S.units_for(lay)
q = u[0]['quad']
print('quad', q)
g = S.raster([u[0]])
print('blocked', g.sum())
g2 = S.raster(u[:200])
print('blocked200', g2.sum())
g3 = S.raster(u)
print('blocked all', g3.sum())

# manual check of one quad
HALF, RES, PAD = S.HALF, S.RES, S.PAD
xs = [(p[0] + HALF) / RES for p in q]
ys = [(p[1] + HALF) / RES for p in q]
x0, x1 = int(math.floor(min(xs) - PAD / RES)), int(math.ceil(max(xs) + PAD / RES))
y0, y1 = int(math.floor(min(ys) - PAD / RES)), int(math.ceil(max(ys) + PAD / RES))
print('bounds', x0, x1, y0, y1)
px = (np.arange(x0, x1 + 1) + 0.5) * RES - HALF
py = (np.arange(y0, y1 + 1) + 0.5) * RES - HALF
gx, gy = np.meshgrid(px, py)
print('shapes', gx.shape)
inside = np.ones(gx.shape, dtype=bool)
area = 0.0
for i in range(4):
    ax, ay = q[i]
    bx, by = q[(i + 1) % 4]
    area += (ax * (by - ay) - ay * (bx - ax))
print('area2', area)
sgn = 1.0 if area > 0 else -1.0
for i in range(4):
    ax, ay = q[i]
    bx, by = q[(i + 1) % 4]
    dx, dy = bx - ax, by - ay
    cr = ((gx - ax) * dy - (gy - ay) * dx) * sgn
    print(i, 'cr min %.2f max %.2f  tol %.2f' % (cr.min(), cr.max(), -PAD * math.hypot(dx, dy)))
    inside &= (cr >= -PAD * math.hypot(dx, dy))
print('inside count', inside.sum(), 'of', inside.size)
