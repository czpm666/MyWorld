using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 把 MyWorldBootstrap 在编辑期生成的对象"烘焙"成场景里的真实内容。
    ///
    /// 为什么必须做这一步：生成器用的是 `new Material(...)` / `new Texture2D(...)`，
    /// 这些是**内存对象、不是资源**。场景文件存不下对非资源对象的引用，
    /// 直接保存的话材质引用会变成 Missing。所以要把它们落成 Assets 下的资源再重新指回去。
    /// </summary>
    public static class MyWorldBaker
    {
        private const string GeneratedFolder = "Assets/Generated";
        private const string MaterialFolder = GeneratedFolder + "/Materials";
        private const string TextureFolder = GeneratedFolder + "/Textures";
        private const string VolumeFolder = GeneratedFolder + "/PostFx";
        private const string ProfilePath = VolumeFolder + "/DioramaProfile.asset";

        /// <summary>
        /// 清掉旧内容 → 重新生成 → 把贴图/材质/后处理写成资源 → 贴回场景。
        ///
        /// 顺序很重要：**必须先烘焙贴图、再烘焙材质**。因为 Unity 无法把"对非资源对象"的引用
        /// 存进资源文件（会写成 fileID: 0，也就是引用直接丢失）。
        /// 如果先生成材质资源，它引用的还是内存里的贴图，存下来就是空的。
        /// </summary>
        public static void Bake(MyWorldBootstrap bootstrap)
        {
            if (bootstrap == null)
            {
                Debug.LogError("[My World] 烘焙失败：场景里找不到 MyWorldBootstrap。");
                return;
            }

            EnsureFolders();

            AssignCharacterPrefab(bootstrap);

            bootstrap.ClearGenerated();
            bootstrap.BuildAll();

            int texs = BakeTextures();
            int mats = BakeMaterials();
            BakeVolumeProfile();

            Debug.Log($"[My World] 烘焙完成：贴图 {texs} 张、材质资源 {mats} 个、后处理 Profile 1 个。");
        }

        /// <summary>
        /// 把法师预制体的引用写进 bootstrap。放在代码里而不是让人手拖，
        /// 是为了让"生成世界场景"这一步永远能自洽跑通。
        /// </summary>
        private static void AssignCharacterPrefab(MyWorldBootstrap bootstrap)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(MageSetup.PrefabPath);
            if (prefab == null)
            {
                Debug.LogWarning($"[My World] 没找到 {MageSetup.PrefabPath}，" +
                                 "玩家会用占位胶囊。先跑一次 Tools → My World → 安装法师角色。");
                return;
            }

            var so = new SerializedObject(bootstrap);
            SetRef(so, "characterPrefab", prefab);

            SetRef(so, "swordPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(WeaponSetup.SwordPrefab));
            SetRef(so, "staffPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(WeaponSetup.StaffPrefab));
            SetRef(so, "bowPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(WeaponSetup.BowPrefab));
            SetRef(so, "shieldPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(WeaponSetup.ShieldPrefab));
            SetRef(so, "ropeGunPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(WeaponSetup.RopeGunPrefab));
            SetRef(so, "gauntletPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(WeaponSetup.GauntletPrefab));
            SetRef(so, "enemyPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(EnemySetup.PrefabPath));

            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void SetRef(SerializedObject so, string field, Object value)
        {
            var prop = so.FindProperty(field);
            if (prop != null) prop.objectReferenceValue = value;
        }

        // ---------------- 材质 ----------------

        /// <summary>
        /// 把世界里所有渲染器用到的材质实例（去重后）各存成一个资源，再让渲染器指向资源。
        /// 去重是按"原材质实例"做的，所以生成器里共用的材质（比如所有墙共用一个 stoneMat）
        /// 只会产出一个资源文件。
        /// </summary>
        private static int BakeMaterials()
        {
            var remap = new Dictionary<Material, Material>();
            var usedNames = new HashSet<string>();

            foreach (var r in CollectRenderers())
            {
                var src = r.sharedMaterial;
                if (src == null) continue;

                if (!remap.TryGetValue(src, out var asset))
                {
                    // 已经是资源（比如武器材质）就别再复制一份，否则会在 Generated 里堆出重复材质。
                    if (!string.IsNullOrEmpty(AssetDatabase.GetAssetPath(src)))
                    {
                        remap[src] = src;
                        continue;
                    }
                    asset = new Material(src) { name = UniqueName(src.name, usedNames) };
                    AssetDatabase.CreateAsset(asset, $"{MaterialFolder}/{asset.name}.mat");
                    remap[src] = asset;
                }
                r.sharedMaterial = asset;
            }

            return remap.Count;
        }

        // ---------------- 贴图 ----------------

        /// <summary>
        /// 把材质里引用的"运行时生成的内存贴图"写成 PNG 资源。目前只有地面那张方格贴图。
        /// 走 PNG + 重新导入（而不是 CreateAsset）是为了拿到正常的 TextureImporter，
        /// 能正确设置 Repeat / mipmap / 各项异性过滤，否则贴图缩放时会有接缝和摩尔纹。
        /// </summary>
        private static int BakeTextures()
        {
            var remap = new Dictionary<Texture, Texture>();
            var usedNames = new HashSet<string>();

            foreach (var r in CollectRenderers())
            {
                var mat = r.sharedMaterial;
                if (mat == null || !mat.HasProperty("_BaseMap")) continue;

                var tex = mat.GetTexture("_BaseMap");
                // 已经是资源的（比如包内置贴图）不用动；只处理内存里 new 出来的。
                if (tex == null || !string.IsNullOrEmpty(AssetDatabase.GetAssetPath(tex))) continue;

                if (!remap.TryGetValue(tex, out var asset))
                {
                    string name = UniqueName(string.IsNullOrWhiteSpace(tex.name) ? "Tex" : tex.name, usedNames);
                    string path = $"{TextureFolder}/{name}.png";

                    var src = tex as Texture2D;
                    if (src == null) continue;

                    File.WriteAllBytes(path, src.EncodeToPNG());
                    AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);

                    var importer = AssetImporter.GetAtPath(path) as TextureImporter;
                    if (importer != null)
                    {
                        importer.wrapMode = TextureWrapMode.Repeat;
                        importer.filterMode = FilterMode.Bilinear;
                        importer.mipmapEnabled = true;
                        importer.anisoLevel = 4;
                        importer.SaveAndReimport();
                    }

                    asset = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                    remap[tex] = asset;
                }

                // 此刻改的还是内存材质，等 BakeMaterials 复制它时就会带上资源引用。
                mat.SetTexture("_BaseMap", asset);
                EditorUtility.SetDirty(mat);
            }

            return remap.Count;
        }

        // ---------------- 后处理 Profile ----------------

        /// <summary>
        /// 把 DioramaPostFx 的临时 Profile 参数固化成一个资源并挂回去。
        /// 挂上资源后，DioramaPostFx.Start 会检测到 sharedProfile 已存在而不再另建一份。
        /// </summary>
        private static void BakeVolumeProfile()
        {
            var fx = Object.FindFirstObjectByType<DioramaPostFx>();
            if (fx == null) return;

            var volume = fx.GetComponent<Volume>();
            if (volume == null) return;

            AssetDatabase.DeleteAsset(ProfilePath);

            var asset = ScriptableObject.CreateInstance<VolumeProfile>();
            asset.name = "DioramaProfile";
            AssetDatabase.CreateAsset(asset, ProfilePath);

            // 用和运行时同一份构建逻辑填参数，避免两边默认值漂移。
            fx.PopulateProfile(asset);

            // 把子组件也写成子资源，Profile 才能完整保存。
            foreach (var c in asset.components)
            {
                if (c == null) continue;
                c.hideFlags = HideFlags.HideInHierarchy;
                AssetDatabase.AddObjectToAsset(c, asset);
            }

            EditorUtility.SetDirty(asset);
            AssetDatabase.SaveAssets();

            // 丢掉 Volume 可能已经缓存的内部副本，改指向资源。
            volume.profile = null;
            volume.sharedProfile = asset;
            EditorUtility.SetDirty(volume);
        }

        // ---------------- 辅助 ----------------

        private static IEnumerable<Renderer> CollectRenderers()
        {
            foreach (string rootName in MyWorldBootstrap.GeneratedRootNames)
            {
                var go = GameObject.Find(rootName);
                if (go == null) continue;
                foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                    yield return r;
            }
        }

        /// <summary>资源文件名不能重名，重名会让后写入的覆盖前面那个。</summary>
        private static string UniqueName(string baseName, HashSet<string> used)
        {
            if (string.IsNullOrWhiteSpace(baseName)) baseName = "Unnamed";

            // 去掉文件名非法字符，避免 CreateAsset 报错。
            foreach (char bad in System.IO.Path.GetInvalidFileNameChars())
                baseName = baseName.Replace(bad, '_');

            string name = baseName;
            int i = 1;
            while (!used.Add(name)) name = $"{baseName}_{i++}";
            return name;
        }

        private static void EnsureFolders()
        {
            EnsureFolderChain(GeneratedFolder, "Assets", "Generated");
            EnsureFolderChain(MaterialFolder, GeneratedFolder, "Materials");
            EnsureFolderChain(TextureFolder, GeneratedFolder, "Textures");
            EnsureFolderChain(VolumeFolder, GeneratedFolder, "PostFx");
        }

        private static void EnsureFolderChain(string full, string parent, string leaf)
        {
            if (!AssetDatabase.IsValidFolder(full))
                AssetDatabase.CreateFolder(parent, leaf);
        }
    }
}
