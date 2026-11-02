#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// T-091：把 KayKit 冒险者包里的三套贴图做成**可切换外观**（零重定向、零新模型）。
    ///
    /// **为什么这条路是对的**（实测支撑，别再猜）：
    /// 1. `mage_texture.png` / `knight_texture.png` / `rogue_texture.png` 都是 **1024×1024**，
    ///    逐像素比较「图集未占用区」掩码一致度 **99.5%** → 三套贴图共用同一套 UV 布局。
    /// 2. 同机位离屏渲染（`WorkQC/appearance_render_compare.png`）里三个人形完整：
    ///    脸、精灵耳、法袍、腰带扣、护腕、靴子都在正确位置，只有配色/发色不同，无拉伸错位。
    /// 3. 三张图在工程里**原本零引用**（只有 `mage_texture` 被 `M_Mage.mat` 用到）——
    ///    也就是说「更丰富的人物外观」这个诉求，素材早就在盘上，只是没人接。
    ///
    /// **为什么不新增模型**：KayKit 的 knight/rogue 是**独立 FBX + 各自的骨骼**，
    /// 换模型要重做动画重定向、要和 26 个状态对齐 → 风险远大于收益；
    /// 而换贴图**一个材质都不用重定向**，动画/控制器/碰撞完全不受影响。
    ///
    /// ⚠️ 输出放 `Resources/Appearance/` 是为了让运行时 `PlayerAppearance` 能用
    ///    `Resources.Load` 取到（材质引用的贴图仍按 GUID 走，不必进 Resources）。
    /// </summary>
    public static class AppearanceSetup
    {
        private const string KitDir = "Assets/ThirdParty/KayKit_Adventurers";
        private const string BaseMatPath = KitDir + "/M_Mage.mat";
        private const string OutDir = "Assets/Scripts/MyWorld/Animation/Resources/Appearance";

        /// <summary>变体名 —— 必须与 `MyWorld.PlayerAppearance` 里的名字表逐字一致。</summary>
        private static readonly string[] Variants = { "M_Knight", "M_Rogue" };
        /// <summary>对应贴图（与 <see cref="Variants"/> 同下标）。</summary>
        private static readonly string[] Textures = { "knight_texture.png", "rogue_texture.png" };

        [MenuItem("Tools/My World/生成外观材质（骑士 · 游侠）", priority = 32)]
        public static void Generate()
        {
            var baseMat = AssetDatabase.LoadAssetAtPath<Material>(BaseMatPath);
            if (baseMat == null)
            {
                Debug.LogError("[外观] 找不到 " + BaseMatPath + "，先把法师角色装好（Tools > My World/安装法师角色）。");
                return;
            }

            EnsureFolder();

            for (int i = 0; i < Variants.Length; i++)
            {
                string texPath = KitDir + "/" + Textures[i];
                var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
                if (tex == null)
                {
                    Debug.LogWarning("[外观] 缺贴图 " + texPath + "，跳过 " + Variants[i] + "。");
                    continue;
                }

                string path = OutDir + "/" + Variants[i] + ".mat";
                var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (existing == null)
                {
                    // 用基材复制：shader / 关键字 / 其余属性全部继承，只换 `_BaseMap`。
                    var mat = new Material(baseMat);
                    mat.SetTexture("_BaseMap", tex);
                    mat.SetTexture("_MainTex", tex);   // 老的内置管线属性名，一起写上不吃亏
                    AssetDatabase.CreateAsset(mat, path);
                }
                else
                {
                    // 幂等：已存在就只刷贴图，不重建资产（重建会让引用它的地方丢引用）。
                    existing.SetTexture("_BaseMap", tex);
                    existing.SetTexture("_MainTex", tex);
                    EditorUtility.SetDirty(existing);
                }
                Debug.Log("[外观] " + Variants[i] + " → " + path + "（贴图 " + Textures[i] + "）");
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("[外观] 完成。运行时用 PlayerAppearance.Apply(1/2) 切换；入口 UI 由 Lead 统一安排。");
        }

        private static void EnsureFolder()
        {
            if (AssetDatabase.IsValidFolder(OutDir)) return;
            string parent = Path.GetDirectoryName(OutDir).Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(OutDir));
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }
    }
}
#endif
