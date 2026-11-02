# --------------------------------------------------------------------------
#  the gatehouse and its forebuilding
# --------------------------------------------------------------------------
R_NOTCH = RO + 0.02      # the wall opening the vault tube sits inside
GH_TOP = 19.60
GH_KEEL = 19.74          # top of the roof walk slab


def _del(ob):
    if ob is not None and ob.name in bpy.data.objects:
        bpy.data.objects.remove(ob, do_unlink=True)


def build_gatehouse(MAT, rng):
    """The main gate: a tall block pierced by the passage, a forebuilding in
    front of it, twin drum towers butted into the flanks (built separately)."""
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron = MAT["stone_pale"], MAT["iron_dark"]
    T0 = Ts(0, 0, 0)

    # ---- the body and the forebuilding -----------------------------------
    body = H.prism("gh_body", T0,
                   arch_notch_poly(GH_W, GH_TOP, R_NOTCH, Z_SPRING, seg=40),
                   2 * GH_D, st, axis="y")
    p.append(body)
    Tfp = Ts(0, (FP_Y0 + FP_Y1) * 0.5, 0)
    porch = H.prism("gh_fp", Tfp,
                    arch_notch_poly(FP_W, FP_H, R_NOTCH, Z_SPRING, seg=40),
                    FP_Y1 - FP_Y0, st, axis="y")
    p.append(porch)

    # ======================================================================
    #  CITY FACE   (local +Y = -Y, the face plane is y = -GH_D)
    # ======================================================================
    Tc = _frame(0, -GH_D, 0.0, 1.5 * PI)
    # ashlar field, cut for the passage mouth and the postern
    c_mouth = _rect_cutter("gh_cm", Tc, 7.44, 8.10, 1.20)
    c_post = _loop_cutter("gh_cp", Tc, 1.70, 2.45, 0.95)
    asc = ashlar("gh_asc", Tc, 19.40, GH_TOP, sw, rng, bw=1.48, bh=0.66)[0]
    _bool(asc, c_mouth)
    _bool(asc, c_post)
    _del(c_mouth)
    p.append(asc)
    # the postern is cut through the body too
    _cut([body], _loop_cutter("gh_cp2", Tc, 1.70, 2.45, 0.95))
    # city-face openings
    c_win = _loop_cutter("gh_cwc", Tc @ Ts(0, 0, 11.40), 4.30, 3.00, 0.80)
    c_sm = []
    for s in (-1, 1):
        c_sm.append(_rect_cutter("gh_cwl%d" % s, Tc @ Ts(s * 5.85, 0, 8.55),
                                 1.35, 1.85, 0.72))
    for c in [c_win] + c_sm:
        _cut([body, asc], c)
    p += pointed_window("gh_cwin", Tc @ Ts(0, 0, 11.40), 4.30, 3.00, MAT,
                        tracery=3, transom=1, depth=0.80, hood=True)
    for s in (-1, 1):
        p += pointed_window("gh_cws%d" % s, Tc @ Ts(s * 5.85, 0, 8.55), 1.35, 1.85,
                            MAT, tracery=1, transom=0, depth=0.74, hood=True)
    p += _arched_door("gh_post", Tc, 1.70, 2.45, MAT, depth=0.42, steps=1)
    p += coat_of_arms("gh_ccoa", Tc @ Ts(0, 0.0, 9.30), 1.22, MAT)
    # plinth, middle string and cornice
    p.append(box("gh_cpl", Ts(0, -GH_D - 0.12, 0.55), (19.40, 0.26, 1.10), sd, bev=0.02))
    p.append(box("gh_cpl2", Ts(0, -GH_D - 0.19, 0.10), (19.40, 0.14, 0.22), sd))
    p.append(box("gh_cco", Ts(0, -GH_D - 0.15, 19.02), (19.40, 0.32, 0.32), pale, bev=0.02))
    p.append(box("gh_cco2", Ts(0, -GH_D - 0.22, 18.84), (19.40, 0.14, 0.18), sd))

    # ======================================================================
    #  ROAD FACE above the forebuilding   (y = +GH_D, but the porch hides
    #  everything below FP_H, so this starts at the porch roof)
    # ======================================================================
    Tf = _frame(0, GH_D, FP_H, PI * 0.5)
    c_fl = []
    for s in (-1, 1):
        c_fl.append(_loop_cutter("gh_fl%d" % s,
                                 Tf @ Ts(s * 4.55, 0, 15.20 - FP_H), 1.15, 2.00, 0.85))
    asf = ashlar("gh_asft", Tf, 19.40, GH_TOP - FP_H, sw, rng, bw=1.46, bh=0.64)[0]
    for c in c_fl:
        _cut([body, asf], c)
    p.append(asf)
    for s in (-1, 1):
        p += pointed_window("gh_flw%d" % s, Tf @ Ts(s * 4.55, 0, 15.20 - FP_H),
                            1.15, 2.00, MAT, tracery=1, transom=0, depth=0.86,
                            hood=True)
    p += coat_of_arms("gh_fcoa", Tf @ Ts(0, 0.0, 16.65 - FP_H), 1.28, MAT)
    # the two flanking strips beside the forebuilding
    for s in (-1, 1):
        p.append(ashlar("gh_asf%d" % s, _frame(s * 8.09, GH_D, 0.0, PI * 0.5),
                        3.18, FP_H, sw, rng))
    p.append(box("gh_fsc", Ts(0, GH_D + 0.11, 14.55), (19.40, 0.30, 0.32), pale, bev=0.02))
    p.append(box("gh_fsc2", Ts(0, GH_D + 0.19, 14.36), (19.40, 0.13, 0.16), sd))

    # ======================================================================
    #  THE FOREBUILDING FRONT
    # ======================================================================
    Tp = _frame(0, FP_Y1, 0.0, PI * 0.5)
    cp_m = _rect_cutter("gh_pmc", Tp, 7.44, 8.10, 1.10)
    asp = ashlar("gh_asp", Tp, FP_W * 2, FP_H, sw, rng, bw=1.40, bh=0.62)[0]
    _bool(asp, cp_m)
    _del(cp_m)
    p.append(asp)
    # side faces of the forebuilding
    for s in (-1, 1):
        Tside = Ts(s * FP_W, (FP_Y0 + FP_Y1) * 0.5, 0.0) @ RotZ(-s * PI * 0.5)
        p.append(ashlar("gh_asps%d" % s, Tside, FP_Y1 - FP_Y0, FP_H, sw, rng))
    # the great arch order
    p += arch_order("gh_arch", Ts(0, FP_Y1, Z_SPRING), RO, MAT, n=23, w=0.58,
                    depth=0.34, hood=True)
    p += arch_order("gh_archc", Ts(0, -GH_D - 0.01, Z_SPRING), RO, MAT, n=23, w=0.52,
                    depth=0.30, hood=True)
    # porch sculpture
    p += coat_of_arms("gh_pcoa", Ts(0, FP_Y1 + 0.02, 9.30), 1.30, MAT)
    for s in (-1, 1):
        p += niche("gh_nic%d" % s, Ts(s * 5.02, FP_Y1 + 0.01, 2.35), 1.48, 3.20, MAT, rng)
        p += guardian("gh_grd%d" % s, Ts(s * 5.02, FP_Y1 + 0.12, 2.58), 3.10, MAT)
    # porch roof: flat, with a low crenellated parapet
    p.append(box("gh_fproof", Ts(0, (FP_Y0 + FP_Y1) * 0.5 + 0.14, FP_H - 0.14),
                 (FP_W * 2 - 0.08, FP_Y1 - FP_Y0 + 0.28, 0.28), sd, bev=0.02))
    p.append(box("gh_fproof2", Ts(0, (FP_Y0 + FP_Y1) * 0.5 + 0.10, FP_H - 0.30),
                 (FP_W * 2 - 0.16, FP_Y1 - FP_Y0 + 0.10, 0.08), MAT["slate"]))
    p.append(box("gh_fpar", Ts(0, FP_Y1 - 0.22, FP_H + 0.34), (FP_W * 2, 0.44, 0.70),
                 st, bev=0.025))
    p.append(box("gh_fcop", Ts(0, FP_Y1 - 0.20, FP_H + 0.72), (FP_W * 2 + 0.10, 0.56,
                                                              0.13), pale, bev=0.015))
    p += crenel_line("gh_fmer", Ts(0, FP_Y1 - 0.24, FP_H + 0.78), FP_W * 2 - 0.20,
                     st, merlon=0.92, gap=0.50, h=0.86, depth=0.50)
    # porch parapet returns on the sides
    for s in (-1, 1):
        p.append(box("gh_fprs%d" % s, Ts(s * (FP_W - 0.22), (FP_Y0 + FP_Y1) * 0.5,
                                        FP_H + 0.34), (0.44, FP_Y1 - FP_Y0, 0.70), st,
                     bev=0.02))

    # ======================================================================
    #  ROOF WALK  (level with the tower walks)
    # ======================================================================
    p.append(box("gh_walk", Ts(0, 0, GH_TOP + 0.07), (2 * GH_W, 2 * GH_D, 0.14),
                 pale, bev=0.02))
    p.append(box("gh_walk2", Ts(0, 0, GH_TOP + 0.02), (2 * GH_W - 0.30, 2 * GH_D - 0.30,
                                                     0.10), sd))
    p += machic_line("gh_mF", Ts(0, GH_D, 0), 12.60, MAT, out=1.02, wall_z=GH_TOP)
    p += machic_line("gh_mB", Ts(0, -GH_D, 0) @ RotZ(PI), 19.00, MAT, out=1.02,
                     wall_z=GH_TOP)
    # cap house (the guard room) on the walk
    chx, chy = 3.55, -2.30
    p.append(box("gh_ch", Ts(chx, chy, GH_TOP + 0.14 + 1.65), (5.30, 4.30, 3.30), sw,
                 bev=0.03))
    p.append(box("gh_chb", Ts(chx, chy, GH_TOP + 0.34), (5.66, 4.66, 0.40), sd, bev=0.02))
    p += gable_roof("gh_chr", Ts(chx, chy, GH_TOP + 0.14 + 3.30), 5.30, 4.30, 1.85,
                    MAT["slate"], sd)
    p.append(H.chimney("gh_chim", Ts(chx + 1.60, chy + 1.35, GH_TOP + 3.40), 2.50, sw))
    # cap-house door (on the walk, facing +Y) and a window
    p += _arched_door("gh_chd", _frame(chx + 1.55, chy + 2.16, GH_TOP + 0.16, PI * 0.5),
                      1.10, 1.95, MAT, depth=0.26, steps=0, arched=False)
    Tchw = _frame(chx - 1.20, chy + 2.16, GH_TOP + 1.62, PI * 0.5)
    p.append(box("gh_chwf", Tchw @ Ts(0, 0.04, 0.0), (1.05, 0.10, 1.10), sw, bev=0.01))
    p.append(box("gh_chwg", Tchw @ Ts(0, 0.075, 0.0), (0.85, 0.05, 0.92), MAT["glass"]))
    for i in range(2):
        p.append(box("gh_chwb%d" % i, Tchw @ Ts(0, 0.11, -0.28 + i * 0.56),
                     (0.90, 0.03, 0.05), iron))
    for i in range(2):
        p.append(box("gh_chs%d" % i, Ts(chx + 1.55, chy + 2.52 + i * 0.34,
                                        GH_TOP + 0.06), (1.50, 0.34, 0.16), pale,
                     bev=0.012))
    # bench, water butt, braziers
    p.append(box("gh_bench", Ts(-3.30, GH_D - 1.15, GH_TOP + 0.50), (2.60, 0.52, 0.12),
                 MAT["wood"], bev=0.02))
    for s in (-1, 1):
        p.append(box("gh_benchl%d" % s, Ts(-3.30 + s * 1.10, GH_D - 1.15, GH_TOP + 0.28),
                     (0.16, 0.44, 0.44), MAT["wood_dark"]))
    p.append(H.barrel("gh_butt", Ts(-5.30, GH_D - 0.90, GH_TOP + 0.14), 0.42, 1.05,
                      MAT["wood"], iron))
    for s in (-1, 1):
        p += brazier("gh_brz%d" % s, Ts(s * 5.55, GH_D - 0.85, GH_TOP + 0.14), MAT)
    # flag over the gate
    p += flag("gh_flag", Ts(0, -4.40, GH_KEEL + 0.10), 0.10, 2.60, 1.55,
              MAT["banner_blue"], MAT["gold"], iron)
    return p


