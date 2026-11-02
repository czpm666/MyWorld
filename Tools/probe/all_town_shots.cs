var root = UnityEngine.GameObject.Find("Towns");
if (root == null) return "NO_TOWNS";
var ty = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
var mi = ty.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
var sb = new System.Text.StringBuilder();
foreach (UnityEngine.Transform tr in root.transform) {
  string n = tr.name;
  if (!n.StartsWith("farm") && !n.StartsWith("mine") && !n.StartsWith("port")) continue;
  string k = n.Substring(0, n.Length - 2);
  if (sb.ToString().Contains("|" + k + "|")) continue;
  sb.Append("|").Append(k).Append("|");
  float yaw = tr.eulerAngles.y * UnityEngine.Mathf.Deg2Rad;
  float ix = UnityEngine.Mathf.Sin(yaw), iz = UnityEngine.Mathf.Cos(yaw);
  UnityEngine.Vector3 p = tr.position;
  float cx = p.x - ix * 15f, cy = p.y + 2.2f, cz = p.z - iz * 15f;
  object r1 = mi.Invoke(null, new object[] { "v3_" + k + "_gate", cx, cy, cz, p.x + ix * 6f, p.y + 1.2f, p.z + iz * 6f, 40f, false });
  float ax = p.x - ix * 46f, ay = p.y + 44f, az = p.z - iz * 46f;
  object r2 = mi.Invoke(null, new object[] { "v3_" + k + "_air", ax, ay, az, p.x, p.y + 1f, p.z, 40f, false });
  sb.Append("\n").Append(k).Append(" ").Append(r1).Append(" ").Append(r2);
}
return sb.ToString();
