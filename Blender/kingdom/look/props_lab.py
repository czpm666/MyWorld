"""Prop lab: street life on top of the capital's layout, seen through the game camera.

Two modes:

* mini (default) - no .blend at all.  Builds a mock city out of layout.json
  footprints (ground, street ribbons, box houses with pitched roofs) in a fresh
  empty scene, then runs `hd_streetlife.build()` with `region=` so only the
  ~100 m around the chosen stand is filled.  ~1.5 GB, renders in seconds, used
  for every iteration.

      blender -b --python look/props_lab.py -- --shots g01,g02,e1 --res 480x270 \
          --samples 8 --tag i1

* full (`--full`) - opens the saved 474 MB city and renders the ten game-camera
  spots from `look/spots.json` plus two eye-level street views.  This is the
  real verification pass; it needs ~10 GB and must be the only Blender on the
  machine.

      blender -b renders/kingdom/capital_v23.blend --python look/props_lab.py -- \
          --full --shots all --res 960x540 --samples 32 --tag r2
"""
import bpy
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib.util as _ilu         # noqa: E402
import hd_streetlife as SL            # noqa: E402
import hd_dense                       # noqa: E402
import hd_shops                       # noqa: E402

# look/ is not a package and "render" is too generic a name to put on sys.path
_spec = _ilu.spec_from_file_location("asura_rig", os.path.join(HERE, "render.py"))
RIG = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(RIG)

BLEND = os.path.join(ROOT, "..", "renders", "kingdom", "capital_v23.blend")
OUTDIR = os.path.join(ROOT, "..", "renders", "kingdom", "look")
LAYOUT = os.path.join(ROOT, "layout.json")

# the material dict built by capital.init_mats(); we pick the datablocks the
# saved scene already renders with instead of rebuilding them.
MAT_KEYS = ("plaster", "plaster2", "wood", "wood_dark", "tile", "tile_blue",
            "stone", "stone_warm", "rock", "cobble", "flag", "iron", "gold",
            "glass", "leaf", "leaf_dark", "water", "earth", "town_ground")


def log(*a):
    print("[lab]", *a, flush=True)


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------
def opts():
    o = {}
    a = sys.argv
    if "--" in a:
        a = a[a.index("--") + 1:]
    else:
        a = []
    i = 0
    while i < len(a):
        k = a[i]
        if k.startswith("--"):
            k = k[2:]
            if i + 1 < len(a) and not a[i + 1].startswith("--"):
                o[k] = a[i + 1]
                i += 2
            else:
                o[k] = "1"
                i += 1
        else:
            i += 1
    return o


def fnum(o, k, d=None):
    v = o.get(k)
    if v in (None, ""):
        return d
    try:
        return float(v)
    except ValueError:
        return d


# ---------------------------------------------------------------------------
# scene
# ---------------------------------------------------------------------------
def open_scene(path):
    cur = os.path.abspath(bpy.data.filepath) if bpy.data.filepath else ""
    if cur and os.path.normcase(cur) == os.path.normcase(os.path.abspath(path)):
        return cur
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise SystemExit("no blend: %s" % path)
    t = time.time()
    bpy.ops.wm.open_mainfile(filepath=path)
    log("opened %s in %.1fs" % (os.path.basename(path), time.time() - t))
    return path


def materials():
    """capital.init_mats() is the source of truth for the MAT dict the city uses."""
    try:
        import capital
        n0 = len(bpy.data.materials)
        capital.init_mats()
        MAT = dict(capital.MAT)
        log("MAT: %d keys from capital.init_mats(), %d new datablocks"
            % (len(MAT), len(bpy.data.materials) - n0))
        return MAT
    except Exception as exc:                                  # noqa: BLE001
        log("capital.init_mats() failed (%s); falling back to names" % exc)
    MAT = {}
    miss = []
    for k in MAT_KEYS:
        m = bpy.data.materials.get(k)
        if m is None:
            miss.append(k)
        else:
            MAT[k] = m
    log("MAT: %d/%d keys (%s)" % (len(MAT), len(MAT_KEYS),
                                  "missing " + ",".join(miss) if miss else "all"))
    return MAT


def layout():
    with open(LAYOUT, "r", encoding="utf-8") as f:
        return json.load(f)


def units_for(res):
    t = time.time()
    u = hd_dense.placements(res, foot_override=hd_shops.FOOTPRINT)
    log("placements: %d units in %.1fs" % (len(u), time.time() - t))
    return u