# --------------------------------------------------------------------------
#  small iron / light fittings
# --------------------------------------------------------------------------
def torch(name, T, MAT, nx):
    """A pitch torch in an iron basket on a wall; T is the wall point and nx the
    direction it projects in (world X)."""
    iron, wood = MAT["iron_dark"], MAT["wood_dark"]
    p = []
    x = T.translation.x
    p.append(box(name + "_br", Ts(x + nx * 0.10, T.translation.y, T.translation.z - 0.30),
                 (0.34, 0.09, 0.09), iron))
    p.append(box(name + "_br2", Ts(x + nx * 0.26, T.translation.y, T.translation.z - 0.12),
                 (0.09, 0.09, 0.46), iron))
    p.append(cyl(name + "_cup", Ts(x + nx * 0.26, T.translation.y, T.translation.z + 0.10), 0.13, 0.20,
                 iron, seg=10, r2=0.17))
    p.append(cyl(name + "_stk", Ts(x + nx * 0.26, T.translation.y, T.translation.z + 0.24), 0.045, 0.36,
                 wood, seg=8))
    p.append(sphere(name + "_fl", Ts(x + nx * 0.26, T.translation.y, T.translation.z + 0.52), 0.11,
                    MAT["glow"], seg=8, ring=5, squash=1.6))
    for i in range(6):
        a = TAU * i / 6.0
        p.append(box(name + "_pr%d" % i,
                     Ts(x + nx * 0.26 + math.cos(a) * 0.13, T.translation.y + math.sin(a) * 0.13,
                        T.translation.z + 0.22), (0.035, 0.035, 0.20), iron))
    return p


