using System.Collections;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **全局特效中枢**（全场景常驻，DontDestroyOnLoad）。
    ///
    /// 职责：
    ///   * 建好所有粒子池 / 冲击环池（进 Play 时用 RuntimeInitializeOnLoadMethod 自动创建，新地图也一样生效）；
    ///   * 提供统一的 `Burst / Flash / Ring / Shake / HitStop` 入口，业务代码（VfxCombat 等）只调这些；
    ///   * 维护「全局粒子预算」：密集战斗时把发射数量按比例降下来，保证 ≤300 active；
    ///   * 顿帧（hitstop）：用 unscaled 计时恢复 Time.timeScale，不破坏暂停（暂停时 timeScale=0 不会被误恢复）。
    ///
    /// 注意：所有粒子池 GameObject 都在本对象下，跨场景不销毁；场景里**不允许**放对旧场景的序列化引用。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxHub : MonoBehaviour
    {
        public static VfxHub Instance { get; private set; }

        public VfxPool Spark { get; private set; }
        public VfxPool Flare { get; private set; }
        public VfxPool Glow { get; private set; }
        public VfxPool Dust { get; private set; }
        public VfxPool Smoke { get; private set; }
        public VfxPool Streak { get; private set; }
        public VfxRingPool Rings { get; private set; }

        /// <summary>伤害飘字池（世界空间 billboard，池化，见 `VfxTextPool`）。</summary>
        public VfxTextPool Text { get; private set; }

        VfxCameraShake shake;
        float cameraScanTimer;

        float hitstopUntil;
        bool hitstopRunning;
        /// <summary>本次顿帧实际冻结到的 `Time.timeScale`（重叠时取更深的一档）。</summary>
        float hitstopDepth = DefaultHitStopDepth;

        int transientFrame = -1;
        int transientUsed;

        /// <summary>累计创建过多少个"一次性特效物体"（月牙/盾弧/感叹号这类必须 new 的）。</summary>
        public static int TransientsCreated { get; private set; }

        /// <summary>当前还活着的一次性特效物体数。**没有回落就是泄漏**（验收标准④的观测量）。</summary>
        public static int TransientsAlive { get; private set; }

        /// <summary>一次性物体被销毁时回报（由 SkillVfx 的四个特效类在 Destroy 前调用）。</summary>
        public static void NoteTransientDestroyed()
        {
            if (TransientsAlive > 0) TransientsAlive--;
        }

        // ---------------- 生命周期 ----------------

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            if (!Application.isPlaying) return;
            Ensure();
        }

        /// <summary>取中枢（没有就自动创建）。Play 之外返回 null。</summary>
        public static VfxHub Ensure()
        {
            if (!Application.isPlaying) return null;
            if (Instance != null) return Instance;

            var go = new GameObject("[VfxHub]");
            DontDestroyOnLoad(go);
            Instance = go.AddComponent<VfxHub>();
            return Instance;
        }

        void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);
            BuildPools();

            // 手感调参面板 + 伤害飘字池。
            // 顺序有讲究：先加 Settings（它的 Awake 会把 Inspector 值写回 VfxFeel 静态表），
            // 再加 TextPool —— 否则飘字池第一次用到 VfxFeel 的表时拿到的还是出厂值。
            if (GetComponent<VfxFeelSettings>() == null) gameObject.AddComponent<VfxFeelSettings>();
            Text = gameObject.AddComponent<VfxTextPool>();

            EnsureShake();
            gameObject.AddComponent<VfxDirector>();   // 事件接线（敌人受击/死亡、金币、玩家血量等）
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void Update()
        {
            // 场景切换后 Camera.main 会变；低频检查并补挂震屏组件
            cameraScanTimer -= Time.unscaledDeltaTime;
            if (cameraScanTimer <= 0f)
            {
                cameraScanTimer = 0.5f;
                EnsureShake();
            }
        }

        void BuildPools()
        {
            var pools = new GameObject("Pools").transform;
            pools.SetParent(transform, false);

            // 火花：拉长条 + 重力，飞行中减速
            Spark = new VfxPool("Spark", pools, VfxMaterials.Streak, true, 300, 0.65f, 0.22f, true, 1.6f);
            // 高光四芒星：命中瞬间 / 拾取
            Flare = new VfxPool("Flare", pools, VfxMaterials.Star, true, 80, 0f, 0f, false);
            // 球形光斑：施法 / 治疗 / 顿帧闪光
            Glow = new VfxPool("Glow", pools, VfxMaterials.Dot, true, 160, 0f, 0f, false);
            // 尘土：落地 / 死亡 / 挥空
            Dust = new VfxPool("Dust", pools, VfxMaterials.Dust, false, 160, -0.03f, 0.55f, false);
            // 烟：少量，燃烧 / 死亡
            Smoke = new VfxPool("Smoke", pools, VfxMaterials.Dust, false, 60, -0.10f, 0.70f, false);
            // 风线：箭矢 / 刀光 / 抓钩（不落地的直线能量条）
            Streak = new VfxPool("Streak", pools, VfxMaterials.Streak, true, 120, 0f, 0.05f, true, 2.4f);

            var ringGo = new GameObject("Rings");
            ringGo.transform.SetParent(transform, false);
            Rings = ringGo.AddComponent<VfxRingPool>();
        }

        // ---------------- 一次性特效配额 ----------------

        /// <summary>
        /// 本帧还能不能再新建一个"一次性特效物体"（月牙刀光 / 盾弧 / 蓄力环 / 感叹号）。
        ///
        /// 为什么需要它：这几类是**必须 new GameObject + LineRenderer** 的（形状每帧变、
        /// 形状表在编辑期就定死，做池化不划算）。正常情况下每秒只有几个，
        /// 但"同屏二十个敌人同时被范围技打中"会一瞬间冒出几十个。
        /// 配额让**最坏情况有上界**，代价是那一帧少数几个月牙不出现 —— 比卡帧划算。
        ///
        /// ⚠️ 粒子（Spark/Flare/…）和飘字**不走这条路**，它们是预建好的池，不受配额限制。
        /// </summary>
        public bool AllowTransient()
        {
            int limit = VfxFeel.MaxTransientPerFrame;
            if (limit <= 0) return false;

            int frame = Time.frameCount;
            if (frame != transientFrame)
            {
                transientFrame = frame;
                transientUsed = 0;
            }

            if (transientUsed >= limit) return false;

            transientUsed++;
            TransientsCreated++;
            TransientsAlive++;
            return true;
        }

        /// <summary>便捷版：取中枢并问一次配额；中枢不存在时返回 false。</summary>
        public static bool RequestTransient()
        {
            VfxHub hub = Ensure();
            return hub != null && hub.AllowTransient();
        }

        // ---------------- 发射入口 ----------------

        /// <summary>当前活跃粒子数（所有池加总，用于性能验收）。</summary>
        public int ActiveParticles
        {
            get
            {
                int n = 0;
                if (Spark != null) n += Spark.Active;
                if (Flare != null) n += Flare.Active;
                if (Glow != null) n += Glow.Active;
                if (Dust != null) n += Dust.Active;
                if (Smoke != null) n += Smoke.Active;
                if (Streak != null) n += Streak.Active;
                return n;
            }
        }

        int Budget(int requested)
        {
            if (requested <= 0) return 0;
            int active = ActiveParticles;
            if (active >= 280) return Mathf.Max(1, requested / 4);
            if (active >= 200) return Mathf.Max(1, requested / 2);
            return requested;
        }

        /// <summary>锥形喷射一批粒子。</summary>
        public void Burst(VfxPool pool, Vector3 position, Vector3 direction, int count,
            float speedMin, float speedMax, float spreadDegrees, Color color,
            float sizeMin, float sizeMax, float lifeMin, float lifeMax,
            float upwardBias = 0f, float jitter = 0.06f)
        {
            if (pool == null) return;
            count = Budget(count);
            if (count <= 0) return;

            Vector3 dir = direction.sqrMagnitude > 1e-6f ? direction.normalized : Vector3.up;
            float spread = Mathf.Clamp(spreadDegrees, 0f, 180f) / 180f;

            for (int i = 0; i < count; i++)
            {
                Vector3 randomDir = Random.onUnitSphere;
                Vector3 d = Vector3.Slerp(dir, randomDir, Random.Range(0f, 1f) * spread).normalized;
                float speed = Random.Range(speedMin, speedMax);
                Vector3 pos = position + Random.insideUnitSphere * jitter;
                Vector3 vel = d * speed;
                if (upwardBias != 0f) vel.y += upwardBias;

                float hot = Random.Range(0f, 0.35f);
                Color c = Color.Lerp(color, Color.white, hot);
                c.a *= Random.Range(0.55f, 1f);

                pool.Emit(pos, vel, c, Random.Range(sizeMin, sizeMax), Random.Range(lifeMin, lifeMax));
            }
        }

        /// <summary>单颗大光斑（命中高光 / 施法闪光）。</summary>
        public void Flash(Vector3 position, Color color, float size, float lifetime)
        {
            if (Glow == null) return;
            Glow.Emit(position, Vector3.zero, color, size, lifetime);
        }

        /// <summary>四芒星闪一下（单颗粒子）。</summary>
        public void FlareBurst(VfxPool pool, Vector3 position, Color color, float size, float lifetime)
        {
            if (pool != null) pool.Emit(position, Vector3.zero, color, size, lifetime);
        }

        /// <summary>扩散冲击环（沿 normal 平面）。</summary>
        public void Ring(Vector3 position, Vector3 normal, float startRadius, float endRadius,
            Color color, float lifetime, float width)
        {
            if (Rings != null) Rings.PlayRing(position, normal, startRadius, endRadius, color, lifetime, width);
        }

        /// <summary>竖直光弧（盾格挡 / 施法正面弧）。</summary>
        public void Arc(Vector3 anchor, Vector3 toTarget, float radius, float arcDegrees,
            Color color, float lifetime, float width)
        {
            if (Rings != null) Rings.PlayArc(anchor, toTarget, radius, arcDegrees, color, lifetime, width);
        }

        // ---------------- 相机震动 ----------------

        /// <summary>确保主相机上有 VfxCameraShake；相机换了会自动补。</summary>
        public VfxCameraShake EnsureShake()
        {
            if (shake != null) return shake;
            Camera mainCam = Camera.main;
            if (mainCam == null) return null;

            shake = mainCam.GetComponent<VfxCameraShake>();
            if (shake == null) shake = mainCam.gameObject.AddComponent<VfxCameraShake>();
            return shake;
        }

        /// <summary>相机微震（振幅单位米；0.1 左右就很明显）。</summary>
        public void AddShake(float amplitude, float duration)
        {
            VfxCameraShake s = EnsureShake();
            if (s != null) s.Add(amplitude, duration);
        }

        public static void Shake(float amplitude, float duration)
        {
            VfxHub hub = Ensure();
            if (hub != null) hub.AddShake(amplitude, duration);
        }

        /// <summary>
        /// **FOV 推近**（重击/暴击的"镜头怼一下"）。单位是**度**，例：30° FOV 上怼 1.2° 已很明显。
        /// 同样是渲染前施加、渲染后还原，不会和 `TopDownCameraRig` 抢相机状态。
        /// </summary>
        public void AddPushIn(float degrees, float duration)
        {
            VfxCameraShake s = EnsureShake();
            if (s != null) s.PushIn(degrees, duration);
        }

        public static void PushIn(float degrees, float duration)
        {
            VfxHub hub = Ensure();
            if (hub != null) hub.AddPushIn(degrees, duration);
        }

        // ---------------- 顿帧（hitstop） ----------------

        /// <summary>默认顿帧深度（调用方不传 depth 时用这一档，等价于旧版的 0.06）。</summary>
        public const float DefaultHitStopDepth = 0.06f;

        /// <summary>
        /// 打击顿帧：把 Time.timeScale 压到 <see cref="DefaultHitStopDepth"/> 持续 seconds 秒（真实时间），然后恢复。
        /// 用 unscaled 计时；外部暂停（timeScale=0）时不会被本功能擅自恢复。
        /// </summary>
        public static void HitStop(float seconds)
        {
            HitStop(seconds, DefaultHitStopDepth);
        }

        /// <summary>
        /// 带**深度**的顿帧。<paramref name="depth"/> 是 `Time.timeScale` 要被压到的值，
        /// **越小顿得越死** —— 轻击 0.10 只是"卡一下"，暴击 0.035 才是"整个世界一顿"。
        /// 分级表见 <c>VfxFeel.HitStopDepth</c> / <c>VfxFeel.HitStopDepthFor(grade)</c>。
        /// </summary>
        public static void HitStop(float seconds, float depth)
        {
            if (!Application.isPlaying || seconds <= 0f) return;
            VfxHub hub = Ensure();
            if (hub == null) return;

            depth = Mathf.Clamp(depth, 0.005f, 1f);
            hub.hitstopUntil = Mathf.Max(hub.hitstopUntil, Time.unscaledTime + Mathf.Min(seconds, 0.12f));
            // 重叠时取**更深**的一档：重击压过轻击，别让随后的一记轻击把暴击的深度抬回去
            hub.hitstopDepth = hub.hitstopRunning ? Mathf.Min(hub.hitstopDepth, depth) : depth;
            if (!hub.hitstopRunning)
            {
                hub.StartCoroutine(hub.HitStopRoutine());
            }
        }

        IEnumerator HitStopRoutine()
        {
            hitstopRunning = true;
            float restoreScale = Time.timeScale > 0.001f ? Time.timeScale : 1f;
            float lastWritten = float.NaN;

            while (Time.unscaledTime < hitstopUntil)
            {
                float depth = hitstopDepth;     // 每帧重读：协程运行期间可能又叠了一记更深的
                float current = Time.timeScale;
                // "外部改动"的判定必须排除两种自己人：本帧要写的 depth、上一帧自己写下去的 lastWritten。
                // 少了后半个条件，中途加重深度时会把"上一档深度"误认成外部倍速，结束时恢复成错的值。
                bool ours = Mathf.Approximately(current, depth)
                            || (!float.IsNaN(lastWritten) && Mathf.Approximately(current, lastWritten));
                // 外部主动改了倍速（例如慢动作/暂停）→ 以外部为准，结束时恢复它
                if (current > 0.001f && !ours)
                {
                    restoreScale = current;
                }
                Time.timeScale = depth;
                lastWritten = depth;
                yield return null;
            }

            // 只在自己还压着的时候才恢复，别覆盖外部在顿帧期间做的改动
            if (!float.IsNaN(lastWritten) && Mathf.Approximately(Time.timeScale, lastWritten))
            {
                Time.timeScale = restoreScale;
            }
            hitstopDepth = DefaultHitStopDepth;
            hitstopRunning = false;
        }
    }
}
