import io

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
L = io.open(p, encoding="utf-8").read().split("\n")
for i, l in enumerate(L):
    if l.startswith("def _ashlar"):
        for k in range(i, i + 46):
            print(k + 1, L[k])
        break