def lantern(name, T, MAT):
    """A hanging lantern under the vault."""
    iron, gold = MAT["iron_dark"], MAT["gold"]
    p = [chain(name + "_ch", T, T + Vector((0, 0, 1.0)), 0.02, iron, links=7,
               R=0.045, r=0.014)]
    z = T.translation.z - 1.10
    p.append(cyl(name + "_top", Ts(T.translation.x, T.translation.y, z + 0.34), 0.20, 0.10, iron, seg=8, r2=0.10))
    p.append(cyl(name + "_bot", Ts(T.translation.x, T.translation.y, z - 0.20), 0.16, 0.09, iron, seg=8, r2=0.20))
    for i in range(4):
        a = TAU * i / 4.0 + PI * 0.25
        p.append(box(name + "_f%d" % i,
                     Ts(T.translation.x + math.cos(a) * 0.19, T.translation.y + math.sin(a) * 0.19, z + 0.06),
                     (0.045, 0.045, 0.48), iron))
    p.append(cyl(name + "_gl", Ts(T.translation.x, T.translation.y, z + 0.06), 0.155, 0.46, MAT["glow"], seg=10))
    p.append(sphere(name + "_kn", Ts(T.translation.x, T.translation.y, z + 0.44), 0.05, gold, seg=8, ring=5))
    return p


