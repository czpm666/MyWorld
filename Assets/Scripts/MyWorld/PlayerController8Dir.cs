using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 8 方向行走：输入方向直接决定移动方向，朝向吸附到 8 个方向之一。
    /// 用 CharacterController 而不是 Rigidbody —— 俯视游戏贴着墙走的时候，
    /// 刚体会被弹开/抖动，CharacterController 自带沿墙滑行，手感干净得多。
    ///
    /// **输入是"屏幕空间"的**（x = 屏幕右，y = 屏幕上），要换算成世界方向才走得对，
    /// 换算依据是相机 yaw（`TopDownCameraRig.MovementYaw`）：
    ///  · **yaw == 0（默认俯视模式）**：屏幕上方正好是世界 +Z，换算是**恒等映射** ——
    ///    这一段与"输入直接当世界方向"的历史实现逐位一致，是本文件的硬要求。
    ///  · **yaw ≠ 0（第三人称转了视角）**：WASD 变成**相对相机**，W 永远 = 往画面里走，
    ///    否则一转视角操作就错乱。
    /// 两种情况下朝向都照样吸附到 8 个方向，角色"只有 8 个朝向"这条规则不变。
    /// </summary>
    [DisallowMultipleComponent]
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController8Dir : MonoBehaviour
    {
        [Header("移动")]
        [Tooltip("最高行走速度(单位/秒)")]
        [SerializeField] private float walkSpeed = 5.5f;
        [Tooltip("按住 Shift 疾跑时的最高速度")]
        [SerializeField] private float runSpeed = 9.5f;
        [Tooltip("速度向目标收敛的加速度：越大越跟手，越小惯性越强")]
        [SerializeField] private float accel = 38f;
        [Tooltip("松开按键时的减速度，比加速稍大一点，停得干脆")]
        [SerializeField] private float decel = 46f;
        [Header("转向")]
        [Tooltip("朝向转动的跟随速度，越大转得越快")]
        [SerializeField] private float turnLerp = 18f;

        [Header("重力与跳跃")]
        [SerializeField] private float gravity = -26f;
        [Tooltip("落地时保留的一点向下速度，避免在斜坡上抖动")]
        [SerializeField] private float groundedStick = -2f;
        [Tooltip("起跳初速(单位/秒)。跳跃高度 ≈ jumpSpeed² / (2*|gravity|)")]
        [SerializeField] private float jumpSpeed = 9f;
        [Tooltip("离地后还能起跳的宽限时间，避免刚离开边缘就按不出来")]
        [SerializeField] private float coyoteTime = 0.12f;
        [Tooltip("跳跃输入缓冲：落地前这么早按下的跳跃会被记住，落地那一刻自动起跳。\n" +
                 "没有它的时候，玩家在离地 0.1 秒时按跳会被**直接丢掉**（输入只在按键那一帧有效），" +
                 "体感就是「我明明按了却不跳」。0.15 = 大约提前 9 帧按都算数")]
        [SerializeField] private float jumpBufferTime = 0.15f;

        [Header("动量衰减")]
        [Tooltip("抓钩松手后保留的动量按这个速率衰减(单位/秒²)，比正常刹车慢得多，才有'滑出去'的感觉")]
        [SerializeField] private float momentumDecay = 7f;

        [Header("击退")]
        [Tooltip("击退的衰减速率。要远大于 momentumDecay —— 击退要的是'瞬间被打飞、很快稳住'，不是慢慢滑")]
        [SerializeField] private float knockbackDecay = 55f;
        [Tooltip("击退的最低初速。有了它小距离击退也有'被撞飞'的爆发感，不然只是被推了一下")]
        [SerializeField] private float knockbackMinSpeed = 26f;
        [Tooltip("被击退时玩家自己的僵直时长(秒)，这段时间 WASD 不生效，让击退能完整打完")]
        [SerializeField] private float knockbackStun = 0.35f;

        private CharacterController cc;
        private MyWorldInput input;

        /// <summary>
        /// 动画手感参数（播放倍率 / 起步加成 / 转身减速）。来自
        /// `Assets/Scripts/MyWorld/Animation/Resources/AnimFeelSettings.asset`；
        /// 资产不存在时自动回落到代码里的默认值 —— **永不返回 null**。
        /// 🔴 参数**故意不放在本类的 `[SerializeField]` 上**：场景里那份组件已经序列化过一轮，
        ///    只有**新增**字段会吃代码默认值，**改老字段默认值对已存在的场景实例完全无效**。
        /// </summary>
        private AnimFeelSettings feel;

        private Vector3 planarVelocity;   // 水平速度
        private float verticalVelocity;

        // ---------------- T-079 §⑥ 跳跃动画（接法二）----------------
        /// <summary>角色身上的 Animator（**懒解析**；取不到也不报错 —— 占位胶囊阶段可能还没有）。</summary>
        private Animator anim;
        /// <summary>最近一次"在空中"的时刻。**卡死保护**用它算"已经落地多久了"。</summary>
        private float airborneSince = -99f;

        [Tooltip("T-079 §⑥ 卡死保护：**落地后**仍未回到 Idle 超过这个秒数，就强制回 Idle。"
                 + "⚠️ **暂定值，待用户确认**（属表现层，不是战斗数值）")]
        [SerializeField] private float jumpStuckRecoverSeconds = 0.5f;

        // ⚠️ 下面三个字符串**必须与 `MageSetup` 的 `JumpTrigger` / `AirborneParam` /
        //    状态名 `Idle` **逐字一致**。`MageSetup` 在 Editor 程序集、本类在运行时程序集，
        //    **无法共享常量** → 只能靠这段注释互相指认。**改名时两处都要改**：
        //    参数名不匹配**不会报错**，只会让跳跃**静默不动**（这类静默失败本项目吃过多次）。
        private const string JumpTriggerParam = "Jump";
        private const string AirborneParam = "Airborne";
        private const string IdleStateName = "Idle";
        /// <summary>移动速度参数名（Float）。**本类是它唯一的写入者**（见 `UpdateAnimPlayback` 的说明）。</summary>
        private const string SpeedParam = "Speed";

        // ---- T-079 §⑧ 片 3：侧移组 ----
        // ⚠️ 下面这个字符串与四个取值**必须与 `MageSetup` 的 `StrafeDirParam` / `StrafeStates`
        //    （以及那三个状态名）**逐字一致**。Editor 程序集 ↔ 运行时程序集**不能互相引用**，
        //    只能各写一份 → **改名不报错，只会让侧移静默不动**（陷阱 20 / 21）。
        /// <summary>侧移方向参数名（Int）。**0 = 不启用侧移组**（未锁定，或锁定下朝前走）。</summary>
        private const string StrafeDirParam = "StrafeDir";
        private const int StrafeDirNone = 0;     // 不启用
        private const int StrafeDirBack = 1;     // 向后（→ `Walk_Back`）
        private const int StrafeDirLeft = 2;     // 向角色左侧（→ `Run_Strafe_L`）
        private const int StrafeDirRight = 3;    // 向角色右侧（→ `Run_Strafe_R`）
        private float yaw;                // 当前朝向(度)
        private float yawTarget;          // 吸附到 8 方向后的目标朝向
        private float animSpeed;          // 喂给 Animator 的语义化速度
        private bool hasForcedFacing;     // 锁定目标时用，优先级最高
        private Vector3 forcedFacing;
        private bool hasAimFacing;        // 鼠标朝向，优先级次之
        private Vector3 aimFacing;
        private bool hasReelFacing;       // 被抓钩拽着时的朝向，优先级最高
        private Vector3 reelFacing;
        private bool hasExternalVelocity;
        private Vector3 externalVelocity;
        private bool hasMomentum;      // 抓钩松手后残留的动量，按更慢的速率衰减
        private float lastGroundedTime;
        /// <summary>最近一次**按下跳跃键**的时刻，用于输入缓冲（见 <see cref="jumpBufferTime"/>）。</summary>
        private float lastJumpPressTime = -99f;

        // ================= T-091 批次 1：翻滚闪避 =================
        // ⚠️ 下面两个参数名必须与 `MageSetup.DodgeTrigger` / `DodgeDirParam` 逐字一致
        //    （Editor 程序集 ↔ 运行时程序集不能互相引用 → 改名不报错，只会让翻滚静默不动）。
        private const string DodgeTriggerParam = "Dodge";
        private const string DodgeDirParam = "DodgeDir";

        [Header("翻滚闪避（T-091 批次 1）")]
        // 距离按方向分开给（Lead 2026-10-20 定）：四条 Dodge 剪辑末端根部还留着一点位移，
        // 翻滚一结束这个偏移会被"回漂"抹掉 —— 所以距离越长，回漂占比越小、越看不出来。
        // 实测末端根位移：前 +0.25 m｜后 -0.65 m｜左右 ∓0.50 m；阈值 0.30 m 以上就要处理。
        // ⚠️ 2026-10-20 Play 实测：`cc.Move` 每帧会吃掉一点水平位移，**配置 2.2 m 实走只有 2.05 m**
        //    （时长 1.5 s 时更差，1.91 m）→ 三个值按 0.93 折算上调，目标是"实打实"走到名义距离。
        //    验收口径：实测落在配置值 ±0.15 m 内。
        [Tooltip("前滚推进距离（米，名义值）。末端根位移 +0.25 m，回漂占 11% → 不动。")]
        [SerializeField] private float dodgeForwardDistance = 2.40f;
        [Tooltip("后滚推进距离（米，名义值）。末端根位移 -0.65 m，回漂占 23% → 加长把占比压下来。")]
        [SerializeField] private float dodgeBackwardDistance = 3.05f;
        [Tooltip("左/右滚推进距离（米，名义值）。末端根位移 ∓0.50 m，回漂占 19%。")]
        [SerializeField] private float dodgeSideDistance = 2.85f;
        [Tooltip("翻滚窗口时长（秒）。四条 Dodge 剪辑实测长度都是 0.400 s，改这里必须同步改剪辑。")]
        [SerializeField] private float dodgeDuration = 0.40f;
        [Tooltip("剪辑走完全部位移所用的时长占比（实测 0.62）。位移曲线=缓出，0.62 之后不再推进、只收势。")]
        [SerializeField] private float dodgePushFraction = 0.62f;
        [Tooltip("翻滚结束后的硬冷却（秒）。防连滚，也给落地缓冲留时间。")]
        [SerializeField] private float dodgeCooldown = 0.35f;
        [Tooltip("翻滚时是否允许无视输入方向、始终朝当前朝向滚。关掉后才用 8 向自由翻滚。")]
        [SerializeField] private bool dodgeFollowsInput = true;

        /// <summary>单帧时间上限（秒）。编辑器卡顿或窗口切回来时 deltaTime 会突然变成几百毫秒，
        /// 不平滑会把整段位移在一帧里打完（实测翻滚一次飞出 11.19 m）。</summary>
        private const float MaxDeltaTime = 0.05f;

        private float dodgeTimer;          // 剩余翻滚时间（>0 = 正在翻滚）
        private float dodgeCooldownTimer;  // 冷却剩余
        private Vector3 dodgeDirection;    // 翻滚推进方向（世界空间，已归一）
        private float dodgeDistanceActive; // 本次翻滚实际使用的距离（按方向从三个字段里选）
        private bool dodgeIsBackstep;      // 后翻滚：不转身，保持面朝原方向倒退
        private PlayerMage mage;           // 懒解析，只为调 PlayDodge（状态参数由它写，本类不抢）

        /// <summary>当前是否真的在移动（给动画/音效用）。</summary>
        public bool IsMoving => planarVelocity.sqrMagnitude > 0.04f;

        /// <summary>T-091 批次 1：是否正在翻滚闪避（翻滚期间只有本类的位移推进在生效）。</summary>
        public bool IsDodging => dodgeTimer > 0f;

        /// <summary>是否正在疾跑（按着 Shift 且有移动输入）。</summary>
        public bool IsSprinting { get; private set; }

        /// <summary>
        /// 喂给 Animator 的 Speed 参数 = **实际**水平速度 ÷ `AnimFeelSettings.speedParamFullSpeed`。
        /// ⚠️ 语义与早期版本不同：早期是 0=站住 / 0.5=走 / 1=跑 的"意图值"，
        /// 现在是"实际速度归一化"（可以大于 1）。控制器里的阈值 0.15 / 0.75 依旧是唯一的分档依据。
        /// </summary>
        public float AnimSpeed => animSpeed;

        /// <summary>是否在空中（抓钩的规则要靠它区分地面/空中）。</summary>
        public bool IsAirborne => cc != null && !cc.isGrounded;

        /// <summary>离地高度：从胶囊底部往下打射线取最近的非自身命中。</summary>
        public float HeightAboveGround
        {
            get
            {
                Vector3 from = cc != null ? cc.bounds.min + Vector3.up * 0.05f : transform.position;
                var hits = Physics.RaycastAll(from, Vector3.down, 80f, ~0, QueryTriggerInteraction.Ignore);

                float best = float.MaxValue;
                for (int i = 0; i < hits.Length; i++)
                {
                    if (hits[i].collider == null) continue;
                    if (hits[i].collider.transform.IsChildOf(transform)) continue;
                    if (hits[i].distance < best) best = hits[i].distance;
                }
                return best == float.MaxValue ? 0f : best;
            }
        }

        /// <summary>
        /// 强制朝向（锁定目标时用）。传入世界方向，内部照样吸附到 8 方向，
        /// 这样锁定不会破坏"角色只有 8 个朝向"这条规则。
        /// </summary>
        public void SetForcedFacing(Vector3 worldDirection)
        {
            if (worldDirection.sqrMagnitude < 0.0001f) return;
            forcedFacing = worldDirection;
            hasForcedFacing = true;
        }

        /// <summary>取消强制朝向。</summary>
        public void ClearForcedFacing()
        {
            hasForcedFacing = false;
        }

        /// <summary>鼠标指向（优先级低于锁定、高于移动方向）。同样吸附到 8 方向。</summary>
        public void SetAimFacing(Vector3 worldDirection)
        {
            if (worldDirection.sqrMagnitude < 0.0001f) return;
            aimFacing = worldDirection;
            hasAimFacing = true;
        }

        public void ClearAimFacing()
        {
            hasAimFacing = false;
        }

        /// <summary>
        /// 抓钩拉拽中的朝向（优先级最高）。
        /// 必须让角色朝着"被拽过去的方向"，否则会一边被拖走一边播跑步动画，看起来像倒着飞。
        /// </summary>
        public void SetReelFacing(Vector3 worldDirection)
        {
            if (worldDirection.sqrMagnitude < 0.0001f) return;
            reelFacing = worldDirection;
            hasReelFacing = true;
        }

        public void ClearReelFacing()
        {
            hasReelFacing = false;
        }

        /// <summary>抓钩拉拽期间接管水平速度。设置后 WASD 不再参与移动。</summary>
        public void SetExternalVelocity(Vector3 worldVelocity)
        {
            externalVelocity = new Vector3(worldVelocity.x, 0f, worldVelocity.z);
            hasExternalVelocity = true;
        }

        /// <summary>松开抓钩：解除接管，速度原样留下，切成惯性滑行。</summary>
        public void ClearExternalVelocity()
        {
            currentMomentumDecay = momentumDecay;   // 抓钩交接的动量用普通衰减
            HandOffMomentum(1f);
        }

        /// <summary>
        /// 解除接管并交接动量，carry 是**保留比例**。
        /// 为什么要有这个系数：拉拽到末尾时速度很高（20+），原样交接再慢衰减
        /// 等于滑出几十米——"地面钩墙只拽一下"就会变成"直接飞过去"。所以短拽给很小的系数。
        /// </summary>
        public void HandOffMomentum(float carry)
        {
            if (!hasExternalVelocity) return;
            planarVelocity = externalVelocity * Mathf.Clamp01(carry);
            hasExternalVelocity = false;
            hasMomentum = planarVelocity.sqrMagnitude > 0.04f;
            // 抓钩过来的动量用普通衰减；击退会先把它设成 knockbackDecay
            if (currentMomentumDecay <= 0f) currentMomentumDecay = momentumDecay;
        }

        /// <summary>当前水平速度（抓钩用它做速度连续性）。</summary>
        public Vector3 PlanarVelocity => planarVelocity;

        private float speedMultiplier = 1f;
        private float stunTimer;
        private float currentMomentumDecay;   // 当前这次惯性的衰减速率（抓钩和击退不同）

        /// <summary>移速倍率（比如流血时降低 15%）。</summary>
        public void SetSpeedMultiplier(float multiplier)
        {
            speedMultiplier = Mathf.Clamp(multiplier, 0.1f, 3f);
        }

        /// <summary>是否处于受击僵直（这段时间 WASD 不生效）。</summary>
        public bool IsStunned => stunTimer > 0f;

        /// <summary>
        /// 受击僵直。**没有这个，击退是看不出来的**——
        /// 玩家一按 WASD，加速收敛会立刻把击退速度覆盖掉，位移几乎为零。
        /// </summary>
        public void ApplyStun(float duration)
        {
            stunTimer = Mathf.Max(stunTimer, duration);
        }

        /// <summary>
        /// 把玩家按指定**距离**击退。
        ///
        /// 关键：击退用的是**独立的、远大于普通惯性的衰减**（knockbackDecay），
        /// 并且有一个最低初速。这样同样是"击退 2 格"，表现是"头 0.3 秒被打飞出去、然后稳住"，
        /// 而不是用慢衰减一路滑过去 —— 后者看着只是被推了一下，不像被击飞。
        /// </summary>
        public void ApplyKnockback(Vector3 direction, float distance)
        {
            Vector3 flat = new Vector3(direction.x, 0f, direction.z);
            if (flat.sqrMagnitude < 0.0001f) return;

            float d = Mathf.Max(0.1f, distance);

            // 初速：先按衰减反推，再抬到最低初速 —— 这一步决定了"被打飞"的爆发感
            float speed = Mathf.Max(knockbackMinSpeed, Mathf.Sqrt(2f * knockbackDecay * d));

            // 速度抬高之后，衰减必须同步抬高，否则击退距离会跟着变长。
            // 由 s = v²/(2a) 反解 a，保证"击退 2 格"始终是 2 格。
            currentMomentumDecay = speed * speed / (2f * d);

            SetExternalVelocity(flat.normalized * speed);
            HandOffMomentum(1f);

            // 僵直至少要覆盖击退全过程，否则玩家中途一按 WASD 就把击退抵消了
            ApplyStun(Mathf.Max(knockbackStun, speed / currentMomentumDecay));
        }

        /// <summary>把 (x, z) 方向吸附到 45° 的整数倍。0° = +Z。</summary>
        private static float SnapTo45(float x, float z)
        {
            return Mathf.Round(Mathf.Atan2(x, z) * Mathf.Rad2Deg / 45f) * 45f;
        }

        /// <summary>
        /// 屏幕空间输入（x = 右，y = 屏幕上）→ 世界方向 (x, z)。
        ///
        /// `yawDeg == 0` 时**原样返回**：一个浮点运算都不做，所以默认俯视模式下这条路径
        /// 与历史实现（输入直接当世界方向）**逐位一致** —— 这是硬要求，别在这里"顺手优化"。
        ///
        /// yaw ≠ 0 时按相机基向量投影：相机前方 = (sin, 0, cos)、相机右方 = (cos, 0, -sin)
        /// （与 `TopDownCameraRig` 里 `Quaternion.Euler(pitch, yaw, 0)` 的机位定义一致）。
        /// </summary>
        private static Vector2 ScreenToWorldInput(Vector2 move, float yawDeg)
        {
            if (yawDeg == 0f) return move;

            float rad = yawDeg * Mathf.Deg2Rad;
            float s = Mathf.Sin(rad);
            float c = Mathf.Cos(rad);
            return new Vector2(move.x * c + move.y * s, -move.x * s + move.y * c);
        }

        /// <summary>当前朝向对应的 8 方向索引，0=正前(+Z)，顺时针递增。</summary>
        public int FacingIndex => Mathf.RoundToInt(Mathf.Repeat(yawTarget, 360f) / 45f) % 8;

        /// <summary>
        /// T-079 §⑧ 片 3：把"锁定态下的移动方向"折算成 `StrafeDir`。
        ///
        /// **分类只用"哪一轴占优"这条纯比较 —— 不引入任何新阈值**：
        /// 朝向是 45° 吸附的、输入也是 8 方向，所以"占优轴"本身就是正确的分类器
        /// （这也顺带满足"本片不新增数值"的约束）。
        ///
        /// **未锁定时一律返回 0**：未锁定态下朝向本来就跟着移动方向转，
        /// 这时播"倒退/侧移"等于**播一个不存在的行为**（§⑧ H1 的反向臂）。
        /// 判"锁没锁"用的是 `hasForcedFacing` —— 全工程**只有 `PlayerLockOn` 在锁定时**会
        /// `SetForcedFacing`（`PlayerLockOn.cs:132-134`，解锁时 `:153` 清掉）。
        ///
        /// ⚠️ **本方法不碰速度、不碰朝向、不碰位移** —— 它只产出一个给动画层的整数。
        /// </summary>
        private int ComputeStrafeDir(Vector2 worldMove)
        {
            if (!hasForcedFacing) return StrafeDirNone;

            Vector3 fwd = transform.forward;
            fwd.y = 0f;
            if (fwd.sqrMagnitude < 0.0001f) return StrafeDirNone;
            fwd.Normalize();

            // ⚠️ 这里要的是**世界**移动方向，不是屏幕空间输入 —— 所以调用方传的是
            //    `ScreenToWorldInput` 的结果（相机 yaw = 0 时两者逐位相同）。
            float mx = worldMove.x;
            float mz = worldMove.y;

            float f = mx * fwd.x + mz * fwd.z;    // 前后分量（+ = 朝前）
            float r = mx * fwd.z - mz * fwd.x;    // 左右分量（+ = 朝角色右侧；right = (fwd.z, 0, -fwd.x)）

            if (Mathf.Abs(r) > Mathf.Abs(f))
                return r < 0f ? StrafeDirLeft : StrafeDirRight;

            return f < 0f ? StrafeDirBack : StrafeDirNone;
        }

        private void Awake()
        {
            cc = GetComponent<CharacterController>();
            input = GetComponent<MyWorldInput>();
            feel = AnimFeelSettings.Active;
            yaw = yawTarget = transform.eulerAngles.y;
        }

        private void Update()
        {
            // 单帧时间上限：编辑器卡顿/切回窗口/断点会让 deltaTime 突然变成几百毫秒。
            // 翻滚是按"这一帧要走多远"算位移的，没有上限时一次卡顿就能把整段推进
            // 在一帧里打完 —— 实测 1.6 s 走了 11.19 m（名义 2.4 m），等于穿墙飞行。
            // 封顶后极端卡顿只会表现为"动作变慢"，不会把角色甩出去。
            float dt = Mathf.Min(Time.deltaTime, MaxDeltaTime);

            // `Awake` 没跑过（组件后加/被禁用再启用）也不会空引用 —— `Active` 自己会兜底。
            if (feel == null) feel = AnimFeelSettings.Active;

            if (stunTimer > 0f) stunTimer -= dt;

            Vector2 move = input != null ? input.Move : Vector2.zero;
            // 僵直期间忽略输入：让击退/被拉拽的动量大完再接受操作
            if (IsStunned) move = Vector2.zero;
            bool hasMove = move.sqrMagnitude > 0.01f;
            IsSprinting = hasMove && input != null && input.Sprint;

            // 屏幕空间 → 世界方向。`MovementYaw == 0`（默认俯视）时是恒等映射，逐位一致；
            // 第三人称转了视角之后就变成"相对相机"（W = 往画面里走）。
            Vector2 worldMove = ScreenToWorldInput(move, TopDownCameraRig.MovementYaw);

            // T-091 批次 1：翻滚窗口（起手判定 + 计时推进）。必须在速度分支之前跑，
            // 这样本帧刚起的翻滚就能接管速度，晚一帧都会多滑一步。
            UpdateDodgeWindow(worldMove, hasMove, dt);

            if (hasExternalVelocity)
            {
                // 被抓钩拽着走时，WASD 完全不参与——想改方向只能松手。
                planarVelocity = externalVelocity;
            }
            else if (dodgeTimer > 0f)
            {
                // 翻滚位移：**按剪辑实测的位移曲线走**，不是线性。
                // 实测（`AnimationMode` 逐帧采样 `Clips/Dodge_*.anim` 的 `Rig/root`）：
                //   Dodge_Forward  0.400 s 根位移 +0.25 m ｜ Dodge_Backward -0.65 m
                //   Dodge_Left/Right 0.400 s ∓0.50 m
                //   四条都是 **前 62% 时长走完全部位移**、后 38% 收势（缓出曲线）。
                // 所以这里也按同一条缓出走：起手最快、0.62 处走满、剩下时间停住收势。
                // ⚠️ 若改成线性衰减，会和剪辑的节奏错开 —— 观感就是"脚下先冲、身上后跟"的滑步。
                // ⚠️ prefab 上 `applyRootMotion=false`，`Rig/root` 那 0.25~0.65 m 只是**骨骼内部**
                //    位移（退出动作时会被混合回 0）；本段推进才是角色真正移动的那一份。
                float u = Mathf.Clamp01(1f - dodgeTimer / Mathf.Max(dodgeDuration, 0.01f));
                float frac = Mathf.Clamp(dodgePushFraction, 0.1f, 1f);
                float a = Mathf.Clamp01(u / frac);
                float dodgeSpeed = 2f * dodgeDistanceActive / Mathf.Max(frac * dodgeDuration, 0.01f) * (1f - a);
                planarVelocity = dodgeDirection * dodgeSpeed;
            }
            else if (hasMomentum && !hasMove)
            {
                // 惯性滑行：衰减速率看这次惯性是抓钩来的（慢）还是击退来的（快）。
                planarVelocity = Vector3.MoveTowards(planarVelocity, Vector3.zero, currentMomentumDecay * dt);
                if (planarVelocity.sqrMagnitude < 0.04f)
                {
                    hasMomentum = false;
                    currentMomentumDecay = 0f;   // 清零，下一次交接重新按来源决定
                }
            }
            else
            {
                hasMomentum = false;   // 一旦给了输入（或本来就没有动量），交回正常控制
                currentMomentumDecay = 0f;

                // **转身减速**：朝向还没转过来时先压一点速度（差 45° → ×0.955，差 180° → ×0.82）。
                // 为什么：8 方向 + 18/秒 转体，180° 掉头要 ~0.25s；这期间若照常全速平移，
                // 观感就是"脚朝旧方向、人往新方向横着滑出去"。减速把它变成"刹一下再走"。
                // ⚠️ 这里读到的是**上一帧**的 `yawTarget`（它在下面才更新）——正是想要的：
                //    同一帧里刚按下的新方向不会和刚起步的速度互相打架。
                float turnOffDeg = Mathf.Abs(Mathf.DeltaAngle(yaw, yawTarget));
                float targetSpeed = (IsSprinting ? runSpeed : walkSpeed) * speedMultiplier
                                    * (1f - feel.turnSpeedPenalty * (turnOffDeg / 180f));

                // 输入是屏幕空间：x 向右，y 向上(屏幕上方)。经 `ScreenToWorldInput` 换成世界方向 ——
                // 相机 yaw=0 时屏幕上正好是世界 +Z（恒等映射，与历史逐位一致）；
                // yaw≠0 时换算成相对相机的方向，W 永远指向画面深处。
                Vector3 desired = new Vector3(worldMove.x, 0f, worldMove.y) * targetSpeed;

                float rate = desired.sqrMagnitude > planarVelocity.sqrMagnitude ? accel : decel;
                // **加速曲线**：起步那一下额外乘 (1 + accelKick)，随速度升高回到 1×。
                // 匀速线性加速的观感是"先慢吞吞、到顶才突然有速度"；加这一项之后
                // 头 30ms 就推到约七成，起步立刻有感，剩下的尾巴负责"顺"。
                if (desired.sqrMagnitude > planarVelocity.sqrMagnitude && desired.sqrMagnitude > 0.0001f)
                {
                    float progress = Mathf.Clamp01(planarVelocity.magnitude / desired.magnitude);
                    rate *= 1f + feel.accelKick * (1f - progress);
                }
                planarVelocity = Vector3.MoveTowards(planarVelocity, desired, rate * dt);
            }

            // ---- 动画 Speed 参数 = **实际**水平速度归一化 ----
            // 🔴 这里原来是"用意图而不是实际速度"（`hasMove ? 冲刺?1 : 0.5 : 0`），注释给的理由是
            //    "起步瞬间就能切到走/跑，不会先站一下再动"。而那条路线的代价正是**起步滑步**：
            //    意图值在按键当帧就跳到 0.5/1.0，实际速度却要 ~0.14s 才追上来（加速度 38）——
            //    这 0.14s 里动画已经在全速迈步、人还没走出去，脚往哪踩都踩不到地面。
            //    改成实际速度驱动后，起步时脚是"慢 → 快"地踩，与位移全程一致；
            //    而"别先站一下再动"改由 `AnimFeelSettings.accelKick`（起步加速曲线）保证：
            //    走阈值 0.15 × speedParamFullSpeed(2.2) = 0.33 m/s，只要 6ms，一帧内就开始迈步。
            animSpeed = Mathf.Clamp(planarVelocity.magnitude / Mathf.Max(feel.speedParamFullSpeed, 0.01f), 0f, 2.5f);

            // 朝向优先级：抓钩拉拽 > 锁定目标 > 鼠标(仅出手瞬间) > 移动方向。
            // 拉拽时必须朝着被拽的方向，否则会出现"人往前跑、身体倒着飞"的错乱动画。
            if (hasReelFacing)
                yawTarget = SnapTo45(reelFacing.x, reelFacing.z);
            else if (dodgeTimer > 0f && !dodgeIsBackstep)
                // 翻滚时朝向锁在翻滚方向上（前/左/右滚），后撤步例外：保持面朝原方向倒退。
                yawTarget = SnapTo45(dodgeDirection.x, dodgeDirection.z);
            else if (hasForcedFacing)
                yawTarget = SnapTo45(forcedFacing.x, forcedFacing.z);
            else if (hasAimFacing)
                yawTarget = SnapTo45(aimFacing.x, aimFacing.z);
            else if (worldMove.sqrMagnitude > 0.01f)
                yawTarget = SnapTo45(worldMove.x, worldMove.y);

            yaw = Mathf.LerpAngle(yaw, yawTarget, 1f - Mathf.Exp(-turnLerp * dt));
            transform.rotation = Quaternion.Euler(0f, yaw, 0f);

            // 跳跃（带土狼时间：刚走出平台边缘的一小会儿也能起跳）
            if (cc.isGrounded) lastGroundedTime = Time.time;
            bool canJump = Time.time - lastGroundedTime <= coyoteTime;

            // T-0xx 动画手感：**输入缓冲**。
            // 原来判定直接吃 `input.JumpPressed`（只有按下那一帧为 true），
            // 于是"落地前一点点按跳"必然丢输入 —— 玩家体感是"按了没反应"，
            // 再按一次才跳起来，这就是最典型的"操作不跟手"。
            // 现在改成：记下**按下那一刻**，在 `jumpBufferTime` 之内只要条件成立就起跳。
            if (input != null && input.JumpPressed) lastJumpPressTime = Time.time;
            bool hasBufferedJump = Time.time - lastJumpPressTime <= jumpBufferTime;

            if (hasBufferedJump && canJump && verticalVelocity <= 0f)
            {
                verticalVelocity = jumpSpeed;
                lastGroundedTime = -99f;    // 一次按键只起跳一次
                lastJumpPressTime = -99f;   // 缓冲同时清空，否则落地瞬间会连跳两次
                // T-079 §⑥：**起跳那一帧**触发跳跃动作。
                // 这就是当初的"接法一"那一条 —— 但接法二（`MageSetup` 里那三条转换）
                // 在此之上补了 `Jump_Start → Jump_Idle → Jump_Land → Idle` 的完整链，
                // 所以这里只负责"按开关"，**衔接由控制器 + 下面的 `Airborne` 负责**。
                if (anim != null) anim.SetTrigger(JumpTriggerParam);
            }

            // 重力
            if (cc.isGrounded && verticalVelocity < 0f) verticalVelocity = groundedStick;
            verticalVelocity += gravity * dt;

            // ---- T-079 §⑥：把"是否离地"喂给动画层（接法二的**唯一数据通道**）----
            if (anim == null) anim = GetComponentInChildren<Animator>();
            if (anim != null)
            {
                // `Speed` 参数的**唯一写入者**是本类 —— `PlayerMage` 原来也写一遍，现在不写了。
                // 两处写同一个参数不会报错，但**谁后写谁赢**，而脚本执行顺序本来就不保证；
                // 一旦 `PlayerMage` 先跑，动画就慢一帧喂到，起步那一帧正好看得见。
                anim.SetFloat(SpeedParam, animSpeed);

                bool air = IsAirborne;
                anim.SetBool(AirborneParam, air);
                if (air) airborneSince = Time.time;

                // 🔴 **卡死保护**（为什么必须有）：
                // `Jump_Idle` 是**循环**态，它**唯一**的出边是"`Airborne == false`"那条条件转移。
                // 若那条转移因任何原因没触发（参数没喂上 / 被某个 AnyState 抢走），
                // 角色会**永远停在滞空动作里，而且不报错** —— 正是 §3 R4 当初担心的形状。
                // → 兜底：**持续不在空中**超过阈值而动画仍停在某个跳跃状态，就强制回 `Idle`。
                else if (Time.time - airborneSince > jumpStuckRecoverSeconds)
                {
                    var st = anim.GetCurrentAnimatorStateInfo(0);
                    if (st.IsName("Jump_Start") || st.IsName("Jump_Idle") || st.IsName("Jump_Land"))
                    {
                        anim.Play(IdleStateName, 0, 0f);
                        airborneSince = Time.time;   // 复位，避免每帧重复强制
                        Debug.LogWarning("[My World] 跳跃卡死保护触发：落地后仍未回 Idle，已强制回 Idle");
                    }
                }
            }

            // ---- T-079 §⑧ 片 3：把"锁定态下的移动方向"喂给侧移组 ----
            // ⚠️ 位置要紧：必须在上面那段 `if (air) … else if (…)` 的**后面**。
            //    插在 `if` 与 `else if` 之间会**直接编译不过**
            //    （我本轮就踩了一次：`error CS8641: 'else' cannot start a statement`，被编译探针当场抓住）。
            // 每帧都写：`0` 就是"不启用"，所以**松键 / 解锁的那一帧**参数立刻回 0，
            // 不会卡在侧移动作里（与 `Airborne` 同一纪律：电平量每帧刷）。
            if (anim != null) anim.SetInteger(StrafeDirParam, ComputeStrafeDir(worldMove));

            // ---- 播放倍率：让脚步速度与**实际位移**对上（不滑步）+ 攻击动作的轻重分级 ----
            UpdateAnimPlayback(dt);

            Vector3 motion = planarVelocity + Vector3.up * verticalVelocity;
            cc.Move(motion * dt);
        }

        /// <summary>
        /// 把 `Animator.speed` 调到"与当前动作匹配的播放倍率"。
        ///
        /// 🔴 **为什么只靠 `Speed` 参数不够**：`Speed` 只决定**播哪一段**（Idle/Walk/Run 三选一），
        /// 而**播多快**永远是 1.0（实测控制器里每个 state 的 `speed = 1`、`speedParameterActive = false`）。
        /// 于是 5.5 m/s 的走路上播着自带 0.83 m/s 的 Walk 剪辑，脚在地上滑 6 倍。
        /// `Animator.speed` 才是"播多快"的旋钮，**两个一起调**才不滑步。
        ///
        /// 平滑用 `MoveTowards` 而不是直接赋值：剪辑切换（Walk→Run）那一帧目标倍率会跳变
        /// （≈0.9 → 1.53），直接写会让新剪辑**从第一帧就快进**，看起来是"脚下一顿"。
        /// 45/秒 的收敛速度 ≈ 20ms 跟上 —— 快到看不出延迟，又足够把跳变磨平。
        /// </summary>
        /// <summary>
        /// T-091 批次 1：翻滚的起手判定与计时。
        ///
        /// **方向怎么分档**：把"输入方向"与"当前朝向"的夹角（`SignedAngle`，右正左负）切成四段 ——
        /// |角| ≤ 67.5° = 前滚、≥ 112.5° = 后滚、中间按正负分左右。8 方向输入吸附到 45° 的整数倍，
        /// 所以这条分界让"前/前左/前右"都走前滚（对角滚前更跟手），只有正后/后左/后右才是后滚。
        ///
        /// **无输入 = 后撤步**：这是动作游戏的老规矩（站着不动按翻滚 = 后跳），
        /// 也顺手绕开了"没方向输入该往哪滚"这个无解问题。
        ///
        /// ⚠️ 冷却从**起手那一刻**开始计（`dodgeDuration + dodgeCooldown`），
        ///    不是播完再计 —— 否则按住键会在动画结束那一帧立刻接第二滚。
        /// </summary>
        private void UpdateDodgeWindow(Vector2 worldMove, bool hasMove, float dt)
        {
            if (dodgeCooldownTimer > 0f) dodgeCooldownTimer -= dt;
            if (dodgeTimer > 0f) dodgeTimer -= dt;

            if (input == null || !input.DodgePressed) return;
            if (dodgeTimer > 0f || dodgeCooldownTimer > 0f) return;   // 翻滚中 / 冷却中：吞掉这次按键
            if (IsStunned || hasExternalVelocity || !cc.isGrounded) return;  // 僵直 / 被拽 / 空中不许翻滚

            // 翻滚方向：有输入就朝输入方向，没输入就朝身后（后撤步）。
            Vector3 dir = (dodgeFollowsInput && hasMove && worldMove.sqrMagnitude > 0.01f)
                ? new Vector3(worldMove.x, 0f, worldMove.y).normalized
                : -transform.forward;

            float signed = Vector3.SignedAngle(transform.forward, dir, Vector3.up);
            float abs = Mathf.Abs(signed);
            PlayerMage.DodgeDirection kind;
            if (abs <= 67.5f) kind = PlayerMage.DodgeDirection.Forward;
            else if (abs >= 112.5f) kind = PlayerMage.DodgeDirection.Backward;
            else kind = signed > 0f ? PlayerMage.DodgeDirection.Right : PlayerMage.DodgeDirection.Left;

            dodgeDirection = dir;
            dodgeIsBackstep = kind == PlayerMage.DodgeDirection.Backward;
            // 距离按方向取（Lead 定的表）：后滚/侧滚的剪辑末端根位移更大，
            // 只能用更长的人工推进去稀释回漂占比（0.65/2.8=23% → 仍然偏大，但已压到可接受档）。
            switch (kind)
            {
                case PlayerMage.DodgeDirection.Backward: dodgeDistanceActive = dodgeBackwardDistance; break;
                case PlayerMage.DodgeDirection.Left:
                case PlayerMage.DodgeDirection.Right: dodgeDistanceActive = dodgeSideDistance; break;
                default: dodgeDistanceActive = dodgeForwardDistance; break;
            }
            dodgeTimer = Mathf.Max(dodgeDuration, 0.05f);
            dodgeCooldownTimer = dodgeTimer + Mathf.Max(dodgeCooldown, 0f);
            hasMomentum = false;
            currentMomentumDecay = 0f;

            // 参数由 `PlayerMage` 写（它是"状态类参数"的唯一写入者，本类只写 Speed/Airborne/StrafeDir/Jump）。
            if (mage == null) mage = GetComponent<PlayerMage>();
            if (mage != null)
            {
                mage.PlayDodge(kind);
            }
            else if (anim != null)
            {
                // 没有 `PlayerMage`（例如木桩/占位阶段）时的兜底，保证翻滚动画仍然会播。
                anim.SetInteger(DodgeDirParam, (int)kind);
                anim.SetTrigger(DodgeTriggerParam);
            }
        }

        private void UpdateAnimPlayback(float dt)
        {
            if (anim == null) return;

            float target = AnimPlaybackTuner.DesiredScale(anim, planarVelocity, feel);
            anim.speed = Mathf.MoveTowards(anim.speed, target, Mathf.Max(feel.playbackLerp, 0.01f) * dt);
        }
    }
}
