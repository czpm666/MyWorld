var go = UnityEngine.GameObject.Find("Towns");
UnityEngine.Vector3 p = UnityEngine.Vector3.zero; string nm = "";
foreach (UnityEngine.Transform t in go.transform) { if (t.name.StartsWith("farm_a")) { p = t.position; nm = t.name; break; } }
var ty = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
var mi = ty.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
object r = mi.Invoke(null, new object[] { "dbg_top_" + nm, p.x + 0.01f, p.y + 95f, p.z, p.x, p.y, p.z, 45f, false });
return nm + " " + r;
