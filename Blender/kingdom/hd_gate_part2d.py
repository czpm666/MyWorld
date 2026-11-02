# --------------------------------------------------------------------------
#  ground, moat, roads
# --------------------------------------------------------------------------
SITE_X = 46.0
FRONT_Y = 56.0
BACK_Y = -46.0
PLAZA_Y = -13.0
STREET_X = 5.20


def _prism_z(name, pts, z0, z1, mat):
    """A vertical prism from a 2-D (x, y) polygon."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        xa, ya = pts[i]
        xb, yb = pts[(i + 1) % n]
        area += xa * yb - xb * ya
    if area < 0.0:
        pts = list(reversed(pts))
    verts = [(x, y, z0) for (x, y) in pts] + [(x, y, z1) for (x, y) in pts]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return _mk(name, verts, faces, mat)


def _strip(name, p0, p1, w, z0, z1, mat):
    """A straight box between two ground points, w wide."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    ang = math.atan2(dx, dy)
    mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
    return box(name, Ts(mx, my, (z0 + z1) * 0.5, rz=ang), (w, ln, z1 - z0), mat,
               bev=0.01)


def _plane(name, x0, x1, y0, y1, z, mat, t=0.10):
    """A ground plate; thin so it never fights with the objects on it."""
    return box(name, Ts((x0 + x1) * 0.5, (y0 + y1) * 0.5, z - t * 0.5),
               (x1 - x0, y1 - y0, t), mat)


