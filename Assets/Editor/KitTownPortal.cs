// 把石墙镇接进地图网络：两侧各放一座传送门。
//
// 为什么需要：BlenderKitTown 之前是个"孤儿场景"——场景本身能玩，但玩家从主城走不到，
// 只能手动打开场景文件。这个菜单给它补上双向传送门，接进 GameSession 的 MapId 体系。
//
// 两个菜单各自作用于**当前打开的场景**，所以在哪个场景里点哪个。
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using MyWorld;

public static class KitTownPortal
{
    [MenuItem("Tools/My World/石墙镇：加「回罗亚市」传送门", false, 63)]
    public static void AddPortalToRoaTown()
    {
        if (EditorApplication.isPlaying) { Debug.LogError("[KitTownPortal] 先退出 Play。"); return; }

        var town = GameObject.Find("BlenderKitTown");
        if (town == null)
        {
            Debug.LogError("[KitTownPortal] 当前场景不是石墙镇（找不到 BlenderKitTown 根）。");
            return;
        }

        var host = town.transform.Find("Portals");
        if (host == null)
        {
            var go = new GameObject("Portals");
            go.transform.SetParent(town.transform, false);
            host = go.transform;
        }

        // 南门外，面朝城外（玩家从城里走出去按 E）
        var portal = ScenePortal.Create(host, new Vector3(0f, 0f, 41.5f),
            MapId.RoaTown, "gate", "罗亚市", 0f);

        EditorSceneManager.MarkSceneDirty(town.scene);
        Selection.activeGameObject = portal.gameObject;
        Debug.Log("[KitTownPortal] 已在南门外放下通往罗亚市的传送门（记得保存场景）");
    }

    [MenuItem("Tools/My World/罗亚市：加「去石墙镇」传送门", false, 64)]
    public static void AddPortalToKitTown()
    {
        if (EditorApplication.isPlaying) { Debug.LogError("[KitTownPortal] 先退出 Play。"); return; }

        var root = GameObject.Find("RoaTown");
        if (root == null)
        {
            Debug.LogError("[KitTownPortal] 当前场景不是罗亚市（找不到 RoaTown 根）。");
            return;
        }

        var host = root.transform.Find("Portals");
        if (host == null)
        {
            var go = new GameObject("Portals");
            go.transform.SetParent(root.transform, false);
            host = go.transform;
        }

        // 进城主街北端，靠近协会那一侧；避开中央喷泉和摊位环
        var portal = ScenePortal.Create(host, new Vector3(-9.5f, 0f, 26f),
            MapId.BlenderKitTown, "start", "石墙镇", 200f);

        EditorSceneManager.MarkSceneDirty(root.scene);
        Selection.activeGameObject = portal.gameObject;
        Debug.Log("[KitTownPortal] 已在罗亚市放下通往石墙镇的传送门（记得保存场景）");
    }
}
