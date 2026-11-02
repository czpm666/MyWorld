var go = UnityEngine.GameObject.Find("Towns");
var sb = new System.Text.StringBuilder();
var seen = new System.Collections.Generic.HashSet<string>();
int notex = 0, total = 0;
foreach (UnityEngine.Transform t in go.transform) {
  if (!t.name.StartsWith("mine_a")) continue;
  var rs = t.GetComponentsInChildren<UnityEngine.MeshRenderer>(true);
  foreach (var r in rs) {
    foreach (var m in r.sharedMaterials) {
      if (m == null) continue;
      total++;
      if (!seen.Add(m.name)) continue;
      bool tex = m.HasProperty("_BaseMap") && m.GetTexture("_BaseMap") != null;
      if (!tex) { notex++; if (sb.Length < 1200) sb.Append("NOTEX ").Append(m.name).Append(" sh=").Append(m.shader.name).Append("\n"); }
    }
  }
  break;
}
return "materials=" + seen.Count + " slots=" + total + " notex=" + notex + "\n" + sb;
