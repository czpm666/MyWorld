# -*- coding: utf-8 -*-
"""Acceptance numbers for hd_layout, written to a UTF-8 file."""
import collections
import io
import math
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_layout as L            # noqa: E402

lay = L.generate(radius=636.0, seed=20261022)
pl = lay["plots"]
bl = lay["blocks"]
sts = lay["streets"]

area_city = math.pi * 636.0 ** 2
area_blocks = sum(L.area(b["poly"]) for b in bl)
area_built = sum(max(1.0, p.get("w", 8.0)) * max(1.0, p.get("d", 9.0)) for p in pl)

k = collections.Counter(p["kind"] for p in pl)
src = collections.Counter(p.get("source", "house") for p in pl)
ring = collections.Counter(str(p.get("ring")) for p in pl)
role = collections.Counter(b.get("role", "?") for b in bl)

# ---- 1. names derived from geometry --------------------------------
want = {"北门大道": (45, 135), "东门大街": (135, 225),
        "南门大道": (225, 315), "西门大街": (315, 45)}
agg = {}
for s in sts:
    nm = s.get("name")
    if not nm:
        continue
    for pt in (tuple(s["a"]), tuple(s["b"])):
        r = math.hypot(pt[0], pt[1])
        if nm not in agg or r > agg[nm][0]:
            agg[nm] = (r, math.degrees(math.atan2(pt[1], pt[0])) % 360.0)
bad_names = []
for nm, (r, ang) in agg.items():
    if nm not in want:
        continue
    lo, hi = want[nm]
    ok = (lo <= ang < hi) if lo < hi else (ang >= lo or ang < hi)
    if not ok:
        bad_names.append((nm, round(r, 1), round(ang, 1)))

# ---- 2. empty blocks ----------------------------------------------
empty = [b for b in bl if b.get("buildings", 0) == 0]
declared = [b for b in bl if b.get("open")]

# ---- 3. block role mix (types must follow the block, not a radius band) --
mix = {}
for b in bl:
    if not b.get("buildings"):
        continue
    ps = [p for p in pl if p["block_id"] == b["id"]]
    kinds = collections.Counter(p["kind"] for p in ps)
    mix.setdefault(b.get("role", "?"), collections.Counter()).update(kinds)
mix_txt = {}
for rl, c in mix.items():
    tot = sum(c.values())
    mix_txt[rl] = ", ".join("%s %d%%" % (kk, 100 * v / tot)
                            for kk, v in c.most_common(3))

# ---- 4. functional distance --------------------------------------
marks = {m[0]: (m[1], m[2]) for m in lay["city"].get("marks", [])} \
    if isinstance(lay.get("city"), dict) and lay["city"].get("marks") else {}
gate_pts = [s["pos"] for s in lay.get("landmarks", []) if s.get("kind") == "gate"]
palace = None
for lm in lay.get("landmarks", ()):
    if lm.get("kind") in ("palace", "castle"):
        palace = lm["pos"]
military = ("armory", "barracks", "garrison", "weaponsmith", "stable")
comm = ("tavern", "inn", "shop", "market", "baker", "bakery", "clothier",
        "general_store", "magic_shop", "guild")
noble = ("noble_manor", "manor", "palace_house")


def dmin(p, pts):
    return min((math.hypot(p[0] - q[0], p[1] - q[1]) for q in pts), default=1e9)


mil_d, com_d, nob_d = [], [], []
for p in pl:
    d = math.hypot(p["pos"][0], p["pos"][1])
    if p["kind"] in military:
        mil_d.append(round(dmin(p["pos"], gate_pts) if gate_pts else d, 1))
    if p["kind"] in comm:
        com_d.append(round(d, 1))
    if p["kind"] in noble:
        nob_d.append(round(dmin(p["pos"], [palace]) if palace else d, 1))

# ---- 5. setback + street intrusion -------------------------------
clear = []
for p in pl:
    try:
        clear.append(L.street_clearance([tuple(p["pos"])]))
    except Exception:
        pass
intr = sum(1 for c in clear if c < 0.35)

# street length by tier
seglen = collections.Counter()
for s in sts:
    L2 = s.get("len")
    if L2 is None:
        L2 = math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1])
    seglen[s["kind"]] += L2

out = io.StringIO()
w = out.write
w(u"[stat] blocks %d  sub-blocks %d  plots %d (house %d / shop %d)\n"
  % (len(bl), sum(1 for _ in ()), len(pl), src.get("house", 0), src.get("shop", 0)))
w(u"[stat] coverage %.1f%% of %.2f km2   block fill %.1f%% of %.2f km2\n"
  % (100 * area_built / area_city, area_city / 1e6,
     100 * area_built / max(1.0, area_blocks), area_blocks / 1e6))
w(u"[stat] blocks with no building %d   declared squares/open %d\n"
  % (len(empty), len(declared)))
w(u"[stat] street length  main %.0f m  secondary %.0f m  alley %.0f m\n"
  % (seglen.get("main", 0), seglen.get("secondary", 0), seglen.get("alley", 0)))
w(u"[stat] names: %d distinct, %d gate-roads off-sector %s\n"
  % (len(agg), len(bad_names), bad_names[:4]))
w(u"[stat] intrusion (plot within 0.35 m of a carriageway edge): %d of %d\n"
  % (intr, len(clear)))
w(u"[stat] kinds: %s\n" % ", ".join("%s %d" % (kk, v) for kk, v in k.most_common(18)))
w(u"[stat] by ring: %s\n" % ", ".join("%s %d" % (kk, v) for kk, v in ring.most_common()))
w(u"[stat] block roles: %s\n" % ", ".join("%s %d" % (kk, v) for kk, v in role.most_common(10)))
for rl in mix_txt:
    w(u"[stat]   %-12s -> %s\n" % (rl, mix_txt[rl]))
w(u"[stat] military kinds: n=%d  dist-to-gate min %.0f / med %.0f / max %.0f m\n"
  % (len(mil_d), min(mil_d or [0]), sorted(mil_d or [0])[len(mil_d) // 2] if mil_d else 0,
     max(mil_d or [0])))
w(u"[stat] noble kinds:    n=%d  dist-to-palace med %.0f m\n"
  % (len(nob_d), sorted(nob_d)[len(nob_d) // 2] if nob_d else 0))

io.open(r"E:\My World\Blender\kingdom\_tmp\qc.txt", "w", encoding="utf-8").write(out.getvalue())
print("written")