def build_ground(MAT, rng):
    p = []
    st, sd, pale = MAT["stone"], MAT["stone_dark"], MAT["stone_pale"]
    grass, cob, water = MAT["grass"], MAT["cobble"], MAT["water"]
    BIG = 240.0
    # ---- meadow: four plates leaving a hole for the moat ------------------
    p.append(_plane("gd_grS", -BIG, BIG, -BIG, MOAT_A - 0.40, 0.0, grass))
    p.append(_plane("gd_grN", -BIG, BIG, MOAT_B + 0.40, BIG, 0.0, grass))
    p.append(_plane("gd_grW", -BIG, -SITE_X, MOAT_A - 0.40, MOAT_B + 0.40, 0.0, grass))
    p.append(_plane("gd_grE", SITE_X, BIG, MOAT_A - 0.40, MOAT_B + 0.40, 0.0, grass))

    # ---- the moat --------------------------------------------------------
    p.append(box("gd_bed", Ts(0, (MOAT_A + MOAT_B) * 0.5, MOAT_BED - 0.10),
                 (SITE_X * 2, MOAT_B - MOAT_A, 0.20), sd, bev=0.02))
    p.append(_mk("gd_water",
                 [(-SITE_X + 0.05, MOAT_A + 0.05, WATER_Z),
                  (SITE_X - 0.05, MOAT_A + 0.05, WATER_Z),
                  (SITE_X - 0.05, MOAT_B - 0.05, WATER_Z),
                  (-SITE_X + 0.05, MOAT_B - 0.05, WATER_Z)],
                 [[0, 1, 2, 3]], water))
    # revetments (both banks) and the two end walls
    for tag, y0, y1 in (("gd_rvn", MOAT_A - 0.40, MOAT_A),
                        ("gd_rvf", MOAT_B, MOAT_B + 0.40)):
        p.append(box(tag, Ts(0, (y0 + y1) * 0.5, MOAT_BED * 0.5),
                     (SITE_X * 2, y1 - y0, abs(MOAT_BED)), sd, bev=0.02))
        p.append(box(tag + "_cop", Ts(0, (y0 + y1) * 0.5, 0.06),
                     (SITE_X * 2, y1 - y0 + 0.16, 0.12), pale, bev=0.015))
    for s in (-1, 1):
        p.append(box("gd_rve%d" % s, Ts(s * (SITE_X - 0.20), (MOAT_A + MOAT_B) * 0.5,
                                        MOAT_BED * 0.5),
                     (0.40, MOAT_B - MOAT_A, abs(MOAT_BED)), sd, bev=0.02))

    # ---- approach road: bridge throat then the highway -------------------
    road = [(2.70, MOAT_B), (2.70, 31.90), (4.20, 33.60), (4.20, ROAD_END),
            (-4.20, ROAD_END), (-4.20, 33.60), (-2.70, 31.90), (-2.70, MOAT_B)]
    p.append(_prism_z("rd_body", road, 0.0, DECK, cob))
    for s in (-1, 1):
        p.append(_strip("rd_kr%dA" % s, (s * 2.70, MOAT_B), (s * 2.70, 31.90),
                        0.30, 0.0, 0.17, pale))
        p.append(_strip("rd_kr%dB" % s, (s * 2.70, 31.90), (s * 4.20, 33.60),
                        0.30, 0.0, 0.17, pale))
        p.append(_strip("rd_kr%dC" % s, (s * 4.20, 33.60), (s * 4.20, ROAD_END),
                        0.30, 0.0, 0.17, pale))
        # cart ruts
        p.append(box("rd_rut%d" % s, Ts(s * 0.78, (33.60 + ROAD_END) * 0.5, DECK - 0.025),
                     (0.34, ROAD_END - 33.60, 0.05), MAT["stone_dark"]))
    # the far abutment, buried under the joint
    p.append(box("rd_ab", Ts(0, 31.20, MOAT_BED * 0.5),
                 (9.20, 0.95, abs(MOAT_BED) + 0.46), sd, bev=0.02))

    # ---- city street and the plaza --------------------------------------
    p.append(_prism_z("ct_st", [(-STREET_X, BACK_Y), (STREET_X, BACK_Y),
                                (STREET_X, PLAZA_Y), (-STREET_X, PLAZA_Y)],
                      0.0, DECK, cob))
    p.append(_prism_z("ct_pl", [(-11.0, PLAZA_Y), (11.0, PLAZA_Y),
                                (11.0, -GH_D), (-11.0, -GH_D)], 0.0, DECK, cob))
    for s in (-1, 1):
        p.append(_strip("ct_kr%d" % s, (s * STREET_X, BACK_Y), (s * STREET_X, PLAZA_Y),
                        0.30, 0.0, 0.17, pale))
        p.append(_strip("ct_kp%d" % s, (s * 11.0, PLAZA_Y), (s * 11.0, -GH_D),
                        0.30, 0.0, 0.17, pale))
    # paving in front of the gate, laid as real stones
    p += flagstones("ct_fs1", Ts(0, 0, DECK + 0.005), 21.0, PLAZA_Y + 0.4, -GH_D + 0.4,
                    MAT["cobble"], rng, cw=1.20, cl=0.95, h=0.05)
    p += flagstones("ct_fs2", Ts(0, 0, DECK + 0.005), 9.6, -22.0, PLAZA_Y - 0.2,
                    MAT["cobble"], rng, cw=1.15, cl=0.90, h=0.05)
    # stone aprons at the two tower doors
    for s in (-1, 1):
        p.append(_prism_z("ct_ap%d" % s,
                          [(s * 10.6, -GH_D - 0.6), (s * 18.4, -GH_D - 0.6),
                           (s * 18.4, -11.2), (s * 10.6, -11.2)],
                          0.0, 0.08, pale))
    return p


