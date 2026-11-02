var t = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
if (t == null)
{
    foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
    {
        t = asm.GetType("MyWorldProbes.ZzKingdomShots");
        if (t != null) break;
    }
}
var mi = t.GetMethod("Shoot", new System.Type[] {
    typeof(string), typeof(float), typeof(float), typeof(float),
    typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
var sb = new System.Text.StringBuilder();

float[] tx = new float[] { -511.91f, 357.00f, -268.67f };
float[] ty = new float[] { -0.03f, -2.68f, 37.44f };
float[] tz = new float[] { 162.64f, -762.25f, -1199.80f };
string[] nm = new string[] { "p4", "p19", "m29" };

for (int i = 0; i < tx.Length; i++)
{
    float len = (float)System.Math.Sqrt(tx[i] * tx[i] + tz[i] * tz[i]);
    float ux = -tx[i] / len, uz = -tz[i] / len;
    float gx = tx[i] + ux * 36f, gz = tz[i] + uz * 36f;
    sb.AppendLine(mi.Invoke(null, new object[] { nm[i] + "_gate", gx + ux * 16f, ty[i] + 1.9f, gz + uz * 16f, gx, ty[i] + 2.4f, gz, 38f, false }).ToString());
    sb.AppendLine(mi.Invoke(null, new object[] { nm[i] + "_aerial", tx[i] + 55f, ty[i] + 66f, tz[i] + 55f, tx[i], ty[i] + 1f, tz[i], 40f, false }).ToString());
}
return sb.ToString();