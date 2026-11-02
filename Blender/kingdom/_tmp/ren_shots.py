import io

p = r"E:\My World\Blender\kingdom\capital.py"
s = io.open(p, encoding="utf-8").read()
pairs = [('"hd_gate_south"', '"b5_gate_in"'), ('"hd_castle"', '"b5_castle"'),
         ('"hd_cathedral"', '"b5_cathedral"'), ('"hd_market"', '"b5_plaza"'),
         ('"hd_street"', '"b5_street"'), ('"hd_overview"', '"b5_overview"'),
         ('"hd_outer"', '"b5_outer"'), ('"hd_suburb"', '"b5_suburb"')]
n = 0
for a, b in pairs:
    n += s.count(a)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("renamed", n)
