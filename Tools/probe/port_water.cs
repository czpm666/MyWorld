var sb = new System.Text.StringBuilder();
var go = GameObject.Find("port_a_19");
if (go == null) return "not found";
var rs = go.GetComponentsInChildren<MeshRenderer>(true);
foreach (var r in rs)
{
    var mats = r.sharedMaterials;
    for (int i = 0; i < mats.Length; i++)
    {
        if (mats[i] == null) continue;
        string n = mats[i].name.ToLower();
        if (n.Contains("water") || n.Contains("sea") || n.Contains("boat"))
        {
            var b = r.bounds;
            sb.AppendLine(mats[i].name + " center=" + b.center.ToString() + " size=" + b.size.ToString() + " localY=" + (b.center.y - go.transform.position.y).ToString("0.00"));
            break;
        }
    }
}
return sb.Length == 0 ? "no water material found" : sb.ToString();