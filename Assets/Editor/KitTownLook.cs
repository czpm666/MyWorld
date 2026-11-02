// 给 BlenderKit 城镇场景补"氛围"：后处理 Volume + 环境光 + 雾。
// 复用工程里已有的 DioramaPostFx（它在运行时用代码建 VolumeProfile，不需要资源文件）。
// 独立于 BlenderKitSceneBuilder，方便场景重建后单独再套一次。
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using MyWorld;

public static class KitTownLook
{
    const string RootName = "BlenderKitTown";
    const string FxName = "DioramaPostFx";

    // 注意：MenuItem 名字里不能再出现 "/"，否则 Unity 会当成子菜单，execute_menu_item 找不到这个路径。
    [MenuItem("Tools/My World/给 kit 城镇上氛围", false, 62)]
    public static void ApplyLook()
    {
        if (EditorApplication.isPlaying)
        {
            Debug.LogError("[KitTownLook] 先退出 Play 再改场景。");
            return;
        }

        var town = GameObject.Find(RootName);
        if (town == null)
        {
            Debug.LogError("[KitTownLook] 找不到 " + RootName + "，先生成城镇场景。");
            return;
        }

        // 后处理：已存在就复用，不重复叠
        var fx = town.transform.Find(FxName);
        if (fx == null)
        {
            var go = new GameObject(FxName);
            go.transform.SetParent(town.transform, false);
            go.AddComponent<DioramaPostFx>();      // RequireComponent(Volume) 会自动带上 Volume
            fx = go.transform;
        }

        // 环境光：压一点，让阳光和阴影有对比，不要整片打亮
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.42f, 0.50f, 0.62f);
        RenderSettings.ambientEquatorColor = new Color(0.36f, 0.34f, 0.30f);
        RenderSettings.ambientGroundColor = new Color(0.18f, 0.16f, 0.13f);
        RenderSettings.ambientIntensity = 1f;

        // 雾：远处树线糊进天色里，别再出现"草地硬边"
        RenderSettings.fog = true;
        RenderSettings.fogMode = FogMode.Linear;
        RenderSettings.fogColor = new Color(0.62f, 0.70f, 0.80f);
        RenderSettings.fogStartDistance = 55f;
        RenderSettings.fogEndDistance = 190f;

        EditorSceneManager.MarkSceneDirty(town.scene);
        Selection.activeGameObject = fx.gameObject;
        Debug.Log("[KitTownLook] 已加后处理 + 环境光 + 线性雾（记得保存场景）");
    }
}
