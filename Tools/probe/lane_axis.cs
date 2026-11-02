var paths = new string[]{
  "Assets/Generated/KingdomKit/farm/Prefabs/farm_b.prefab",
  "Assets/Generated/KingdomKit/mine/Prefabs/mine_a.prefab",
  "Assets/Generated/KingdomKit/port/Prefabs/port_b.prefab"
};
var sb = new System.Text.StringBuilder();
foreach (var p in paths)
{
    var go = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(p);
    if (go == null) { sb.AppendLine("MISS " + p); continue; }
    var t = go.transform;
    sb.AppendLine("== " + p + " children=" + t.childCount);
    for (int i = 0; i < t.childCount; i++)
    {
        var c = t.GetChild(i);
        string n = c.name.ToLower();
        if (n.Contains("lane") || n.Contains("road") || n.Contains("plate") || n.Contains("apron") || n.Contains("street") || n.Contains("plaza"))
        {
            var mf = c.GetComponent<UnityEngine.MeshFilter>();
            if (mf != null && mf.sharedMesh != null)
            {
                var b = mf.sharedMesh.bounds;
                sb.AppendLine("  " + c.name + " n=" + mf.sharedMesh.name + " center=" + b.center.ToString("F1") + " size=" + b.size.ToString("F1"));
            }
            else sb.AppendLine("  " + c.name + " (no mesh)");
        }
    }
}
return sb.ToString();
