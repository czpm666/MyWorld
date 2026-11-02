"""Splice a span of hd_castle_int.py between two markers with new text."""
import sys

path, m0, m1, newfile = sys.argv[1:5]
src = open(path, encoding="utf-8", newline="").read()
i = src.index(m0)
j = src.index(m1, i + len(m0))
new = open(newfile, encoding="utf-8", newline="").read()
out = src[:i] + new + src[j:]
open(path, "w", encoding="utf-8", newline="").write(out)
print("spliced %d..%d -> %d chars, %d lines" % (i, j, len(out), out.count("\n") + 1))
