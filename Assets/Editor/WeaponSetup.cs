using UnityEditor;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 一键安装武器：配置剑/法杖的 FBX 导入器 + 材质，并用图元拼出抓钩（PEAK 绳索枪风）和魔法护手，
    /// 四种武器统一存成预制体，供 WeaponMount 挂到 handslot.r / handslot.l 上。
    ///
    /// 注意方向：内置武器是 handslot 下"局部归零"的普通网格，且长轴指向 +Z，
    /// 所以这里所有武器也一律建成"沿 +Z 伸出"。
    ///
    /// 菜单：Tools → My World → 安装武器
    /// </summary>
    public static class WeaponSetup
    {
        private const string Root = "Assets/ThirdParty/KayKit_Adventurers";
        private const string WDir = Root + "/Weapons";

        public const string SwordPrefab = WDir + "/W_Sword.prefab";
        public const string StaffPrefab = WDir + "/W_Staff.prefab";
        public const string RopeGunPrefab = WDir + "/W_RopeGun.prefab";
        public const string GauntletPrefab = WDir + "/W_Gauntlet.prefab";
        public const string BowPrefab = WDir + "/W_Bow.prefab";
        public const string ShieldPrefab = WDir + "/W_Shield.prefab";

        [MenuItem("Tools/My World/安装武器")]
        public static void Install()
        {
            ConfigureWeaponImporter(WDir + "/sword_1handed.fbx");
            ConfigureWeaponImporter(WDir + "/staff.fbx");

            var knightTex = LoadTex(Root + "/knight_texture.png");
            var mageTex = LoadTex(Root + "/mage_texture.png");

            var swordMat = MakeMat(WDir + "/M_Sword.mat", knightTex, 0.35f);
            var staffMat = MakeMat(WDir + "/M_Staff.mat", mageTex, 0.2f);

            // FBX 武器是 Y-up 的（刀身竖着），绕 X 转 90° 才能和手部挂点的 +Z 朝前对齐
            BuildFromFbx(WDir + "/sword_1handed.fbx", SwordPrefab, swordMat, "W_Sword", 90f);
            BuildFromFbx(WDir + "/staff.fbx", StaffPrefab, staffMat, "W_Staff", 90f);

            // 弓（弩）和盾：贴图分别是 rogue / knight 的图集
            ConfigureWeaponImporter(WDir + "/crossbow_1handed.fbx");
            ConfigureWeaponImporter(WDir + "/shield_round.fbx");
            var rogueTex = LoadTex(Root + "/rogue_texture.png");
            var bowMat = MakeMat(WDir + "/M_Bow.mat", rogueTex, 0.25f);
            BuildFromFbx(WDir + "/crossbow_1handed.fbx", BowPrefab, bowMat, "W_Bow", 90f);
            BuildFromFbx(WDir + "/shield_round.fbx", ShieldPrefab, swordMat, "W_Shield", 90f);

            BuildRopeGun();
            BuildGauntlet();

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("[My World] 武器安装完成。");
        }

        // ---------------- 导入器 / 材质 ----------------

        private static void ConfigureWeaponImporter(string path)
        {
            var importer = AssetImporter.GetAtPath(path) as ModelImporter;
            if (importer == null)
            {
                Debug.LogWarning($"[My World] 找不到武器模型 {path}");
                return;
            }
            // 武器是静态网格，不带动画也不带动骨骼
            importer.animationType = ModelImporterAnimationType.None;
            importer.importAnimation = false;
            importer.bakeAxisConversion = false;
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.materialSearch = ModelImporterMaterialSearch.Everywhere;
            importer.SaveAndReimport();
        }

        private static Texture2D LoadTex(string path)
        {
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (tex == null) return null;

            var ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti != null)
            {
                ti.filterMode = FilterMode.Point;
                ti.mipmapEnabled = false;
                ti.SaveAndReimport();
            }
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        private static Material MakeMat(string path, Texture2D tex, float smoothness)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader) { name = System.IO.Path.GetFileNameWithoutExtension(path) };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            if (tex != null)
            {
                mat.SetTexture("_BaseMap", tex);
                mat.SetColor("_BaseColor", Color.white);
            }
            mat.SetFloat("_Metallic", 0f);
            mat.SetFloat("_Smoothness", smoothness);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>
        /// 建一个 URP/Lit 材质**资源**。
        /// 关键：图元拼出来的武器如果挂的是内存材质（PlaceholderArt.NewLit），
        /// 存成预制体时引用会丢成 null，武器就会渲染成品红色。必须落成资源。
        /// </summary>
        private static Material MakeLitAsset(string path, Color color, float smoothness, string name)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            mat.color = color;
            mat.SetFloat("_Metallic", 0f);
            mat.SetFloat("_Smoothness", smoothness);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>建一个自发光材质资源（护手宝石、法术弹用）。</summary>
        private static Material MakeUnlitAsset(string path, Color color, string name)
        {
            var shader = Shader.Find("Universal Render Pipeline/Unlit");
            if (shader == null) shader = Shader.Find("Unlit/Color");

            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            mat.color = color;
            EditorUtility.SetDirty(mat);
            return mat;
        }

        // ---------------- 由 FBX 生成武器预制体 ----------------

        private static void BuildFromFbx(string fbxPath, string prefabPath, Material mat, string name, float rotateX)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
            if (model == null)
            {
                Debug.LogWarning($"[My World] 缺少 {fbxPath}");
                return;
            }

            // 预制体根做成一个干净的容器，模型放子节点里再转 —— 这样挂载时能自由设置根的变换，
            // 不会被模型自带的方向干扰。
            var root = new GameObject(name);
            var inst = Object.Instantiate(model);
            inst.name = "Model";
            inst.transform.SetParent(root.transform, false);
            inst.transform.localPosition = Vector3.zero;
            inst.transform.localRotation = Quaternion.Euler(rotateX, 0f, 0f);

            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
                if (mat != null) r.sharedMaterial = mat;

            Save(root, prefabPath, name);
        }

        // ---------------- 图元拼：抓钩（PEAK 绳索枪风） ----------------

        private static void BuildRopeGun()
        {
            var root = new GameObject("W_RopeGun");

            var metal = MakeLitAsset(WDir + "/M_RopeGunMetal.mat", new Color(0.28f, 0.29f, 0.32f), 0.45f, "M_RopeGunMetal");
            var accent = MakeLitAsset(WDir + "/M_RopeGunAccent.mat", new Color(0.93f, 0.68f, 0.16f), 0.4f, "M_RopeGunAccent");
            var dark = MakeLitAsset(WDir + "/M_RopeGunDark.mat", new Color(0.16f, 0.16f, 0.18f), 0.25f, "M_RopeGunDark");
            var rope = MakeLitAsset(WDir + "/M_Rope.mat", new Color(0.82f, 0.80f, 0.74f), 0.1f, "M_Rope");

            // 机身（沿 +Z 伸出，握把朝下后方）
            Part(PrimitiveType.Cube, root.transform, "Body", metal,
                new Vector3(0f, 0.02f, 0.02f), new Vector3(0.13f, 0.16f, 0.26f), Vector3.zero);
            Part(PrimitiveType.Cube, root.transform, "Grip", dark,
                new Vector3(0f, -0.11f, -0.05f), new Vector3(0.10f, 0.20f, 0.11f), new Vector3(-18f, 0f, 0f));
            // 顶上的绞盘：绳索就绕在这
            Part(PrimitiveType.Cylinder, root.transform, "Drum", accent,
                new Vector3(0f, 0.10f, 0.0f), new Vector3(0.15f, 0.065f, 0.15f), new Vector3(90f, 0f, 0f));
            // 枪管
            Part(PrimitiveType.Cylinder, root.transform, "Barrel", metal,
                new Vector3(0f, 0.03f, 0.24f), new Vector3(0.075f, 0.11f, 0.075f), new Vector3(90f, 0f, 0f));
            // 枪口环
            Part(PrimitiveType.Cylinder, root.transform, "Muzzle", accent,
                new Vector3(0f, 0.03f, 0.35f), new Vector3(0.10f, 0.022f, 0.10f), new Vector3(90f, 0f, 0f));
            // 钩爪：三片向外张开的钩，绕枪管均布并外倾
            for (int i = 0; i < 3; i++)
            {
                float a = i * 120f;
                Quaternion rot = Quaternion.Euler(0f, a, 0f) * Quaternion.Euler(-26f, 0f, 0f);
                var claw = Part(PrimitiveType.Cube, root.transform, "Claw" + i, dark,
                    new Vector3(0f, 0.03f, 0.40f), new Vector3(0.034f, 0.034f, 0.15f), Vector3.zero);
                claw.transform.localRotation = rot;
                claw.transform.localPosition = new Vector3(0f, 0.03f, 0.40f) + rot * new Vector3(0f, 0f, 0.06f);
            }
            // 一小段露出的缆绳
            Part(PrimitiveType.Cylinder, root.transform, "Rope", rope,
                new Vector3(0f, 0.03f, 0.30f), new Vector3(0.028f, 0.05f, 0.028f), new Vector3(90f, 0f, 0f));

            Save(root, RopeGunPrefab, "W_RopeGun");
        }

        // ---------------- 图元拼：魔法护手 ----------------

        private static void BuildGauntlet()
        {
            var root = new GameObject("W_Gauntlet");

            var leather = MakeLitAsset(WDir + "/M_GauntletLeather.mat", new Color(0.30f, 0.22f, 0.17f), 0.12f, "M_GauntletLeather");
            var plate = MakeLitAsset(WDir + "/M_GauntletPlate.mat", new Color(0.42f, 0.45f, 0.52f), 0.55f, "M_GauntletPlate");

            // 前臂套
            Part(PrimitiveType.Cube, root.transform, "Sleeve", leather,
                new Vector3(0f, 0.01f, -0.02f), new Vector3(0.19f, 0.19f, 0.24f), Vector3.zero);
            // 三圈束带
            for (int i = 0; i < 3; i++)
                Part(PrimitiveType.Cube, root.transform, "Strap" + i, plate,
                    new Vector3(0f, 0.01f, -0.10f + i * 0.08f), new Vector3(0.205f, 0.205f, 0.028f), Vector3.zero);
            // 护手背板
            Part(PrimitiveType.Cube, root.transform, "Guard", plate,
                new Vector3(0f, 0.06f, 0.10f), new Vector3(0.22f, 0.07f, 0.17f), new Vector3(10f, 0f, 0f));
            // 指节块
            Part(PrimitiveType.Cube, root.transform, "Knuckle", plate,
                new Vector3(0f, 0.02f, 0.18f), new Vector3(0.21f, 0.11f, 0.06f), Vector3.zero);
            // 法术核心：发光宝石（"护手=法术增幅器"的视觉线索）
            // 必须用资源材质：内存里 new 出来的材质存不进预制体，会变成空引用。
            var gemMat = MakeUnlitAsset(WDir + "/M_GauntletGem.mat", new Color(0.5f, 0.9f, 1f), "M_GauntletGem");
            Part(PrimitiveType.Sphere, root.transform, "Gem", gemMat,
                new Vector3(0f, 0.10f, 0.03f), Vector3.one * 0.085f, Vector3.zero);

            Save(root, GauntletPrefab, "W_Gauntlet");
        }

        // ---------------- 辅助 ----------------

        private static GameObject Part(
            PrimitiveType type, Transform parent, string name, Material mat,
            Vector3 pos, Vector3 scale, Vector3 euler)
        {
            var go = PlaceholderArt.Primitive(type, parent, name, pos, scale, mat);
            go.transform.localRotation = Quaternion.Euler(euler);
            return go;
        }

        private static void Save(GameObject root, string prefabPath, string name)
        {
            LogBounds(root, name);
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            Object.DestroyImmediate(root);
        }

        private static void LogBounds(GameObject go, string name)
        {
            var rends = go.GetComponentsInChildren<Renderer>(true);
            if (rends.Length == 0) return;
            var b = rends[0].bounds;
            bool first = true;
            foreach (var r in rends)
            {
                if (!r.enabled) continue;
                if (first) { b = r.bounds; first = false; } else b.Encapsulate(r.bounds);
            }
            Debug.Log($"[My World]   武器 {name,-12} 尺寸={b.size.ToString("F3")} 中心={b.center.ToString("F3")} " +
                      $"（长轴应沿 +Z；中心偏了就用挂点偏移修）");
        }
    }
}
