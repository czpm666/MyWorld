import re, io
p = "hd_sky.py"
s = open(p, encoding="utf-8").read()
def fix(m):
    v = int(m.group(1))
    return "ap_depth=%d" % (int(round(v * 0.55 / 100.0) * 100))
s2, n = re.subn(r"ap_depth=(\d+)", fix, s)
print("ap_depth rewritten:", n)
s2 = s2.replace('ap_near="#7c8f9c", ap_far=None', 'ap_near="#c2d0d8", ap_far=None')
s2 = s2.replace("ap=0.85, ap_start=500, ap_depth=6000", "ap=0.85, ap_start=400, ap_depth=6000")
open(p, "w", encoding="utf-8").write(s2)
for ln in s2.splitlines():
    if "ap=" in ln and "ap_" in ln:
        print(ln.strip())
