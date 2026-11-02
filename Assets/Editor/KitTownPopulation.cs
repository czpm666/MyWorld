// 给 BlenderKit 城镇场景放"人气"：商人 / 冒险者协会职员 / 卫兵 / 村民。
// 只在**编辑期**跑，把 NPC 直接烙进场景文件（和烘焙地图是同一套思路：看得见、手能改）。
// 全程复用既有的 NpcFactory / MerchantShop / QuestBoardInteractable，不新造交互逻辑。
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using MyWorld;

public static class KitTownPopulation
{
    const string RootName = "BlenderKitTown";
    const string NpcRootName = "Population";

    static readonly string[] NpcPrefabs =
    {
        "Assets/ThirdParty/KayKit_Adventurers/NpcCharacter.prefab",
        "Assets/ThirdParty/KayKit_Adventurers/NpcCharacter_Red.prefab",
        "Assets/ThirdParty/KayKit_Adventurers/NpcCharacter_Green.prefab",
        "Assets/ThirdParty/KayKit_Adventurers/NpcCharacter_Blue.prefab",
        "Assets/ThirdParty/KayKit_Adventurers/NpcCharacter_Tan.prefab",
    };

    [MenuItem("Tools/My World/给 kit 城镇放 NPC", false, 61)]
    public static void Populate()
    {
        if (EditorApplication.isPlaying)
        {
            Debug.LogError("[KitTownPopulation] 先退出 Play 再放 NPC（要写进场景文件）。");
            return;
        }

        var town = GameObject.Find(RootName);
        if (town == null)
        {
            Debug.LogError("[KitTownPopulation] 当前场景里找不到 " + RootName +
                           "，先跑 Tools/My World/用 Blender Kit 生成城镇场景。");
            return;
        }

        var prefabs = new List<GameObject>();
        foreach (var p in NpcPrefabs)
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(p);
            if (go != null) prefabs.Add(go);
        }
        if (prefabs.Count == 0)
        {
            Debug.LogError("[KitTownPopulation] 一个 NPC 预制体都没加载到。");
            return;
        }

        // 幂等：先删掉上一次放的
        var old = town.transform.Find(NpcRootName);
        if (old != null) Object.DestroyImmediate(old.gameObject);

        var root = new GameObject(NpcRootName);
        root.transform.SetParent(town.transform, false);

        int idx = 0;
        int made = 0;

        // ---- 四块市集空地：每块一个商人 + 一个村民 ----
        float[] quad = { 1f, -1f };
        int shopTurn = 0;
        foreach (float sx in quad)
        foreach (float sz in quad)
        {
            float cx = sx * 25f;
            float cz = sz * 25f;
            float yawToCenter = Mathf.Atan2(-cx, -cz) * Mathf.Rad2Deg;

            // 站在装饰摊位旁边（摊位在 cx+0.6, cz-0.4）
            string shopId = shopTurn % 2 == 0 ? "kittown_general" : "kittown_arcane";
            string who = shopTurn % 2 == 0 ? "杂货商人" : "魔法用品商人";
            Make(root.transform, prefabs[idx++ % prefabs.Count], NpcRole.Merchant, who,
                 new Vector3(cx + 1.9f, 0f, cz - 0.9f), yawToCenter,
                 new[] { "风尘仆仆的旅人，看看吧。", "货是从王都拉来的，价钱公道。" }, shopId);
            made++;
            shopTurn++;

            Make(root.transform, prefabs[idx++ % prefabs.Count], NpcRole.Villager,
                 "镇民" + (made + 1), new Vector3(cx - 2.4f, 0f, cz - 1.8f), yawToCenter + 30f,
                 new[] { "今天集上人多，小心扒手。", "听说协会又贴了新委托。" }, null);
            made++;
        }

        // ---- 中央广场：协会职员 + 两条闲聊的村民 ----
        Make(root.transform, prefabs[idx++ % prefabs.Count], NpcRole.GuildStaff, "协会职员 米莉",
             new Vector3(-3.4f, 0f, 3.2f), 200f,
             new[] { "委托都写在板子上了，接了就算数。", "讨伐、采集、护送，挑一件吧。" }, null, "roa_guild");
        made++;

        Make(root.transform, prefabs[idx++ % prefabs.Count], NpcRole.Villager, "广场闲人",
             new Vector3(4.2f, 0f, -5.0f), 90f,
             new[] { "喷泉的水是山里引下来的。", "晚上别往城墙外头走。" }, null);
        made++;

        Make(root.transform, prefabs[idx++ % prefabs.Count], NpcRole.Villager, "面包摊老板",
             new Vector3(-6.0f, 0f, -4.4f), 55f,
             new[] { "刚出炉的黑麦面包。", "十个铜板一个，热乎的。" }, null);
        made++;

        // ---- 四个城门：每门两个卫兵，站成八字 ----
        Vector3[] gateSpots =
        {
            new Vector3(0f, 0f, 40f), new Vector3(0f, 0f, -40f),
            new Vector3(40f, 0f, 0f), new Vector3(-40f, 0f, 0f),
        };
        for (int g = 0; g < gateSpots.Length; g++)
        {
            Vector3 c = gateSpots[g];
            Vector3 outward = c.normalized;
            Vector3 side = Vector3.Cross(Vector3.up, outward).normalized;
            for (int s = 0; s < 2; s++)
            {
                Vector3 p = c + outward * 5.5f + side * (s == 0 ? 2.6f : -2.6f);
                float yaw = Mathf.Atan2(-outward.x, -outward.z) * Mathf.Rad2Deg;
                Make(root.transform, prefabs[idx++ % prefabs.Count], NpcRole.Guard,
                     "城门卫兵", p, yaw,
                     new[] { "出城当心，最近野地里有东西。", "天黑前回来。" }, null);
                made++;
            }
        }

        EditorSceneManager.MarkSceneDirty(town.scene);
        Selection.activeGameObject = root;
        Debug.Log("[KitTownPopulation] 放了 " + made + " 个 NPC 到 " + RootName + "/" + NpcRootName +
                  "（记得保存场景）");
    }

    static void Make(Transform parent, GameObject prefab, NpcRole role, string name, Vector3 pos,
        float yaw, string[] lines, string shopId, string boardId = null)
    {
        var actor = NpcFactory.Create(parent, prefab, role, name, pos, yaw, lines, shopId, boardId);

        // 名字牌收小：NpcFactory 默认 size=0.16，在这个俯视机位下每字约 0.48 m，糊满半个广场。
        // 只改本场景的实例，不动 NpcFactory（罗亚市那边已经烘焙进场景，改了也不会重算）。
        var meshes = actor.GetComponentsInChildren<TextMesh>(true);
        for (int i = 0; i < meshes.Length; i++)
        {
            var t = meshes[i].transform;
            t.localScale = t.localScale * 0.42f;
        }
    }
}
