using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// KayKit 角色安装的共用工具。法师和蛮兵（敌人）的骨架是同一套，
    /// 导入器配置 / 抽动画剪辑 / 材质 / 打包预制体这些机械步骤完全一样，抽出来共用。
    ///
    /// 每个角色各自的动画状态机不在这里（法师要 Cast、蛮兵要 Attack，状态不一样）。
    /// </summary>
    public static class KayKitCharacter
    {
        /// <summary>要抽出来的剪辑：目标名 → (是否循环, 匹配关键词，先精确后模糊)。</summary>
        public struct ClipSpec
        {
            public string name;
            public bool loop;
            public string[] keys;

            public ClipSpec(string name, bool loop, params string[] keys)
            {
                this.name = name;
                this.loop = loop;
                this.keys = keys;
            }
        }

        /// <summary>
        /// 配置导入器。用 Generic 而不是 Humanoid：这套骨架的命名（.l/.r 后缀、单段手臂）
        /// 不符合 Unity Humanoid 映射要求，强行映射会失败；Generic 直接播原动画最稳。
        /// </summary>
        public static bool ConfigureImporter(string fbxPath)
        {
            var importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            if (importer == null)
            {
                Debug.LogError($"[My World] 找不到模型 {fbxPath}");
                return false;
            }

            importer.animationType = ModelImporterAnimationType.Generic;
            importer.importAnimation = true;
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            // 交付的 FBX 已是 Y-up、正面 +Z，不需要再烘轴转换（重复转换会让角色躺倒/转 90°）
            importer.bakeAxisConversion = false;
            importer.useFileScale = true;
            importer.globalScale = 1f;
            // 贴图用裸文件名引用，放同目录 + 全局搜索即可找到
            importer.materialSearch = ModelImporterMaterialSearch.Everywhere;
            importer.materialLocation = ModelImporterMaterialLocation.External;

            importer.SaveAndReimport();
            return true;
        }

        public static Texture2D LoadPointTexture(string path)
        {
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (tex == null) return null;

            var ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti != null)
            {
                // 低多边形色块贴图用点采样更"脆"，贴合这套美术
                ti.filterMode = FilterMode.Point;
                ti.mipmapEnabled = false;
                ti.SaveAndReimport();
            }
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        /// <summary>建一个 URP/Lit 材质**资源**（内存材质存不进预制体，会变 null）。</summary>
        public static Material MakeLitAsset(string path, Texture2D tex, float smoothness, string name)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");

            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            if (tex != null)
            {
                if (mat.HasProperty("_BaseMap")) mat.SetTexture("_BaseMap", tex);
                mat.mainTexture = tex;
                if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", Color.white);
                mat.color = Color.white;
            }
            mat.SetFloat("_Metallic", 0f);
            mat.SetFloat("_Smoothness", smoothness);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        public static List<AnimationClip> SourceClips(string fbxPath)
        {
            return AssetDatabase.LoadAllAssetsAtPath(fbxPath)
                .OfType<AnimationClip>()
                .Where(c => !c.name.StartsWith("__preview__"))
                .ToList();
        }

        /// <summary>
        /// 把需要的动画从 FBX 里复制成独立的 .anim 资源。
        /// 必须复制：FBX 内的剪辑是只读子资源，改不了"是否循环"，
        /// 否则 Idle/Walk 播一遍就停住，攻击/死亡又会鬼畜循环。
        /// </summary>
        public static Dictionary<string, AnimationClip> ExtractClips(
            string fbxPath, string clipDir, string rootFolder, ClipSpec[] wanted)
        {
            if (!AssetDatabase.IsValidFolder(clipDir))
                AssetDatabase.CreateFolder(rootFolder, "Clips");

            var src = SourceClips(fbxPath);
            var result = new Dictionary<string, AnimationClip>();

            foreach (var spec in wanted)
            {
                AnimationClip found = null;

                // 先要求完全同名：FBX 里有一堆 2H_Melee_Idle / Jump_Idle 之类，
                // 只按子串找会先撞上它们，把真正的 "Idle" 挤掉。
                foreach (var k in spec.keys)
                {
                    found = src.FirstOrDefault(c => string.Equals(c.name, k, System.StringComparison.OrdinalIgnoreCase));
                    if (found != null) break;
                }
                if (found == null)
                {
                    foreach (var k in spec.keys)
                    {
                        found = src.FirstOrDefault(c => c.name.IndexOf(k, System.StringComparison.OrdinalIgnoreCase) >= 0);
                        if (found != null) break;
                    }
                }

                if (found == null)
                {
                    Debug.LogWarning($"[My World] 没找到动画 '{spec.name}'（关键词 {string.Join("/", spec.keys)}）");
                    continue;
                }

                string path = $"{clipDir}/{spec.name}.anim";
                AssetDatabase.DeleteAsset(path);

                var copy = Object.Instantiate(found);
                copy.name = spec.name;
                var settings = AnimationUtility.GetAnimationClipSettings(copy);
                settings.loopTime = spec.loop;
                AnimationUtility.SetAnimationClipSettings(copy, settings);

                AssetDatabase.CreateAsset(copy, path);
                result[spec.name] = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
                Debug.Log($"[My World] 剪辑 {spec.name} ← {found.name}（{(spec.loop ? "循环" : "单次")}，{found.length:F2}s）");
            }

            return result;
        }

        /// <summary>
        /// 由 FBX 建角色预制体。会按 keepWeapons 白名单关掉多余的内置附件，
        /// 并把脚底对齐到 local y=0（模型的节点原点不在脚底）。
        /// </summary>
        public static GameObject BuildPrefab(
            string fbxPath, Material mat, AnimatorController ctrl, string prefabPath,
            string name, string[] keepWeapons, float modelScale = 1f)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
            if (model == null)
            {
                Debug.LogError($"[My World] 找不到模型 {fbxPath}");
                return null;
            }

            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            inst.name = name;

            var bodyRends = new List<Renderer>();
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                if (mat != null) r.sharedMaterial = mat;

                // 内置武器附件：只留白名单里的，其余关掉（否则会和挂上去的武器重叠）
                bool isAttachment = IsAttachment(r.name);
                if (isAttachment && (keepWeapons == null || System.Array.IndexOf(keepWeapons, r.name) < 0))
                    r.enabled = false;
                else if (!isAttachment)
                    bodyRends.Add(r);
            }

            // 原点不在脚底：把身体最低点抬到 local y=0，否则角色会陷进地里
            float minY = float.MaxValue;
            foreach (var r in bodyRends) minY = Mathf.Min(minY, r.bounds.min.y);
            if (minY < float.MaxValue && Mathf.Abs(minY) > 0.001f)
            {
                var p = inst.transform.localPosition;
                inst.transform.localPosition = new Vector3(p.x, p.y - minY, p.z);
                Debug.Log($"[My World] {name} 脚底对齐：最低点 y={minY:F4} → 上移 {-minY:F4}");
            }

            var animator = inst.GetComponent<Animator>();
            if (animator == null) animator = inst.AddComponent<Animator>();
            animator.runtimeAnimatorController = ctrl;
            // 位移由 PlayerController8Dir / Enemy 自己负责；动画带根位移会和控制器打架
            animator.applyRootMotion = false;
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;

            if (modelScale != 1f) inst.transform.localScale = Vector3.one * modelScale;

            PrefabUtility.SaveAsPrefabAsset(inst, prefabPath);
            Object.DestroyImmediate(inst);
            Debug.Log($"[My World] 角色预制体: {prefabPath}");
            return AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
        }

        /// <summary>判断某个网格是不是"内置武器附件"（要按白名单筛选的）。</summary>
        private static bool IsAttachment(string rendererName)
        {
            // 各角色自带的可换装部件：法杖/魔杖/魔法书、斧/盾/杯子……
            string[] markers = { "Axe", "Staff", "Wand", "Spellbook", "Shield", "Mug", "Sword", "Dagger", "Quiver" };
            foreach (var m in markers)
                if (rendererName.IndexOf(m, System.StringComparison.OrdinalIgnoreCase) >= 0) return true;
            return false;
        }
    }
}
