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

float tx = -268.7f, ty = 37.4f, tz = -1199.8f;
float len = (float)System.Math.Sqrt(tx * tx + tz * tz);
float ux = -tx / len, uz = -tz / len;
float gx = tx + ux * 36f, gz = tz + uz * 36f;
sb.AppendLine(mi.Invoke(null, new object[] { "t29_gate", gx + ux * 16f, ty + 1.8f, gz + uz * 16f, gx, ty + 2.2f, gz, 38f, false }).ToString());
sb.AppendLine(mi.Invoke(null, new object[] { "t29_player", tx + 2f, ty + 13.5f, tz + 17.3f, tx, ty + 0.5f, tz, 32f, false }).ToString());
sb.AppendLine(mi.Invoke(null, new object[] { "t29_aerial", tx + 55f, ty + 70f, tz + 55f, tx, ty + 1f, tz, 40f, false }).ToString());
return sb.ToString();