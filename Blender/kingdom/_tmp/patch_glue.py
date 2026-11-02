import io
p = r"E:\My World\Blender\kingdom\capital_hd_glue.py"
s = io.open(p, encoding="utf-8").read()
# 1. drop the duplicate FAILED reset (it would hide the import failures)
s = s.replace("FAILED = []\n_FAIL_N = {}", "_FAIL_N = {}", 1)
# 2. x is not defined in the mesh path; note the three mesh calls
pairs = [
 ('    return note(name, place(guard(name, lambda: hd_gate.build_gatehouse(MAT, rng)),\n                            x, y, z, rot))',
  '    if hd_gate is None:\n        return []\n    return note(name, place(guard(name, lambda: hd_gate.build_gatehouse(MAT, rng)),\n                            x, y, z, rot))'),
 ('    return note("castle", place(guard("castle", lambda: hd_castle.build(castle_mats(MAT), rng)),\n                                x, y, z, rot))',
  '    if hd_castle is None:\n        return []\n    return note("castle", place(guard("castle", lambda: hd_castle.build(castle_mats(MAT), rng)),\n                                x, y, z, rot))'),
 ('    return note("cathedral",\n                place(guard("cathedral",',
  '    if hd_cathedral is None:\n        return []\n    return note("cathedral",\n                place(guard("cathedral",'),
 ('    return note("market_hall",\n                place(guard("market_hall",',
  '    if hd_market is None:\n        return []\n    return note("market_hall",\n                place(guard("market_hall",'),
 ('    return note("guild_hall",\n                place(guard("guild_hall",',
  '    if hd_market is None:\n        return []\n    return note("guild_hall",\n                place(guard("guild_hall",'),
 ('    return note("fountain",\n                place(guard("fountain",',
  '    if hd_market is None:\n        return []\n    return note("fountain",\n                place(guard("fountain",'),
 ('    return place(guard("house",\n                       lambda: hd_houses.house(',
  '    if hd_houses is None:\n        return []\n    return place(guard("house",\n                       lambda: hd_houses.house('),
]
for a, b in pairs:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched")
