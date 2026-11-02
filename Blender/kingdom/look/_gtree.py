import bpy, sys, os
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import capital as C
C.init_mats()
for name in ("cobble", "street", "town_ground", "flag", "earth"):
    m = C.MAT.get(name)
    if m is None:
        print("MISSING", name); continue
    nt = m.node_tree
    print("=" * 70)
    print("MATERIAL", name, "nodes", len(nt.nodes))
    for n in nt.nodes:
        extra = ""
        if n.type == "TEX_VORONOI":
            extra = " scale=%s rand=%s feat=%s" % (n.inputs["Scale"].default_value, n.inputs["Randomness"].default_value, n.feature)
        elif n.type == "TEX_NOISE":
            extra = " scale=%s detail=%s rough=%s" % (n.inputs["Scale"].default_value, n.inputs["Detail"].default_value, n.inputs["Roughness"].default_value)
        elif n.type == "TEX_COORD":
            pass
        elif n.type == "MAPPING":
            extra = " scale=%s loc=%s" % (tuple(round(v,3) for v in n.inputs["Scale"].default_value), tuple(round(v,3) for v in n.inputs["Location"].default_value))
        elif n.type == "VALTORGB":
            extra = " stops=" + ",".join("%.2f:%s" % (e.position, tuple(round(c,3) for c in e.color[:3])) for e in n.color_ramp.elements)
        elif n.type in ("MATH", "MIX_RGB", "MIX", "MIX_SHADER"):
            try:
                extra = " op=%s" % (n.operation or "")
            except Exception:
                extra = ""
        elif n.type == "BUMP":
            extra = " strength=%s dist=%s" % (n.inputs["Strength"].default_value, n.inputs["Distance"].default_value)
        print("  %-22s %-14s%s" % (n.name, n.type, extra))
    for l in nt.links:
        print("   %s.%s -> %s.%s" % (l.from_node.name, l.from_socket.identifier, l.to_node.name, l.to_socket.identifier))
