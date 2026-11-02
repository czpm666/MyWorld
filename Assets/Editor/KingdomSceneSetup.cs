using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 生成阿斯拉王国的两个场景：
    ///   KingdomWorld  —— 3km 大地图，中央王都城门 + 几十座小镇（小镇是 FBX 预制体）
    ///   AsuraCapital  —— 王都本体（Blender 导出的 ars_* 分件预制体）
    ///
    /// 场景内容在菜单里直接烘焙：MapBootstrap 只在 Play 的 Awake 里调 BuildAll()，
    /// 编辑期没人调，所以旧版菜单保存下来的 .unity 只有一个空根（本次空场景的根因）。
    /// 现在复用 MapSceneBaker 的范式：BuildAll() → bakedIntoScene=true → 保存。
    /// </summary>
    public static class KingdomSceneSetup
    {
        private const string SceneDir = "Assets/Scenes";
        private const string PrefabRoot = "Assets/Generated/KingdomKit";
        private const string CapitalRoot = "Assets/Generated/KingdomKit/capital";

        // ---------------- 菜单 ----------------

        [MenuItem("Tools/My World/王国③生成王国大地图场景", false, 72)]
        public static void BuildKingdomWorld()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = new GameObject("KingdomWorld");
            var map = root.AddComponent<MyWorld.Maps.KingdomWorldMap>();

            var so = new SerializedObject(map);
            SetEnum(so, "mapId", "AsuraKingdom");
            SetInt(so, "groundSize", 3000);
            SetInt(so, "townCount", 30);
            SetFloat(so, "worldSize", 3000f);
            SetFloat(so, "minTownGap", 250f);
            SetFloat(so, "camDistance", 26f);

            SetObject(so, "characterPrefab", LoadPrefab(MageSetup.PrefabPath));
            var npc = LoadPrefab(NpcSetup.PrefabPath);
            SetObject(so, "npcPrefab", npc != null ? npc : LoadPrefab(MageSetup.PrefabPath));
            SetObject(so, "enemyPrefab", LoadPrefab(EnemySetup.PrefabPath));
            SetWeapons(so);

            // towns only: the capital's ars_* pieces also live under KingdomKit now, and a
            // 35 MB city chunk dropped in as a "town" would both look wrong and stall Play.
            SetTownPrefabs(so, "townPrefabs", CollectTowns());
            SetTownPrefabs(so, "treePrefabs", CollectTrees());
            SetTownPrefabs(so, "housePrefabs", CollectHouses());
            so.ApplyModifiedPropertiesWithoutUndo();

            BakeIntoScene(map);
            SaveScene(scene, "KingdomWorld");
            RefreshBuildSettings();
        }

        [MenuItem("Tools/My World/王国④生成王都场景", false, 73)]
        public static void BuildCapitalScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = new GameObject("AsuraCapital");
            var map = root.AddComponent<MyWorld.Maps.AsuraCapitalMap>();

            var so = new SerializedObject(map);
            SetEnum(so, "mapId", "AsuraCapital");
            SetInt(so, "groundSize", 720);
            SetFloat(so, "camDistance", 24f);

            SetObject(so, "characterPrefab", LoadPrefab(MageSetup.PrefabPath));
            var npc = LoadPrefab(NpcSetup.PrefabPath);
            SetObject(so, "npcPrefab", npc != null ? npc : LoadPrefab(MageSetup.PrefabPath));
            SetObject(so, "enemyPrefab", LoadPrefab(EnemySetup.PrefabPath));
            SetWeapons(so);

            // ars_* 分件：地面 / 城墙 / 城门 / 内城 / 城堡 / 教堂 / 公会 / 集市 / 港口 / 城区 / 郊区
            SetTownPrefabs(so, "capitalPrefabs", CollectPrefabs(CapitalRoot));
            // 城内联排立面：用 kit 的 house 预制体补密度（王都分件本身只有 ~400 栋，太散）
            SetTownPrefabs(so, "housePrefabs", CollectHouses());
            // 街道陈设：木桶、板条箱、手推车、摊位、水井、栅栏
            SetTownPrefabs(so, "propPrefabs", CollectProps());
            so.ApplyModifiedPropertiesWithoutUndo();

            BakeIntoScene(map);
            SaveScene(scene, "AsuraCapital");
            RefreshBuildSettings();
        }

        [MenuItem("Tools/My World/王国⑤检查王国场景", false, 74)]
        public static void Inspect()
        {
            foreach (var n in new[] { "KingdomWorld", "AsuraCapital" })
            {
                string p = SceneDir + "/" + n + ".unity";
                Debug.Log((File.Exists(p) ? "✅ " : "❌ ") + p);
            }
            var prefabs = CollectPrefabs(PrefabRoot);
            Debug.Log("[Kingdom] 小镇预制体 " + prefabs.Count + " 个");
            foreach (var p in prefabs) Debug.Log("    " + AssetDatabase.GetAssetPath(p));
            var cap = CollectPrefabs(CapitalRoot);
            Debug.Log("[Kingdom] 王都分件预制体 " + cap.Count + " 个");
            foreach (var p in cap) Debug.Log("    " + AssetDatabase.GetAssetPath(p));
        }

        // ---------------- 工具 ----------------

        /// <summary>
        /// 编辑期把地图内容真正建出来，并标记为已烘焙。
        /// 不调 BuildAll() 的话，MapBootstrap 只会在进 Play 的 Awake 里生成内容，
        /// 菜单保存下来的 .unity 就永远只有一个空根。
        /// </summary>
        private static void BakeIntoScene(MyWorld.MapBootstrap map)
        {
            map.BuildAll();

            var scene = map.gameObject.scene;
            var so = new SerializedObject(map);
            var baked = so.FindProperty("bakedIntoScene");
            if (baked == null)
            {
                Debug.LogError("[Kingdom] MapBootstrap 缺少 bakedIntoScene 字段，Play 时会重建地图。");
            }
            else
            {
                baked.boolValue = true;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            EditorUtility.SetDirty(map);
            EditorSceneManager.MarkSceneDirty(scene);
        }

        private static List<GameObject> CollectPrefabs(string root)
        {
            var result = new List<GameObject>();
            if (!Directory.Exists(root)) return result;
            var files = Directory.GetFiles(root, "*.prefab", SearchOption.AllDirectories);
            Array.Sort(files, StringComparer.OrdinalIgnoreCase);
            foreach (var f in files)
            {
                string assetPath = f.Replace('\\', '/').Replace(
                    Directory.GetParent(Application.dataPath).FullName.Replace('\\', '/') + "/", "");
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
                if (go != null) result.Add(go);
                else Debug.LogWarning("[Kingdom] 预制体读不到：" + assetPath);
            }
            return result;
        }

        /// <summary>Only tree/bush prefabs, for roadside rows and groves.</summary>
        private static List<GameObject> CollectTrees()
        {
            var all = CollectPrefabs("Assets/Generated/MedievalKitBlender");
            var result = new List<GameObject>();
            foreach (var go in all)
            {
                if (go == null) continue;
                string n = go.name.ToLowerInvariant();
                if (n.Contains("tree") || n.Contains("bush")) result.Add(go);
            }
            return result;
        }

        /// <summary>Town archetype prefabs only (farm_* / mine_* / port_*).</summary>
        private static List<GameObject> CollectTowns()
        {
            var all = CollectPrefabs(PrefabRoot);
            var result = new List<GameObject>();
            foreach (var go in all)
            {
                if (go == null) continue;
                string n = go.name.ToLowerInvariant();
                if (n.StartsWith("ars_")) continue;
                if (n.Contains("house")) continue;
                if (n.Contains("tree") || n.Contains("bush")) continue;
                result.Add(go);
            }
            return result;
        }

        /// <summary>Street dressing: barrels, crates, carts, stalls, wells, fences.</summary>
        private static List<GameObject> CollectProps()
        {
            var all = CollectPrefabs("Assets/Generated/MedievalKitBlender");
            var result = new List<GameObject>();
            foreach (var go in all)
            {
                if (go == null) continue;
                string n = go.name.ToLowerInvariant();
                if (n.Contains("tree") || n.Contains("bush") || n.Contains("house")) continue;
                if (n.Contains("barrel") || n.Contains("crate") || n.Contains("cart") ||
                    n.Contains("stall") || n.Contains("well") || n.Contains("fence") ||
                    n.Contains("sack") || n.Contains("lantern") || n.Contains("sign"))
                    result.Add(go);
            }
            return result;
        }

        /// <summary>Only house_a..house_f, for the capital's roof mass.</summary>
        private static List<GameObject> CollectHouses()
        {
            var all = CollectPrefabs("Assets/Generated/MedievalKitBlender");
            var result = new List<GameObject>();
            foreach (var go in all)
            {
                if (go == null) continue;
                if (go.name.ToLowerInvariant().StartsWith("house")) result.Add(go);
            }
            return result;
        }

        private static void SetTownPrefabs(SerializedObject so, string field, List<GameObject> prefabs)
        {
            var p = so.FindProperty(field);
            if (p == null)
            {
                Debug.LogError("[Kingdom] 字段不存在：" + field);
                return;
            }
            p.arraySize = prefabs.Count;
            for (int i = 0; i < prefabs.Count; i++)
                p.GetArrayElementAtIndex(i).objectReferenceValue = prefabs[i];
            Debug.Log("[Kingdom] " + field + " ← " + prefabs.Count + " 个预制体");
        }

        private static void SetWeapons(SerializedObject so)
        {
            var p = so.FindProperty("weaponPrefabs");
            if (p == null) return;
            string[] paths =
            {
                WeaponSetup.StaffPrefab, WeaponSetup.SwordPrefab, WeaponSetup.BowPrefab,
                WeaponSetup.RopeGunPrefab, WeaponSetup.ShieldPrefab, WeaponSetup.GauntletPrefab,
            };
            p.arraySize = paths.Length;
            for (int i = 0; i < paths.Length; i++)
                p.GetArrayElementAtIndex(i).objectReferenceValue = LoadPrefab(paths[i]);
        }

        private static GameObject LoadPrefab(string path)
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (go == null) Debug.LogWarning("[Kingdom] 缺预制体：" + path);
            return go;
        }

        private static void SetObject(SerializedObject so, string field, UnityEngine.Object value)
        {
            var p = so.FindProperty(field);
            if (p == null) return;
            p.objectReferenceValue = value;
        }

        private static void SetInt(SerializedObject so, string field, int v)
        {
            var p = so.FindProperty(field);
            if (p != null) p.intValue = v;
        }

        private static void SetFloat(SerializedObject so, string field, float v)
        {
            var p = so.FindProperty(field);
            if (p != null) p.floatValue = v;
        }

        private static void SetEnum(SerializedObject so, string field, string enumName)
        {
            var p = so.FindProperty(field);
            if (p == null) return;
            if (!Enum.IsDefined(typeof(MyWorld.MapId), enumName))
            {
                Debug.LogError("[Kingdom] MapId 里没有 " + enumName + "，先补 GameSession.cs");
                return;
            }
            p.enumValueIndex = (int)(MyWorld.MapId)Enum.Parse(typeof(MyWorld.MapId), enumName);
        }

        private static void SaveScene(UnityEngine.SceneManagement.Scene scene, string name)
        {
            if (!AssetDatabase.IsValidFolder(SceneDir)) AssetDatabase.CreateFolder("Assets", "Scenes");
            string path = SceneDir + "/" + name + ".unity";
            EditorSceneManager.SaveScene(scene, path);
            Debug.Log("[Kingdom] 已生成 " + path);
        }

        private static void RefreshBuildSettings()
        {
            var list = new List<EditorBuildSettingsScene>();
            string[] ordered =
            {
                "MyWorld", "RoaTown", "BuenaVillage", "RanoaAcademy", "BlenderKitTown",
                "KingdomWorld", "AsuraCapital",
            };
            foreach (var n in ordered)
            {
                string p = SceneDir + "/" + n + ".unity";
                if (File.Exists(p)) list.Add(new EditorBuildSettingsScene(p, true));
            }
            EditorBuildSettings.scenes = list.ToArray();
            Debug.Log("[Kingdom] Build Settings 已刷新：" + list.Count + " 个场景");
        }
    }
}
