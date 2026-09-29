using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 8 方向行走：输入方向直接决定移动方向，朝向吸附到 8 个方向之一。
    /// 用 CharacterController 而不是 Rigidbody —— 俯视游戏贴着墙走的时候，
    /// 刚体会被弹开/抖动，CharacterController 自带沿墙滑行，手感干净得多。
    ///
    /// 相机不参与转向（相机 yaw 固定为 0），所以 WASD 永远对应世界坐标的四个正方向，
    /// 角色也就只有 8 个朝向，不会出现"斜着看世界"导致的方向错乱。
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
        [Tooltip("动画 Speed 参数的跟随速度：0=站住 0.5=走 1=跑")]
        [SerializeField] private float animSpeedLerp = 8f;

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

        private Vector3 planarVelocity;   // 水平速度
        private float verticalVelocity;
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

        /// <summary>当前是否真的在移动（给动画/音效用）。</summary>
        public bool IsMoving => planarVelocity.sqrMagnitude > 0.04f;

        /// <summary>是否正在疾跑（按着 Shift 且有移动输入）。</summary>
        public bool IsSprinting { get; private set; }

        /// <summary>喂给 Animator 的 Speed 参数：0=站住、0.5=走、1=跑。</summary>
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

        /// <summary>当前朝向对应的 8 方向索引，0=正前(+Z)，顺时针递增。</summary>
        public int FacingIndex => Mathf.RoundToInt(Mathf.Repeat(yawTarget, 360f) / 45f) % 8;

        private void Awake()
        {
            cc = GetComponent<CharacterController>();
            input = GetComponent<MyWorldInput>();
            yaw = yawTarget = transform.eulerAngles.y;
        }

        private void Update()
        {
            float dt = Time.deltaTime;

            if (stunTimer > 0f) stunTimer -= dt;

            Vector2 move = input != null ? input.Move : Vector2.zero;
            // 僵直期间忽略输入：让击退/被拉拽的动量大完再接受操作
            if (IsStunned) move = Vector2.zero;
            bool hasMove = move.sqrMagnitude > 0.01f;
            IsSprinting = hasMove && input != null && input.Sprint;

            if (hasExternalVelocity)
            {
                // 被抓钩拽着走时，WASD 完全不参与——想改方向只能松手。
                planarVelocity = externalVelocity;
                animSpeed = Mathf.MoveTowards(animSpeed, 1f, animSpeedLerp * dt);
            }
            else if (hasMomentum && !hasMove)
            {
                // 惯性滑行：衰减速率看这次惯性是抓钩来的（慢）还是击退来的（快）。
                planarVelocity = Vector3.MoveTowards(planarVelocity, Vector3.zero, currentMomentumDecay * dt);
                animSpeed = Mathf.MoveTowards(animSpeed, planarVelocity.sqrMagnitude > 0.25f ? 1f : 0f,
                    animSpeedLerp * dt);
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
                float targetSpeed = (IsSprinting ? runSpeed : walkSpeed) * speedMultiplier;

                // 输入是屏幕空间：x 向右，y 向上(屏幕上方)。相机 yaw=0，
                // 所以屏幕上方正好是世界 +Z，直接映射即可。
                Vector3 desired = new Vector3(move.x, 0f, move.y) * targetSpeed;

                float rate = desired.sqrMagnitude > planarVelocity.sqrMagnitude ? accel : decel;
                planarVelocity = Vector3.MoveTowards(planarVelocity, desired, rate * dt);

                // 动画速度用"意图"而不是实际速度：起步瞬间就能切到走/跑，不会先站一下再动。
                float animTarget = hasMove ? (IsSprinting ? 1f : 0.5f) : 0f;
                animSpeed = Mathf.MoveTowards(animSpeed, animTarget, animSpeedLerp * dt);
            }

            // 朝向优先级：抓钩拉拽 > 锁定目标 > 鼠标(仅出手瞬间) > 移动方向。
            // 拉拽时必须朝着被拽的方向，否则会出现"人往前跑、身体倒着飞"的错乱动画。
            if (hasReelFacing)
                yawTarget = SnapTo45(reelFacing.x, reelFacing.z);
            else if (hasForcedFacing)
                yawTarget = SnapTo45(forcedFacing.x, forcedFacing.z);
            else if (hasAimFacing)
                yawTarget = SnapTo45(aimFacing.x, aimFacing.z);
            else if (move.sqrMagnitude > 0.01f)
                yawTarget = SnapTo45(move.x, move.y);

            yaw = Mathf.LerpAngle(yaw, yawTarget, 1f - Mathf.Exp(-turnLerp * dt));
            transform.rotation = Quaternion.Euler(0f, yaw, 0f);

            // 跳跃（带土狼时间：刚走出平台边缘的一小会儿也能起跳）
            if (cc.isGrounded) lastGroundedTime = Time.time;
            bool canJump = Time.time - lastGroundedTime <= coyoteTime;

            if (input != null && input.JumpPressed && canJump && verticalVelocity <= 0f)
            {
                verticalVelocity = jumpSpeed;
                lastGroundedTime = -99f;   // 一次按键只起跳一次
            }

            // 重力
            if (cc.isGrounded && verticalVelocity < 0f) verticalVelocity = groundedStick;
            verticalVelocity += gravity * dt;

            Vector3 motion = planarVelocity + Vector3.up * verticalVelocity;
            cc.Move(motion * dt);
        }
    }
}
