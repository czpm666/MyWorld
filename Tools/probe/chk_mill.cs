var go = UnityEngine.GameObject.Find("Towns");
var sb = new System.Text.StringBuilder();
foreach (UnityEngine.Transform t in go.transform) {
  if (!t.name.StartsWith("farm_a")) continue;
  sb.Append("== ").Append(t.name).Append(" pos=").Append(t.position.ToString()).Append(" yaw=").Append(t.eulerAngles.y.ToString("F1")).Append("\n");
  var rs = t.GetComponentsInChildren<UnityEngine.MeshRenderer>(true);
  foreach (var r in rs) {
    var mats = r.sharedMaterials;
    for (int i = 0; i < mats.Length; i++) {
      if (mats[i] == null) continue;
      string mn = mats[i].name.ToLower();
      if (mn.Contains("sail") || mn.Contains("wind") || mn.Contains("mill")) {
        var b = r.bounds;
        UnityEngine.Vector3 lp = t.InverseTransformPoint(b.center);
        sb.Append("  ").Append(r.name).Append(" mat=").Append(mats[i].name).Append(" localCenter=").Append(lp.ToString("F1")).Append(" size=").Append(b.size.ToString("F1")).Append("\n");
      }
    }
  }
  break;
}
return sb.ToString();
