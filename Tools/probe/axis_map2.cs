var p = "Assets/Generated/KingdomKit/farm/Prefabs/farm_a.prefab";
var go = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(p);
var sb = new System.Text.StringBuilder();
string[] want = { "farm_a_windmill", "farm_a_well", "farm_a_barn_a", "farm_a_barn_b" };
foreach (var w in want)
{
    var tr = go.transform.Find(w);
    if (tr == null) { sb.AppendLine(w + " missing"); continue; }
    var mf = tr.GetComponent<UnityEngine.MeshFilter>();
    var m = mf.sharedMesh;
    var v = m.vertices;
    if (v.Length == 0) { sb.AppendLine(w + " verts=0 readable=" + m.isReadable); continue; }
    float minx = v[0].x, miny = v[0].y, minz = v[0].z;
    float maxx = minx, maxy = miny, maxz = minz;
    double sx = 0, sy = 0, sz = 0;
    for (int i = 0; i < v.Length; i++)
    {
        float x = v[i].x, y = v[i].y, z = v[i].z;
        if (x < minx) minx = x; if (x > maxx) maxx = x;
        if (y < miny) miny = y; if (y > maxy) maxy = y;
        if (z < minz) minz = z; if (z > maxz) maxz = z;
        sx += x; sy += y; sz += z;
    }
    sb.AppendLine(w + " n=" + v.Length +
        " centroid=(" + (sx / v.Length).ToString("F1") + ", " + (sy / v.Length).ToString("F1") + ", " + (sz / v.Length).ToString("F1") + ")" +
        " min=(" + minx.ToString("F1") + ", " + miny.ToString("F1") + ", " + minz.ToString("F1") + ")" +
        " max=(" + maxx.ToString("F1") + ", " + maxy.ToString("F1") + ", " + maxz.ToString("F1") + ")");
}
return sb.ToString();