# ---------------------------------------------------------------------------
# cameras: 10 game spots from spots.json + 2 eye level + hero frames
# ---------------------------------------------------------------------------
class HeightGrid(object):
    """Per-cell building TOP height.

    `UnitGrid.hit()` only knows footprints, so a "good" stand can still be one
    where a 12 m house stands between the camera and the ground.  This lets the
    lab test what the 26.8 m game camera can actually see past.
    """

    def __init__(self, units, cell=5.0):
        self.cell = cell
        self.g = {}
        for u in units:
            q = u.get("quad") or ()
            if len(q) < 3:
                continue
            try:
                fl = float(u.get("floors") or 1)
                sc = float(u.get("scale") or 1.0)
                d = float(u.get("d") or 6.0)
            except (TypeError, ValueError):
                fl, sc, d = 1.0, 1.0, 6.0
            h = (2.9 * fl + 1.0) * sc + min(2.0, d * 0.30)
            xs = [p[0] for p in q]
            ys = [p[1] for p in q]
            for ix in range(int(min(xs) // cell), int(max(xs) // cell) + 1):
                for iy in range(int(min(ys) // cell), int(max(ys) // cell) + 1):
                    k = (ix, iy)
                    if h > self.g.get(k, 0.0):
                        self.g[k] = h

    def top(self, x, y):
        return self.g.get((int(x // self.cell), int(y // self.cell)), 0.0)


CAM_BACK = 20.9
CAM_UP = 26.8


def _clear_los(hg, cx, cy, cz, px, py, pz, n=16):
    """True if the straight camera->point line clears every roof."""
    for i in range(1, n):
        k = i / float(n)
        if hg.top(cx + (px - cx) * k, cy + (py - cy) * k) > cz + (pz - cz) * k:
            return False
    return True


def _vis_score(hg, x, y, ux, uy):
    """Fraction of the game camera's ground band that is actually visible.

    Ground band = 9.5 m behind the pivot to 14.7 m in front of it, 8 m to each
    side.  A stand where this is 0.2 shows roofs and nothing else, no matter
    what is on the ground.
    """
    cx, cy, cz = x - ux * CAM_BACK, y - uy * CAM_BACK, CAM_UP
    ok = tot = 0
    for t in (-9.0, -6.0, -3.0, 0.0, 3.0, 6.0, 9.0, 12.0, 15.0):
        for s in (-8.0, -4.0, 0.0, 4.0, 8.0):
            px = x + ux * t - uy * s
            py = y + uy * t + ux * s
            tot += 1
            if _clear_los(hg, cx, cy, cz, px, py, 0.6):
                ok += 1
    return ok / float(tot)


def _frame_ground(hg, x, y, ux, uy, cols=11, rows=7):
    """Fraction of the actual game frame that lands on the ground.

    Casts a coarse ray grid through the real 2.5D camera and marches each ray
    until it either hits a roof (blocked) or the ground plane.  This is the
    honest version of _vis_score: a 10 m roof 12 m from the camera covers the
    whole bottom of the frame while hiding very little ground area, so a
    ground-band sample count lies; a frame ray grid does not.
    """
    eye, look = RIG.game_cam(((x, y), (x + ux, y + uy)))
    cx, cy, cz = eye
    fx, fy, fz = look[0] - cx, look[1] - cy, look[2] - cz
    n = math.sqrt(fx * fx + fy * fy + fz * fz)
    fx, fy, fz = fx / n, fy / n, fz / n
    # right = forward x world_up
    rx, ry, rz = fy * 0.0 - fz * 0.0, fz * 0.0 - fx * 0.0, 0.0
    rx, ry, rz = -fy, fx, 0.0
    rn = math.hypot(rx, ry) or 1.0
    rx, ry = rx / rn, ry / rn
    # up = right x forward
    ux2 = ry * fz - rz * fy
    uy2 = rz * fx - rx * fz
    uz2 = rx * fy - ry * fx
    tv = math.tan(math.radians(30.0) * 0.5)          # 30 deg vertical FOV
    th = tv * (16.0 / 9.0)
    g = b = s = 0
    for i in range(cols):
        su = (2.0 * (i + 0.5) / cols - 1.0) * th
        for j in range(rows):
            sv = (2.0 * (j + 0.5) / rows - 1.0) * tv
            dx = fx + rx * su + ux2 * sv
            dy = fy + ry * su + uy2 * sv
            dz = fz + rz * su + uz2 * sv
            dn = math.sqrt(dx * dx + dy * dy + dz * dz)
            dx, dy, dz = dx / dn, dy / dn, dz / dn
            hit = 0
            for k in range(1, 40):
                t = 2.0 * k
                pz = cz + dz * t
                if pz <= 0.25:
                    hit = 1
                    break
                if hg.top(cx + dx * t, cy + dy * t) > pz:
                    hit = 2
                    break
                if t > 90.0:
                    break
            if hit == 1:
                g += 1
            elif hit == 2:
                b += 1
            else:
                s += 1
    tot = float(cols * rows)
    return g / tot, b / tot, s / tot


def _cam_clear(hg, x, y, ux, uy, rad=15.0, n=110):
    """Fraction of the disc under the camera that is NOT over a roof.

    The 2.5D camera flies 20.9 m behind and 26.8 m above the stand.  If that
    patch of sky is over a house, that house's roof fills the bottom of the
    frame no matter how well the street below reads -- this is the failure that
    produced 80 %-roof frames from spots that scored 0.89 on ground-band
    visibility.  Returns 0..1 (1 = camera is over open ground).
    """
    cx = x - ux * 20.9
    cy = y - uy * 20.9
    open_n = 0
    for i in range(n):
        a = 2.39996 * i
        r = rad * math.sqrt((i + 0.5) / n)
        if hg.top(cx + math.cos(a) * r, cy + math.sin(a) * r) < 1.5:
            open_n += 1
    return open_n / float(n)


def _low_rise(hg, x, y, ux, uy, lo=0.0, hi=34.0, half=15.0):
    """Fraction of the ground band around the stand that is low-rise.

    Even when the ground is technically visible, an 8 m terrace next to a 7 m
    street puts a roof across the bottom half of a 52-degree frame.  The band
    that actually lands on screen is ~11-35 m in front of the camera, so this
    samples that band on a coarse grid and returns how much of it has roofs
    below 6.5 m -- i.e. one or two storeys, the stock that lets street life read
    from the game camera.
    """
    cx = x - ux * 20.9
    cy = y - uy * 20.9
    px, py = -uy, ux
    ok = 0
    tot = 0
    lo = max(lo, 4.0)
    n = 7
    for i in range(n + 1):
        d = lo + (hi - lo) * (i / float(n))
        for j in range(-3, 4):
            s = half * (j / 3.0)
            t = hg.top(cx + ux * d + px * s, cy + uy * d + py * s)
            tot += 1
            if t < 6.5:
                ok += 1
    return ok / float(tot or 1)


def _frame_score(ug, x, y, ux, uy):
    """Score a stand the way the game camera sees it.

    The game camera sits 20.9 m behind and 26.8 m above the pivot, pitched 52
    deg with a 30 deg vertical FOV, so the visible ground runs from ~9.5 m
    behind the pivot to ~14.7 m in front.  A good 2.5D frame is a corridor:
    open ground down the middle (the street the player walks) and facades at
    both sides (which is what stops the shot reading as a car park).

    Returns open_centre * min(1, wall_sides / 0.45); 0 = no frame at all.
    """
    ok = tot = 0
    for t in range(-9, 16, 3):
        for s in (-5, -2, 0, 2, 5):
            px = x + ux * t - uy * s
            py = y + uy * t + ux * s
            tot += 1
            if not ug.hit(px, py, 0.0):
                ok += 1
    inside = stot = 0
    for t in range(-9, 16, 3):
        for s in (-16, -13, -10, 10, 13, 16):
            px = x + ux * t - uy * s
            py = y + uy * t + ux * s
            stot += 1
            if ug.hit(px, py, 0.0):
                inside += 1
    oc = ok / float(tot)
    ws = inside / float(stot)
    return oc * min(1.0, ws / 0.45), oc, ws


def _density(units, cell=20.0):
    """Count of buildings within a radius, on a coarse bucket grid."""
    g = {}
    for u in units:
        try:
            x, y = float(u["x"]), float(u["y"])
        except (KeyError, TypeError, ValueError):
            continue
        g.setdefault((int(x // cell), int(y // cell)), []).append((x, y))

    def count(x, y, rad):
        r = int(math.ceil(rad / cell))
        ix, iy = int(x // cell), int(y // cell)
        c = 0
        rr = rad * rad
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for (px, py) in g.get((ix + dx, iy + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 <= rr:
                        c += 1
        return c
    return count


def hero_spots(units, res, n_game=3, n_street=2, sep=140.0, near=None):
    """Street stands where the game camera actually sees the ground.

    near=(x, y, r) restricts the search to one neighbourhood, which is what the
    mini lab needs: one region, four game cameras and two eye-level views.
    """
    import random as _random
    ug = SL.UnitGrid(units)
    rng = _random.Random(20261101)
    cand = SL.street_spots(list(res.get("streets") or ()), ug, rng)
    if near is not None:
        nx, ny, nr = near
        cand = [sp for sp in cand
                if (sp["x"] - nx) ** 2 + (sp["y"] - ny) ** 2 <= nr * nr]
    ranked = []
    dens = _density(units)
    hg = HeightGrid(units)
    xs = [float(u["x"]) for u in units]
    ys = [float(u["y"]) for u in units]
    # the city wall is not a "unit", so HeightGrid reports open ground for it and
    # the scorer happily picks stands outside the wall.  Keep well inside.
    bx0, bx1 = min(xs) + 60.0, max(xs) - 60.0
    by0, by1 = min(ys) + 60.0, max(ys) - 60.0
    for sp in cand[::3]:
        # a spot on the edge of the map scores "open" for the wrong reason:
        # there is nothing beyond it.  Require a dense town around the stand.
        if dens(sp["x"], sp["y"], 70.0) < 30:
            continue
        if not (bx0 <= sp["x"] <= bx1 and by0 <= sp["y"] <= by1):
            continue
        best = -1.0
        bax, bay = sp["ax"], sp["ay"]
        bgr = 0.0
        bcc = 0.0
        for (ax, ay) in ((sp["ax"], sp["ay"]), (-sp["ax"], -sp["ay"])):
            gr, blk, sky = _frame_ground(hg, sp["x"], sp["y"], ax, ay)
            cc = _cam_clear(hg, sp["x"], sp["y"], ax, ay)
            lr = _low_rise(hg, sp["x"], sp["y"], ax, ay)
            # ground in the frame is the whole game: roof and sky fill whatever
            # the props do not.  A camera parked over a roof ruins the shot
            # outright, so it multiplies rather than adds.
            _, oc, ws = _frame_score(ug, sp["x"], sp["y"], ax, ay)
            s_ = gr * cc * cc * lr * lr * (0.85 + 0.15 * min(1.0, ws / 0.45))
            if s_ > best:
                best, bax, bay, bgr, bcc = s_, ax, ay, gr, cc
        rec = dict(sp)
        rec["ax"], rec["ay"] = bax, bay
        rec["vis"] = round(_vis_score(hg, sp["x"], sp["y"], bax, bay), 3)
        rec["ground"] = round(bgr, 3)
        rec["cam"] = round(bcc, 3)
        ranked.append((best, rec))
    ranked.sort(key=lambda kv: -kv[0])
    picked = []
    want = n_game + n_street
    for s, sp in ranked:
        if s < 0.10:
            break
        if any((sp["x"] - q["x"]) ** 2 + (sp["y"] - q["y"]) ** 2 < sep * sep
               for q in picked):
            continue
        rec = dict(sp)
        rec["score"] = round(s, 3)
        picked.append(rec)
        if len(picked) >= want:
            break
    log("hero spots: " + ", ".join("%s@%.0f,%.0f o=%.2f g=%.2f c=%.2f v=%.2f"
                                   % (p["kind"], p["x"], p["y"], p["score"],
                                      p.get("ground", 0.0), p.get("cam", 0.0),
                                      p.get("vis", 0.0))
                                   for p in picked))
    return picked


def hero_table(hero, n_street=2):
    """game cameras + eye-level views from a hero_spots() list.

    The eye-level stands are taken from spots 2 and 3, not from the top two:
    the best game-camera stands tend to sit under a landmark arcade or a bridge,
    which is invisible from 26 m up but fills an eye-level frame with columns.
    """
    t = {}
    eyes = []
    for i, h in enumerate(eyes[:n_street]):
        t["e%d_street" % (i + 1)] = dict(
            loc=(h["x"], h["y"], 1.72),
            look=(h["x"] + h["ax"] * 46.0, h["y"] + h["ay"] * 46.0, 3.2),
            lens=22.0, kind="street")
    rest = list(hero)
    for i, h in enumerate(rest[:max(0, len(rest))]):
        eye, look = RIG.game_cam(((h["x"], h["y"]),
                                  (h["x"] + h["ax"], h["y"] + h["ay"])))
        t["h%02d_%s" % (i + 1, h["kind"])] = dict(loc=eye, look=look, vfov=30.0,
                                                  kind="wide")
    return t


def eye_spots(units, res, n=2, sep=120.0):
    """Eye-level stands with a long clear run down the street.

    Picking an eye stand from a game-camera score is a trap: the 26 m camera can
    see over an arcade or a colonnade that fills a 1.72 m frame with stone.  This
    marches straight ahead from each street station and keeps the ones with the
    longest unobstructed run, so the camera looks *down a street*, not into a wall.
    """
    import random as _rnd
    ug = SL.UnitGrid(units)
    cand = SL.street_spots(list(res.get("streets") or ()), ug,
                           _rnd.Random(770031))
    out = []
    for sp in cand:
        if sp["kind"] == "alley":
            continue
        ax, ay = sp["ax"], sp["ay"]
        run = 0.0
        for k in range(1, 56):
            t = 0.5 * k
            if ug.hit(sp["x"] + ax * t, sp["y"] + ay * t, 0.45):
                break
            run = t
        # a hard left/right test keeps the camera out of a colonnade too
        side = 0
        for s_ in (-3.0, -1.5, 1.5, 3.0):
            if not ug.hit(sp["x"] - ay * s_, sp["y"] + ax * s_, 0.4):
                side += 1
        if side < 2:
            continue
        out.append((run, sp))
    out.sort(key=lambda kv: -kv[0])
    picked = []
    for run, sp in out:
        if run < 12.0:
            break
        if all((sp["x"] - p["x"]) ** 2 + (sp["y"] - p["y"]) ** 2 > sep * sep
               for p in picked):
            rec = dict(sp)
            rec["run"] = round(run, 1)
            picked.append(rec)
        if len(picked) >= n:
            break
    log("eye spots: " + ", ".join("%s@%.0f,%.0f run=%.0f"
                                  % (p["kind"], p["x"], p["y"], p["run"])
                                  for p in picked))
    return picked


def cluster_shots(pts, units, n=3, want=12, cell=8.0):
    """Hand-placed eye-level cameras aimed at the densest prop clusters.

    The game camera and the street sampler both keep landing on roofs and
    facades in this blend, so this is the shot that actually answers "does the
    street life read at 1.72 m, and is it the right size next to a door".
    """
    ug = SL.UnitGrid(units)
    grid = {}
    for (x, y, name) in pts:
        grid.setdefault((int(x // cell), int(y // cell)), []).append((x, y))
    cands = []
    for _k, lst in grid.items():
        cnt = len(lst)
        if cnt < want:
            continue
        cx = sum(p[0] for p in lst) / cnt
        cy = sum(p[1] for p in lst) / cnt
        if ug.hit(cx, cy, 0.6):
            continue
        cands.append((cnt, cx, cy))
    cands.sort(key=lambda t: -t[0])
    out = []
    for cnt, cx, cy in cands:
        if len(out) >= n:
            break
        if any((cx - o["x"]) ** 2 + (cy - o["y"]) ** 2 < 200.0 ** 2 for o in out):
            continue
        ang0 = (len(out) * 2.3) % (2.0 * math.pi)
        spot = None
        for k in range(8):
            ang = ang0 + k * (math.pi / 4.0)
            r_ = 5.2 if k % 2 == 0 else 3.9
            ex = cx + math.cos(ang) * r_
            ey = cy + math.sin(ang) * r_
            if ug.hit(ex, ey, 0.45):
                continue
            # the sight line has to be clear too, or the camera ends up
            # photographing the inside of a wall from 4 m away
            ok = True
            for j in range(1, 8):
                f = j / 8.0
                if ug.hit(ex + (cx - ex) * f, ey + (cy - ey) * f, 0.35):
                    ok = False
                    break
            if ok:
                spot = (ex, ey)
                break
        if spot is None:
            continue
        ex, ey = spot
        out.append(dict(x=cx, y=cy, ex=ex, ey=ey, n=cnt))
    log("clusters: " + ", ".join("%d props @%.0f,%.0f" % (o["n"], o["x"], o["y"])
                                 for o in out))
    return out


def plaza_shot(res):
    """Wide three-quarter view of the biggest square/plaza block.

    This is the shot that answers "do the stalls read as a market?"  Aimed at
    the block centroid from 60 m out at 28 m up, so the stalls, carts, crowd and
    awnings are all in frame at once.
    """
    best = None
    for b in res.get("blocks") or ():
        if (b.get("role") or "") not in ("square", "plaza"):
            continue
        q = b.get("poly") or b.get("quad") or ()
        if len(q) < 3:
            continue
        xs = [p[0] for p in q]
        ys = [p[1] for p in q]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if best is None or area > best[0]:
            best = (area, (sum(xs) / len(xs), sum(ys) / len(ys)),
                    max(max(xs) - min(xs), max(ys) - min(ys)))
    if best is None:
        return None
    area, (cx, cy), span = best
    d = max(40.0, min(95.0, span * 0.95))
    return dict(loc=(cx - d * 0.60, cy - d * 0.68, 15.5),
                look=(cx, cy, 1.2), lens=28.0, kind="wide",
                note="plaza span %.0f m" % span)


def lab_table(n_game=10, n_street=2, units=None, res=None, n_hero=3):
    t = {}
    rays = RIG.street_rays(n_game)
    for i, (p, u, w, kind) in enumerate(rays):
        eye, look = RIG.game_cam((p, u))
        t["g%02d_%s" % (i + 1, kind)] = dict(loc=eye, look=look, vfov=30.0,
                                              kind="wide", w=w)
    views = RIG.street_views(n_street)
    for i, spot in enumerate(views):
        t["e%d_street" % (i + 1)] = dict(loc=spot[0], look=spot[1], lens=24.0,
                                         kind="street")
    if units is not None and res is not None and n_hero > 0:
        hero = hero_spots(units, res, n_hero, n_street)
        t.update(hero_table(hero, n_street))
        # eye-level stand on the same open ground the game camera proved clear:
        # a random street station keeps ending up nose-first against a facade,
        # whereas a hero pivot is known to be open street at ground level.
        for i, h in enumerate(hero[:2]):
            t["y%d_street" % (i + 1)] = dict(
                loc=(h["x"], h["y"], 1.72),
                look=(h["x"] + h["ax"] * 26.0, h["y"] + h["ay"] * 26.0, 2.4),
                lens=20.0, kind="street")
    return t


def sheet_shot(cols, step):
    """Camera for the prop sheet, which we park outside the city."""
    rows = 12
    cx = cols * step * 0.5
    cy = rows * step * 0.5
    return dict(loc=(cx, cy - 46.0, 34.0), look=(cx, cy, 0.8), lens=32.0,
                kind="street")


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------
def render(table, wants, outdir, preset, samples, res, tag, haze=True,
           exposure=None, tilt=None, tazim=None):
    os.makedirs(outdir, exist_ok=True)
    RIG.setup_engine("eevee", samples, res, vols=haze)
    done = []
    for name in wants:
        spec = table.get(name)
        if spec is None:
            log("no shot %r" % name)
            continue
        t1 = time.time()
        RIG.wipe_rig()
        cam = RIG.make_camera(spec)
        c = cam.location
        elev = tilt if tilt is not None else \
            RIG.L.PRESETS[preset]["sun_elev_wide" if spec["kind"] == "wide"
                                 else "sun_elev_street"]
        RIG.build_rig(preset, elev, tazim, haze=haze,
                      haze_mul=spec.get("haze_mul", 1.0),
                      haze_extent=spec.get("haze_extent", 2800.0),
                      cam=(c.x, c.y))
        if exposure is not None:
            bpy.context.scene.view_settings.exposure = exposure
        path = os.path.join(outdir, "%s%s.png" % (tag + "_" if tag else "", name))
        bpy.context.scene.render.filepath = path
        t2 = time.time()
        bpy.ops.render.render(write_still=True)
        t3 = time.time()
        done.append(dict(shot=name, path=path, rig_s=round(t2 - t1, 2),
                         render_s=round(t3 - t2, 2)))
        log("%-12s %5.1fs  (rig %.1fs)" % (name, t3 - t2, t2 - t1))
    return done


def _mini_faces(MAT, P, units, streets, cx, cy, r):
    """Footprint stand-in for the real city: ground, street ribbons, box houses.

    Loading capital_v23.blend costs ~10 GB and blue-screened the machine, so
    iteration happens on this 250-house mock-up: same layout.json footprints,
    same street widths, but boxes instead of 9,532 detailed houses.  It is a
    fair test of prop density, colour and occlusion, which is what I need to
    judge; it is not a test of the final render.
    """
    g = SL.Geo()
    gmat = MAT.get("town_ground") or MAT.get("stone")
    s = r + 45.0
    g.quad(gmat, (cx - s, cy - s, -0.02), (cx + s, cy - s, -0.02),
           (cx + s, cy + s, -0.02), (cx - s, cy + s, -0.02))
    cob = MAT.get("cobble") or MAT.get("stone")
    for st in streets:
        hw = float(st.get("w") or 6.0) * 0.5
        for ch in SL._chains(st):
            for i in range(len(ch) - 1):
                ax, ay = ch[i]
                bx, by = ch[i + 1]
                L = math.hypot(bx - ax, by - ay)
                if L < 0.3:
                    continue
                ux, uy = (bx - ax) / L, (by - ay) / L
                nx, ny = -uy, ux
                ax -= ux * hw * 0.5
                ay -= uy * hw * 0.5
                bx += ux * hw * 0.5
                by += uy * hw * 0.5
                g.quad(cob,
                       (ax - nx * hw, ay - ny * hw, 0.02),
                       (bx - nx * hw, by - ny * hw, 0.02),
                       (bx + nx * hw, by + ny * hw, 0.02),
                       (ax + nx * hw, ay + ny * hw, 0.02))
    wall = MAT.get("plaster") or MAT.get("wood")
    roof = MAT.get("tile") or wall
    roof2 = MAT.get("tile_blue") or roof
    dark = MAT.get("wood_dark") or wall
    n = 0
    for u in units:
        try:
            x, y = float(u["x"]), float(u["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if (x - cx) ** 2 + (y - cy) ** 2 > (r + 30.0) ** 2:
            continue
        w = float(u.get("w") or 6.0)
        d = float(u.get("d") or 5.0)
        yaw = float(u.get("yaw") or 0.0)
        fl = float(u.get("floors") or 1.0)
        h = max(3.4, min(7.8, 2.9 * fl + 1.0))
        R = SL._rot3(rz=yaw)
        g.box(wall, (x, y, h * 0.5), (w, d, h), R=R)
        # dark door + two windows on the facade (local +Y) so the wall reads as
        # a house and I can judge how clutter sits against it
        fw = max(0.55, w * 0.12)
        for (ox, wz, hh) in ((-w * 0.22, h * 0.34, min(1.7, h * 0.4)),
                             (w * 0.22, h * 0.34, min(1.7, h * 0.4)),
                             (0.0, min(1.05, h * 0.24), min(2.1, h * 0.45))):
            p = SL._mx(R, (ox, d * 0.5 + 0.06, wz))
            g.box(dark, (x + p[0], y + p[1], p[2]),
                  (fw * 1.6 if ox else fw * 1.9, 0.10, hh), R=R)
        rise = min(2.0, d * 0.30)
        e = 0.32
        hw_, hd_ = w * 0.5 + e, d * 0.5 + e
        rm = roof if (n % 3) else roof2
        for sgn in (1, -1):
            pts = [(-hw_, sgn * hd_, h - 0.12), (hw_, sgn * hd_, h - 0.12),
                   (hw_, 0.0, h + rise), (-hw_, 0.0, h + rise)]
            wp = []
            for (px, py, pz) in pts:
                v = SL._mx(R, (px, py, pz))
                wp.append((x + v[0], y + v[1], v[2]))
            g.quad(rm, wp[0], wp[1], wp[2], wp[3])
            # gable triangle as a sliver quad, so the end of the roof is closed
            gt = [(sgn * hw_, -hd_, h - 0.12), (sgn * hw_, hd_, h - 0.12),
                  (sgn * hw_, 0.0, h + rise), (sgn * hw_, 0.0, h + rise - 0.02)]
            wp = []
            for (px, py, pz) in gt:
                v = SL._mx(R, (px, py, pz))
                wp.append((x + v[0], y + v[1], v[2]))
            g.quad(rm, wp[0], wp[1], wp[2], wp[3])
        n += 1
    proto = SL.to_proto(g)
    b = SL.Batch("mini_city")
    b.put(proto, 0.0, 0.0, 0.0, 0.0, 1.0)
    ob = b.emit(P)
    log("mini city: %d houses, ground + streets" % n)
    return ob


def mini_city(MAT, units, res, centre, r):
    P = SL.palette(MAT)
    us, ss = SL._clip((centre[0], centre[1], r + 25.0), list(units),
                      list(res.get("streets") or ()))
    return _mini_faces(MAT, P, us, ss, centre[0], centre[1], r)


def main():
    o = opts()
    t0 = time.time()
    full = "full" in o
    if full:
        open_scene(o.get("blend") or BLEND)
    else:
        bpy.ops.wm.read_homefile(use_empty=True)
    res = layout()
    MAT = materials()
    units = units_for(res)
    if units:
        log("unit keys: %s" % ",".join(sorted(units[0])))
        log("floors sample: %s"
            % [units[i].get("floors") for i in range(0, 60, 7)])
        hg0 = HeightGrid(units)
        hs = sorted(hg0.g.values())
        log("height grid: %d cells, roof top min %.1f med %.1f max %.1f"
            % (len(hs), hs[0], hs[len(hs) // 2], hs[-1]))

    seed = int(fnum(o, "seed", 7))
    dens = fnum(o, "density", 1.0)
    cell = fnum(o, "cell", 56.0)
    n_game = int(fnum(o, "game", 10 if full else 3))
    n_street = int(fnum(o, "street", 2))

    region = None
    if full:
        table = lab_table(n_game, n_street, units=units, res=res,
                          n_hero=int(fnum(o, "hero", 3)))
    else:
        rad = float(fnum(o, "rad", 95.0))
        best = hero_spots(units, res, 0, 1, sep=1e9)[0]
        region = (best["x"], best["y"], rad)
        hero = hero_spots(units, res, max(1, n_game), n_street, sep=rad * 0.34,
                          near=(best["x"], best["y"], rad * 0.55))
        table = hero_table(hero, n_street)
        mini_city(MAT, units, res, (best["x"], best["y"]), rad)

    t1 = time.time()
    objs = SL.build(MAT, units, res, seed=seed, density=dens, cell=cell,
                    region=region, keep_points=True)
    st = SL.stats()
    log("build: %d props, %d faces, %d objects, %.1fs"
        % (st["props"], st["faces"], st["objects"], time.time() - t1))
    log("street stations: %d (%d with no wall found)"
        % (st.get("stations", 0), st.get("no_wall", 0)))
    # how much of the street life actually falls inside each camera's view?
    pts = st.get("points") or []
    for nm, spec in table.items():
        lx, ly, lz = spec["look"]
        n30 = sum(1 for (px, py, _) in pts
                  if (px - lx) ** 2 + (py - ly) ** 2 < 900.0)
        log("  %-14s props within 30 m of look-at: %d" % (nm, n30))
    if o.get("dump"):
        dd = dict(st)
        dd.pop("points", None)
        with open(o["dump"], "w", encoding="utf-8") as f:
            json.dump(dd, f, indent=1, sort_keys=True)
    top = sorted(st["by_kind"].items(), key=lambda kv: -kv[1])[:14]
    log("by kind: " + ", ".join("%s %d" % kv for kv in top))

    for i, c in enumerate(cluster_shots(pts, units, 3)):
        table["c%d_props" % (i + 1)] = dict(
            loc=(c["ex"], c["ey"], 1.72), look=(c["x"], c["y"], 1.05),
            lens=26.0, kind="street")
        # same ground, the real game camera: this is the pair that answers
        # "does a courtyard still read as an empty plate from 34 m".
        eye, look = RIG.game_cam(((c["x"], c["y"]), (c["x"] + 1.0, c["y"] + 0.6)))
        table["d%d_cam" % (i + 1)] = dict(loc=eye, look=look,
                                          vfov=30.0, kind="wide")

    if o.get("plaza") and full:
        pz = plaza_shot(res)
        if pz is not None:
            table["w1_plaza"] = pz
            log("plaza: " + str(pz.get("note")))

    wants = o.get("shots", "all")
    if wants == "all":
        names = list(table)
    else:
        names = [n.strip() for n in wants.split(",") if n.strip()]
        names = [n for n in table if any(n == w or n.startswith(w) for w in names)]

    if o.get("propsheet"):
        sheet, keys = SL.build_prop_sheet(MAT, cols=8, step=3.2)
        table["propsheet"] = dict(loc=(0.0, 0.0, 0.0), look=(0.0, 0.0, 0.0),
                                  kind="wide")
        table["propsheet"] = sheet_shot(8, 3.2)
        if "propsheet" in wants or wants == "all":
            names.append("propsheet")

    if o.get("dry"):
        dd = dict(st)
        dd.pop("points", None)
        print("[lab-result] " + json.dumps(dict(stats=dd,
                                               seconds=round(time.time() - t0, 1))))
        return

    outdir = o.get("out") or OUTDIR
    done = render(table, names, outdir, o.get("preset", "morning_town"),
                  int(fnum(o, "samples", 24)),
                  [int(x) for x in str(o.get("res", "960x540")).split("x")],
                  o.get("tag", ""), haze="no-haze" not in o,
                  exposure=fnum(o, "exposure"), tilt=fnum(o, "elev"),
                  tazim=fnum(o, "azim"))
    log("done in %.1fs" % (time.time() - t0))
    print("[lab-result] " + json.dumps(dict(
        stats={k: st[k] for k in ("props", "faces", "objects", "seconds",
                                  "rejected", "kinds", "seed", "density")},
        shots=done, seconds=round(time.time() - t0, 1))))


if __name__ == "__main__":
    main()
