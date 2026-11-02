var root = UnityEngine.GameObject.Find("Towns");
if (root == null) return "NO_TOWNS";
var sb = new System.Text.StringBuilder();
var ty = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
if (ty == null) return "NO_PROBE";
var mi = ty.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
if (mi == null) return "NO_SHOOT";
string[] names = new string[] { "port_a_4", "port_b_2" };
for (int k = 0; k < names.Length; k++) {
  var tr = root.transform.Find(names[k]);
  if (tr == null) { sb.Append(" |missing ").Append(names[k]); continue; }
  float yaw = tr.eulerAngles.y * UnityEngine.Mathf.Deg2Rad;
  float ix = UnityEngine.Mathf.Sin(yaw), iz = UnityEngine.Mathf.Cos(yaw);
  UnityEngine.Vector3 p = tr.position;
  float cx = p.x - ix * 15f, cy = p.y + 2.2f, cz = p.z - iz * 15f;
  float lx = p.x + ix * 6f, ly = p.y + 1.0f, lz = p.z + iz * 6f;
  object r1 = mi.Invoke(null, new object[] { names[k] + "_gate", cx, cy, cz, lx, ly, lz, 40f, false });
  float ax = p.x - ix * 20f, ay = p.y + 34f, az = p.z - iz * 20f;
  object r2 = mi.Invoke(null, new object[] { names[k] + "_air", ax, ay, az, p.x, p.y + 1f, p.z, 40f, false });
  sb.Append("\n").Append(names[k]).Append(" gate=").Append(r1).Append(" air=").Append(r2);
}
return sb.ToString();
