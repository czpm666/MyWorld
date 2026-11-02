def build_seals(M):
    """Two things the set needs that are not furniture: a sealed roof gap and
    a stone vault closing the head of the stair well."""
    P = []
    # a black backing plate under the feast-hall floor: kills every light leak
    # between the great hall roof and the floor above
    P.append(bx("ci_roof_seal", Ts(0, 0, 19.60),
                (2 * (HX + WT), 2 * (HY + WT), 0.26), _m(M, "stone_dark")))
    # the well head: a corbelled stone vault closing the shaft at 15.5 m, with a
    # hanging iron lantern under it, so the well is a lit 15 m shaft
    P.append(cyl("ci_st_vault", Ts(ST_CX, ST_CY, 15.62), ST_RIN + 0.16, 0.30,
                 _m(M, "stone_course"), seg=36))
    P.append(cyl("ci_st_vault2", Ts(ST_CX, ST_CY, 15.32), ST_RIN - 0.14, 0.34,
                 _m(M, "stone_light"), seg=36, r2=ST_RIN + 0.10))
    P.append(cyl("ci_st_vk", Ts(ST_CX, ST_CY, 15.05), ST_WELL + 0.10, 0.22,
                 _m(M, "stone_dark"), seg=24))
    # lantern: iron cage, four bars, a warm flame inside
    P.append(cyl("ci_st_lan_t", Ts(ST_CX, ST_CY, 15.02), 0.16, 0.10,
                 _m(M, "iron"), seg=10))
    P.append(cyl("ci_st_lan_b", Ts(ST_CX, ST_CY, 14.06), 0.24, 0.10,
                 _m(M, "iron"), seg=12))
    P.append(sph("ci_st_lan_fl", Ts(ST_CX, ST_CY, 14.32), 0.19,
                 _m(M, "fire"), seg=12, ring=7, squash=1.25))
    for k in range(4):
        a = TAU * k / 4.0 + 0.4
        P.append(bx("ci_st_lan_bar", Ts(ST_CX + 0.28 * math.cos(a),
                                       ST_CY + 0.28 * math.sin(a), 14.30),
                    (0.035, 0.035, 0.46), _m(M, "iron")))
    return P


