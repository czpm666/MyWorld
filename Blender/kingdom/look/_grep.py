import io
import sys

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
L = io.open(p, encoding="utf-8").read().split("\n")
for i, l in enumerate(L):
    if any(k in l for k in sys.argv[1:]):
        print(i + 1, l)
