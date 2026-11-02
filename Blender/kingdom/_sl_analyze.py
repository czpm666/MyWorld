import json, math, collections
d = json.load(open("layout.json", encoding="utf-8"))
print("keys:", list(d.keys()))
print("streets:", len(d.get("streets") or ()))
print("blocks:", len(d.get("blocks") or ()))
print("landmarks:", len(d.get("landmarks") or ()))
roles = collections.Counter((b.get("role") for b in d.get("blocks") or ()))
print("roles:", roles.most_common())
kinds = collections.Counter((s.get("kind") for s in d.get("streets") or ()))
print("street kinds:", kinds.most_common())
s0 = (d.get("streets") or [])[0]
print("street[0] keys:", list(s0.keys()))
print("street[0]:", {k: (v if not isinstance(v, list) else ("[%d]" % len(v))) for k, v in s0.items()})
b0 = (d.get("blocks") or [])[0]
print("block[0] keys:", list(b0.keys()))
print("block[0]:", {k: (v if not isinstance(v, list) else ("[%d] len" % len(v))) for k, v in b0.items()})
# total street length
tot = 0.0
for s in d["streets"]:
    a, b = s.get("a"), s.get("b")
    if a and b:
        tot += math.hypot(b[0]-a[0], b[1]-a[1])
print("sum street a-b length: %.0f m" % tot)
xs=[]; ys=[]
for s in d["streets"]:
    if s.get("a"):
        xs.append(s["a"][0]); ys.append(s["a"][1])
if xs:
    print("extent x %.0f..%.0f  y %.0f..%.0f" % (min(xs),max(xs),min(ys),max(ys)))
