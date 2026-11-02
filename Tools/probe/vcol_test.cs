var gm = GameObject.Find("GroundMesh");
var mf = gm.GetComponent<MeshFilter>();
var mesh = mf.sharedMesh;
var cols = mesh.colors;
for (int i = 0; i < cols.Length; i++) cols[i] = new Color(1f, 0.2f, 0.2f, 1f);
mesh.colors = cols;

var t = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
if (t == null) { foreach (var a in System.AppDomain.CurrentDomain.GetAssemblies()) { t = a.GetType("MyWorldProbes.ZzKingdomShots"); if (t != null) break; } }
var mi = t.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
return mi.Invoke(null, new object[] { "dbg_vcol", -511.91f - 44f, -0.03f + 33f, 162.64f - 44f, -511.91f, 2.2f, 162.64f, 42f, false }).ToString();