def brazier(name, T, MAT):
    """A coal brazier on the roof walk."""
    iron, gold = MAT["iron_dark"], MAT["gold"]
    p = []
    p.append(H.lathe(name + "_bowl", [(0.0, 0.0), (0.34, 0.28), (0.40, 0.46),
                                      (0.36, 0.50)], iron, seg=16, T=Ts(T.translation.x, T.translation.y, T.translation.z),
                     close_bottom=True, close_top=False))
    for i in range(3):
        a = TAU * i / 3.0
        p.append(box(name + "_lg%d" % i,
                     Ts(T.translation.x + math.cos(a) * 0.28, T.translation.y + math.sin(a) * 0.28, T.translation.z - 0.04),
                     (0.07, 0.07, 0.30), iron))
    p.append(sphere(name + "_coal", Ts(T.translation.x, T.translation.y, T.translation.z + 0.42), 0.26, MAT["glow"],
                    seg=10, ring=6, squash=0.45))
    return p


# --------------------------------------------------------------------------
#  the passage
# --------------------------------------------------------------------------
def build_passage(MAT, rng):
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron, wd = MAT["stone_pale"], MAT["iron_dark"], MAT["wood_dark"]
    y0, y1 = -GH_D - 0.02, FP_Y1 + 0.02

    # ---- floor -----------------------------------------------------------
    p += flagstones("ps_floor", Ts(0, 0, DECK), 2 * RO - 0.04, y0, y1, MAT["cobble"],
                    rng, cw=1.30, cl=1.05, h=0.17)
    for i, yy in enumerate((y0 + 0.34, y1 - 0.34)):
        p.append(box("ps_thr%d" % i, Ts(0, yy, DECK - 0.025),
                     (2 * RO - 0.04, 0.54, 0.07), pale, bev=0.015))
    # central drain with iron grates
    p.append(box("ps_drn", Ts(0, (y0 + y1) * 0.5, DECK - 0.045),
                 (0.46, y1 - y0 - 0.7, 0.03), sd))
    for i in range(6):
        yy = y0 + 2.5 + i * 1.95
        p.append(box("ps_grt%d" % i, Ts(0, yy, DECK - 0.012), (0.54, 0.64, 0.035), iron))
        for k in range(4):
            p.append(box("ps_gb%d_%d" % (i, k), Ts(-0.18 + k * 0.12, yy, DECK + 0.006),
                         (0.05, 0.58, 0.02), iron))

    # ---- side walls ------------------------------------------------------
    for s in (-1, 1):
        Tside = Ts(s * (RO + 0.006), (y0 + y1) * 0.5, DECK - 0.02) @ RotZ(-s * PI * 0.5)
        p.append(ashlar("ps_ash%d" % s, Tside, y1 - y0 - 0.12,
                        Z_SPRING - DECK + 0.12, sw, rng, bw=1.22, bh=0.56))
        p.append(box("ps_pl%d" % s, Ts(s * (RO - 0.07), (y0 + y1) * 0.5, DECK + 0.16),
                     (0.16, y1 - y0 - 0.24, 0.34), sd, bev=0.02))
        p.append(box("ps_sc%d" % s, Ts(s * (RO - 0.11), (y0 + y1) * 0.5,
                                       Z_SPRING - 0.13), (0.24, y1 - y0 - 0.24, 0.22),
                     pale, bev=0.02))

    # ---- vault -----------------------------------------------------------
    p.append(arch_tube("ps_vault", Ts(0, 0, 0), RO, Z_SPRING, y0, y1, 0.58, st, seg=54))
    for i in range(8):
        yy = y0 + 1.40 + i * 1.92
        p.append(arch_band("ps_rib%d" % i, Ts(0, yy, Z_SPRING), RO - 0.07, RO + 0.26,
                           -0.15, 0.15, pale, seg=30))
        p.append(box("ps_rks%d" % i, Ts(0, yy, Z_SPRING + RO + 0.05),
                     (0.34, 0.34, 0.28), sw, bev=0.02))
    p.append(box("ps_ridge", Ts(0, (y0 + y1) * 0.5, Z_SPRING + RO + 0.01),
                 (0.30, y1 - y0, 0.22), sw))

    # ---- portcullis and windlass -----------------------------------------
    p += portcullis("ps_pc", Ts(0, 5.45, 0), 2 * RO - 0.30, 3.55, 7.00, MAT, n=9)
    p.append(box("ps_pcs", Ts(0, 5.45, 1.30), (2 * RO - 0.12, 0.46, 0.05), sd))
    p += windlass("ps_wl", Ts(0, 4.10, 0), 3.20, 6.40, MAT)

    # ---- the two leaves, standing open ----------------------------------
    p += door_leaf("ps_lfL", Ts(-2.76, 0.62, DECK), 2.62, 3.95, MAT, ang=95.0)
    p += door_leaf("ps_lfR", Ts(2.76, 0.62, DECK), 2.62, 3.95, MAT, ang=85.0)
    for s in (-1, 1):
        for k in range(3):
            p.append(cyl("ps_hn%d_%d" % (s, k), Ts(s * 2.82, 0.62, 1.15 + k * 1.30),
                         0.075, 0.24, iron, seg=10))

    # ---- lighting and fittings -------------------------------------------
    for i, (yy, s) in enumerate(((-5.30, -1), (-2.20, 1), (1.35, -1), (2.95, 1),
                                 (6.60, -1), (8.35, 1))):
        p += torch("ps_tch%d" % i, Ts(s * RO, yy, 3.05), MAT, -s)
    p += lantern("ps_lan", Ts(0, 3.30, Z_SPRING + RO - 0.42), MAT)
    p.append(box("ps_bench", Ts(-2.18, -1.10, DECK + 0.42), (0.46, 2.20, 0.12),
                 MAT["wood"], bev=0.02))
    for yy in (-2.10, -0.10):
        p.append(box("ps_bl", Ts(-2.18, yy, DECK + 0.21), (0.40, 0.14, 0.42),
                     MAT["wood_dark"]))
    p.append(H.barrel("ps_bar", Ts(2.26, -1.55, DECK), 0.32, 0.86, MAT["wood"], iron))
    p.append(H.crate("ps_crt", Ts(2.24, -0.55, DECK), 0.66, MAT["wood"]))
    for i in range(3):
        p.append(torus("ps_rg%d" % i, Ts(-(RO - 0.07), -4.4, 1.30 + i * 0.0)
                       @ RotZ(PI * 0.5) @ RotX(PI * 0.5), 0.16, 0.035, iron, seg=12,
                       ring=5))
    return p


