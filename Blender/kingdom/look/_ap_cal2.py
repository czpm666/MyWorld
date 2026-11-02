import re, io
p = "hd_sky.py"
src = io.open(p, encoding="utf-8").read()
plan = [(400,9000),(500,11000),(800,14000),(300,8000),(500,9000),
        (400,10000),(300,9000),(400,8000),(180,5000),(400,9000)]
pat = re.compile(r"ap_start=([\d.]+), ap_depth=([\d.]+)")
hits = list(pat.finditer(src))
print("found", len(hits))
it = iter(plan)
def sub(m):
    try:
        s, d = next(it)
    except StopIteration:
        return m.group(0)
    return "ap_start=%g, ap_depth=%g" % (s, d)
out = []
last = 0
for i, m in enumerate(hits):
    if i == 0:          # BASE, already calibrated
        continue
    out.append(src[last:m.start()])
    out.append(sub(m))
    last = m.end()
out.append(src[last:])
src2 = "".join(out)
io.open(p, "w", encoding="utf-8", newline="\n").write(src2)
for line in src2.splitlines():
    if "ap_start=" in line:
        print(line.strip())
