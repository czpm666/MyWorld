using System;
using System.IO;
using UnityEngine;

namespace MyWorld.Maps
{
    /// <summary>layout JSON 的根对象。字段名和 Blender 侧导出的 JSON **逐字对应**，别改。</summary>
    [Serializable]
    public class BlenderKitLayout
    {
        public string units = "meters";
        public string blender_axes = "Z-up";
        public BlenderKitPiece[] pieces = new BlenderKitPiece[0];
    }

    /// <summary>一件摆放：`prefab` 是件名（对应 prefab 文件名），`pos`/`rot_z` 是 **Blender 世界坐标**。</summary>
    [Serializable]
    public class BlenderKitPiece
    {
        public string prefab;
        public float[] pos = new float[3];
        public float rot_z;
        /// <summary>可选：实例名。空则用 `prefab`。只影响 Hierarchy 里好不好找。</summary>
        public string name;
    }

    /// <summary>
    /// 把 Blender 导出的 `medieval_layout.json` 实例化成 Unity 场景内容。
    ///
    /// **坐标约定（全项目唯一一处换算，改这里就够了）**
    /// JSON 里是 Blender 世界坐标：右手系、Z 朝上、+Y 是"屏幕里"。
    /// Unity 是 Y 朝上，所以用绕 X 轴 -90° 的纯旋转做映射：
    ///   `unity = (bx, bz, -by)`   —— 行列式 +1，不镜像、不切轴。
    /// 朝向同理推导：Blender 绕 +Z 的 yaw 直接就是 Unity 绕 +Y 的 yaw（**同号**，不取反）：
    ///   取 Blender +X 上的点，绕 Z 转 θ 得 (cosθ, sinθ, 0)，映射后是 (cosθ, 0, -sinθ)；
    ///   而 Unity `Quaternion.Euler(0, θ, 0)` 作用在 +X 上是 (cosθ, 0, -sinθ)。两者恒等 ⇒ 角度不用翻。
    ///   另一个基准：Blender 的 +Y 映射到 Unity 的 -Z，这与 Blender 的"正视图朝 -Y"= Unity 的"朝 +Z"一致。
    ///
    /// ⚠️ 上面这套是**给 layout JSON 用的**。FBX 网格自身的朝向由 Blender 的 FBX 导出器负责（导出时已经
    /// 烧成 Y-up），导入侧不要重复转换 —— 不然会转两次。
    /// </summary>
    public static class BlenderKitMapBuilder
    {
        public const string DefaultLayoutFile = "medieval_layout.json";
        public const string DefaultRootName = "BlenderKit";

        // ---------------------------------------------------------------- 坐标换算

        /// <summary>Blender(Z-up) → Unity(Y-up)。`unity = (bx, bz, -by)`。</summary>
        public static Vector3 BlenderPosToUnity(float bx, float by, float bz)
        {
            return new Vector3(bx, bz, -by);
        }

        /// <summary>同上，向量版。</summary>
        public static Vector3 BlenderPosToUnity(Vector3 blenderZUp)
        {
            return new Vector3(blenderZUp.x, blenderZUp.z, -blenderZUp.y);
        }

        /// <summary>Blender 绕 Z 的 yaw（度）→ Unity 绕 Y 的 yaw（度）。**同号**，见类注释的推导。</summary>
        public static float BlenderYawToUnity(float rotZDegrees)
        {
            return rotZDegrees;
        }

        // ---------------------------------------------------------------- 读 JSON

        public static string LayoutPath(string fileName)
        {
            return Path.Combine(Application.streamingAssetsPath, fileName);
        }

        /// <summary>读 StreamingAssets 下的 layout 文件。失败返回 null 并报错（不抛）。</summary>
        public static BlenderKitLayout LoadLayout(string fileName)
        {
            string path = LayoutPath(fileName);
            if (!File.Exists(path))
            {
                Debug.LogError("[BlenderKit] 找不到布局文件：" + path);
                return null;
            }
            string json;
            try
            {
                json = File.ReadAllText(path, System.Text.Encoding.UTF8);
            }
            catch (Exception e)
            {
                Debug.LogError("[BlenderKit] 读布局文件失败：" + path + " —— " + e.Message);
                return null;
            }
            return ParseLayout(json, fileName);
        }

        /// <summary>解析 + 校验。约定不对时**报错但仍然返回**，让调用方自己决定要不要摆。</summary>
        public static BlenderKitLayout ParseLayout(string json, string label)
        {
            BlenderKitLayout layout;
            try
            {
                layout = JsonUtility.FromJson<BlenderKitLayout>(json);
            }
            catch (Exception e)
            {
                Debug.LogError("[BlenderKit] " + label + " JSON 解析失败：" + e.Message);
                return null;
            }
            if (layout == null)
            {
                Debug.LogError("[BlenderKit] " + label + " JSON 解析结果为空（顶层必须是对象，不能是数组）。");
                return null;
            }

            // 约定漂了就必须吼出来：轴/单位错了会静默地把整座城摆错方向或放大 100 倍。
            if (!string.IsNullOrEmpty(layout.units) && layout.units != "meters")
                Debug.LogError("[BlenderKit] " + label + " 的 units=\"" + layout.units + "\"，本管线只支持 \"meters\"。");
            if (!string.IsNullOrEmpty(layout.blender_axes) && layout.blender_axes != "Z-up")
                Debug.LogError("[BlenderKit] " + label + " 的 blender_axes=\"" + layout.blender_axes + "\"，本管线只支持 \"Z-up\"。");

            if (layout.pieces == null) layout.pieces = new BlenderKitPiece[0];
            return layout;
        }

