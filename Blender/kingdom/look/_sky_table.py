"""Print the 13 documented knobs for each hd_sky preset (no Blender needed)."""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
src = io.open(os.path.join(HERE, "..", "hd_sky.py"), encoding="utf-8").read()
i = src.index("PRESETS = {")
j = src.index("\n}\n", i)
block = src[i:j]

keys = ["sun_elev", "sun_azim", "sun_energy", "sun_color", "zenith", "horizon",
        "haze", "clouds", "cloud_scale", "gain", "sat", "ambient", "exposure"]
cur = None
rows = []
for line in block.splitlines():
    m = re.match(r'\s{4}"(\w+)":\s*dict\(', line)
    if m:
        cur = {"name": m.group(1)}
        rows.append(cur)
        continue
    if cur is None:
        continue
    for k in keys:
        mm = re.search(r"\b%s=([^,]+)" % k, line)
        if mm:
            cur.setdefault(k, mm.group(1).strip())

hdr = "| preset | " + " | ".join(keys) + " |"
print(hdr)
print("|" + "---|" * (len(keys) + 1))
for r in rows:
    print("| `%s` | %s |" % (r["name"], " | ".join(r.get(k, "-") for k in keys)))
print()
print("%d presets" % len(rows))
