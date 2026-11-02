var root = UnityEngine.GameObject.Find("Towns");
if (root == null) return "NO_TOWNS";
var tr = root.transform.Find("port_a_4");
if (tr == null) return "NO_TOWN";
var mfs = tr.GetComponentsInChildren<UnityEngine.MeshRenderer>(true);
var seen = new System.Collections.Generic.HashSet<string>();
var sb = new System.Text.StringBuilder();
sb.Append("town renderers=").Append(mfs.Length);
foreach (var mr in mfs) {
  foreach (var m in mr.sharedMaterials) {
    if (m == null) continue;
    if (!seen.Add(m.name)) continue;
    bool tex = m.HasProperty("_BaseMap") && m.GetTexture("_BaseMap") != null;
    string texName = tex ? m.GetTexture("_BaseMap").name : "-";
    string col = m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor").ToString("F2") : "-";
    string bump = (m.IsKeywordEnabled("_NORMALMAP") && m.HasProperty("_BumpMap") && m.GetTexture("_BumpMap") != null) ? "NM" : "noNM";
    sb.Append("\n").Append(m.name).Append(" sh=").Append(m.shader.name.Replace("Universal Render Pipeline/", "URP/"))
      .Append(" tex=").Append(texName).Append(" base=").Append(col).Append(" ").Append(bump);
  }
}
return sb.ToString();
