from PIL import Image
import os
D = r"E:\My World\renders\kingdom\look\sky"
for n in ["night_torch","fog_pale"]:
    p = os.path.join(D, n+".png")
    im = Image.open(p)
    print(n, im.size)
