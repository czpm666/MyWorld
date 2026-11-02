using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **冲击环 / 盾弧池**：用一小组 LineRenderer 画「会扩散淡出的环」或「面向攻击者的弧」。
    ///
    /// 为什么不用粒子：冲击环需要**精确的平面朝向**（沿命中法线 / 沿攻击者方向），
    /// LineRenderer 每帧重算点位比粒子便宜且可控；40 个环全部预建、循环复用，跑起来零 Instantiate。
    /// </summary>
    public sealed class VfxRingPool : MonoBehaviour
    {
        const int MaxRings = 40;

        sealed class Ring
        {
            public GameObject Go;
            public LineRenderer Lr;
            public Vector3[] Points;
            public Vector3 Center;
            public Vector3 AxisX;
            public Vector3 AxisY;
            public float R0;
            public float R1;
            public float Life;
            public float Age;
            public float Width;
            public float ArcDegrees;
            public Color Color;
            public int Segments;
            public bool Arc;
            public bool Active;
        }

        readonly Ring[] rings = new Ring[MaxRings];
        Material material;

        public int ActiveCount
        {
            get
            {
                int n = 0;
                for (int i = 0; i < rings.Length; i++) if (rings[i] != null && rings[i].Active) n++;
                return n;
            }
        }

        void Awake()
        {
            material = PlaceholderArt.GetVertexColorMaterial();
            if (material == null) material = PlaceholderArt.GetGlowMaterial();

            for (int i = 0; i < MaxRings; i++)
            {
                var go = new GameObject("VfxRing#" + i);
                go.transform.SetParent(transform, false);

                var lr = go.AddComponent<LineRenderer>();
                lr.useWorldSpace = true;
                lr.loop = false;
                lr.positionCount = 0;
                lr.material = material;
                lr.startWidth = 0.06f;
                lr.endWidth = 0.06f;
                lr.numCapVertices = 2;
                lr.numCornerVertices = 0;
                lr.textureMode = LineTextureMode.Stretch;
                lr.alignment = LineAlignment.View;
                lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                lr.receiveShadows = false;
                lr.sortingOrder = 30;
                lr.generateLightingData = false;

                go.SetActive(false);
                rings[i] = new Ring { Go = go, Lr = lr, Active = false };
            }
        }

        Ring Acquire()
        {
            for (int i = 0; i < rings.Length; i++)
            {
                if (!rings[i].Active) return rings[i];
            }
            // 全忙：抢最老的（环形缓冲），保证永远不 Instantiate
            Ring oldest = rings[0];
            for (int i = 1; i < rings.Length; i++)
            {
                if (rings[i].Age > oldest.Age) oldest = rings[i];
            }
            return oldest;
        }

        /// <summary>扩散环（默认躺在 normal 所在平面）。</summary>
        public void PlayRing(Vector3 position, Vector3 normal, float radiusStart, float radiusEnd,
            Color color, float life, float width)
        {
            if (normal.sqrMagnitude < 1e-4f) normal = Vector3.up;
            normal.Normalize();

            Vector3 axisX = Vector3.ProjectOnPlane(Vector3.forward, normal);
            if (axisX.sqrMagnitude < 1e-3f) axisX = Vector3.ProjectOnPlane(Vector3.right, normal);
            axisX.Normalize();
            Vector3 axisY = Vector3.Cross(normal, axisX);

            Ring r = Acquire();
            Begin(r, position, axisX, axisY, radiusStart, radiusEnd, color, life, width, 40, false, 0f);
        }

        /// <summary>竖直弧（盾格挡 / 法术起源的弧形光），弧心朝上、平面正对 toTarget。</summary>
        public void PlayArc(Vector3 anchor, Vector3 toTarget, float radius, float arcDegrees,
            Color color, float life, float width)
        {
            Vector3 flat = new Vector3(toTarget.x, 0f, toTarget.z);
            if (flat.sqrMagnitude < 1e-4f) flat = Vector3.forward;
            flat.Normalize();

            // 弧所在平面：right = up × forward（水平），up = 世界竖直 → 弧呈"∩"形罩在目标方向
            Vector3 right = Vector3.Cross(Vector3.up, flat);
            Vector3 up = Vector3.Cross(flat, right);

            Ring r = Acquire();
            Begin(r, anchor, right, up, radius, radius, color, life, width, 22, true, arcDegrees);
        }

        void Begin(Ring r, Vector3 center, Vector3 axisX, Vector3 axisY,
            float r0, float r1, Color color, float life, float width, int segments, bool arc, float arcDegrees)
        {
            if (segments < 3) segments = 3;

            r.Center = center;
            r.AxisX = axisX;
            r.AxisY = axisY;
            r.R0 = r0;
            r.R1 = r1;
            r.Color = color;
            r.Life = Mathf.Max(0.02f, life);
            r.Age = 0f;
            r.Width = Mathf.Max(0.005f, width);
            r.Arc = arc;
            r.ArcDegrees = arcDegrees;
            r.Segments = segments;
            r.Active = true;
            r.Go.SetActive(true);

            if (r.Points == null || r.Points.Length != segments + 1)
                r.Points = new Vector3[segments + 1];
            r.Lr.positionCount = segments + 1;
            r.Lr.widthMultiplier = 1f;
            r.Lr.startWidth = width;
            r.Lr.endWidth = width;
            r.Lr.startColor = color;
            r.Lr.endColor = color;

            // 立即写一次点，避免第一帧在原点闪一下
            ApplyPoints(r, 0f, color);
        }

        void ApplyPoints(Ring r, float t, Color color)
        {
            float radius = Mathf.Lerp(r.R0, r.R1, EaseOutQuad(t));
            int n = r.Segments;
            Vector3[] pts = r.Points;

            if (r.Arc)
            {
                float half = r.ArcDegrees * 0.5f * Mathf.Deg2Rad;
                for (int i = 0; i <= n; i++)
                {
                    float a = -half + (2f * half) * (i / (float)n);
                    pts[i] = r.Center + r.AxisX * (Mathf.Sin(a) * radius) + r.AxisY * (Mathf.Cos(a) * radius);
                }
            }
            else
            {
                for (int i = 0; i <= n; i++)
                {
                    float a = (i / (float)n) * Mathf.PI * 2f;
                    pts[i] = r.Center + r.AxisX * (Mathf.Cos(a) * radius) + r.AxisY * (Mathf.Sin(a) * radius);
                }
            }

            r.Lr.SetPositions(pts);
            float alpha = Mathf.Clamp01(color.a) * (1f - t * t);
            Color c = new Color(color.r, color.g, color.b, alpha);
            r.Lr.startColor = c;
            r.Lr.endColor = c;
        }

        void Update()
        {
            float dt = Time.deltaTime;
            for (int i = 0; i < rings.Length; i++)
            {
                Ring r = rings[i];
                if (r == null || !r.Active) continue;

                r.Age += dt;
                float t = r.Age / r.Life;
                if (t >= 1f)
                {
                    r.Active = false;
                    r.Go.SetActive(false);
                    continue;
                }

                // 宽度随时间收细（视觉上是"能量散掉"）
                r.Lr.widthMultiplier = 1f - 0.6f * t;
                ApplyPoints(r, t, r.Color);
            }
        }

        static float EaseOutQuad(float t)
        {
            return 1f - (1f - t) * (1f - t);
        }
    }
}
