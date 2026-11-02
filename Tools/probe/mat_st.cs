var m = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Material>("Assets/Generated/KingdomKit/mine/M_tile_3.mat");
if (m == null) m = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Material>("Assets/Generated/KingdomKit/mine/mine_a/M_tile_3.mat");
if (m == null) {
  var guids = UnityEditor.AssetDatabase.FindAssets("M_tile_3 t:Material");
  if (guids.Length == 0) return "NO_MAT";
  m = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Material>(UnityEditor.AssetDatabase.GUIDToAssetPath(guids[0]));
}
var sb = new System.Text.StringBuilder();
sb.Append(m.name).Append(" sh=").Append(m.shader.name);
sb.Append(" st=").Append(m.GetVector("_BaseMap_ST").ToString("F3"));
sb.Append(" detailStrength=").Append(m.GetFloat("_DetailStrength").ToString("F2"));
sb.Append(" detailGain=").Append(m.GetFloat("_DetailGain").ToString("F2"));
sb.Append(" mean=").Append(m.GetFloat("_DetailMean").ToString("F3"));
sb.Append(" bump=").Append(m.GetFloat("_BumpScale").ToString("F2"));
sb.Append(" tex=").Append(m.GetTexture("_BaseMap") != null ? m.GetTexture("_BaseMap").name : "none");
var g2 = UnityEditor.AssetDatabase.FindAssets("M_plaster_5 t:Material");
if (g2.Length > 0) {
  var m2 = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Material>(UnityEditor.AssetDatabase.GUIDToAssetPath(g2[0]));
  sb.Append("\n").Append(m2.name).Append(" st=").Append(m2.GetVector("_BaseMap_ST").ToString("F3")).Append(" tex=").Append(m2.GetTexture("_BaseMap") != null ? m2.GetTexture("_BaseMap").name : "none");
}
return sb.ToString();
