"""Count objects per tag group inside each built village .blend (report numbers)."""
import bpy
import os
import json
import re
from collections import Counter

KD = r"E:\My World\Blender\kingdom"

for v in ("farm_a", "farm_b", "farm_c"):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(KD, v + ".blend"))
    c = Counter()
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        n = o.name
        if not n.startswith(v + "_"):
            c["(rig)"] += 1
            continue
        tag = re.sub(r"_\d+$", "", n[len(v) + 1:])
        c[tag] += 1
    print("TAGS " + json.dumps({"variant": v, "n": len(c), "tags": dict(c)}))
