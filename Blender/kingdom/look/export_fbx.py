"""Minimal, dependency-free reader for binary FBX 7.x (Kaydara) files.

Why this exists
---------------
Every claim about "the mesh is X tris, the axes are Y, the material is Z" must
be checkable *outside* Blender, because Blender's own export log lies by
omission (it happily writes empty geometry, drops material slots, flips axes
and still prints "FBX export finished").

This module is plain Python 3 (no bpy, no numpy), so it also runs from the
system interpreter for post-hoc verification of a finished export tree:

    python look/export_fbx.py <file.fbx> [more.fbx ...]

or from code:

    import export_fbx as F
    doc = F.read(path)
    doc.global_settings()   # UpAxis / CoordAxis / UnitScaleFactor ...
    doc.summary()           # verts, polys, bbox, material names, node xforms

Format notes (FBX 7.4 / 7.5):
    header   : b"Kaydara FBX Binary  \\x00" + 0x1a 0x00 + u32 version
    node     : EndOffset, NumProps, PropListLen, NameLen(u8), Name,
               properties, children (recursive), 13-byte null terminator
    v7.5+    : the three offset/length fields are u64 (25-byte header)
    property : u8 type code then payload; arrays carry
               ArrayLength(u32), Encoding(u32), CompressedLen(u32), data
"""
import struct
import zlib

MAGIC = b"Kaydara FBX Binary  \x00"

_SCALAR = {"Y": ("<h", 2), "C": ("<B", 1), "I": ("<i", 4), "F": ("<f", 4),
           "D": ("<d", 8), "L": ("<q", 8)}
_ARRAY = {"f": ("f", 4), "d": ("d", 8), "l": ("q", 8), "i": ("i", 4), "b": ("B", 1)}


