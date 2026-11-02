var w = UnityEngine.GameObject.Find("Towns");
if (w == null) return "NO_TOWNS";
var sb = new System.Text.StringBuilder();
foreach (UnityEngine.Transform t in w.transform) {
  if (!t.name.StartsWith("port")) continue;
  Vector3 p = t.position;
  sb.Append("\n").Append(t.name).Append(" ").Append(p.ToString("F2")).Append(" rotY=").Append(t.eulerAngles.y.ToString("F1"))
    .Append(" scale=").Append(t.localScale.x.ToString("F2")).Append(" children=").Append(t.childCount);
}
return sb.ToString();
