var go = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Generated/KingdomKit/port/Prefabs/port_a.prefab");
if (go == null) return "NO_PREFAB";
var mfs = go.GetComponentsInChildren<UnityEngine.MeshRenderer>(true);
int tris = 0;
var sb = new System.Text.StringBuilder();
sb.Append("renderers=").Append(mfs.Length);
float minx = 99999f, miny = 99999f, minz = 99999f, maxx = -99999f, maxy = -99999f, maxz = -99999f;
foreach (var mr in mfs) {
  var mf = mr.GetComponent<UnityEngine.MeshFilter>();
  if (mf == null || mf.sharedMesh == null) continue;
  tris += mf.sharedMesh.triangles.Length / 3;
  var vs = mf.sharedMesh.vertices;
  var t = mf.transform;
  for (int i = 0; i < vs.Length; i++) {
    var w = t.TransformPoint(vs[i]);
    if (w.x < minx) minx = w.x; if (w.x > maxx) maxx = w.x;
    if (w.y < miny) miny = w.y; if (w.y > maxy) maxy = w.y;
    if (w.z < minz) minz = w.z; if (w.z > maxz) maxz = w.z;
  }
  foreach (var mm in mr.sharedMaterials) {
    if (mm == null) continue;
    string nm = mm.name.ToLower();
    if (nm.Contains("water") || nm.Contains("sea") || nm.Contains("bay"))
      sb.Append(" |WATER ").Append(mm.name).Append(" shader=").Append(mm.shader.name);
  }
}
sb.Append(" tris=").Append(tris);
sb.Append(" bbox=[").Append(minx.ToString("F2")).Append(",").Append(miny.ToString("F2")).Append(",").Append(minz.ToString("F2")).Append("]..[")
  .Append(maxx.ToString("F2")).Append(",").Append(maxy.ToString("F2")).Append(",").Append(maxz.ToString("F2")).Append("]");
return sb.ToString();
