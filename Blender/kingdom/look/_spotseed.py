"""Prove which seed reproduces the built city.

build_v24.log says:

    [capital] plan2: 642 blocks / 63 streets in 0.2 s
    [capital] hd_dense: 12215 placements (276 shops), 463 dropped by reservations/wall

so the real city is 642 blocks and 12678 raw placements, 12215 of them kept.
spots.py built its clearance raster with seed=7, which is not SEED.  This
script rebuilds both and prints the numbers so the mismatch is a fact, not a
suspicion.

    E:\\GameProject\\Python313\\python.exe look\\_spotseed.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(KING))
sys.path.insert(0, KING)

import hd_plan2 as P2                                            # noqa: E402
import hd_dense as DN                                            # noqa: E402

S = 1.48
SEED = 20261022
RESERVED = ((0.0, 205.0 * S, 82.0 + 16.0),
            (-152.0 * S, 58.0 * S, 78.0),
            (142.0 * S, 66.0 * S, 52.0),
            (0.0, 0.0, 96.0))


def run(seed):
    res = P2.build(radius=640.0 * S, seed=seed, reserved=RESERVED)
    st = (res.get("city") or {}).get("stats") or {}
    units = DN.placements(res, seed=seed, cov_max=0.36)
    print("[chk] seed %-9d blocks %-4s streets %-4s units %d"
          % (seed, st.get("blocks"), st.get("streets"), len(units)))
    return res, units


for seed in (7, SEED):
    run(seed)
print("[chk] built city (build_v24.log): blocks 642 streets 63 units 12678 (12215 kept)")
