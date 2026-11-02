using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// NPC 待机「活着」组件 —— 拆掉 18 个 NPC 的复制品感。
    ///
    /// 为什么需要它：RoaTown 的 18 个 NPC 共用同一个预制体，Idle 是同一个剪辑、
    /// 同一个循环起点，于是所有人同相位同步呼吸，一眼看上去像 18 个复制品。
    /// 这个组件只做四件事：
    ///   1. 随机 Idle 起始相位 + 播放速率抖动 → 18 个人各呼吸各的；
    ///   2. 玩家不在附近时缓慢左右张望；
    ///   3. 玩家在视野内时每 6~18 秒随机抬手比划一下（需要控制器有 Talk 参数）；
    ///   4. 万一没有可用的 Animator（例如没跑过生成菜单），退化成程序化呼吸起伏。
    ///
    /// 分工：转向玩家是 <c>World/NpcActor.cs</c> 的职责，本组件刻意不抢 —— 玩家在
    /// <see cref="handoverRadius"/> 以内时本组件完全不写 rotation，玩家走远后才接管张望，
    /// 接管的那一帧会先把当前朝向收编成新基准，所以不会出现「回头跳一下」。
    /// 本组件也不写 Speed 参数、不做位移。
    ///
    /// 参数用 [SerializeField] 而不是集中到 AnimFeelSettings：这是**新组件**，
    /// 还没有任何场景/预制体序列化过它，默认值一定能生效（老组件改默认值无效的坑不适用）。
    /// </summary>
    [DisallowMultipleComponent]
    public class NpcIdleLife : MonoBehaviour
    {
        private const string IdleStateName = "Idle";
        private const string TalkTriggerName = "Talk";

        private static readonly int IdleHash = Animator.StringToHash(IdleStateName);
        private static readonly int TalkHash = Animator.StringToHash(TalkTriggerName);

        // ── 待机呼吸 ────────────────────────────────────────────────
        [Header("待机呼吸（拆同步）")]
        [Tooltip("每个 NPC 的 Idle/Talk 播放速率随机范围。全都 1.0 会让 18 个人呼吸同拍。")]
        [SerializeField] private Vector2 playbackRange = new Vector2(0.90f, 1.12f);

        // ── 张望 ────────────────────────────────────────────────────
        [Header("张望（玩家走远时）")]
        [Tooltip("玩家进到这个半径以内就交出转向权，交给 NpcActor 的「面向玩家」逻辑；要比 NpcActor 的 5 米大一点。")]
        [SerializeField] private float handoverRadius = 5.6f;
        [Tooltip("两次改变张望目标的间隔（秒，随机区间）。")]
        [SerializeField] private Vector2 scanGapRange = new Vector2(3f, 9f);
        [Tooltip("张望的最大偏转角度（度）。")]
        [SerializeField] private float scanAngle = 42f;
        [Tooltip("转头速度（度/秒）。给小一点才像在看，不像在扫射。")]
        [SerializeField] private float scanSpeed = 32f;

        // ── 手势 ────────────────────────────────────────────────────
        [Header("说话手势（需要控制器有 Talk 参数）")]
        [Tooltip("两次自发手势的间隔（秒，随机区间）。")]
        [SerializeField] private Vector2 gestureGapRange = new Vector2(6f, 18f);
        [Tooltip("玩家在这个半径内才值得比划；更远的时候比划没人看得见，纯浪费。")]
        [SerializeField] private float gestureNoticeRange = 10f;
        [Tooltip("玩家走到这个半径内算「凑近了」，额外触发一次招呼手势。")]
        [SerializeField] private float greetRadius = 4f;
        [Tooltip("招呼手势的冷却（秒），免得玩家在边上蹭来蹭去把 NPC 变成招财猫。")]
        [SerializeField] private float greetCooldown = 14f;
        [Tooltip("手势剪辑的大致时长（秒）。这段时间内不再叠新触发，避免 Talk 状态被反复重启。")]
        [SerializeField] private float gestureHoldSeconds = 1.4f;

        // ── 无骨骼/无控制器兜底 ─────────────────────────────────────
        [Header("兜底程序化呼吸（没有可用 Animator 时）")]
        [Tooltip("上下起伏幅度（米）。只做 2 厘米级别，够看出活着就行，不要像在飘。")]
        [SerializeField] private float fallbackBob = 0.025f;
        [Tooltip("一次完整呼吸的秒数。")]
        [SerializeField] private float fallbackPeriod = 3.4f;

        private Animator animator;
        private Transform visual;
        private Vector3 visualBasePos;

        private bool hasIdle;
        private bool hasTalk;
        private bool useFallbackBob;

        private float baseYaw;
        private float yawOffset;
        private float yawTarget;
        private float scanTimer;
        private float gestureTimer;
        private float talkBusyUntil;
        private float greetReadyAt;
        private float breathPhase;

        private Transform player;
        private float playerProbeTimer;
        private float playerDistance = float.MaxValue;
        private bool playerHasSteering;
        private bool scanSuspended;

        private void Awake()
        {
            animator = GetComponentInChildren<Animator>();
            visual = transform.childCount > 0 ? transform.GetChild(0) : null;
            if (visual != null) visualBasePos = visual.localPosition;
            baseYaw = transform.eulerAngles.y;
        }

        private void Start()
        {
            hasIdle = HasState(IdleHash);
            hasTalk = hasIdle && HasParameter(TalkTriggerName);

            // 随机相位：没有控制器/状态时才退化成程序化呼吸。
            if (hasIdle)
            {
                animator.speed = Random.Range(playbackRange.x, playbackRange.y);
                animator.Play(IdleHash, 0, Random.value);
                animator.Update(0f);
            }
            else
            {
                useFallbackBob = visual != null;
                if (!useFallbackBob && animator == null)
                {
                    Debug.LogWarning($"[My World] {name} 上既没有可用的 Animator 也没有可起伏的子物体，NPC 会保持完全静止。" +
                                     "请跑「Tools/My World/NPC 一键安装（预制体 + 接入地图）」。");
                }
            }

            breathPhase = Random.value * Mathf.PI * 2f;
            scanTimer = Random.Range(0f, Mathf.Max(0.01f, scanGapRange.y));
            gestureTimer = Random.Range(gestureGapRange.x, gestureGapRange.y);
            yawTarget = 0f;
            greetReadyAt = Time.time + 2f;
        }

        private void Update()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;

            ProbePlayer(dt);

            if (useFallbackBob) FallbackBreath();
            UpdateScan(dt);
            UpdateGesture(dt);
        }

        // ── 内部实现 ────────────────────────────────────────────────

        /// <summary>0.5 秒才查一次玩家：FindFirstObjectByType 不便宜，而 NPC 有 18 个。</summary>
        private void ProbePlayer(float dt)
        {
            playerProbeTimer -= dt;
            if (playerProbeTimer > 0f) return;
            playerProbeTimer = 0.5f;

            if (player == null)
            {
                var health = Object.FindFirstObjectByType<PlayerHealth>();
                player = health != null ? health.transform : null;
                if (player == null)
                {
                    playerDistance = float.MaxValue;
                    playerHasSteering = false;
                    return;
                }
            }

            Vector3 a = transform.position;
            Vector3 b = player.position;
            playerDistance = new Vector2(a.x - b.x, a.z - b.z).magnitude;

            // NpcActor 在 5 米内每 0.15 秒 slerp 一次朝向，那段时间转向权归它。
            playerHasSteering = playerDistance < handoverRadius;
        }

        private void UpdateScan(float dt)
        {
            if (playerHasSteering)
            {
                // 交还控制权的那一刻把当前朝向收编成新基准，避免下一帧弹回去。
                if (!scanSuspended)
                {
                    scanSuspended = true;
                    baseYaw = transform.eulerAngles.y;
                    yawOffset = 0f;
                    yawTarget = 0f;
                }
                return;
            }

            if (scanSuspended)
            {
                scanSuspended = false;
                baseYaw = transform.eulerAngles.y;
                yawOffset = 0f;
                yawTarget = 0f;
                scanTimer = Random.Range(scanGapRange.x, scanGapRange.y);
            }

            scanTimer -= dt;
            if (scanTimer <= 0f)
            {
                scanTimer = Random.Range(scanGapRange.x, scanGapRange.y);
                yawTarget = Random.Range(-scanAngle, scanAngle);
            }

            if (!Mathf.Approximately(yawOffset, yawTarget))
            {
                yawOffset = Mathf.MoveTowards(yawOffset, yawTarget, Mathf.Max(0f, scanSpeed) * dt);
                transform.rotation = Quaternion.Euler(0f, baseYaw + yawOffset, 0f);
            }
        }

        private void UpdateGesture(float dt)
        {
            gestureTimer -= dt;
            if (gestureTimer > 0f) return;
            gestureTimer = Random.Range(gestureGapRange.x, gestureGapRange.y);

            if (!hasTalk) return;
            if (Time.time < talkBusyUntil) return;
            if (player == null) return;

            bool greeting = playerDistance <= greetRadius && Time.time >= greetReadyAt;
            if (!greeting && playerDistance > gestureNoticeRange) return;

            animator.SetTrigger(TalkHash);
            talkBusyUntil = Time.time + Mathf.Max(0.2f, gestureHoldSeconds);
            if (greeting) greetReadyAt = Time.time + Mathf.Max(1f, greetCooldown);
        }

        private void FallbackBreath()
        {
            float w = Mathf.PI * 2f / Mathf.Max(0.2f, fallbackPeriod);
            float s = Mathf.Sin(Time.time * w + breathPhase);
            visual.localPosition = visualBasePos + new Vector3(0f, s * fallbackBob, 0f);
        }

        private bool HasState(int stateHash)
        {
            if (animator == null || !animator.isActiveAndEnabled) return false;
            if (animator.runtimeAnimatorController == null) return false;
            return animator.HasState(0, stateHash);
        }

        /// <summary>Animator 没有公开的单参数查询接口，只能翻一遍 parameters 数组；只在 Start 调一次。</summary>
        private bool HasParameter(string parameterName)
        {
            if (animator == null || animator.runtimeAnimatorController == null) return false;
            AnimatorControllerParameter[] ps = animator.parameters;
            for (int i = 0; i < ps.Length; i++)
            {
                if (ps[i].name == parameterName) return true;
            }
            return false;
        }
    }
}
