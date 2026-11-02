# -*- coding: utf-8 -*-
import io
P = r"E:\My World\Blender\kingdom\_cint_test.py"
t = io.open(P, encoding="utf-8").read()
old = """seat = 0.0
for k, (lo, hi) in enumerate(B):
    if 0.34 <= hi[2] <= 1.32 and 2.00 < lo[0] < 8.75 and hi[0] < 8.78:
        seat = max(seat, hi[0])"""
new = """seat = 0.0
for k, (lo, hi) in enumerate(B):
    if O[k].name.split("_")[0][:2] in ("bn", "tb", "ch") and 2.00 < lo[0] < 8.75:
        seat = max(seat, hi[0])"""
assert t.count(old) == 1
t = t.replace(old, new)
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("PATCHED test seating")
