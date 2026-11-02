import re, io
p = "hd_sky.py"
src = io.open(p, encoding="utf-8").read()
plan = [(500,11000),(400,9000),(500,11000),(800,14000),(300,8000),
        (500,9000),(400,10000),(300,9000),(400,8000),(180,5000),(400,9000)]
pat = re.compile(r"(\n\s*)ap=([\d.]+), ap_start=[\d.]+, ap_depth=[\d.]+, ap_gamma=[\d.]+,", re.U)
it = iter(plan)
def sub(m):
    s, d = next(it)
    return "%sap=%s, ap_start=%g, ap_depth=%g, ap_gamma=1.0," % (m.group(1), m.group(2), s, d)
src2, n = pat.subn(sub, src)
io.open(p, "w", encoding="utf-8", newline="\n").write(src2)
print("rewrote", n, "triples")
for line in src2.splitlines():
    if "ap_start=" in line:
        print(line.strip())
