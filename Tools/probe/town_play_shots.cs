var root = UnityEngine.GameObject.Find("Towns");
if (root == null) return "NO_TOWNS";
var ty = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
var mi = ty.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
string[] names = new string[] { "port_a_4", "port_b_2", "mine_a_29", "farm_b_4" };
var sb = new System.Text.StringBuilder();
for (int k = 0; k < names.Length; k++) {
  var tr = root.transform.Find(names[k]);
  if (tr == null) { sb.Append(" |missing ").Append(names[k]); continue; }
  float yaw = tr.eulerAngles.y * UnityEngine.Mathf.Deg2Rad;
  float ix = UnityEngine.Mathf.Sin(yaw), iz = UnityEngine.Mathf.Cos(yaw);
  UnityEngine.Vector3 p = tr.position;
  float cx = p.x + ix * 12f, cy = p.y + 20f, cz = p.z + iz * 12f;
  float lx = p.x - ix * 10f, ly = p.y + 1.5f, lz = p.z - iz * 10f;
  object r = mi.Invoke(null, new object[] { names[k] + "_play", cx, cy, cz, lx, ly, lz, 30f, false });
  sb.Append("\n").Append(names[k]).Append(" ").Append(r);
}
return sb.ToString();
