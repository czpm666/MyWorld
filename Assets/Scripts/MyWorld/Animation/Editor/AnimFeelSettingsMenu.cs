#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;

namespace MyWorld.EditorTools
{
    /// <summary>
    /// 动画手感参数的**入口菜单**：`Tools > My World > 动画手感参数`。
    ///
    /// 第一次点会自动创建 `Assets/Scripts/MyWorld/Animation/Resources/AnimFeelSettings.asset`
    /// （字段值 = <see cref="AnimFeelSettings"/> 里写的代码默认值），之后每次都是选中它，
    /// 在 Inspector 里直接调、运行时立刻生效。
    ///
    /// ⚠️ 放在 `Assets/Scripts/...` 下的 `Editor/` 子目录里，而不是 `Assets/Editor/` ——
    ///    **不碰 Lead 的 `Assets/Editor/MageSetup.cs`**，也不用重新生成 AnimatorController。
    ///    本文件属于 anim-dev 的写入范围（`Assets/Scripts/MyWorld/Animation/`）。
    /// </summary>
    public static class AnimFeelSettingsMenu
    {
        /// <summary>相对 `Application.dataPath` 的目录（`Resources` 必须叫这个名字，否则 `Resources.Load` 找不到）。</summary>
        private const string RelativeFolder = "Scripts/MyWorld/Animation/Resources";

        private const string AssetPath = "Assets/" + RelativeFolder + "/" + AnimFeelSettings.ResourceName + ".asset";

        [MenuItem("Tools/My World/动画手感参数", priority = 30)]
        public static void Open()
        {
            AnimFeelSettings settings = AssetDatabase.LoadAssetAtPath<AnimFeelSettings>(AssetPath);

            if (settings == null)
            {
                string absoluteFolder = Path.Combine(Application.dataPath, RelativeFolder);
                if (!Directory.Exists(absoluteFolder))
                {
                    Directory.CreateDirectory(absoluteFolder);
                    AssetDatabase.Refresh();
                }

                settings = ScriptableObject.CreateInstance<AnimFeelSettings>();
                AssetDatabase.CreateAsset(settings, AssetPath);
                AssetDatabase.SaveAssets();

                Debug.Log("[My World] 已创建动画手感参数资产（初值 = 代码默认值）：" + AssetPath);
            }

            Selection.activeObject = settings;
            EditorGUIUtility.PingObject(settings);
        }
    }
}
#endif
