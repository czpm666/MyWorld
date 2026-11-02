var root = UnityEngine.GameObject.Find("Towns");
var tr = root.transform.Find("mine_a_29");
if (tr == null) return "NO_TOWN";
var ty = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
var mi = ty.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
UnityEngine.Vector3 p = tr.position;
object r1 = mi.Invoke(null, new object[] { "roof_close", p.x - 14f, p.y + 9f, p.z - 16f, p.x - 2f, p.y + 5f, p.z - 4f, 35f, false });
object r2 = mi.Invoke(null, new object[] { "wall_close", p.x + 9f, p.y + 3f, p.z - 9f, p.x + 2f, p.y + 3f, p.z + 2f, 40f, false });
return r1 + " || " + r2;
