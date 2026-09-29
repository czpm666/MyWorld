using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 挂在木桩头顶的世界空间血条：背景条 + 填充条两块方片，
    /// 每帧转向相机（billboard），并按血量缩放填充条。
    ///
    /// 用两块缩放过的立方体而不是 UI Canvas：3D 场景里不需要额外的事件系统/Canvas，
    /// 也不会有 UI 与 3D 的排序问题。
    /// </summary>
    [DisallowMultipleComponent]
    public class HealthBar : MonoBehaviour
    {
        [SerializeField] private float width = 1.3f;
        [SerializeField] private float height = 0.16f;
        [SerializeField] private Vector3 offset = new Vector3(0f, 0.3f, 0f);

        // 这两个引用必须序列化：烘焙后场景重载时要从场景文件恢复，
        // 否则运行时它们是 null，血条既不会转向相机也不会更新填充。
        [SerializeField] private Transform barRoot;
        [SerializeField] private Transform fill;

        private Camera cam;

        private void Awake()
        {
            // 兜底：万一引用没存下来，按名字找回。
            if (barRoot == null) barRoot = transform.Find("Bar");
            if (fill == null && barRoot != null) fill = barRoot.Find("Fill");
        }

        public static HealthBar Attach(Transform parent, float topY, Color fillColor)
        {
            var go = new GameObject("HealthBar");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = new Vector3(0f, topY, 0f);

            var hb = go.AddComponent<HealthBar>();
            hb.Build(fillColor);
            return hb;
        }

        private void Build(Color fillColor)
        {
            barRoot = new GameObject("Bar").transform;
            barRoot.SetParent(transform, false);

            var bgMat = PlaceholderArt.NewLit(new Color(0.10f, 0.10f, 0.12f), 0.0f);
            bgMat.name = "M_HealthBarBG";
            var fillMat = PlaceholderArt.NewLit(fillColor, 0.0f);
            fillMat.name = "M_HealthBarFill";

            var bg = GameObject.CreatePrimitive(PrimitiveType.Cube);
            bg.name = "BG";
            bg.transform.SetParent(barRoot, false);
            bg.transform.localScale = new Vector3(width, height, 0.02f);
            PlaceholderArt.StripCollider(bg);
            bg.GetComponent<Renderer>().sharedMaterial = bgMat;

            var f = GameObject.CreatePrimitive(PrimitiveType.Cube);
            f.name = "Fill";
            f.transform.SetParent(barRoot, false);
            f.transform.localScale = new Vector3(width * 0.96f, height * 0.62f, 0.03f);
            PlaceholderArt.StripCollider(f);
            f.GetComponent<Renderer>().sharedMaterial = fillMat;
            fill = f.transform;
            // 稍微往相机那侧推一点。barRoot 会转向相机（本地 +Z 指向画面深处），
            // 所以负 Z 才是靠近相机的一侧，不然填充条和背景条共面会 z-fighting。
            f.transform.localPosition = new Vector3(0f, 0f, -0.02f);

            barRoot.localPosition = offset;
        }

        /// <summary>fraction 0..1</summary>
        public void SetFill(float fraction)
        {
            if (fill == null) return;

            fraction = Mathf.Clamp01(fraction);

            // 从左边开始缩，而不是从中心缩，读起来才像进度条
            float fullWidth = width * 0.96f;
            var s = fill.localScale;
            s.x = fullWidth * fraction;
            fill.localScale = s;

            var p = fill.localPosition;
            p.x = -(fullWidth - s.x) * 0.5f;
            fill.localPosition = p;

            fill.gameObject.SetActive(fraction > 0.001f);
        }

        private void LateUpdate()
        {
            if (cam == null) cam = Camera.main;
            if (cam == null || barRoot == null) return;

            // 面向相机：用相机的旋转而不是 LookAt，这样条不会被透视拉斜
            barRoot.rotation = cam.transform.rotation;
        }
    }
}