# --------------------------------------------------------------------------
#  props: the road is alive, the gate is guarded
# --------------------------------------------------------------------------
def _hut(name, T, w, d, h, MAT):
    p = []
    sw, wd, pale = MAT["stone_warm"], MAT["wood_dark"], MAT["stone_pale"]
    p.append(box(name + "_w", T @ Ts(0, 0, h * 0.5), (w, d, h), sw, bev=0.02))
    p += gable_roof(name + "_rf", T @ Ts(0, 0, h), w, d, h * 0.34, MAT["tile"], wd)
    p.append(box(name + "_d", T @ Ts(0, -d * 0.5 - 0.02, 0.90), (0.90, 0.10, 1.80),
                 wd, bev=0.01))
    p.append(box(name + "_dm", T @ Ts(0, -d * 0.5 - 0.08, 1.86), (1.10, 0.10, 0.12),
                 pale))
    for s in (-1, 1):
        p.append(box(name + "_sh%d" % s, T @ Ts(s * w * 0.30, -d * 0.5 - 0.03, 1.45),
                     (0.70, 0.06, 0.60), MAT["glass"]))
    return p


def build_props(MAT, rng):
    p = []
    iron, wd, wood = MAT["iron_dark"], MAT["wood_dark"], MAT["wood"]
    st, pale = MAT["stone"], MAT["stone_pale"]
    # ---- just outside the barbican --------------------------------------
    for s in (-1, 1):
        p.append(cyl("pr_bol%d" % s, Ts(s * 3.90, 31.70, 0.30), 0.22, 0.70, st, seg=12))
        p.append(sphere("pr_bob%d" % s, Ts(s * 3.90, 31.70, 0.68), 0.22, pale, seg=12,
                        ring=6))
    p += _hut("pr_hut", Ts(-8.6, 34.6, 0), 3.20, 2.70, 2.50, MAT)
    p.append(H.lantern_post("pr_lp0", Ts(4.90, 33.20, 0.0), 3.10, iron, MAT["glow"]))
    p.append(H.lantern_post("pr_lp1", Ts(-4.90, 39.00, 0.0), 3.10, iron, MAT["glow"]))
    p.append(H.lantern_post("pr_lp2", Ts(4.90, 45.00, 0.0), 3.10, iron, MAT["glow"]))
    # fence along the meadow edge of the road
    for s in (-1, 1):
        for i in range(7):
            yy = 33.20 + i * 2.10
            p.append(box("pr_fp%d_%d" % (s, i), Ts(s * 5.30, yy, 0.52),
                         (0.13, 0.13, 1.04), wd))
        for k, zz in enumerate((0.46, 0.88)):
            p.append(box("pr_fr%d_%d" % (s, k), Ts(s * 5.30, 39.50, zz),
                         (0.09, 13.00, 0.10), wd))
    # a cart, coming in from the fields
    p.append(H.cart("pr_cart", Ts(2.30, 38.50, 0.0, rz=PI - 0.10), wood, iron, L=2.6,
                    W=1.3))
    p.append(H.barrel("pr_br0", Ts(6.40, 36.20, 0.0), 0.34, 0.92, wood, iron))
    p.append(H.barrel("pr_br1", Ts(7.10, 36.55, 0.0), 0.32, 0.86, wood, iron))
    p.append(H.crate("pr_cr0", Ts(-5.90, 33.10, 0.0), 0.74, wood))
    p.append(H.haystack("pr_hay", Ts(-15.0, 41.0, 0.0), 2.30, 3.40, MAT["grass"]))
    # signpost at the fork
    p.append(cyl("pr_sp", Ts(-6.10, 32.30, 1.35), 0.09, 2.70, wd, seg=10))
    p.append(box("pr_sb0", Ts(-6.10, 32.18, 2.36), (1.20, 0.08, 0.30), wood, bev=0.01))
    p.append(box("pr_sb1", Ts(-6.10, 32.42, 1.94), (0.95, 0.08, 0.26), wood, bev=0.01))
    p.append(sphere("pr_sc", Ts(-6.10, 32.30, 2.78), 0.14, iron, seg=10, ring=6))
    # milestone
    p.append(box("pr_ms", Ts(4.75, 35.80, 0.34), (0.52, 0.34, 0.68), pale, bev=0.02))
    p.append(box("pr_ms2", Ts(4.75, 35.80, 0.70), (0.60, 0.42, 0.08), st))

    # ---- inside the city ------------------------------------------------
    for i, (xx, yy) in enumerate(((7.60, -20.0), (-7.60, -26.0))):
        p += H.market_stall("pr_mk%d" % i, Ts(xx, yy, DECK, rz=0.0 if xx > 0 else PI),
                            MAT["wood"], MAT["banner_red"], MAT["banner_blue"])
    p.append(H.barrel("pr_br2", Ts(-4.40, -15.20, 0.0), 0.34, 0.90, wood, iron))
    p.append(H.barrel("pr_br3", Ts(-3.60, -15.60, 0.0), 0.32, 0.86, wood, iron))
    p.append(H.crate("pr_cr1", Ts(4.60, -16.40, 0.0), 0.72, wood))
    p.append(H.crate("pr_cr2", Ts(4.60, -15.60, 0.0), 0.60, wood))
    for s in (-1, 1):
        p.append(H.lantern_post("pr_lc%d" % s, Ts(s * 5.80, -16.0, 0.0), 3.00, iron,
                                MAT["glow"]))
    p.append(box("pr_bench", Ts(-9.40, -12.40, DECK + 0.42), (0.50, 2.40, 0.14), wood,
                 bev=0.02))
    for yy in (-13.30, -11.50):
        p.append(box("pr_bl", Ts(-9.40, yy, DECK + 0.21), (0.44, 0.16, 0.42), wd))
    return p


