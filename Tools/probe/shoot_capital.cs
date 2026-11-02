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
if (mi == null) return "Shoot(float...) not found";
var sb = new System.Text.StringBuilder();
object[] shots = new object[][] {
    new object[] { "cap_new_paving", -2f, 4.2f, -240f, 3f, 0.4f, -212f, 40f, false },
    new object[] { "cap_new_street", 13f, 2.6f, -196f, -8f, 1.4f, -170f, 42f, false },
    new object[] { "cap_new_aerial", 70f, 95f, -186f, 0f, 0f, -120f, 45f, false }
};
foreach (object[] s in shots)
{
    var r = mi.Invoke(null, s);
    sb.AppendLine(r == null ? "null" : r.ToString());
}
return sb.ToString();
