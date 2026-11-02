# -*- coding: utf-8 -*-
"""Pick a gate camera that sits on a real street centreline."""
import math
import sys
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_layout as L            # noqa: E402

lay = L.generate(radius=636.0, seed=20261022, )
sts = lay["streets"]
gates = [tuple(lm["pos"]) for lm in lay["landmarks"] if lm["kind"] == "gate"]
# north gate
g = min(gates, key=lambda p: math.hypot(p[0], p[1] - 636.0))
print("north gate", g)
best = None
for s in sts:
    for p, q in ((tuple(s["a"]), tuple(s["b"])),):
        for e, o in ((p, q), (q, p)):
            d = math.hypot(e[0] - g[0], e[1] - g[1])
            if best is None or d < best[0]:
                best = (d, e, o, s["kind"], s.get("w"))
print("nearest street end %.1f m kind=%s w=%s" % (best[0], best[3], best[4]))
d, e, o, kind, w = best
seg = math.hypot(o[0] - e[0], o[1] - e[1])
need = 70.0
t = min(0.92, need / max(1.0, seg))
eye = (e[0] + (o[0] - e[0]) * t, e[1] + (o[1] - e[1]) * t)
print("eye %.1f %.1f (%.1f m from gate, on %s)" % (eye[0], eye[1],
                                                   math.hypot(eye[0] - g[0], eye[1] - g[1]), kind))
print("look %.1f %.1f 13.0 lens 38" % (g[0], g[1]))