# --------------------------------------------------------------------------
#  assembly
# --------------------------------------------------------------------------
def build(MAT, rng, **kw):
    """Return every object of the gate complex (origin at the footprint centre,
    +Y out of the city, ground at z = 0)."""
    with_ground = kw.get("with_ground", True)
    with_props = kw.get("with_props", True)
    obs = []
    obs += build_gatehouse(MAT, rng)
    for s in (-1, 1):
        obs += build_tower(MAT, rng, s)
        obs += build_curtain(MAT, rng, s)
        obs += build_stair(MAT, rng, s)
    obs += build_barbican(MAT, rng)
    obs += build_drawbridge(MAT, rng)
    if with_ground:
        obs += build_ground(MAT, rng)
    if with_props:
        obs += build_props(MAT, rng)
    return obs


def footprint():
    """(x, y) extent of the whole complex in metres."""
    return (2.0 * (CURT_X1 + 2.95), MOAT_B + 1.90 - (-16.40))


def eval_tris(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for ob in objs:
        if ob is None or ob.type != "MESH":
            continue
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    return n


# --------------------------------------------------------------------------
#  preview-only context: a slice of the city behind the gate
# --------------------------------------------------------------------------
def _context(MAT, rng):
    p = []
    pl, tile, ti, wd = MAT["plaster"], MAT["tile"], MAT["tile_blue"], MAT["wood_dark"]
    for i in range(7):
        for s in (-1, 1):
            x = s * (13.5 + rng.uniform(0.0, 1.6) + (i % 3) * 2.4)
            y = -16.0 - i * 5.6
            w = rng.uniform(6.0, 8.4)
            d = rng.uniform(5.2, 6.6)
            h = rng.uniform(5.0, 7.6)
            T = Ts(x, y, 0, rz=rng.uniform(-0.10, 0.10))
            p.append(box("cx_w%d_%d" % (i, s), T @ Ts(0, 0, h * 0.5), (w, d, h), pl,
                         bev=0.02))
            p += gable_roof("cx_r%d_%d" % (i, s), T @ Ts(0, 0, h), w, d,
                            rng.uniform(1.8, 2.6), tile if i % 2 else ti, wd)
            p.append(box("cx_pl%d_%d" % (i, s), T @ Ts(0, 0, 0.28),
                         (w + 0.16, d + 0.16, 0.56), MAT["stone_dark"]))
            for k in range(2):
                p.append(box("cx_wn%d_%d_%d" % (i, s, k),
                             T @ Ts(-w * 0.22 + k * w * 0.44, -d * 0.5 - 0.02,
                                    h * 0.58), (1.10, 0.10, 1.50), MAT["glass"]))
            if i % 3 == 0:
                p.append(H.chimney("cx_ch%d_%d" % (i, s), T @ Ts(w * 0.26, d * 0.18, h),
                                   2.20, MAT["stone_dark"], pots=2))
    # a green and a few trees along the approach
    p.append(_plane("cx_gr", -26.0, 26.0, 33.0, 40.0, 0.02, MAT["grass"], t=0.04))
    for i, (x, y, r) in enumerate(((11.0, 44.0, 2.4), (-12.5, 47.5, 2.8),
                                   (16.0, 37.0, 2.1), (-18.0, 35.0, 2.5),
                                   (-21.0, 50.0, 3.0), (21.0, 50.0, 2.7),
                                   (9.5, 24.5, 1.9), (-10.5, 25.5, 2.1))):
        p.append(cyl("cx_tr%d" % i, Ts(x, y, 1.35), 0.26, 2.70, wd, seg=8))
        p.append(sphere("cx_cn%d" % i, Ts(x, y, 2.70 + r * 0.55), r, MAT["grass"],
                        seg=12, ring=8, squash=0.92))
    return p


# --------------------------------------------------------------------------
#  lighting and cameras
# --------------------------------------------------------------------------
def _lights(MAT):
    def lamp(name, loc, energy, size=0.6, color=(1.0, 0.72, 0.42)):
        ld = bpy.data.lights.new(name, "POINT")
        ld.energy = energy
        ld.color = color
        ld.shadow_soft_size = size
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        bpy.context.collection.objects.link(ob)
        return ob
    # the passage, the barbican tunnel and the ward
    for i, (yy, zz, e) in enumerate(((-5.00, 3.10, 55.0), (-1.20, 3.10, 55.0),
                                     (2.80, 3.10, 55.0), (6.90, 3.10, 45.0))):
        lamp("lt_ps%d" % i, (0.0, yy, zz), e)
    lamp("lt_bg0", (0.0, 22.15, 3.00), 60.0)
    lamp("lt_wd0", (0.0, 15.00, 4.20), 90.0, 1.2)
    lamp("lt_wd1", (-5.30, 13.30, 2.10), 30.0, 0.4)
    # a soft fill from the city side so the back never goes black
    ld = bpy.data.lights.new("fill_city", "SUN")
    ld.energy = 1.10
    ld.angle = math.radians(12.0)
    ld.color = (0.72, 0.82, 1.0)
    ob = bpy.data.objects.new("fill_city", ld)
    ob.rotation_euler = (math.radians(58.0), 0.0, math.radians(198.0))
    bpy.context.collection.objects.link(ob)


SHOTS = [
    ("a",        (52.0, 78.0, 22.0),   (0.0, 10.0, 14.0),  45.0),
    ("b",        (0.0, 96.0, 15.0),    (0.0, 12.0, 12.0),  48.0),
    ("c",        (-50.0, 72.0, 38.0),  (0.0, 10.0, 13.0),  45.0),
    ("south",    (0.0, 74.0, 1.90),    (0.0, 10.0, 11.0),  50.0),
    ("road",     (43.0, 92.0, 9.0),    (0.0, 20.0, 10.0),  42.0),
    ("portal",   (0.0, 40.50, 1.75),   (0.0, -20.0, 3.00), 50.0),
    ("through",  (0.0, 27.20, 1.70),   (0.0, -30.0, 2.60), 42.0),
    ("arch",     (0.0, 29.60, 2.10),   (0.0, 22.00, 4.60), 70.0),
    ("barbican", (17.0, 12.0, 26.0),   (0.0, 15.5, 3.50),  40.0),
    ("back",     (0.0, -33.0, 1.90),   (0.0, -2.0, 9.00),  45.0),
    ("city",     (-17.0, -29.0, 10.0), (0.0, 0.0, 12.0),   42.0),
    ("citywide", (-46.0, -46.0, 26.0), (0.0, 2.0, 12.0),   45.0),
    ("top",      (34.0, 54.0, 68.0),   (0.0, 10.0, 8.0),   45.0),
    ("ward",     (0.0, 11.60, 1.75),   (0.0, 23.0, 3.20),  40.0),
    ("porch",    (0.0, 12.90, 2.00),   (0.0, 9.10, 6.20),  60.0),
    ("moat",     (24.0, 34.0, 6.0),    (0.0, 26.0, 1.20),  45.0),
]

WIDE = [
    ("w_a",  (78.0, 120.0, 34.0),  (0.0, 12.0, 12.0),  55.0),
    ("w_b",  (0.0, 150.0, 26.0),   (0.0, 14.0, 12.0),  62.0),
    ("w_c",  (16.0, 44.0, 118.0),  (0.0, 4.0, 6.0),    42.0),
]


def preview(samples=64, res=(1400, 900), final=False, only=None, wide_only=False):
    import random
    H._clear()
    MAT = materials()
    rng = random.Random(20261030)
    obs = build(MAT, rng)
    nparts = len([o for o in obs if o is not None])
    ntris = sum(len(o.data.loop_triangles) if o.data.loop_triangles else 0
                for o in obs if o is not None and o.type == "MESH")
    for o in obs:
        if o is not None and o.type == "MESH":
            o.data.calc_loop_triangles()
    ntris = sum(len(o.data.loop_triangles) for o in obs
                if o is not None and o.type == "MESH")
    neval = eval_tris(obs)
    lo, hi = H.bbox(obs)
    print("[gate] parts=%d tris=%d tris_eval=%d" % (nparts, ntris, neval), flush=True)
    print("[gate] bbox lo=(%.2f, %.2f, %.2f) hi=(%.2f, %.2f, %.2f)"
          % (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]), flush=True)

    _context(MAT, rng)
    H.setup_world(sun_energy=4.2, sky="#9fc4e8", fill=0.0)
    _lights(MAT)
    H.setup_engine(samples=samples, res=res, gpu=True)
    shots = WIDE if wide_only else SHOTS
    for name, loc, look, lens in shots:
        if only and name not in only:
            continue
        cam = H.camera("cam_" + name, loc, look, lens)
        H.render_to(os.path.join(OUT_DIR, "hd_gate_%s.png" % name), cam)
        print("[gate] wrote %s" % name, flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--stats" in argv or "--quick" in argv:
        H._clear()
        _m = materials()
        _r = __import__("random").Random(20261030)
        _o = build(_m, _r)
        for _ob in _o:
            if _ob is not None and _ob.type == "MESH":
                _ob.data.calc_loop_triangles()
        _nt = sum(len(_ob.data.loop_triangles) for _ob in _o
                  if _ob is not None and _ob.type == "MESH")
        _ne = eval_tris(_o)
        _lo, _hi = H.bbox(_o)
        print("[gate] stats parts=%d tris=%d tris_eval=%d" % (len(_o), _nt, _ne),
              flush=True)
        print("[gate] bbox lo=(%.2f, %.2f, %.2f) hi=(%.2f, %.2f, %.2f)"
              % (_lo[0], _lo[1], _lo[2], _hi[0], _hi[1], _hi[2]), flush=True)
        print("[gate] footprint=(%.1f, %.1f)" % footprint(), flush=True)
        if "--stats" in argv:
            sys.exit(0)
        sys.exit(0)
    preview(samples=192 if "--final" in argv else 64,
            res=(1600, 900) if "--final" in argv else (1400, 900),
            final="--final" in argv,
            only=None, wide_only="--wide" in argv)
