var go = UnityEngine.GameObject.Find("Towns");
var sb = new System.Text.StringBuilder();
if (go != null) {
  foreach (UnityEngine.Transform t in go.transform) {
    string n = t.name;
    if (!n.StartsWith("farm_a")) continue;
    var rs = t.GetComponentsInChildren<UnityEngine.MeshRenderer>(true);
    int rc = 0;
    float top = -999f;
    foreach (var r in rs) {
      rc++;
      var b = r.bounds;
      if (b.max.y > top) top = b.max.y;
    }
    sb.Append(n).Append(" renderers=").Append(rc).Append(" topY=").Append(top.ToString("F2")).Append(" pos=").Append(t.position.ToString()).Append("\n");
  }
}
var ground = UnityEngine.GameObject.Find("KingdomGround");
if (ground == null) {
  var ms = UnityEngine.Object.FindObjectsByType<UnityEngine.MeshRenderer>(UnityEngine.FindObjectsSortMode.None);
  foreach (var r in ms) { if (r.name.Contains("Ground")) { sb.Append("ground=").Append(r.name).Append(" mat=").Append(r.sharedMaterial != null ? r.sharedMaterial.name : "null").Append(" kw=").Append(r.sharedMaterial != null ? string.Join(",", r.sharedMaterial.shaderKeywords) : "-").Append("\n"); } }
} else {
  var r = ground.GetComponent<UnityEngine.MeshRenderer>();
  var mf = ground.GetComponent<UnityEngine.MeshFilter>();
  sb.Append("ground found renderers=").Append(r != null).Append(" vcount=").Append(mf != null && mf.sharedMesh != null ? mf.sharedMesh.vertexCount : -1).Append(" colors=").Append(mf != null && mf.sharedMesh != null ? mf.sharedMesh.colors.Length : -1);
  if (r != null && r.sharedMaterial != null) sb.Append(" mat=").Append(r.sharedMaterial.name).Append(" kw=").Append(string.Join(",", r.sharedMaterial.shaderKeywords));
  sb.Append("\n");
}
return sb.ToString();
