var t = System.Type.GetType("MyWorldProbes.ZzKingdomShots, Assembly-CSharp-Editor");
if (t == null)
{
    foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
    {
        t = asm.GetType("MyWorldProbes.ZzKingdomShots");
        if (t != null) break;
    }
}
if (t == null) return "ZzKingdomShots not found";
var mi = t.GetMethod("Shoot", new System.Type[] {
    typeof(string), typeof(float), typeof(float), typeof(float),
    typeof(float), typeof(float), typeof(float), typeof(float), typeof(bool) });
if (mi == null) return "Shoot not found";

var sb = new System.Text.StringBuilder();

float tx = -511.9f, tz = 162.6f;
float gx = tx + 36f * 0.953f, gz = tz - 36f * 0.303f;

object[] a = new object[] { "world_town4_aerial", tx + 78f, 96f, tz + 78f, tx, 2f, tz, 40f, false };
object[] b = new object[] { "world_town4_gate", gx + 30f * 0.953f, 3.4f, gz - 30f * 0.303f, gx, 2.2f, gz, 38f, false };
object[] c = new object[] { "world_town4_wide", tx + 150f, 130f, tz + 60f, tx, 0f, tz, 42f, false };

foreach (object[] s in new object[][] { a, b, c })
{
    var r = mi.Invoke(null, s);
    sb.AppendLine(r == null ? "null" : r.ToString());
}
return sb.ToString();