class Node(object):
    __slots__ = ("name", "props", "children")

    def __init__(self, name):
        self.name = name
        self.props = []
        self.children = []

    def find(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None

    def find_all(self, name):
        return [c for c in self.children if c.name == name]

    def p70(self):
        """Properties70 -> {name: value or tuple}, FBX's P: key,type,label,flags,values..."""
        out = {}
        node = self.find("Properties70")
        if node is None:
            return out
        for p in node.find_all("P"):
            if p.props and isinstance(p.props[0], str):
                vals = p.props[4:]
                out[p.props[0]] = vals[0] if len(vals) == 1 else tuple(vals)
        return out

    def __repr__(self):
        return "<%s props=%d children=%d>" % (self.name, len(self.props), len(self.children))


class Document(object):
    def __init__(self, path, version, header, top):
        self.path = path
        self.version = version
        self.header = header
        self.top = top

    # ---- top-level sections --------------------------------------------
    def section(self, name):
        for n in self.top:
            if n.name == name:
                return n
        return None

    def global_settings(self):
        gs = self.section("GlobalSettings")
        return gs.p70() if gs is not None else {}

    def objects(self, kind):
        obj = self.section("Objects")
        return [] if obj is None else obj.find_all(kind)

    def models(self):
        """[(uid, name, props)] incl. Lcl Translation / Lcl Rotation / PreRotation."""
        out = []
        for m in self.objects("Model"):
            uid = m.props[0] if m.props else None
            name = m.props[1].split("\x00")[0] if len(m.props) > 1 else ""
            out.append((uid, name, m.p70()))
        return out

    def connections(self):
        out = []
        c = self.section("Connections")
        if c is None:
            return out
        for k in c.find_all("C"):
            if len(k.props) >= 3:
                out.append((k.props[0], k.props[1], k.props[2]))
        return out

    # ---- summary --------------------------------------------------------
    def summary(self):
        gs = self.global_settings()
        mm = self.models()
        geos = self.objects("Geometry")
        mats = [m.props[1].split("\x00")[0] for m in self.objects("Material") if len(m.props) > 1]

        xform_keys = ("Lcl Translation", "Lcl Rotation", "Lcl Scaling", "PreRotation",
                      "PostRotation", "RotationOffset", "RotationPivot",
                      "ScalingOffset", "ScalingPivot",
                      "GeometricTranslation", "GeometricRotation", "GeometricScaling")
        info = {
            "path": self.path,
            "fbx_version": self.version,
            "header": self.header.decode("ascii", "replace"),
            "up_axis": gs.get("UpAxis"),
            "up_axis_sign": gs.get("UpAxisSign"),
            "front_axis": gs.get("FrontAxis"),
            "front_axis_sign": gs.get("FrontAxisSign"),
            "coord_axis": gs.get("CoordAxis"),
            "coord_axis_sign": gs.get("CoordAxisSign"),
            "unit_scale_factor": gs.get("UnitScaleFactor"),
            "orig_unit_scale_factor": gs.get("OriginalUnitScaleFactor"),
            "models": len(mm),
            "geometries": len(geos),
            "materials": mats,
            "model_xforms": {n: {k: v for k, v in p.items() if k in xform_keys}
                             for _u, n, p in mm[:8]},
        }

        tv = tp = 0
        mn = [1e30] * 3
        mx = [-1e30] * 3
        per_geo = []
        for g in geos:
            v = g.find("Vertices")
            p = g.find("PolygonVertexIndex")
            uv = g.find("LayerElementUV")
            nv = np_ = 0
            if v is not None and v.props:
                data = v.props[0]
                nv = len(data) // 3
                tv += nv
                for i in range(0, len(data), 3):
                    x, y, z = data[i], data[i + 1], data[i + 2]
                    if x < mn[0]: mn[0] = x
                    if y < mn[1]: mn[1] = y
                    if z < mn[2]: mn[2] = z
                    if x > mx[0]: mx[0] = x
                    if y > mx[1]: mx[1] = y
                    if z > mx[2]: mx[2] = z
            if p is not None and p.props:
                # polygons are index runs; the last index of each poly is ^-1 (negative)
                npt = sum(1 for i in p.props[0] if i < 0)
                tp += npt
                np_ = npt
            per_geo.append({"name": g.props[1].split("\x00")[0] if len(g.props) > 1 else "",
                            "verts": nv, "polys": np_,
                            "has_uv": uv is not None})
        info["verts"] = tv
        info["polys"] = tp
        info["bbox_min"] = [round(x, 4) for x in mn] if tv else None
        info["bbox_max"] = [round(x, 4) for x in mx] if tv else None
        if len(per_geo) <= 12:
            info["per_geometry"] = per_geo
        return info


def read(path):
    with open(path, "rb") as fh:
        buf = fh.read()
    if not buf.startswith(MAGIC):
        raise ValueError("%s: not a binary FBX (magic=%r)" % (path, buf[:24]))
    version = struct.unpack_from("<I", buf, 23)[0]
    wide = version >= 7500
    doc = Document(path, version, buf[27:27 + 12], [])
    p = 27
    while p < len(buf):
        node, p = _read_node(buf, p, wide)
        if node is None:
            break
        doc.top.append(node)
    return doc


def _read_node(buf, p, wide):
    """Return (Node|None, next_position). None means 'null record' = end of list."""
    hdr = 25 if wide else 13
    if p + hdr > len(buf):
        return None, len(buf)
    if wide:
        end, nprops, _plen = struct.unpack_from("<QQQ", buf, p)
    else:
        end, nprops, _plen = struct.unpack_from("<III", buf, p)
    nlen = buf[p + hdr - 1]               # NameLen sits right before the name
    if end == 0:
        return None, p + hdr
    name = buf[p + hdr:p + hdr + nlen].decode("ascii", "replace")
    q = p + hdr + nlen
    node = Node(name)
    for _ in range(nprops):
        val, q = _read_prop(buf, q)
        node.props.append(val)
    while q < end:
        child, q = _read_node(buf, q, wide)
        if child is None:
            break
        node.children.append(child)
    return node, end


def _read_prop(buf, p):
    code = chr(buf[p])
    p += 1
    if code in _SCALAR:
        fmt, size = _SCALAR[code]
        val = struct.unpack_from(fmt, buf, p)[0]
        return (bool(val) if code == "C" else val), p + size
    if code in _ARRAY:
        typecode, size = _ARRAY[code]
        n, enc, clen = struct.unpack_from("<III", buf, p)
        p += 12
        if enc == 1:
            raw = zlib.decompress(buf[p:p + clen])
            nxt = p + clen
        else:
            raw = buf[p:p + n * size]
            nxt = p + n * size
        return list(struct.unpack_from("<%d%s" % (n, typecode), raw, 0)), nxt
    if code in "SR":
        ln = struct.unpack_from("<I", buf, p)[0]
        p += 4
        raw = buf[p:p + ln]
        return (raw.decode("utf-8", "replace") if code == "S" else raw), p + ln
    raise ValueError("unknown FBX property code %r at offset %d" % (code, p))


def main(argv):
    import json
    for path in argv[1:]:
        print(json.dumps(read(path).summary(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
