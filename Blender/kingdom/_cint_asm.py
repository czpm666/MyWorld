# -*- coding: utf-8 -*-
"""Assemble p1..p4 into hd_castle_int.py."""
import io
import os

D = r"E:\My World\Blender\kingdom"
parts = []
for nm in ("_cint_p1.py", "_cint_p2.py", "_cint_p3.py", "_cint_p4.py"):
    t = io.open(os.path.join(D, nm), encoding="utf-8").read()
    lines = t.split("\n")
    # drop leading coding cookie / module docstring fragments from later parts
    if nm != "_cint_p1.py":
        while lines and (lines[0].startswith("# -*-") or lines[0].strip() == ""):
            lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    parts.append("\n".join(lines))

src = "\n\n\n".join(parts) + "\n"
dst = os.path.join(D, "hd_castle_int.py")
io.open(dst, "w", encoding="utf-8", newline="\n").write(src)
print("WROTE", dst, len(src), "chars", src.count("\n"), "lines")
for key in ("def build(", "def footprint(", "def height(", "def preview(", "MAT_KEYS = ("):
    print(key, "->", src.count(key))
