import bpy
for nm in ("hu_roof_hd_tile_terra1", "hd_tile_terra1"):
    m = bpy.data.materials.get(nm)
    print("[mat]", nm, "found" if m else "MISSING")
    if not m or not m.use_nodes:
        continue
    for nd in m.node_tree.nodes:
        print("   %-26s %s" % (nd.bl_idname, nd.name))
