"""Fast QA render of selected shots at reduced size.

    blender -b --factory-startup --python _gtest.py -- a,c[,names] [samples] [w] [h]

Writes to renders\\kingdom\\_qa so a quick 700x450 check never clobbers the
full-size deliverable renders in renders\\kingdom.
"""
import os
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_gate as G                                            # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
names = (argv[0] if argv else "a,c").split(",")
samples = int(argv[1]) if len(argv) > 1 else 24
w = int(argv[2]) if len(argv) > 2 else 700
h = int(argv[3]) if len(argv) > 3 else 450

QA = os.path.join(G.OUT_DIR, "_qa")
os.makedirs(QA, exist_ok=True)
G.OUT_DIR = QA
G.preview(samples=samples, res=(w, h), only=names)
