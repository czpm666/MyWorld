from PIL import Image, ImageDraw
import os
D = r"E:\My World\renders\kingdom\look\sky"
names = ["wide_castle_noon","wide_castle_low20","wide_castle_back"]
W,H = 960,540
sheet = Image.new("RGB",(W,H*3),(0,0,0))
d = ImageDraw.Draw(sheet)
for i,n in enumerate(names):
    p = os.path.join(D,n+".png")
    im = Image.open(p).convert("RGB").resize((W,H))
    sheet.paste(im,(0,i*H))
    d.text((6,6+i*H),n,fill=(255,255,0))
out = os.path.join(D,"_wide_sheet.png")
sheet.save(out); print("saved",out,sheet.size)
