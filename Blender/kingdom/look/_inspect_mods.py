"""_inspect_mods.py -- quick health check of the modules other agents left behind."""
import io
import os
import sys

ROOT = r"E:\My World\Blender\kingdom"
FILES = sys.argv[1:] or [
    "hd_streetlife.py", "hd_house_parts.py", "hd_houses.py", "export_unity.py",
    "bake_palette.py", "hd_landscape.py", "hd_sky.py", "hd_paving.py",
    "hd_street.py", "hd_dense.py", "capital.py",
]

for f in FILES:
    p = os.path.join(ROOT, f)
    if not os.path.exists(p):
        print("%-22s MISSING" % f)
        continue
    raw = io.open(p, "rb").read()
    s = raw.decode("utf-8", "replace")
    tail = s.rstrip()[-70:].replace("\n", " | ")
    print("%-22s %7d B %5d lines  def=%-4d class=%-2d  tail: %s"
          % (f, len(raw), s.count("\n"), s.count("\ndef ") + s.startswith("def "),
             s.count("\nclass "), tail))
    for probe in ("def build", "def preview", "def main", "TODO", "FIXME", "XXX", "NotImplemented"):
        if probe in s:
            print("      has %r x%d" % (probe, s.count(probe)))
