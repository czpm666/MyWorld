var p = "Assets/Generated/KingdomKit/farm/Prefabs/farm_a.prefab";
var go = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(p);
var sb = new System.Text.StringBuilder();
if (go == null) return "MISS";
sb.AppendLine("root localPos=" + go.transform.localPosition.ToString("F2") + " rot=" + go.transform.localEulerAngles.ToString("F1") + " scale=" + go.transform.localScale.ToString("F2"));
var all = go.GetComponentsInChildren<UnityEngine.Transform>(true);
int shown = 0;
foreach (var tr in all)
{
    string n = tr.name.ToLower();
    if (n.Contains("windmill") || n.Contains("barn") || n.Contains("well"))
    {
        if (shown++ > 12) break;
        var mf = tr.GetComponent<UnityEngine.MeshFilter>();
        string vs = "-";
        if (mf != null && mf.sharedMesh != null) vs = mf.sharedMesh.vertexCount.ToString();
        sb.AppendLine("  " + tr.name + " local=" + tr.localPosition.ToString("F2") + " world=" + tr.position.ToString("F1") + " rotY=" + tr.localEulerAngles.y.ToString("F0") + " verts=" + vs);
    }
}
return sb.ToString();
