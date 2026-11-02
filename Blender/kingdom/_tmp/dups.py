import sys; sys.path.insert(0, r"E:\My World\Blender\kingdom")
import collections, hd_layout as L
specs = L.capital_layout_specs(seed=20261022, r_core=296.0, plaza=(0,0,84), castle=(0,205,94), cathedral=(-152,58,54,98), guild=(142,66,26,44), market_hall=(0,34,48,34), fountain=(0,0,26), gates=((300,0),(0,300),(-300,0),(0,-300)), outer=True)
res = L.layout_city(specs)
P = res["placements"]
print("placements", len(P))
c = collections.Counter((round(p["x"],1), round(p["y"],1), p["kind"]) for p in P)
dup = [(k,v) for k,v in c.items() if v>1]
print("dup positions:", len(dup))
inpl = [p for p in P if abs(p["x"])<39 and abs(p["y"])<39]
print("inside plaza:", len(inpl))
for p in inpl[:8]: print("  ", p["kind"], round(p["x"],1), round(p["y"],1), p["source"], "block", p.get("block"))
