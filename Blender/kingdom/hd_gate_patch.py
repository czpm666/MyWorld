# -*- coding: utf-8 -*-
"""One-off patch helper: literal replacements in hd_gate.py (UTF-8 safe)."""
import io
import sys

PAIRS = [
    ('asc = ashlar("gh_asc", Tc, 19.40, GH_TOP, sw, rng)[0]',
     'asc = ashlar("gh_asc", Tc, 19.40, GH_TOP, sw, rng, bw=1.00, bh=0.44)[0]'),
    ('GH_D - 0.10, MAT["cobble"], rng, cw=0.82, cl=0.64, h=0.05)',
     'GH_D - 0.10, MAT["cobble"], rng, cw=1.10, cl=0.90, h=0.05)'),
    ('-0.22, MAT["cobble"], rng, cw=0.82, cl=0.64, h=0.05)',
     '-0.22, MAT["cobble"], rng, cw=1.10, cl=0.90, h=0.05)'),
]

path = sys.argv[1] if len(sys.argv) > 1 else "hd_gate.py"
src = io.open(path, "rb").read().decode("utf-8")
n = 0
for a, b in PAIRS:
    if a in src:
        src = src.replace(a, b)
        n += 1
    else:
        print("MISS:", a[:60])
io.open(path, "wb").write(src.encode("utf-8"))
print("applied", n, "of", len(PAIRS))
