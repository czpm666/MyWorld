using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 抬画质：工程里有两个质量档（Mobile / PC），而编辑器里当前选中是 **Mobile** ——
    /// PC 档才有 MSAA 4、更高阴影质量。Play 时如果还挂在 Mobile 上，画面会明显发糊发平。
    ///
    /// 用 RuntimeInitializeOnLoadMethod 在**场景加载前**统一切到 PC 档：
    /// 不依赖编辑器当前设置，也不改任何既有脚本，打包和编辑器里行为一致。
    /// 找不到 PC 档就保持原样，不报错（别的工程也能用）。
    /// </summary>
    public static class QualityBootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Apply()
        {
            var names = QualitySettings.names;
            if (names == null || names.Length == 0) return;

            int pc = -1;
            for (int i = 0; i < names.Length; i++)
            {
                if (names[i] == "PC") { pc = i; break; }
            }

            if (pc >= 0 && QualitySettings.GetQualityLevel() != pc)
            {
                QualitySettings.SetQualityLevel(pc, true);
                Debug.Log("[My World] 画质档已切到 PC（MSAA / 阴影质量提升）");
            }
        }
    }
}
