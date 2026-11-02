from PIL import Image, ImageDraw
import os
R = r"E:\My World\Blender\renders\kingdom"
Q = os.path.join(R, "_qc")
BOXES = [
    ("top",     "hd_gate_top.png",      640, 560,  750, 700, 3.0, "1a top 640,560-750,700"),
    ("top",     "hd_gate_top.png",      950, 390, 1090, 520, 3.0, "1b top 950,390-1090,520"),
    ("c",       "hd_gate_c.png",        280, 430,  750, 580, 2.0, "1c c 280,430-750,580"),
    ("portal",  "hd_gate_portal.png",   575, 380, 1085, 500, 2.2, "2a portal 575,455-1085,470 (arch head)"),
    ("arch",    "hd_gate_arch.png",     560, 340,  900, 470, 3.0, "2b arch 560,375-830,385"),
    ("portal",  "hd_gate_portal.png",   440, 350,  540, 430, 5.0, "4a portal 462,370-500,400"),
    ("through", "hd_gate_through.png",  300, 590,  400, 720, 4.0, "4b through 330,620-360,690"),
    ("road",    "hd_gate_road.png",    1010, 610, 1120, 730, 4.0, "4c road 1040,640-1090,700"),
    ("south",   "hd_gate_south.png",    760, 340,  860, 430, 4.0, "4d south 790,370-830,400"),
    ("citywide","hd_gate_citywide.png",  80, 530,  320, 690, 3.0, "3a citywide 100,550-300,650"),
    ("c",       "hd_gate_c.png",        1050, 180, 1180, 450, 3.0, "3b c 1080,200-1150,420"),
]
tiles = []
for name, fn, x0, y0, x1, y1, sc, label in BOXES:
    im = Image.open(os.path.join(R, fn)).convert("RGB")
    box = im.crop((x0, y0, x1, y1))
    w = int(box.width * sc); h = int(box.height * sc)
    box = box.resize((w, h), Image.LANCZOS)
    lab = Image.new("RGB", (w, 26), (245, 245, 245))
    d = ImageDraw.Draw(lab)
    d.text((5, 7), "%s  [%s]" % (label, name), fill=(20, 20, 20))
    tile = Image.new("RGB", (w, h + 26), (255, 255, 255))
    tile.paste(box, (0, 26)); tile.paste(lab, (0, 0))
    tiles.append(tile)
# pack rows of max width 1560
CW = 1560
rows, cur, curw = [], [], 0
for t in tiles:
    if cur and curw + t.width + 8 > CW:
        rows.append(cur); cur, curw = [], 0
    cur.append(t); curw += t.width + 8
if cur: rows.append(cur)
Hh = sum(max(t.height for t in r) + 8 for r in rows)
sheet = Image.new("RGB", (CW, Hh), (238, 238, 238))
y = 0
for r in rows:
    x = 0
    for t in r:
        sheet.paste(t, (x, y)); x += t.width + 8
    y += max(t.height for t in r) + 8
out = os.path.join(Q, "final_qc_sheet.png")
sheet.save(out)
print("wrote", out, sheet.size)
