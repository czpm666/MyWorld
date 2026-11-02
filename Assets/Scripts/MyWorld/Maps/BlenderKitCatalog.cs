using System;
using System.Collections.Generic;
using UnityEngine;

namespace MyWorld.Maps
{
    /// <summary>
    /// Blender kit 的**运行时目录**：名字 → prefab。
    ///
    /// 为什么需要这个中间层：prefab 按约定落在 `Assets/Generated/MedievalKitBlender/Prefabs/`，
    /// 那不在任何 `Resources/` 下，运行时 `Resources.Load` 取不到；而地图是**运行时生成**的
    /// （见 `World/MapBootstrap.cs`），场景里没有序列化引用可以挂 prefab。
    /// ⇒ 编辑器侧把 prefab 列表写进这个 SO，运行时按 layout JSON 里的名字查表。
    /// SO 本身放在 `Assets/Resources/MedievalKitBlender/` 下，它引用的 prefab 会被一起打进包。
    ///
    /// ⚠️ 这个资源由 `Assets/Editor/BlenderKitImporter.cs` 自动生成/刷新，**不要手改**。
    /// </summary>
    public class BlenderKitCatalog : ScriptableObject
    {
        /// <summary>`Resources.Load` 用的路径（不带扩展名）。</summary>
        public const string ResourcePath = "MedievalKitBlender/BlenderKitCatalog";

        [Serializable]
        public struct Entry
        {
            public string name;
            public GameObject prefab;
        }

        public Entry[] entries = new Entry[0];

        private Dictionary<string, GameObject> lookup;

        public int Count => entries != null ? entries.Length : 0;

        /// <summary>按名字取 prefab（大小写不敏感；找不到返回 null，不抛）。</summary>
        public GameObject Find(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            if (lookup == null)
            {
                lookup = new Dictionary<string, GameObject>(StringComparer.OrdinalIgnoreCase);
                if (entries != null)
                {
                    foreach (var e in entries)
                    {
                        if (string.IsNullOrEmpty(e.name) || e.prefab == null) continue;
                        if (!lookup.ContainsKey(e.name)) lookup.Add(e.name, e.prefab);
                    }
                }
            }
            return lookup.TryGetValue(name, out var go) ? go : null;
        }

        /// <summary>目录里所有件的名字（排好序，便于日志/报错时给出候选）。</summary>
        public string[] Names()
        {
            var list = new List<string>();
            if (entries != null)
                foreach (var e in entries)
                    if (!string.IsNullOrEmpty(e.name)) list.Add(e.name);
            list.Sort(StringComparer.OrdinalIgnoreCase);
            return list.ToArray();
        }

        private static BlenderKitCatalog cached;

        /// <summary>
        /// 取目录（带缓存）。缺资源时**只报一次错**并返回 null —— 调用方负责降级，
        /// 不要让整张地图炸掉：这里返回 null 的后果是地图空着，而不是异常。
        /// </summary>
        public static BlenderKitCatalog Load()
        {
            if (cached != null) return cached;
            cached = Resources.Load<BlenderKitCatalog>(ResourcePath);
            if (cached == null)
            {
                Debug.LogError(
                    "[BlenderKitCatalog] 找不到 " + ResourcePath + "（Resources 下）。" +
                    "请先在编辑器里跑菜单 `Tools/My World/导入 Blender Kit` 生成它。");
            }
            return cached;
        }

        /// <summary>清缓存。编辑器重新生成资源之后必须调用，否则会一直用旧的。</summary>
        public static void ClearCache()
        {
            cached = null;
        }
    }
}
