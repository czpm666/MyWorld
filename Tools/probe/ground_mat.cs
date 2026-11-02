var sb = new System.Text.StringBuilder();
var gm = GameObject.Find("GroundMesh");
if (gm == null) return "no GroundMesh";
var mr = gm.GetComponent<MeshRenderer>();
var mf = gm.GetComponent<MeshFilter>();
var m = mr.sharedMaterial;
sb.AppendLine("mat=" + m.name + " shader=" + m.shader.name);
sb.AppendLine("kw_VERTEXCOLOR=" + m.IsKeywordEnabled("_VERTEXCOLOR"));
sb.AppendLine("mesh colors=" + (mf.sharedMesh.colors != null && mf.sharedMesh.colors.Length > 0));
var cols = mf.sharedMesh.colors;
if (cols != null && cols.Length > 0)
{
    // sample a few vertices: find min/max color to see if the tint exists at all
    float minR = 9f, maxR = -9f;
    for (int i = 0; i < cols.Length; i += 37) { if (cols[i].r < minR) minR = cols[i].r; if (cols[i].r > maxR) maxR = cols[i].r; }
    sb.AppendLine("color.r range " + minR.ToString("0.00") + ".." + maxR.ToString("0.00") + " count=" + cols.Length);
}
return sb.ToString();