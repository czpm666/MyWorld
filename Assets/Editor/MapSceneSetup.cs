using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 为每张新地图生成一个"空场景 + 一个 MapBootstrap 子类组件"的场景文件，并登记到 Build Settings。
    ///
    /// 地图内容全部由运行时代码生成，所以场景里**故意只有这一个物体**：
    /// 避免几百个物件被烘焙进 .unity（文件巨大、diff 不可读、agent 之间互相覆盖）。
    ///
    /// 用法：等 map-town / map-world 把 Maps/*.cs 落地后，点菜单
    ///   Tools ▸ My World ▸ 生成新地图场景（全部）
    /// 逐个生成也可以，菜单里有单独的项。
    /// </summary>
    public static class MapSceneSetup
    {
        private const string SceneDir = "Assets/Scenes";

        private struct MapEntry
        {
            public string Scene;
            public string TypeName;
            public string MapEnum;
            public string Label;
        }

        private static readonly MapEntry[] Maps =
        {
            new MapEntry { Scene = "RoaTown",       TypeName = "MyWorld.Maps.RoaTownMap",        MapEnum = "RoaTown",        Label = "罗亚市" },
            new MapEntry { Scene = "BuenaVillage",  TypeName = "MyWorld.Maps.BuenaVillageMap",   MapEnum = "BuenaVillage",   Label = "布耶纳村" },
            new MapEntry { Scene = "RanoaAcademy",  TypeName = "MyWorld.Maps.RanoaAcademyMap",   MapEnum = "RanoaAcademy",   Label = "拉诺亚魔法学园" },
        };

        [MenuItem("Tools/My World/生成新地图场景（全部）", priority = 20)]
        public static void GenerateAll()
        {
            for (int i = 0; i < Maps.Length; i++) Generate(Maps[i]);
            RefreshBuildSettings();
            AssetDatabase.SaveAssets();
            Debug.Log("[MapSceneSetup] 新地图场景全部生成完毕。要试玩：打开场景按 Play，或从训练场走传送门。");
        }

        [MenuItem("Tools/My World/生成地图-罗亚市", priority = 21)]
        public static void GenerateRoaTown() { Generate(Maps[0]); RefreshBuildSettings(); }

        [MenuItem("Tools/My World/生成地图-布耶纳村", priority = 22)]
        public static void GenerateBuenaVillage() { Generate(Maps[1]); RefreshBuildSettings(); }

        [MenuItem("Tools/My World/生成地图-拉诺亚学园", priority = 23)]
        public static void GenerateRanoaAcademy() { Generate(Maps[2]); RefreshBuildSettings(); }

        private static void Generate(MapEntry entry)
        {
            var type = FindType(entry.TypeName);
            if (type == null)
            {
                Debug.LogError("[MapSceneSetup] 找不到地图脚本 " + entry.TypeName +
                               "（map agent 还没交付？）。已跳过 " + entry.Label + "。");
                return;
            }
            if (!typeof(MapBootstrap).IsAssignableFrom(type))
            {
                Debug.LogError("[MapSceneSetup] " + entry.TypeName + " 没有继承 MapBootstrap，已跳过。");
                return;
            }

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = new GameObject(entry.Scene);
            var comp = go.AddComponent(type);

            var so = new SerializedObject(comp);
            SetEnum(so, "mapId", entry.MapEnum);

            var characterPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(MageSetup.PrefabPath);
            SetObject(so, "characterPrefab", characterPrefab);
            // NPC 必须用独立的人形预制体：曾经这里写成 characterPrefab，每次跑地图 setup
            // 都会把三个场景的 npcPrefab 重置成主角（25 个 NPC 全变法师）。
            var npcPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(NpcSetup.PrefabPath);
            if (npcPrefab == null)
            {
                Debug.LogWarning("[MapSceneSetup] 缺 NPC 预制体：" + NpcSetup.PrefabPath + "，退回主角模型。");
                npcPrefab = characterPrefab;
            }
            SetObject(so, "npcPrefab", npcPrefab);
            SetObject(so, "enemyPrefab", AssetDatabase.LoadAssetAtPath<GameObject>(EnemySetup.PrefabPath));

            var weaponProp = so.FindProperty("weaponPrefabs");
            if (weaponProp != null)
            {
                // 顺序：法杖、剑、弓、抓钩、盾、魔法护手（和 WeaponDefs.CreateAll 对应）
                string[] paths =
                {
                    WeaponSetup.StaffPrefab, WeaponSetup.SwordPrefab, WeaponSetup.BowPrefab,
                    WeaponSetup.RopeGunPrefab, WeaponSetup.ShieldPrefab, WeaponSetup.GauntletPrefab,
                };
                weaponProp.arraySize = paths.Length;
                for (int i = 0; i < paths.Length; i++)
                {
                    var p = AssetDatabase.LoadAssetAtPath<GameObject>(paths[i]);
                    weaponProp.GetArrayElementAtIndex(i).objectReferenceValue = p;
                    if (p == null) Debug.LogWarning("[MapSceneSetup] 缺武器预制体：" + paths[i]);
                }
            }
            so.ApplyModifiedPropertiesWithoutUndo();

            EnsureFolder(SceneDir);
            string scenePath = SceneDir + "/" + entry.Scene + ".unity";
            EditorSceneManager.SaveScene(scene, scenePath);
            Debug.Log("[MapSceneSetup] 已生成 " + entry.Label + " → " + scenePath);
        }

        private static Type FindType(string fullName)
        {
            var assemblies = AppDomain.CurrentDomain.GetAssemblies();
            for (int i = 0; i < assemblies.Length; i++)
            {
                var t = assemblies[i].GetType(fullName, false);
                if (t != null) return t;
            }
            return null;
        }

        private static void SetObject(SerializedObject so, string field, UnityEngine.Object value)
        {
            var p = so.FindProperty(field);
            if (p == null) return;
            p.objectReferenceValue = value;
            if (value == null) Debug.LogWarning("[MapSceneSetup] 字段 " + field + " 没找到资源，留空。");
        }

        private static void SetEnum(SerializedObject so, string field, string enumName)
        {
            var p = so.FindProperty(field);
            if (p == null) return;
            if (!Enum.IsDefined(typeof(MapId), enumName)) return;
            p.enumValueIndex = (int)(MapId)Enum.Parse(typeof(MapId), enumName);
        }

        /// <summary>Build Settings：训练场永远是第 0 个（启动场景），新地图按罗亚市→村庄→学园排。</summary>
        private static void RefreshBuildSettings()
        {
            var list = new List<EditorBuildSettingsScene>();
            AddExisting(list, SceneDir + "/MyWorld.unity");
            for (int i = 0; i < Maps.Length; i++) AddExisting(list, SceneDir + "/" + Maps[i].Scene + ".unity");
            EditorBuildSettings.scenes = list.ToArray();
        }

        private static void AddExisting(List<EditorBuildSettingsScene> list, string path)
        {
            if (System.IO.File.Exists(path)) list.Add(new EditorBuildSettingsScene(path, true));
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            AssetDatabase.CreateFolder("Assets", path.Substring("Assets/".Length));
        }

        [MenuItem("Tools/My World/检查新地图场景", priority = 24)]
        public static void InspectScenes()
        {
            for (int i = 0; i < Maps.Length; i++)
            {
                string path = SceneDir + "/" + Maps[i].Scene + ".unity";
                Debug.Log((System.IO.File.Exists(path) ? "✅ " : "❌ ") + Maps[i].Label + "  " + path);
            }
            var scenes = EditorBuildSettings.scenes;
            for (int i = 0; i < scenes.Length; i++)
                Debug.Log("BuildSettings[" + i + "] " + scenes[i].path + " enabled=" + scenes[i].enabled);
        }
    }
}
