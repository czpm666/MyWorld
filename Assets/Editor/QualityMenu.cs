// 画面清晰化：把 Game 视图固定成 1920×1080 并切到 PC 画质档。
//
// 为什么需要：Unity 的 Game 视图是"自由比例"时，渲染分辨率 = 面板大小。
// 面板只有 630×354，Unity 再把它拉伸到整个窗口 → 看起来就是一片糊。
// 固定成 1920×1080 后，无论面板多大，渲染都是 1080p，拉伸比例小得多。
using System;
using UnityEditor;
using UnityEngine;

public static class QualityMenu
{
    const int TargetW = 1920;
    const int TargetH = 1080;

    [MenuItem("Tools/My World/画面：切清晰模式（1080p + PC 画质）", false, 71)]
    public static void Apply()
    {
        // 1) 质量档
        int pc = -1;
        var names = QualitySettings.names;
        for (int i = 0; i < names.Length; i++)
            if (names[i] == "PC") { pc = i; break; }
        if (pc < 0)
            Debug.LogError("[QualityMenu] 找不到 PC 质量档，只处理分辨率。");
        else
            QualitySettings.SetQualityLevel(pc, true);

        // 2) Game 视图分辨率
        try
        {
            SetGameViewSize(TargetW, TargetH, TargetW + "x" + TargetH + " 清晰");
            Debug.Log("[QualityMenu] Game 视图已设为 " + TargetW + "×" + TargetH +
                      "，质量档 = " + (pc >= 0 ? names[pc] : "未变"));
        }
        catch (Exception e)
        {
            Debug.LogError("[QualityMenu] 设置 Game 视图分辨率失败：" + e.Message +
                           "\n可以手动在 Game 视图左上角的下拉里选 1920x1080。");
        }

        // 3) 进 Play 时自动最大化 Game 视图
        //    这是"看起来糊"最常见的原因：Game 视图缩在布局里只有 630×354，
        //    渲染分辨率就是这么点，再被拉伸铺满面板，当然糊。
        //    最大化后渲染尺寸跟着窗口走，直接变成 1080p。
        try
        {
            var gvType = typeof(Editor).Assembly.GetType("UnityEditor.GameView");
            var win = EditorWindow.GetWindow(gvType);
            var prop = gvType.GetProperty("maximizeOnPlay",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic |
                System.Reflection.BindingFlags.Instance);
            if (prop != null) prop.SetValue(win, true, null);
            Debug.Log("[QualityMenu] 已打开「进 Play 自动最大化 Game 视图」"
                      + (prop == null ? "（属性找不到，请手动最大化 Game 视图）" : ""));
        }
        catch (Exception e)
        {
            Debug.LogError("[QualityMenu] 设置自动最大化失败：" + e.Message);
        }
    }

    /// <summary>通过反射调 Unity 内部的 GameViewSizes（没有公开 API）。</summary>
    static void SetGameViewSize(int width, int height, string label)
    {
        var asm = typeof(Editor).Assembly;
        var sizesType = asm.GetType("UnityEditor.GameViewSizes");
        var sizeType = asm.GetType("UnityEditor.GameViewSize");
        var sizeEnumType = asm.GetType("UnityEditor.GameViewSizeType");
        var gameViewType = asm.GetType("UnityEditor.GameView");

        if (sizesType == null || sizeType == null || sizeEnumType == null || gameViewType == null)
            throw new Exception("Unity 内部类型找不到（GameViewSizes / GameViewSize / GameViewSizeType / GameView）");

        var singletonType = typeof(ScriptableSingleton<>).MakeGenericType(sizesType);
        var instance = singletonType.GetProperty("instance").GetValue(null, null);
        var group = sizesType.GetProperty("currentGroup").GetValue(instance, null);

        var ctor = sizeType.GetConstructor(new[] { sizeEnumType, typeof(int), typeof(int), typeof(string) });
        var newSize = ctor.Invoke(new object[]
        {
            Enum.Parse(sizeEnumType, "FixedResolution"), width, height, label
        });

        var addCustomSize = group.GetType().GetMethod("AddCustomSize");
        addCustomSize.Invoke(group, new[] { newSize });

        var getTotalCount = group.GetType().GetMethod("GetTotalCount");
        var getGameViewSize = group.GetType().GetMethod("GetGameViewSize");
        int total = (int)getTotalCount.Invoke(group, null);

        int idx = -1;
        for (int i = 0; i < total; i++)
        {
            var gvs = getGameViewSize.Invoke(group, new object[] { i });
            var w = (int)gvs.GetType().GetProperty("width").GetValue(gvs, null);
            var h = (int)gvs.GetType().GetProperty("height").GetValue(gvs, null);
            if (w == width && h == height) { idx = i; break; }
        }
        if (idx < 0) throw new Exception("刚加的分辨率没找到");

        var gameView = EditorWindow.GetWindow(gameViewType);
        gameViewType.GetProperty("selectedSizeIndex").SetValue(gameView, idx);
        gameView.Repaint();
    }
}
