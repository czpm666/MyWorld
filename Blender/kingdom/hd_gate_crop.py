# -*- coding: utf-8 -*-
"""Crop a region out of a render so it can be inspected at full resolution."""
import sys
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = [int(v) for v in sys.argv[3:7]]
scale = float(sys.argv[7]) if len(sys.argv) > 7 else 2.0
im = Image.open(src).convert("RGB")
box = im.crop((x0, y0, x1, y1))
box = box.resize((int(box.width * scale), int(box.height * scale)), Image.LANCZOS)
box.save(dst)
print("wrote", dst, box.size)
