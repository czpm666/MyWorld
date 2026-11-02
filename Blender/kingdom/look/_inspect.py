import io
import re
import collections

s = io.open(r"E:\My World\Blender\kingdom\hd_castle_int.py",
            encoding="utf-8", newline="").read()
print("build_fireplace defs:", s.count("def build_fireplace("),
      "calls:", s.count("build_fireplace("))
names = collections.Counter(re.findall(r'ci_fp_[a-zA-Z0-9_]+', s))
print(sorted(names.items()))
i = s.index("def build_fireplace(")
print(s[i:i + 700])
