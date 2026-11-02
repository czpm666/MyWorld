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

// 镇心坐标（KingdomWorldMap 实测打印），镇门朝王都 36 m。
float[] tx = new float[] { -511.9f, 3.8f, -3.6f };
float[] ty = new float[] { 0f, 6.4f, 2.8f };
float[] tz = new float[] { 162.6f, -584f, 557.3f };
string[] nm = new string[] { "t04", "t07", "t02" };

for (int i = 0; i < tx.Length; i++)
{
    float len = (float)System.Math.Sqrt(tx[i] * tx[i] + tz[i] * tz[i]);
    float ux = -tx[i] / len, uz = -tz[i] / len;      // 镇 -> 王都
    float gx = tx[i] + ux * 36f, gz = tz[i] + uz * 36f;
    // 门外 18 m、高 1.8 m，看门洞（略高 2.0 m）
    float cx = gx + ux * 18f, cz = gz + uz * 18f;
    var r = mi.Invoke(null, new object[] { "new_" + nm[i] + "_gate", cx, ty[i] + 1.8f, cz, gx, ty[i] + 2.0f, gz, 38f, false });
    sb.AppendLine(r.ToString());
    // 斜看全村
    r = mi.Invoke(null, new object[] { "new_" + nm[i] + "_aerial", tx[i] + 62f, ty[i] + 74f, tz[i] + 62f, tx[i], ty[i] + 1f, tz[i], 40f, false });
    sb.AppendLine(r.ToString());
}
return sb.ToString();