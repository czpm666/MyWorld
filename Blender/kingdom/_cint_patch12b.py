# -*- coding: utf-8 -*-
import io

P = r"E:\My World\Blender\kingdom\_cint_test.py"
t = io.open(P, encoding="utf-8").read()
old = 'if objs[k].name.split("_")[0][:2] in ("bn", "tb", "ch") and 2.00 < lo[0] < 8.75:'
new = ('if objs[k].name.split("_")[0][:2] in ("bn", "tb") '
       'and 2.00 < lo[0] < 8.75 and hi[2] < 1.60:')
if t.count(old) != 1:
    raise SystemExit("marker miss")
io.open(P, "w", encoding="utf-8", newline="\n").write(t.replace(old, new))
print("FIXED seating filter")
