var go = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Generated/KingdomKit/port/Prefabs/port_a.prefab");
if (go == null) return "NO_PREFAB";
var mfs = go.GetComponentsInChildren<UnityEngine.MeshRenderer>(true);
var sb = new System.Text.StringBuilder();
foreach (var mr in mfs) {
  var mf = mr.GetComponent<UnityEngine.MeshFilter>();
  if (mf == null || mf.sharedMesh == null) continue;
  string names = "";
  bool isWater = false;
  foreach (var mm in mr.sharedMaterials) { if (mm == null) continue; names += mm.name + ","; if (mm.name.ToLower().Contains("water")) isWater = true; }
  if (!isWater) continue;
  float minx = 99999f, miny = 99999f, minz = 99999f, maxx = -99999f, maxy = -99999f, maxz = -99999f;
  var vs = mf.sharedMesh.vertices;
  var t = mf.transform;
  for (int i = 0; i < vs.Length; i++) {
    var w = t.TransformPoint(vs[i]);
    if (w.x < minx) minx = w.x; if (w.x > maxx) maxx = w.x;
    if (w.y < miny) miny = w.y; if (w.y > maxy) maxy = w.y;
    if (w.z < minz) minz = w.z; if (w.z > maxz) maxz = w.z;
  }
  sb.Append("\n").Append(mr.name).Append(" mats=").Append(names).Append(" v=").Append(vs.Length)
    .Append(" x[").Append(minx.ToString("F2")).Append(",").Append(maxx.ToString("F2")).Append("]")
    .Append(" y[").Append(miny.ToString("F2")).Append(",").Append(maxy.ToString("F2")).Append("]")
    .Append(" z[").Append(minz.ToString("F2")).Append(",").Append(maxz.ToString("F2")).Append("]");
}
return sb.ToString();
