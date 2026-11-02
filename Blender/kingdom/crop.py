import bpy, os
import numpy as np

src = os.environ.get("SRC", r"E:\My World\Blender\renders\kingdom\mine_a.png")
img = bpy.data.images.load(src)
W, H = img.size
a = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
x0, y0, x1, y1 = (int(os.environ.get(k, d)) for k, d in
                  (("CX0", 600), ("CY0", 240), ("CX1", 1000), ("CY1", 480)))
crop = a[H - y1:H - y0, x0:x1]          # flip to top-down crop box
S = int(os.environ.get("SCALE", 2))
crop = np.repeat(np.repeat(crop, S, axis=0), S, axis=1)
h, w = crop.shape[:2]
out = bpy.data.images.new("crop", w, h, alpha=False)
out.pixels = crop.ravel().tolist()
out.filepath_raw = os.environ.get(
    "DST", r"E:\My World\Blender\renders\kingdom\_crop.png")
out.file_format = "PNG"
out.save()
print("crop saved %dx%d" % (w, h))
