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

UnityEngine.RenderSettings.fog = false;
sb.AppendLine("nofog " + mi.Invoke(null, new object[] { "wtest_nofog", tx + 78f, 96f, tz + 78f, tx, 2f, tz, 40f, false }).ToString());
UnityEngine.RenderSettings.fog = true;

var q = UnityEngine.QualitySettings.shadows;
UnityEngine.QualitySettings.shadows = UnityEngine.ShadowQuality.Disable;
sb.AppendLine("noshadow " + mi.Invoke(null, new object[] { "wtest_noshadow", tx + 78f, 96f, tz + 78f, tx, 2f, tz, 40f, false }).ToString());
UnityEngine.QualitySettings.shadows = q;

// close-up of the big white house wall
sb.AppendLine("close " + mi.Invoke(null, new object[] { "wtest_close", tx + 10f, 6f, tz + 40f, tx - 2f, 4f, tz + 26f, 45f, false }).ToString());
return sb.ToString();