def door_leaf(name, T, w, h, MAT, ang=95.0):
    """A heavy plank leaf hinged at T, swung open by `ang` degrees."""
    wood, wd, iron = MAT["wood"], MAT["wood_dark"], MAT["iron_dark"]
    gold, pale = MAT["gold"], MAT["stone_pale"]
    p = []
    Tw = T @ RotZ(math.radians(ang))
    p.append(box(name + "_lf", Tw @ Ts(-w * 0.5, 0, h * 0.5), (w, 0.15, h), wood,
                 bev=0.012))
    n = 6
    for i in range(n + 1):
        p.append(box(name + "_p%d" % i, Tw @ Ts(-w * i / n, 0.082, h * 0.5),
                     (0.035, 0.02, h - 0.10), wd))
    for k in range(4):
        z = h * (0.12 + 0.25 * k)
        p.append(box(name + "_b%d" % k, Tw @ Ts(-w * 0.5, 0.098, z),
                     (w * 0.96, 0.035, 0.11), iron))
        for j in range(6):
            p.append(cyl(name + "_s%d_%d" % (k, j),
                         Tw @ Ts(-w * 0.09 - j * w * 0.16, 0.118, z) @ RotX(PI * 0.5),
                         0.038, 0.03, iron, seg=7))
    for k in range(2):
        z = h * (0.22 + 0.46 * k)
        p.append(box(name + "_h%d" % k, Tw @ Ts(-0.05, 0.02, z), (0.34, 0.24, 0.14),
                     iron, bev=0.01))
        p.append(cyl(name + "_hp%d" % k, Tw @ Ts(0.0, 0.0, z), 0.055, 0.64, iron, seg=8))
    p.append(torus(name + "_rg", Tw @ Ts(-w + 0.28, 0.14, h * 0.46) @ RotX(PI * 0.5),
                   0.11, 0.026, gold, seg=12, ring=5))
    p.append(cyl(name + "_rk", Tw @ Ts(-w + 0.28, 0.11, h * 0.52) @ RotX(PI * 0.5),
                 0.055, 0.10, gold, seg=10))
    return p


