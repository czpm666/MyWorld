var sb = new System.Text.StringBuilder();
var vols = UnityEngine.Object.FindObjectsByType<UnityEngine.Rendering.Volume>(UnityEngine.FindObjectsSortMode.None);
foreach (var v in vols)
{
    sb.AppendLine("VOLUME " + v.name + " isGlobal=" + v.isGlobal + " priority=" + v.priority + " weight=" + v.weight + " profile=" + (v.sharedProfile == null ? "none" : v.sharedProfile.name));
    if (v.sharedProfile == null) continue;
    var comps = v.sharedProfile.components;
    foreach (var c in comps)
    {
        string line = "  " + c.GetType().Name;
        var f = c.GetType().GetFields();
        foreach (var fi in f)
        {
            if (!fi.Name.StartsWith("m_")) continue;
            if (fi.Name == "m_OverrideState" || fi.Name == "m_List" || fi.Name == "m_Value" || fi.Name == "m_Parameter") { }
            try
            {
                var val = fi.GetValue(c);
                if (val != null && (val.GetType().Name.Contains("FloatParameter") || val.GetType().Name.Contains("ColorParameter") || val.GetType().Name.Contains("Vector2Parameter") || val.GetType().Name.Contains("BoolParameter")))
                {
                    var ov = val.GetType().GetProperty("overrideState").GetValue(val, null);
                    var vv = val.GetType().GetProperty("value").GetValue(val, null);
                    line += "\n    " + fi.Name + "=" + (vv == null ? "null" : vv.ToString()) + " override=" + ov;
                }
            }
            catch { }
        }
        sb.AppendLine(line);
    }
}
return sb.ToString();
