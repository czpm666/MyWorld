import json
p = r"E:\My World\Blender\kingdom\layout.json"
j = json.load(open(p, encoding="utf-8"))
for e in j["landmarks"]:
    print(e["kind"], e.get("name"), e["pos"], "rz=", e["rz"], "w/d=", e.get("w"), e.get("d"))
print("\ncity counts/stats:", json.dumps(j["city"].get("counts"), ensure_ascii=False)[:400])
print("city stats:", json.dumps(j["city"].get("stats"), ensure_ascii=False)[:400])
print("mains:", json.dumps(j["city"].get("mains"), ensure_ascii=False)[:600])
print("plaza:", json.dumps(j["city"].get("plaza"), ensure_ascii=False)[:300])
print("wall pts:", len(j["city"]["wall"]))
