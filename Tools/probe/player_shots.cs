var go = UnityEngine.GameObject.Find("Towns");
var ty = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
var mi = ty.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
var sb = new System.Text.StringBuilder();
int done = 0;
foreach (UnityEngine.Transform t in go.transform) {
  string n = t.name;
  if (!(n.StartsWith("farm_a_1") || n.StartsWith("port_a_4") || n.StartsWith("mine_a"))) continue;
  UnityEngine.Vector3 p = t.position;
  float yaw = t.eulerAngles.y * UnityEngine.Mathf.Deg2Rad;
  // 玩家视角：站在镇门口外侧，抬头 52 度俯视（与 TopDownCameraRig 一致）
  float fx = -UnityEngine.Mathf.Sin(yaw), fz = -UnityEngine.Mathf.Cos(yaw);
  float cx = p.x + fx * 33f, cy = p.y + 26f, cz = p.z + fz * 33f;
  object r = mi.Invoke(null, new object[] { "play_" + n, cx, cy, cz, p.x, p.y + 4f, p.z, 30f, false });
  sb.Append(n).Append(" ").Append(r).Append("\n");
  if (++done >= 3) break;
}
return sb.ToString();
