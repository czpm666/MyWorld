var t = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
if (t == null) { foreach (var a in System.AppDomain.CurrentDomain.GetAssemblies()) { t = a.GetType("MyWorldProbes.ZzKingdomShots"); if (t != null) break; } }
var mi = t.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
var sb = new System.Text.StringBuilder();

// sun comes from south-east: put camera to the north-west so facades are lit
float[] tx = new float[] { 267.73f, -511.91f, -268.67f, 821.81f };
float[] ty = new float[] { 19.25f, -0.03f, 37.44f, 23.84f };
float[] tz = new float[] { 1195.61f, 162.64f, -1199.80f, 893.03f };
string[] nm = new string[] { "lit_farm23", "lit_port4", "lit_mine29", "lit_farm22" };

for (int i = 0; i < tx.Length; i++)
{
    sb.AppendLine(mi.Invoke(null, new object[] { nm[i], tx[i] - 44f, ty[i] + 33f, tz[i] - 44f, tx[i], ty[i] + 2.2f, tz[i], 42f, false }).ToString());
}
return sb.ToString();