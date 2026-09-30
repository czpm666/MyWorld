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
            AssignMapSize(bootstrap);

            bootstrap.ClearGenerated();
            bootstrap.BuildAll();

            int texs = BakeTextures();
            int mats = BakeMaterials();
            BakeVolumeProfile();

            // T-077：**音效槽必须由生成器写**（理由见 AssignGameAudio 的注释）——
            // 顺序放在最后：此时 Player 已经重建完，拿到的就是新的 GameAudio 组件。
            AssignGameAudio();

            Debug.Log($"[My World] 烘焙完成：贴图 {texs} 张、材质资源 {mats} 个、后处理 Profile 1 个。");
        }

        // ---------------- 音效槽（T-077：生成器产出） ----------------

        /// <summary>槽位字段名（顺序 = `GameAudio` 里的 5 个 SerializeField）。</summary>
        private static readonly string[] AudioSlotFields =
        {
            "swingClip", "hitClip", "bowShotClip", "castClip", "hurtClip"
        };

        /// <summary>对应素材路径（工程内命名惯例 `sfx_<用途>_<源文件名>`）。</summary>
        private static readonly string[] AudioSlotPaths =
        {
            "Assets/Audio/sfx_swing_swish-9.wav",
            "Assets/Audio/sfx_hit_bfh1_hit_04.ogg",
            "Assets/Audio/sfx_bow_Bow.wav",
            "Assets/Audio/sfx_cast_spell_01.ogg",
            "Assets/Audio/sfx_hurt_playerhit_0.mp3",
        };

        /// <summary>
        /// 🔴 T-077：把 5 个音效槽**由生成器写入**。
        ///
        /// **为什么必须在这里（而不是手工在 Inspector 上挂）**：
        /// 场景里的 `GameAudio` 是 `MyWorldBootstrap.BuildPlayer()` 里 `AddComponent` 出来的
        /// → **一次"重建世界内容"就会新建组件、5 个槽全为 null**。
        /// 而播放路径是 `clip != null` 才播（设计如此：空槽静默跳过）→
        /// **已经验收过的音效会静默消失，且没有任何报错**。
        ///
        /// 实证（`docs/artifacts/T-077/snapshot_before.txt`，字段级快照）：
        ///   `Player|GameAudio|swingClip|Assets/Audio/sfx_swing_swish-9.wav#...` （带 GUID）
        ///   而 `Player|GameAudio|bowShotClip|<null>`、`|castClip|<null>`
        /// → **那三个已装音效只活在场景实例里**，正是"重建即丢"的形状。
        ///
        /// ⭐ **这是本工程的一条通用模式，请照此办理**：
        /// **凡是"挂在 prefab/场景上的引用"（音效槽、图标 sprite、武器 mount、controller…），
        /// 只要那个宿主是生成器建出来的，赋值就必须由生成器写。**
        /// </summary>
        private static void AssignGameAudio()
        {
            var player = GameObject.Find("Player");
            if (player == null) { Debug.LogWarning("[My World] 音效槽赋值：找不到 Player"); return; }

            var ga = player.GetComponent<GameAudio>();
            if (ga == null) { Debug.LogWarning("[My World] 音效槽赋值：Player 上没有 GameAudio"); return; }

            var so = new SerializedObject(ga);
            int ok = 0;
            for (int i = 0; i < AudioSlotFields.Length; i++)
            {
                var clip = AssetDatabase.LoadAssetAtPath<AudioClip>(AudioSlotPaths[i]);
                if (clip == null)
                {
                    Debug.LogWarning($"[My World] 音效槽 '{AudioSlotFields[i]}' 的素材没找到：{AudioSlotPaths[i]}"
                                     + "（该槽保持为空 —— 空槽是设计允许的）");
                    continue;
                }
                var prop = so.FindProperty(AudioSlotFields[i]);
                if (prop == null)
                {
                    Debug.LogWarning($"[My World] GameAudio 里没有字段 '{AudioSlotFields[i]}'（字段名改了？）");
                    continue;
                }
                prop.objectReferenceValue = clip;
                ok++;
            }
            so.ApplyModifiedPropertiesWithoutUndo();
            Debug.Log($"[My World] 音效槽由生成器赋值：{ok}/{AudioSlotFields.Length} 个");
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

        /// <summary>
        /// 🔴 T-077 地图 B：把**地图尺寸与出生点**写进 bootstrap 的序列化字段。
        ///
        /// **为什么必须在这里写**（本次实测差点踩到的坑）：
        /// `playAreaSize` / `groundSize` / `playerStart` 都是 `[SerializeField]`
        /// → **场景文件里存着它们的值**。实测 `Assets/Scenes/MyWorld.unity`：
        ///   `playAreaSize: 56` ／ `groundSize: 96` ／ `playerStart: {x: 0, y: 0.2, z: -12}`
        /// → **只改 C# 的字段初始化器不会生效**：场景里的旧值会继续被拿去生成世界，
        ///   而且**没有任何报错、没有任何提示**。（与"改数值必须重建世界"是同一类陷阱的反向形态。）
        ///
        /// → 与 `AssignCharacterPrefab` 同一类处理：**由烘焙器写序列化字段**，
        ///   这样"代码里写的口径"与"场景实际用的值"不会再分叉。
        /// </summary>
        private static void AssignMapSize(MyWorldBootstrap bootstrap)
        {
            var so = new SerializedObject(bootstrap);
            var pArea = so.FindProperty("playAreaSize");
            var pGround = so.FindProperty("groundSize");
            var pStart = so.FindProperty("playerStart");

            // 口径 B（面积 ×3，用户裁定）：边长 ×√3 = 56 × 1.732142857 ≈ 96.99 → 取 97
            if (pArea != null) pArea.floatValue = 97f;
            // 必须是 `gridCellSize * 8 = 16` 的整数倍，否则地面格子边缘会截半格 → 144 = 16 × 9
            if (pGround != null) pGround.floatValue = 144f;
            // 出生点**跟着一起缩**（统一缩放才保住点位之间的相对关系，理由见 ContentScale 注释）
            if (pStart != null) pStart.vector3Value = new Vector3(0f, 0.2f, -12f * 1.732142857f);

            so.ApplyModifiedPropertiesWithoutUndo();
            Debug.Log($"[My World] 地图尺寸由烘焙器写入：playAreaSize={pArea.floatValue}"
                      + $" groundSize={pGround.floatValue} playerStart={pStart.vector3Value}");
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
