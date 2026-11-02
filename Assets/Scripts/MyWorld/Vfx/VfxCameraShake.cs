using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld
{
    /// <summary>
    /// **相机微震**：以「附加组件」的方式叠加在相机上，**不改 TopDownCameraRig**（那个文件归 Lead）。
    ///
    /// 关键点：TopDownCameraRig 在 LateUpdate 里每帧把相机摆到跟随位置，
    /// 所以震屏位移不能写进相机自身状态（会被下一帧覆盖），也不能在 LateUpdate 里叠加（顺序不确定）。
    /// 这里挂到 SRP 的 beginCameraRendering / endCameraRendering 上：
    /// 渲染前在相机最终位置上叠加偏移 + 轻微 roll，渲染后立刻还原 → 跟随逻辑完全不受影响。
    /// 用 Time.unscaledTime 驱动噪声 → 顿帧（timeScale≈0）时震屏仍然在动。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxCameraShake : MonoBehaviour
    {
        Camera cam;

        float amplitude;      // 米
        float remain;         // 剩余秒（unscaled）
        float total;          // 本次总时长（unscaled），用于衰减曲线
        float frequency = 26f;
        float seed;

        Vector3 lastOffset;
        float lastRoll;
        bool applied;
        bool offsetApplied;   // 这一帧到底加过位移没有（FOV-only 的帧不能去减上一次的 offset）

        // ---- FOV 推近（重击/暴击的"镜头怼一下"）----
        // 与震动同理：不能直接改相机 FOV（TopDownCameraRig 归 Lead，可能每帧覆盖），
        // 所以在 beginCameraRendering 里改、endCameraRendering 里立刻还原。
        float fovPush;        // 峰值推近多少度
        float fovRemain;      // 剩余秒（unscaled）
        float fovTotal;       // 本次总时长
        float lastFovDelta;   // 这一帧实际改了多少度，用于精确还原

        // ---------------- QA 只读观测点（不参与震动计算） ----------------
        //
        // `Tools/VFX QA` 用它**客观断言**"命中真的震了屏、而且越重的一下震得越狠"，
        // 而不是靠人眼看截图猜。生产代码不读这几个值。

        /// <summary>本次震动的峰值幅度（米）。</summary>
        public float PeakAmplitude { get; private set; }

        /// <summary>当前剩余震动时间（秒，unscaled）。</summary>
        public float Remaining => remain;

        /// <summary>峰值幅度的历史最大值（由 QA 在每段采样前 `ResetPeak` 清零）。</summary>
        public void ResetPeak() { PeakAmplitude = 0f; }

        void Awake()
        {
            cam = GetComponent<Camera>();
            seed = Random.value * 100f;
            if (cam == null) enabled = false;
        }

        void OnEnable()
        {
            RenderPipelineManager.beginCameraRendering += OnBeginCameraRendering;
            RenderPipelineManager.endCameraRendering += OnEndCameraRendering;
            // 兼容 Built-in 管线（URP 下不会触发，留着无副作用）
            Camera.onPreCull += OnPreCullCamera;
            Camera.onPostRender += OnPostRenderCamera;
        }

        void OnDisable()
        {
            RenderPipelineManager.beginCameraRendering -= OnBeginCameraRendering;
            RenderPipelineManager.endCameraRendering -= OnEndCameraRendering;
            Camera.onPreCull -= OnPreCullCamera;
            Camera.onPostRender -= OnPostRenderCamera;
            Restore();
        }

        /// <summary>叠加一次震动（同时有多次时取较大振幅，不会无限累积）。</summary>
        public void Add(float shakeAmplitude, float durationSeconds)
        {
            if (shakeAmplitude <= 0f || durationSeconds <= 0f) return;
            amplitude = Mathf.Max(amplitude, shakeAmplitude);
            if (amplitude > PeakAmplitude) PeakAmplitude = amplitude;
            remain = Mathf.Max(remain, durationSeconds);
            total = Mathf.Max(total, remain);
        }

        /// <summary>
        /// **FOV 推近**：重击/暴击时把镜头轻微"怼"一下再弹回。
        /// 幅度单位是**度**（例：30° FOV 上怼 1.2° 已经很明显），同一次命中多次调用取较大值。
        /// </summary>
        public void PushIn(float degrees, float durationSeconds)
        {
            if (degrees <= 0f || durationSeconds <= 0f) return;
            fovPush = Mathf.Max(fovPush, degrees);
            fovRemain = Mathf.Max(fovRemain, durationSeconds);
            fovTotal = Mathf.Max(fovTotal, fovRemain);
        }

        /// <summary>当前 FOV 推近的剩余时间（秒，unscaled），供 QA 断言。</summary>
        public float PushRemaining => fovRemain;

        /// <summary>强制停止并还原。</summary>
        public void Stop()
        {
            Restore();
            amplitude = 0f;
            remain = 0f;
            total = 0f;
            fovPush = 0f;
            fovRemain = 0f;
            fovTotal = 0f;
            lastFovDelta = 0f;
        }

        public bool IsShaking
        {
            get { return remain > 0f; }
        }

        void Update()
        {
            float dt = Time.unscaledDeltaTime;

            if (remain > 0f)
            {
                remain -= dt;
                if (remain <= 0f)
                {
                    remain = 0f;
                    amplitude = 0f;
                    total = 0f;
                }
            }

            // FOV 推近独立计时：只震屏不推近、或只推近不震屏，两种都要能单独工作
            if (fovRemain > 0f)
            {
                fovRemain -= dt;
                if (fovRemain <= 0f)
                {
                    fovRemain = 0f;
                    fovPush = 0f;
                    fovTotal = 0f;
                }
            }
        }

        // ---------- SRP ----------
        void OnBeginCameraRendering(ScriptableRenderContext context, Camera camera)
        {
            if (camera == cam) Apply();
        }

        void OnEndCameraRendering(ScriptableRenderContext context, Camera camera)
        {
            if (camera == cam) Restore();
        }

        // ---------- Built-in 兼容 ----------
        void OnPreCullCamera(Camera camera)
        {
            if (camera == cam) Apply();
        }

        void OnPostRenderCamera(Camera camera)
        {
            if (camera == cam) Restore();
        }

        void Apply()
        {
            if (cam == null) return;
            if (applied) Restore();

            bool did = false;

            // 1) 位移 + roll 微震
            if (remain > 0f)
            {
                float k = total > 0f ? Mathf.Clamp01(remain / total) : 0f;
                float a = amplitude * k * k;   // 二次衰减，收尾干脆
                if (a > 0.00001f)
                {
                    float now = Time.unscaledTime * frequency + seed;
                    float nx = Mathf.PerlinNoise(now, seed) * 2f - 1f;
                    float ny = Mathf.PerlinNoise(seed, now) * 2f - 1f;

                    Transform tr = cam.transform;
                    lastOffset = tr.right * (nx * a) + tr.up * (ny * a * 0.8f);
                    lastRoll = nx * a * 0.9f;

                    tr.position += lastOffset;
                    tr.rotation = tr.rotation * Quaternion.Euler(0f, 0f, lastRoll);
                    offsetApplied = true;
                    did = true;
                }
            }

            // 2) FOV 推近（重击/暴击）
            if (fovRemain > 0f && fovPush > 0f)
            {
                float fk = fovTotal > 0f ? Mathf.Clamp01(fovRemain / fovTotal) : 0f;
                float d = fovPush * fk * fk;
                if (d > 0.00001f)
                {
                    cam.fieldOfView -= d;
                    lastFovDelta = d;
                    did = true;
                }
                else lastFovDelta = 0f;
            }

            applied = did;
        }

        void Restore()
        {
            if (!applied || cam == null) return;

            // 位移只在**这一帧真的加过**的时候才减：只做 FOV 推近的帧，
            // lastOffset 还是上一帧的残留值，无脑减会让相机一路漂走。
            if (offsetApplied)
            {
                Transform tr = cam.transform;
                tr.position -= lastOffset;
                tr.rotation = tr.rotation * Quaternion.Euler(0f, 0f, -lastRoll);
                offsetApplied = false;
            }

            if (lastFovDelta > 0.00001f)
            {
                cam.fieldOfView += lastFovDelta;
                lastFovDelta = 0f;
            }

            applied = false;
        }
    }
}
