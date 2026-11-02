"""Print the roof-cover palette each material name resolves to."""
import sys

sys.path.insert(0, r"E:\My World\Blender")
sys.path.insert(0, r"E:\My World\Blender\kingdom")

import bpy  # noqa: E402
import hd_roof as R  # noqa: E402

rows = []
for m in bpy.data.materials:
    kind, pal = R._palette_for(m.name)
    if kind is None:
        continue
    rows.append((m.name, kind, pal[0]))
for name, kind, base in sorted(rows):
    print("%-26s %-6s %s" % (name, kind, base))
print("total", len(rows))
