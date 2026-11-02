var go = UnityEngine.GameObject.Find("Towns");
var sb = new System.Text.StringBuilder();
var seen = new System.Collections.Generic.HashSet<string>();
foreach (UnityEngine.Transform t in go.transform) {
  if (!t.name.StartsWith("port_a")) continue;
  var rs = t.GetComponentsInChildren<UnityEngine.MeshRenderer>(true);
  foreach (var r in rs) {
    foreach (var m in r.sharedMaterials) {
      if (m == null) continue;
      string n = m.name.ToLower();
      if (!(n.Contains("dirt") || n.Contains("earth") || n.Contains("yard") || n.Contains("roof") || n.Contains("cobble_far"))) continue;
      if (!seen.Add(m.name)) continue;
      var c = m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor") : UnityEngine.Color.magenta;
      var st = m.HasProperty("_BaseMap_ST") ? m.GetVector("_BaseMap_ST") : UnityEngine.Vector4.zero;
      bool bump = m.HasProperty("_BumpMap") && m.GetTexture("_BumpMap") != null;
      sb.Append(m.name).Append(" sh=").Append(m.shader.name).Append(" base=(").Append(c.r.ToString("F2")).Append(",").Append(c.g.ToString("F2")).Append(",").Append(c.b.ToString("F2")).Append(") ST.z=").Append(st.z.ToString("F2")).Append(" bump=").Append(bump).Append("\n");
    }
  }
  break;
}
return sb.ToString();
