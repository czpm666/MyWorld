var go = GameObject.Find("farm_a_23");
if (go == null) return "no town";
var seen = new System.Collections.Generic.HashSet<string>();
var sb = new System.Text.StringBuilder();
foreach (var r in go.GetComponentsInChildren<MeshRenderer>(true))
{
    foreach (var m in r.sharedMaterials)
    {
        if (m == null || seen.Contains(m.name)) continue;
        seen.Add(m.name);
        string col = "-";
        if (m.HasProperty("_BaseColor")) { var c = m.GetColor("_BaseColor"); col = c.r.ToString("0.00") + "," + c.g.ToString("0.00") + "," + c.b.ToString("0.00"); }
        string tex = "-";
        if (m.HasProperty("_BaseMap")) { var tx = m.GetTexture("_BaseMap"); tex = tx == null ? "null" : tx.name; }
        string st = "-";
        if (m.HasProperty("_BaseMap")) { var sc = m.GetTextureScale("_BaseMap"); st = sc.x.ToString("0.0") + "x" + sc.y.ToString("0.0"); }
        string ds = "-";
        if (m.HasProperty("_DetailStrength")) ds = m.GetFloat("_DetailStrength").ToString("0.00");
        sb.AppendLine(m.name + " [" + m.shader.name + "] col=" + col + " tex=" + tex + " st=" + st + " ds=" + ds);
    }
}
return sb.ToString();