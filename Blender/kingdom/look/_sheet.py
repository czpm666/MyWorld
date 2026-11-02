from PIL import Image, ImageDraw
import os
D = r"E:\My World\renders\kingdom\look\sky"
names = ["dawn_cold","morning_town","noon_harsh","golden_street","overcast_soft",
         "dusk_city","night_torch","storm_dark","fog_pale","sunshower_warm"]
W,H = 400,225
sheet = Image.new("RGB",(W*5,H*2),(0,0,0))
d = ImageDraw.Draw(sheet)
for i,n in enumerate(names):
    im = Image.open(os.path.join(D,n+".png")).convert("RGB").resize((W,H))
    x,y = (i%5)*W,(i//5)*H
    sheet.paste(im,(x,y))
    d.text((x+4,y+4),n,fill=(255,255,0))
out = r"E:\My World\renders\kingdom\look\sky\_sheet.png"
sheet.save(out)
print("saved",out,sheet.size)
