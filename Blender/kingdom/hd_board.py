"""hd_board.py - smoke test for hd_common: builds one of each primitive and
renders three views.  Run:

    blender -b --factory-startup --python hd_board.py -- --out board
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
import hd_common as H
import medkit as K
from medkit import T_at as Ts

MAT = {}


def mats():
    MAT["stone"] = K.mat_stone()
    MAT["stone_warm"] = K.mat_stone("stone_sand", base="#8d8168", dark="#5b5342",
                                    light="#a89b7f", scale=2.0)
    MAT["wood"] = K.mat_wood()
    MAT["wood_dark"] = K.mat_wood("timber_dark", base="#3a2517", light="#543823", scale=12)
    MAT["tile"] = K.mat_tile()
    MAT["slate"] = K.mat_tile("roof_slate", base="#4a5560", dark="#333c46", light="#5f6d7a")
    MAT["glass"] = K.mat_glass()
    MAT["iron"] = K.mat_metal()
    MAT["plaster"] = K.mat_plaster()
    MAT["red"] = K.mat_cloth("banner_red", "#8e2b26")
    MAT["gold"] = K.mat_gold()


def main():
    H._clear()
    mats()
    parts = []
    # 1. wall with windows + door
    T = Ts(-9, 0, 0)
    parts += H.wall_course("wall", T, 12.0, 0.7, 9.0, MAT["stone_warm"])
    for i in range(3):
        parts += H.window_arched("win%d" % i, T @ Ts(-3.6 + i * 3.6, 0.3, 4.2, rz=0),
                                 1.4, 2.6, MAT["stone_warm"], MAT["glass"], hood=True,
                                 shutters=None)
    parts += H.door_arched("door", T @ Ts(0, 0.35, 0), 2.0, 3.2, MAT["wood"], MAT["iron"],
                           MAT["stone_warm"], steps=3)
    parts += H.quoin("q", T @ Ts(6.0, 0, 0), 9.0, mat=MAT["stone_warm"])

    # 2. round tower with cone roof
    parts += H.round_tower("tower", Ts(11, 0, 0), 3.2, 16.0, MAT["stone_warm"],
                           MAT["slate"], cap="cone")

    # 3. house with tiled roof, dormer, chimney
    T = Ts(-2, 22, 0)
    parts += H.wall_course("hh", T, 8.0, 6.0, 3.0, MAT["stone_warm"])
    parts += H.apply([], T)
    parts += H.roof("hroof", T @ Ts(0, 0, 3.0), 8.0, 6.0, 3.0, 42, MAT["tile"],
                    MAT["wood"], courses=True, gable_ends=False)
    parts += H.dormer("dorm", T @ Ts(-1.2, 2.4, 4.6), wall=MAT["plaster"],
                      frame=MAT["wood"], glass=MAT["glass"], roof_mat=MAT["tile"])
    parts += H.chimney("chim", T @ Ts(2.6, -1.4, 5.0), 2.6, MAT["stone_warm"], pots=2)

    # 4. machicolation + crenel + banner
    parts += H.machicolation("mach", Ts(9, 22, 12), 8.0, MAT["stone_warm"])
    parts += H.banner("ban", Ts(13, 22, 10), 1.6, 4.0, MAT["red"], MAT["wood_dark"])

    # 5. street furniture
    parts += H.market_stall("stall", Ts(-10, 22, 0), 2.6, 1.6, MAT["wood"],
                            MAT["red"], MAT["slate"])
    parts += H.barrel("bar", Ts(-13, 20, 0), wood=MAT["wood"], hoop=MAT["iron"])
    parts += H.cart("cart", Ts(-6, 26, 0), MAT["wood"], MAT["iron"])
    parts += H.stairs("st", Ts(4, 22, 0), 3.0, 5, mat=MAT["stone_warm"])
    parts += H.statue("stat", Ts(6.5, 26, 0), 3.4, MAT["stone_warm"])

    lo, hi = H.bbox(parts)
    print("[board] parts=%d tris=%d bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)"
          % (len(parts), H.tri_count(parts), lo.x, lo.y, lo.z, hi.x, hi.y, hi.z),
          flush=True)

    H.diorama_floor(MAT["stone"])
    H.setup_world()
    H.setup_engine(samples=48, res=(1400, 900))
    H.three_views("board", center=(-1, 6, 6), size=(34, 34), dist=30)
    print("[board] done", flush=True)


if __name__ == "__main__":
    main()