def portcullis(name, T, w, zbot, ztop, MAT, n=9):
    """An iron grille with real thickness and spear points; z relative to T."""
    iron, iron2 = MAT["iron"], MAT["iron_dark"]
    p = []
    pitch = w / (n - 1)
    for i in range(n):
        x = -w * 0.5 + i * pitch
        p.append(box(name + "_b%d" % i, T @ Ts(x, 0, (zbot + ztop) * 0.5),
                     (0.075, 0.075, ztop - zbot), iron))
        p.append(cone(name + "_sp%d" % i, T @ Ts(x, 0, zbot - 0.17), 0.055, 0.36, iron2,
                      seg=6))
        p.append(box(name + "_c%d" % i, T @ Ts(x, 0, ztop + 0.06), (0.13, 0.13, 0.16),
                     iron2))
    for k in range(4):
        z = zbot + 0.35 + k * (ztop - zbot - 0.7) / 3.0
        p.append(box(name + "_h%d" % k, T @ Ts(0, 0.01, z), (w + 0.10, 0.09, 0.10), iron))
    for s in (-1, 1):
        p.append(box(name + "_st%d" % s, T @ Ts(s * (w * 0.5 + 0.07), 0,
                                               (zbot + ztop) * 0.5),
                     (0.13, 0.13, ztop - zbot + 0.30), iron2))
        p.append(box(name + "_stl%d" % s, T @ Ts(s * (w * 0.5 + 0.07), 0, ztop + 0.20),
                     (0.22, 0.22, 0.20), iron2))
    return p