        // ---------------------------------------------------------------- 生成

        /// <summary>
        /// 读 StreamingAssets 下的布局并生成到 `parent` 下（parent 为 null 则挂在场景根）。
        /// 返回生成的根节点；失败返回 null。根节点始终创建（哪怕是空的）——
        /// 这样地图侧一眼能看出"跑了但没件"，而不是"没跑"。
        /// </summary>
        public static GameObject Build(Transform parent, string fileName = DefaultLayoutFile, string rootName = DefaultRootName)
        {
            var layout = LoadLayout(fileName);
            if (layout == null) return null;
            return Build(parent, layout, fileName, rootName);
        }

        /// <summary>同上，直接用已经解析好的 layout（编辑器预览/测试走这个入口）。</summary>
        public static GameObject Build(Transform parent, BlenderKitLayout layout, string label, string rootName = DefaultRootName)
        {
            if (layout == null) return null;

            var catalog = BlenderKitCatalog.Load();
            if (catalog == null) return null;

            var root = new GameObject(rootName);
            if (parent != null) root.transform.SetParent(parent, false);

            int placed = 0;
            int missing = 0;
            var pieces = layout.pieces ?? new BlenderKitPiece[0];

            for (int i = 0; i < pieces.Length; i++)
            {
                var piece = pieces[i];
                if (piece == null) continue;

                var prefab = catalog.Find(piece.prefab);
                if (prefab == null)
                {
                    missing++;
                    // 只报前几个，避免 3026 件全缺时把 Console 刷爆
                    if (missing <= 5)
                        Debug.LogWarning("[BlenderKit] " + label + " 第 " + i + " 件找不到 prefab：\"" + piece.prefab + "\"");
                    continue;
                }

                var go = UnityEngine.Object.Instantiate(prefab, root.transform);
                go.name = string.IsNullOrEmpty(piece.name) ? piece.prefab : piece.name;
                go.transform.localPosition = BlenderPosToUnity(PiecePos(piece));
                go.transform.localRotation = Quaternion.Euler(0f, BlenderYawToUnity(piece.rot_z), 0f);
                placed++;
            }

            if (missing > 5) Debug.LogWarning("[BlenderKit] " + label + " 另有 " + (missing - 5) + " 件缺 prefab（不再重复报）。");
            Debug.Log("[BlenderKit] " + label + "：放置 " + placed + " 件，缺件 " + missing + "，共 " + pieces.Length + " 条记录。");
            return root;
        }

        private static Vector3 PiecePos(BlenderKitPiece piece)
        {
            if (piece.pos == null || piece.pos.Length < 3)
            {
                Debug.LogWarning("[BlenderKit] 件 \"" + piece.prefab + "\" 的 pos 不足 3 个分量，按原点处理。");
                return Vector3.zero;
            }
            return new Vector3(piece.pos[0], piece.pos[1], piece.pos[2]);
        }

        // ---------------------------------------------------------------- 自检

        /// <summary>
        /// 摆完之后的朝向自检：算每件实例的**世界朝向**和**包围盒**，打一行日志。
        /// 用途是"用真实物体验证朝向"，而不是靠肉眼在截图里猜 ——
        /// 期望值由 Blender 侧的件名/坐标给出，这里只负责把可观测量如实打出来。
        /// </summary>
        public static void LogPlacements(GameObject root, int maxLines = 20)
        {
            if (root == null) { Debug.LogWarning("[BlenderKit] LogPlacements: root 为空。"); return; }

            var renderers = root.GetComponentsInChildren<Renderer>();
            Bounds bounds = new Bounds(root.transform.position, Vector3.zero);
            bool hasBounds = false;
            for (int i = 0; i < renderers.Length; i++)
            {
                if (renderers[i] == null) continue;
                if (!hasBounds) { bounds = renderers[i].bounds; hasBounds = true; }
                else bounds.Encapsulate(renderers[i].bounds);
            }

            var sb = new System.Text.StringBuilder();
            sb.Append("[BlenderKit] 自检：实例 ").Append(root.transform.childCount)
              .Append(" 个，Renderer ").Append(renderers.Length).Append(" 个");
            if (hasBounds)
                sb.Append("，整体包围盒 ").Append(Fmt(bounds.size)).Append("（米），中心 ").Append(Fmt(bounds.center));
            Debug.Log(sb.ToString());

            int lines = 0;
            for (int i = 0; i < root.transform.childCount && lines < maxLines; i++, lines++)
            {
                var child = root.transform.GetChild(i);
                var r = child.GetComponentInChildren<Renderer>();
                string size = r != null ? Fmt(r.bounds.size) : "无 Renderer";
                Debug.Log("[BlenderKit]   " + child.name
                          + "  pos=" + Fmt(child.position)
                          + "  fwd(+Z)=" + Fmt(child.forward)
                          + "  size=" + size);
            }
            if (root.transform.childCount > lines)
                Debug.Log("[BlenderKit]   …另有 " + (root.transform.childCount - lines) + " 个实例未列出。");
        }

        private static string Fmt(Vector3 v)
        {
            return "(" + v.x.ToString("0.###") + ", " + v.y.ToString("0.###") + ", " + v.z.ToString("0.###") + ")";
        }
    }
}
