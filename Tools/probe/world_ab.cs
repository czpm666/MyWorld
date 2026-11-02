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

float tx = -511.9f, tz = 162.6f;
var sun = UnityEngine.Object.FindFirstObjectByType<UnityEngine.Light>();
sb.AppendLine("sun0=" + sun.intensity.ToString("0.00"));
sb.AppendLine(mi.Invoke(null, new object[] { "wtest_a", tx + 78f, 96f, tz + 78f, tx, 2f, tz, 40f, false }).ToString());

sun.intensity = 3.0f;
var a0 = UnityEngine.RenderSettings.ambientSkyColor; UnityEngine.RenderSettings.ambientSkyColor = new UnityEngine.Color(a0.r * 1.8f, a0.g * 1.8f, a0.b * 1.8f);
var a1 = UnityEngine.RenderSettings.ambientEquatorColor; UnityEngine.RenderSettings.ambientEquatorColor = new UnityEngine.Color(a1.r * 1.6f, a1.g * 1.6f, a1.b * 1.6f);
var a2 = UnityEngine.RenderSettings.ambientGroundColor; UnityEngine.RenderSettings.ambientGroundColor = new UnityEngine.Color(a2.r * 1.6f, a2.g * 1.6f, a2.b * 1.6f);
sb.AppendLine(mi.Invoke(null, new object[] { "wtest_b", tx + 78f, 96f, tz + 78f, tx, 2f, tz, 40f, false }).ToString());
return sb.ToString();