def windlass(name, T, span, z, MAT):
    """A winch drum over the gate, with ratchet wheel, crank and two chains."""
    iron, iron2 = MAT["iron"], MAT["iron_dark"]
    wd = MAT["wood_dark"]
    p = []
    p.append(cyl(name + "_dr", T @ Ts(0, 0, z) @ RotY(PI * 0.5), 0.30, span, wd, seg=18))
    for s in (-1, 1):
        p.append(cyl(name + "_fl%d" % s, T @ Ts(s * span * 0.5, 0, z) @ RotY(PI * 0.5),
                     0.52, 0.10, iron, seg=20))
        p.append(box(name + "_br%d" % s, T @ Ts(s * span * 0.46, 0, z + 0.26),
                     (0.16, 0.34, 0.60), iron2, bev=0.01))
    p.append(cyl(name + "_rt", T @ Ts(-span * 0.40, 0, z) @ RotY(PI * 0.5), 0.62, 0.09,
                 iron2, seg=22))
    for i in range(10):
        a = TAU * i / 10.0
        p.append(box(name + "_rtt%d" % i,
                     T @ Ts(-span * 0.40, math.sin(a) * 0.60, z + math.cos(a) * 0.60,
                            ry=-a), (0.10, 0.10, 0.16), iron2))
    p.append(box(name + "_pw", T @ Ts(-span * 0.40, 0.52, z + 0.48, rx=0.5),
                 (0.10, 0.34, 0.56), iron2))
    p.append(cyl(name + "_ck", T @ Ts(span * 0.54, 0.0, z) @ RotY(PI * 0.5), 0.055, 0.34,
                 iron, seg=10))
    p.append(box(name + "_ck2", T @ Ts(span * 0.70, 0.0, z + 0.24), (0.09, 0.09, 0.62),
                 iron))
    p.append(cyl(name + "_ck3", T @ Ts(span * 0.70, 0.20, z + 0.52) @ RotX(PI * 0.5),
                 0.09, 0.36, wd, seg=10))
    for s in (-1, 1):
        p += chain(name + "_ch%d" % s,
                   T @ Vector((s * span * 0.36, -0.02, z - 0.24)),
                   T @ Vector((s * 1.05, 1.35, 6.98)), 0.14, iron, links=13,
                   R=0.085, r=0.028)
    return p
