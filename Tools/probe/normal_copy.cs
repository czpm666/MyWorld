string[] stems = new string[] { "kit_cobble", "kit_stone_wall", "kit_blocks", "kit_plaster", "kit_roof_tile", "kit_planks", "kit_brick", "kit_thatch" };
var sb = new System.Text.StringBuilder();
foreach (var s in stems) {
  string src = "Assets/Art/Textures/" + s + "_n.png";
  string dst = "Assets/Resources/MapTextures/" + s + "_n.png";
  if (UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Texture2D>(src) == null) { sb.Append(s).Append("=nofile "); continue; }
  System.IO.File.Copy(src, dst, true);
  UnityEditor.AssetDatabase.ImportAsset(dst, UnityEditor.ImportAssetOptions.ForceUpdate);
  var ti = (UnityEditor.TextureImporter)UnityEditor.AssetImporter.GetAtPath(dst);
  if (ti == null) { sb.Append(s).Append("=noimporter "); continue; }
  ti.textureType = UnityEditor.TextureImporterType.NormalMap;
  ti.sRGBTexture = false;
  ti.wrapMode = UnityEngine.TextureWrapMode.Repeat;
  ti.anisoLevel = 8;
  ti.maxTextureSize = 1024;
  ti.SaveAndReimport();
  sb.Append(s).Append("=ok ");
}
return sb.ToString();
