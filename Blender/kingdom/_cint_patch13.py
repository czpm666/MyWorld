# -*- coding: utf-8 -*-
import io

P = r"E:\My World\Blender\kingdom\_cint_p4.py"
t = io.open(P, encoding="utf-8").read()
old = '''        if s > 0:
            C.append(rod(nm + "_ar%d" % s, (x + 0.38, y, 1.56),
                         (x + 0.58, y - 0.02, 1.30), 0.085, iron, seg=6))
        else:
            C.append(rod(nm + "_ar%d" % s, (x - 0.38, y, 1.56),
                         (x - 0.34, y - 0.10, 1.02), 0.085, iron, seg=6))'''
new = '''        if s > 0:
            p0 = T @ Vector((0.38, 0.0, 1.56))
            p1 = T @ Vector((0.58, -0.03, 1.28))
        else:
            p0 = T @ Vector((-0.38, 0.0, 1.56))
            p1 = T @ Vector((-0.34, -0.10, 1.02))
        C.append(rod(nm + "_ar%d" % s, p0, p1, 0.085, iron, seg=6))'''
if t.count(old) != 1:
    raise SystemExit("marker miss")
io.open(P, "w", encoding="utf-8", newline="\n").write(t.replace(old, new))
print("ARMS now follow the body frame")
