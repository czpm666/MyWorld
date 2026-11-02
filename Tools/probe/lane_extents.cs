var paths = new string[]{
  "Assets/Generated/KingdomKit/farm/Prefabs/farm_a.prefab",
  "Assets/Generated/KingdomKit/farm/Prefabs/farm_b.prefab"
};
var sb = new System.Text.StringBuilder();
foreach (var p in paths)
{
    var go = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(p);
    if (go == null) { sb.AppendLine("MISS " + p); continue; }
    var t = go.transform;
    sb.AppendLine("== " + p);
    for (int i = 0; i < t.childCount; i++)
    {
        var c = t.GetChild(i);
        string n = c.name.ToLower();
        if (!(n.Contains("lane") || n.Contains("road") || n.Contains("plate") || n.Contains("ditch"))) continue;
        var mf = c.GetComponent<UnityEngine.MeshFilter>();
        if (mf == null || mf.sharedMesh == null) continue;
        var v = mf.sharedMesh.vertices;
        if (v.Length == 0) continue;
        var mn = v[0]; var mx = v[0];
        for (int k = 1; k < v.Length; k++) { mn = UnityEngine.Vector3.Min(mn, v[k]); mx = UnityEngine.Vector3.Max(mx, v[k]); }
        sb.AppendLine("  " + c.name + " verts=" + v.Length + " min=" + mn.ToString("F1") + " max=" + mx.ToString("F1"));
    }
}
return sb.ToString();
