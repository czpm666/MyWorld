import sys, os, math, json
KING = r"E:\My World\Blender\kingdom"
sys.path.insert(0, KING)
os.chdir(KING)
from PIL import Image, ImageDraw

import spots as S

lay = S.load()
units = S.units_for(lay)
picks = json.load(open(os.path.join(KING, 'look', 'spots.json'), encoding='utf-8'))['picks']

SPAN = 150.0
PPM = 4.0
n = int(SPAN * PPM)
COLS = 2
ROWS = (len(picks[:4]) + COLS - 1) // COLS
img = Image.new('RGB', (n * COLS, n * ROWS), (26, 30, 36))
dr = ImageDraw.Draw(img)

for idx, p in enumerate(picks[:4]):
    ox = (idx % COLS) * n
    oy = (idx // COLS) * n
    cx, cy = p['x'], p['y']
    def T(x, y):
        return (ox + n * 0.5 + (x - cx) * PPM, oy + n * 0.5 - (y - cy) * PPM)
    # buildings
    for u in units:
        if abs(u['x'] - cx) > SPAN or abs(u['y'] - cy) > SPAN:
            continue
        q = u.get('quad')
        if not q:
            continue
        dr.polygon([T(px, py) for (px, py) in q], fill=(70, 76, 86), outline=(96, 104, 116))
    # camera
    ux, uy = p['ux'], p['uy']
    camx = cx - ux * 20.93
    camy = cy - uy * 20.93
    dr.line([T(camx, camy), T(cx + ux * 30, cy + uy * 30)], fill=(255, 210, 90), width=2)
    dr.ellipse([T(cx, cy)[0] - 5, T(cx, cy)[1] - 5, T(cx, cy)[0] + 5, T(cx, cy)[1] + 5],
               fill=(120, 255, 140))
    dr.ellipse([T(camx, camy)[0] - 7, T(camx, camy)[1] - 7, T(camx, camy)[0] + 7, T(camx, camy)[1] + 7],
               fill=(255, 90, 90))
    # the ground band the camera actually sees (11.4 .. 35.5 m ahead of camera)
    for d0, d1, col in ((11.4, 35.5, (255, 255, 255)),):
        for dd in (d0, d1):
            dr.line([T(camx + ux * dd - uy * 16, camy + uy * dd + ux * 16),
                     T(camx + ux * dd + uy * 16, camy + uy * dd - ux * 16)],
                    fill=col, width=1)
    dr.text((ox + 8, oy + 8), "#%d  %.1f,%.1f  w%.1f run%.1f" % (idx, cx, cy, p['w'], p['run']),
            fill=(230, 230, 230))

out = os.path.join(KING, 'look', '_spotmap.png')
img.save(out)
print(out)
