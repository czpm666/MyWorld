var t = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
if (t == null) { foreach (var a in System.AppDomain.CurrentDomain.GetAssemblies()) { t = a.GetType("MyWorldProbes.ZzKingdomShots"); if (t != null) break; } }
var mi = t.GetMethod("Shoot", new System.Type[] { typeof(string), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
var sb = new System.Text.StringBuilder();

// sun from the south-east -> camera sits north-west of the subject so facades are lit
float[] tx = new float[] { 267.73f, -511.91f, -268.67f };
float[] ty = new float[] { 19.25f, -0.03f, 37.44f };
float[] tz = new float[] { 1195.61f, 162.64f, -1199.80f };
string[] nm = new string[] { "v2_farm23", "v2_port4", "v2_mine29" };

for (int i = 0; i < tx.Length; i++)
{
    sb.AppendLine(mi.Invoke(null, new object[] { nm[i], tx[i] - 44f, ty[i] + 33f, tz[i] - 44f, tx[i], ty[i] + 2.2f, tz[i], 42f, false }).ToString());
}

// street level at the mine gate (entrance faces the capital)
float len = (float)System.Math.Sqrt(1199.80f * 1199.80f + 268.67f * 268.67f);
float ux = 268.67f / len, uz = 1199.80f / len;
float gx = -268.67f + ux * 36f, gz = -1199.80f + uz * 36f;
sb.AppendLine(mi.Invoke(null, new object[] { "v2_mine29_gate", gx + ux * 14f, 37.44f + 2.2f, gz + uz * 14f, gx, 37.44f + 3.4f, gz, 40f, false }).ToString());
return sb.ToString();