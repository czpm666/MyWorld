import bpy
m = bpy.data.materials.new("p")
nt = m.node_tree
need = ["ShaderNodeMixRGB", "ShaderNodeMix", "ShaderNodeTexVoronoi", "ShaderNodeTexWave",
        "ShaderNodeBsdfTranslucent", "ShaderNodeBump", "ShaderNodeMapRange",
        "ShaderNodeValToRGB", "ShaderNodeTexNoise", "ShaderNodeSeparateXYZ",
        "ShaderNodeCombineXYZ", "ShaderNodeMapping", "ShaderNodeTexCoord",
        "ShaderNodeRGBToBW", "ShaderNodeMath", "ShaderNodeBsdfPrincipled"]
for t in need:
    try:
        n = nt.nodes.new(t)
        print("OK", t, "| inputs:", [i.name for i in n.inputs][:6])
    except Exception as e:
        print("FAIL", t, e)
print("output node types:", [n.type for n in nt.nodes])
for n in nt.nodes:
    if n.type == "BSDF_PRINCIPLED":
        print("principled default base", list(n.inputs["Base Color"].default_value))
        print("spec", n.inputs["Specular IOR Level"].default_value)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2)
ob = bpy.context.object
print("ico s2 polys", len(ob.data.polygons), "verts", len(ob.data.vertices))
import bmesh
bm = bmesh.new(); bm.from_mesh(ob.data)
print("bevel args ok", len(bm.edges))
bm.free()
print("fbx props", [p for p in bpy.ops.export_scene.fbx.get_rna_type().properties.keys()][:60])
