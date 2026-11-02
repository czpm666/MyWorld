"""Build look/shots.json -- the validated camera library.

Every camera here is derived from geometry that has been measured in the blend
(see look/_shotmap.json), not from the layout engine's street centre lines.
Three families:

  game_*      the Unity TopDownCameraRig: pitch 52 deg, distance 34 m, vertical
              fov 30 deg.  The rig puts the camera 26.79 m up and 20.93 m back,
              so the frame only contains ground between 11.4 m and 35.5 m in
              front of the camera -- i.e. about 24 m of street centred on the
              player, and the roofs within 20 m.  A game frame can never show a
              skyline, a spire or a wall top; it is a street canyon, full stop.
  eye_*       1.72 m, standing on ground that is provably free (the layout's own
              `_reserved()` zones keep houses off squares, avenues and the strips
              in front of the cathedral, the guild and the castle ramp).
  aerial_*    high, wide, for the shape of the town.
  landmark_*  one portrait per landmark: castle, cathedral, market hall, guild,
              and the four gatehouses.

  python look\\_shotgen.py                     # write look/shots.json
  python look\\_shotgen.py --from-qa look\\_qa_shots.json   # fold in measured content
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "shots.json")
SPOTS = os.path.join(HERE, "spots.json")

GAME_PITCH = 52.0
GAME_DIST = 34.0
GAME_UP = GAME_DIST * math.sin(math.radians(GAME_PITCH))     # 26.790
GAME_BACK = GAME_DIST * math.cos(math.radians(GAME_PITCH))   # 20.931
EYE_H = 1.72

# the layout's reserved radii (capital.py _reserved / radial_roads)
R_OUTER = 947.2
AVE_IN, AVE_OUT = 492.0, 917.0     # the four great avenues are kept clear here

SHOTS = []


def yaw_pitch(pos, look):
    dx, dy, dz = (look[0] - pos[0], look[1] - pos[1], look[2] - pos[2])
    d = math.hypot(dx, dy)
    return (round(math.degrees(math.atan2(dy, dx)) % 360.0, 1),
            round(math.degrees(math.atan2(dz, d)), 1))


def add(name, kind, pos, look, lens=None, fov=None, note="", **extra):
    y, p = yaw_pitch(pos, look)
    s = {"name": name, "kind": kind,
         "pos": [round(float(v), 2) for v in pos],
         "look": [round(float(v), 2) for v in look],
         "lens": lens, "fov": fov,
         "yaw": y, "pitch": p,
         "note": note}
    s.update(extra)
    SHOTS.append(s)
    return s


def game(name, px, py, ux, uy, note, **extra):
    """The real rig: player at (px,py) facing (ux,uy)."""
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    pos = (px - ux * GAME_BACK, py - uy * GAME_BACK, EYE_H + GAME_UP)
    look = (px + ux * 1.5, py + uy * 1.5, 1.0)
    return add(name, "game", pos, look, lens=None, fov=30.0, note=note,
               player=[round(px, 1), round(py, 1)],
               heading=[round(ux, 4), round(uy, 4)],
               offset=[0.0, 0.0],
               rig=dict(pitch=GAME_PITCH, dist=GAME_DIST, vfov=30.0,
                        cam_up=round(GAME_UP, 3), cam_back=round(GAME_BACK, 3),
                        lens_equiv_mm=44.8,
                        source="Unity TopDownCameraRig.cs defaults"),
               **extra)


def eye(name, x, y, tx, ty, tz, lens, note, **extra):
    return add(name, "eye", (x, y, EYE_H), (tx, ty, tz), lens=lens, note=note,
               **extra)


def aimed(name, kind, pos, target, lens, note, **extra):
    return add(name, kind, pos, target, lens=lens, note=note, **extra)


# --------------------------------------------------------------------------- #
#  game_*: 52 deg / 34 m.  The four avenues are the only corridors the layout
#  guarantees to keep clear (capital.py _reserved: 0.52 r < along < r - 30 and
#  perp < 8.46), so they carry half of this set.
# --------------------------------------------------------------------------- #
def build_game():
    game("game_avenue_north", 0.0, 640.0, 0.0, 1.0,
         "An 11 m paved avenue in a 17 m corridor, running north to the outer "
         "gate: cobbles up the middle of the frame, two storey-and-a-half eaves "
         "either side, roof ridges filling the lower left and right corners. No "
         "sky -- a 52 degree camera cannot see above the horizon.")
    game("game_avenue_east", 620.0, 0.0, 1.0, 0.0,
         "The east avenue seen from inside: a long cobbled slot with jettied "
         "timber fronts on both sides, the sunlit right-hand wall carrying the "
         "frame, roof tiles along the bottom edge.")
    game("game_avenue_west", -700.0, 0.0, -1.0, 0.0,
         "The west avenue at dusk-side light: shadowed left wall, warm right "
         "wall, the street's own gutter line leading the eye out of frame.")
    game("game_avenue_south", 0.0, -560.0, 0.0, -1.0,
         "The south avenue toward the harbour: same canyon, but the ground is "
         "hollowed by the long shadows the brief asks for, and the far end of "
         "the street dissolves into haze.")
    # The one frame in the set that leans on roofs: the player turns off the
    # avenue into a block corner, so the 52 degree camera looks along a diagonal
    # of tiled ridges instead of down a slot.  Measured 21% roof / 30% street,
    # the most roof any street-readable game camera reached.
    game("game_street_roof", 0.0, -450.0, 0.6, 0.8,
         "Player at (0,-450) heading 53 degrees north-east into a block corner: "
         "roof ridges run diagonally across the middle of the frame, the lane "
         "turns out of sight, both eaves are in shot.")


def build_game_spots():
    """Fill the rest of game_* from the measured street picks."""
    try:
        with open(SPOTS, encoding="utf-8") as fh:
            d = json.load(fh)
    except (IOError, ValueError):
        print("[gen] no spots.json -- game_* stays at %d" % len(SHOTS))
        return
    picks = d.get("picks", [])
    for i, p in enumerate(picks[:4]):
        r = p.get("r", 0.0)
        game("game_street_%d" % (i + 1), p["x"], p["y"], p["ux"], p["uy"],
             "A secondary street %0.0f m from the centre, %0.1f m wide, with "
             "%0.0f m of clear corridor: two facades close enough to read, roofs "
             "at both bottom corners, cobbles between them."
             % (r, p.get("w", 0.0), p.get("run", 0.0)))


# --------------------------------------------------------------------------- #
#  eye_*: 1.72 m.  Every one of these stands inside a `_reserved()` zone, which
#  is the only place where the ground is provably free of houses.
# --------------------------------------------------------------------------- #
def build_eye():
    eye("eye_avenue_gate", 0.0, 860.0, 0.0, R_OUTER + 20.0, 26.0, 28.0,
        "Standing on the north avenue 87 m from the gatehouse: two 32 m towers "
        "fill the frame, the arch between them is a black slot, the avenue's "
        "cobbles run out from under your feet.")
    eye("eye_avenue_south", 0.0, -700.0, 0.0, -900.0, 8.0, 24.0,
        "The south avenue looking away from town: houses step down either side, "
        "the road narrows into haze, the outer wall crosses the far end.")
    eye("eye_plaza_south", -14.0, -48.0, 2.0, 30.0, 9.0, 35.0,
        "The market square from its south-west corner, clear of the misplaced "
        "bridge-rib strip at x=0: the fountain's kerb in the middle distance, the "
        "market hall's steps and arcade across the far side, the cathedral's "
        "south flank closing the left.")
    eye("eye_cathedral_front", -225.0, 4.0, -225.0, 43.0, 16.0, 18.0,
        "The cathedral's west front from 39 m back: the three portal bays at eye "
        "level, paving running up to them, the rose window above, the gable cut "
        "by the top of the frame.  18 mm because 40 m of facade will not fit "
        "otherwise.")
    eye("eye_guild_front", 210.0, 66.0, 210.0, 83.0, 6.5, 18.0,
        "The guildhall's south front at 17 m: the jettied upper floor overhangs "
        "the portal, its windows read as dark rectangles, the eave cuts across "
        "the top, its own cobbled forecourt in the foreground.")
    eye("eye_castle_ramp", 0.0, 172.0, 0.0, 266.0, 30.0, 24.0,
        "The castle ramp looking up at the gatehouse: the road climbs between "
        "retaining walls, the twin towers stand at the top of the rise, the rock "
        "face closes everything behind them.")


def build_eye_spots():
    try:
        with open(SPOTS, encoding="utf-8") as fh:
            d = json.load(fh)
    except (IOError, ValueError):
        return
    for i, p in enumerate(d.get("eye_picks", [])[:2]):
        ux, uy = p["ux"], p["uy"]
        eye("eye_street_%d" % (i + 1), p["x"], p["y"],
            p["x"] + ux * 40.0, p["y"] + uy * 40.0, 4.0, 24.0,
            "A measured street at %0.0f m from the centre, %0.1f m of clear air "
            "ahead at 1.72 m: both facades in the frame, the far end of the "
            "street falling away." % (p.get("r", 0.0), p.get("los", 0.0)))


# --------------------------------------------------------------------------- #
#  aerial_* / overview_*
# --------------------------------------------------------------------------- #
def build_aerial():
    aimed("aerial_city", "aerial", (1036.0, -1835.0, 710.0), (0.0, 20.0, 15.0),
          50.0, "The whole town from the south-east at 710 m: the ring wall reads "
                "as a circle, the four avenues as spokes, the castle rock and the "
                "cathedral spire are the two things that break the roofline.")
    aimed("aerial_castle", "aerial", (222.0, 503.0, 120.0), (0.0, 330.0, 55.0),
          50.0, "The castle from the north-east: the rock shelf, the curtain, and "
                "the keep standing on top of all of it, roofs of the upper town "
                "in front.")
    aimed("aerial_harbour", "aerial", (150.0, -560.0, 150.0), (0.0, -770.0, 6.0),
          40.0, "The harbour: two quays, the bridge with its piers, thirty boats "
                "along the water, warehouses at the back.")
    aimed("overview_city", "overview", (1391.0, -1746.0, 903.0), (0.0, -20.0, 10.0),
          34.0, "The establishing frame: the whole capital in one plate, wall and "
                "towers on the left, cathedral and town right, the river and the "
                "sea haze beyond.")


# --------------------------------------------------------------------------- #
#  landmark_*: one portrait each.  Positions sit above the 18.3 m roofline
#  unless the ground under them is inside a reserved zone.
# --------------------------------------------------------------------------- #
def build_landmark():
    aimed("landmark_castle_keep", "landmark", (0.0, 200.0, 95.0), (0.0, 333.0, 58.0),
          70.0, "The keep from above the gatehouse: the four turrets and the "
                "lantern spire at 84.7 m read against the sky, the curtain wall "
                "and its towers step down in front, the upper town's roofs below.")
    aimed("landmark_cathedral_front", "landmark", (-150.0, -120.0, 38.0),
          (-225.0, 93.0, 34.0), 50.0,
          "The cathedral from the south-east, above the roofs: the transept end, "
          "the apse, the 66 m spire over the ridge, the city's slate and terracotta "
          "between us and it.")
    aimed("landmark_market_hall", "landmark", (0.0, -30.0, 9.0), (0.0, 34.0, 11.0),
          35.0, "The market hall from the square: the open arcade at ground level, "
                "the great tiled roof above it, the lantern on the ridge, stalls "
                "and carts in the foreground.")
    aimed("landmark_guild", "landmark", (196.0, 58.0, 26.0), (210.1, 97.7, 12.0),
          45.0, "The guildhall three-quarter from the south-west: jettied upper "
                "storey, the tall chimney on its east end, the gable end facing "
                "the street.")
    for name, deg in (("north", 90.0), ("south", 270.0),
                      ("east", 0.0), ("west", 180.0)):
        a = math.radians(deg)
        ux, uy = math.cos(a), math.sin(a)
        aimed("landmark_gate_%s" % name, "landmark",
              (ux * 860.0, uy * 860.0, 26.0),
              (ux * R_OUTER, uy * R_OUTER, 20.0), 50.0,
              "The %s gatehouse from the avenue: twin towers, the arch between "
              "them, the curtain wall running away on both sides, roofs of the "
              "ring district in front." % name)


def build_extra():
    aimed("extra_castle_gate", "landmark", (0.0, 130.0, 30.0), (0.0, 266.0, 32.0),
          40.0, "The castle gatehouse with the keep behind it: the gate arch, the "
                "two flanking towers, the rock rising straight out of the roofs.")
    aimed("extra_castle_keep_air", "landmark", (0.0, 110.0, 52.0), (0.0, 320.0, 62.0),
          70.0, "The keep from the city below: the rock rim as a plinth, the gate "
                "towers in the middle ground, the keep's lantern spire at 84.7 m "
                "behind them.")
    aimed("extra_cathedral_west", "landmark", (-270.0, 16.0, 28.0),
          (-225.0, 43.0, 25.0), 18.0,
          "The cathedral's west front from inside its own reserved forecourt, "
          "50 m out and off-axis: both towers' shoulders, the rose window, the "
          "portal, and the paving between us and the doors.")
    aimed("extra_harbour_bridge", "landmark", (60.0, -700.0, 24.0),
          (0.0, -762.0, 4.0), 35.0,
          "The river bridge from the north quay: three arches, the parapet line, "
          "boats moored under it, warehouses behind.")


# --------------------------------------------------------------------------- #
def fold_qa(path):
    """Replace the tail of each note with what the QA pass actually measured."""
    with open(path, encoding="utf-8") as fh:
        qa = json.load(fh)
    rows = qa if isinstance(qa, list) else (qa.get("shots") or qa.get("frames") or [])
    by = {r["name"]: r for r in rows}
    n = 0
    for s in SHOTS:
        r = by.get(s["name"])
        if not r:
            continue
        c = r.get("buckets") or {}
        bits = []
        for key, label in (("sky", "sky"), ("ground", "ground"),
                           ("roof", "roof"), ("facade", "facade"),
                           ("other", "other")):
            v = c.get(key)
            if isinstance(v, (int, float)) and v >= 0.03:
                bits.append("%s %d%%" % (label, round(v * 100)))
        if bits:
            s["note"] = s["note"].rstrip() + " [measured: %s]" % ", ".join(bits)
            n += 1
    print("[gen] folded measured content into %d notes" % n)


def main():
    build_game()
    build_game_spots()
    build_eye()
    build_eye_spots()
    build_aerial()
    build_landmark()
    build_extra()
    if "--from-qa" in sys.argv:
        fold_qa(sys.argv[sys.argv.index("--from-qa") + 1])
    names = [s["name"] for s in SHOTS]
    assert len(names) == len(set(names)), "duplicate shot name"
    kinds = {}
    for s in SHOTS:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"generated_by": "look/_shotgen.py", "shots": SHOTS}, fh, indent=1)
    print("[gen] wrote %s: %d shots %s" % (OUT, len(SHOTS), kinds))


if __name__ == "__main__":
    main()
