import ast
import io
import os

p = r"E:\My World\Blender\kingdom\hd_rock.py"
t = r"E:\My World\Blender\kingdom\hd_rock_tail.py"
s = io.open(p, encoding="utf-8").read()
k = s.index("\n\ndef cliff_ring(")
s = s[:k] + "\n\n" + io.open(t, encoding="utf-8").read()
ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok", len(s))
