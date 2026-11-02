var go = UnityEngine.GameObject.Find("Towns");
var sb = new System.Text.StringBuilder();
foreach (UnityEngine.Transform t in go.transform) {
  if (!t.name.StartsWith("farm_a")) continue;
  sb.Append("== ").Append(t.name).Append(" pos=").Append(t.position.ToString()).Append(" yaw=").Append(t.eulerAngles.y.ToString("F1")).Append("\n");
  foreach (UnityEngine.Transform c in t.GetComponentsInChildren<UnityEngine.Transform>(true)) {
    string n = c.name.ToLower();
    if (n.Contains("wind") || n.Contains("gate") || n.Contains("door") || n.Contains("well")) {
      UnityEngine.Vector3 lp = t.InverseTransformPoint(c.position);
      if (sb.Length < 1400) sb.Append("  ").Append(c.name).Append(" local=").Append(lp.ToString("F1")).Append("\n");
    }
  }
  break;
}
return sb.ToString();
