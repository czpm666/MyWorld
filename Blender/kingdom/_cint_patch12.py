# -*- coding: utf-8 -*-
import io

D = r"E:\My World\Blender\kingdom"
P = D + r"\_cint_test.py"
t = io.open(P, encoding="utf-8").read()
old = 'if O[k].name.split("_")[0][:2] in ("bn", "tb", "ch") and 2.00 < lo[0] < 8.75:'
new = 'if objs[k].name.split("_")[0][:2] in ("bn", "tb", "ch") and 2.00 < lo[0] < 8.75:'
if t.count(old) != 1:
    raise SystemExit("marker miss")
io.open(P, "w", encoding="utf-8", newline="\n").write(t.replace(old, new))
print("FIXED objs ref")

P2 = D + r"\_cint_p4.py"
t = io.open(P2, encoding="utf-8").read()
old2 = "        yy = y - L * 0.5 + 0.22 + (L - 0.44) * j / (max(2, int(L / 2.4) + 1) - 1)"
new2 = "        yy = y - L * 0.5 + 0.05 + (L - 0.10) * j / (max(2, int(L / 2.4) + 1) - 1)"
if t.count(old2) != 1:
    raise SystemExit("marker miss 2")
io.open(P2, "w", encoding="utf-8", newline="\n").write(t.replace(old2, new2))
print("MOVED bench legs to the ends")
