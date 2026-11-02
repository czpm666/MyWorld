# -*- coding: utf-8 -*-
import io
import sys

p = r"E:\My World\Blender\kingdom\hd_layout.py"
s = io.open(p, encoding="utf-8").read()
old = """            fy = rng.uniform(0.25, 0.9)
            ry = rng.uniform(1.6, 4.2)
            depth = fy + bd + ry"""
new = """            fy = rng.uniform(0.25, 0.9)
            ry = rng.uniform(1.6, 4.2)
            # a back-row house has no front yard: its plot is just the building
            # plus the lane it faces, otherwise the fill test rejects it
            depth = (bd + 1.4) if flip else (fy + bd + ry)"""
if old not in s:
    print("MISS depth")
    sys.exit(1)
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched depth")
