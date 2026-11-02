"""Tree LOD / hedge / furrow sanity probe -- runs in plain CPython + numpy.

    python look/_land_geo_probe.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    import hd_landscape_geo as G

    print("== trees ==")
    tot = {}
    for kind in range(4):
        for lod in range(3):
            V, F, C = G.tree_template(kind, lod, seed=3)
            H = V[:, 2].max() - V[:, 2].min()
            W = (V[:, 0].max() - V[:, 0].min()) / H
            tr = [t for t in F]
            print("  %-8s lod%d  %5d tris  %4d verts  crown/H %.2f  shade %.2f..%.2f"
                  % (G.KIND_NAME[kind], lod, len(F), len(V), W,
                     C[:, 0].min(), C[:, 0].max()))
            tot[(kind, lod)] = len(F)

    print("\n== hedge ==")
    class LS:
        @staticmethod
        def _gz(x, y):
            import numpy as np
            return np.zeros(len(x))
    class Acc:
        def __init__(self):
            self.n = 0
        def quad(self, *a, **k):
            self.n += 1
        def tri(self, *a, **k):
            self.n += 1
    import numpy as np
    a = Acc()
    P = [(0.0, 0.0), (0.0, 90.0)]
    n = G.hedge_band(LS, a, P, 3.4, 2.2, np.random.default_rng(1),
                     (0.1, 0.2, 0.1), None, None, gap_p=0.02)
    print("  90 m hedge -> %d tris, %d faces fetched" % (n, a.n))

    print("\n== ridges ==")
    r = G.furrow_mesh(LS, 0.0, 0.0, 0.0, 100.0, 90.0, 2.8, 0.42,
                      np.random.default_rng(2), (0.2, 0.1, 0.05),
                      (0.5, 0.4, 0.2))
    V, F, C = r
    print("  100x90m field @2.8m -> %d quads (%d tris), %d verts"
          % (len(F), len(F) * 2, len(V)))
    print("  z range %.3f..%.3f  (amp was 0.42)" % (V and min(p[2] for p in V),
                                                    V and max(p[2] for p in V)))


main()
