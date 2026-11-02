"""Dump a spatial map of a built .blend: what is in it, and where.

The camera work needs to know where the castle, the cathedral, the market hall,
the guild and the four gates actually are in v24 -- capital.py's constants say
where they were *meant* to go, but the build applies offsets (the market hall
sits at y=34, not 0) and the gates are placed along avenues.  Guessing those
coordinates is how a landmark shot ends up pointing at a wall.

Outputs `look/_shotmap.json`:

    {"prefix": {"count": n, "bbox": [[x0,y0,z0],[x1,y1,z1]],
                "big": [[name, [cx,cy,cz], volume], ...]}}

and prints a table sorted by object count.

    python look/_shotrun.py --tag map --blend --script look/_shotmap.py
"""
import json
import os
import re
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_shotmap.json")
_RE = re.compile(r"^[A-Za-z_]*")


def prefix_of(name):
    m = _RE.match(name)
    p = m.group(0).rstrip("_") if m else name
    return p or name


def main():
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    groups = {}
    n = 0
    for ob in scene.objects:
        if ob.type != "MESH":
            continue
        n += 1
        p = prefix_of(ob.name)
        bb = [ob.matrix_world @ v.to_4d().to_3d() for v in ()]  # noqa: F841
        mw = ob.matrix_world
        xs, ys, zs = [], [], []
        for corner in ob.bound_box:
            w = mw @ __import__("mathutils").Vector(corner)
            xs.append(w.x)
            ys.append(w.y)
            zs.append(w.z)
        g = groups.setdefault(p, dict(count=0, bbox=None, big=[]))
        g["count"] += 1
        bb = [[min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]]
        if g["bbox"] is None:
            g["bbox"] = bb
        else:
            g["bbox"][0] = [min(g["bbox"][0][i], bb[0][i]) for i in range(3)]
            g["bbox"][1] = [max(g["bbox"][1][i], bb[1][i]) for i in range(3)]
        c = [(bb[0][i] + bb[1][i]) * 0.5 for i in range(3)]
        vol = ((bb[1][0] - bb[0][0]) * (bb[1][1] - bb[0][1])
               * (bb[1][2] - bb[0][2]))
        g["big"].append([ob.name, [round(v, 1) for v in c], round(vol, 1)])

    for p, g in groups.items():
        g["big"].sort(key=lambda r: -r[2])
        g["big"] = g["big"][:6]
        g["bbox"] = [[round(v, 1) for v in g["bbox"][0]],
                     [round(v, 1) for v in g["bbox"][1]]]
        g["centre"] = [round((g["bbox"][0][i] + g["bbox"][1][i]) * 0.5, 1)
                       for i in range(3)]
        g["size"] = [round(g["bbox"][1][i] - g["bbox"][0][i], 1) for i in range(3)]

    print("[map] %d meshes in %d prefixes" % (n, len(groups)), flush=True)
    for p, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
        print("[map] %-14s %6d  centre %-22s size %-22s biggest %s"
              % (p, g["count"], g["centre"], g["size"],
                 g["big"][0][0] if g["big"] else ""), flush=True)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(groups, fh, indent=1, sort_keys=True)
    print("[map] wrote %s" % OUT, flush=True)

    # a few direct questions the shot list needs answered
    for want in ("cath", "keep", "gate", "guild", "mh", "fountain", "bridge",
                 "land", "streetlife", "plaza", "rock", "wall", "mkt"):
        g = groups.get(want)
        if g:
            print("[map] Q %-10s centre %-22s bbox %s..%s" %
                  (want, g["centre"], g["bbox"][0], g["bbox"][1]), flush=True)


if __name__ == "__main__":
    main()
