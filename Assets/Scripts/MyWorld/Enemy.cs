using UnityEngine;

namespace MyWorld
{
    /// <summary>敌人会用的招式。</summary>
    public enum EnemyMove
    {
        Melee,          // 普通攻击：近身挥砍
        ShieldBash,     // 盾击：冒黄叹号预警 → 冲刺顶人 → 打掉玩家主手武器
        DashSlash,      // 冲刺斩：9 米内，蓄力 0.5s → 月牙范围斩 → 2 格击退
        ChargedStrike,  // 蓄力一击：蓄力 0.5s → 向前冲刺劈砍 → 流血 5s + 5 格击退
    }

    /// <summary>
    /// 近战敌人（KayKit 蛮兵）。行为：
    ///
    ///   在仇恨范围内**每 3 秒随机挑一个招式**（按距离过滤掉够不到的），每个招式都有前摇和特效；
    ///   挨打时有 30% 概率**举盾格挡**，免掉这次伤害。
    ///
    /// 只有**盾击**会把玩家的主手武器打掉，普通攻击和别的招式都不会。
    /// </summary>
    [DisallowMultipleComponent]
    [RequireComponent(typeof(CharacterController))]
    public class Enemy : MonoBehaviour, IDamageable
    {
        [Header("血量")]
        [SerializeField] private float maxHealth = 70f;

        [Header("仇恨范围")]
        [Tooltip("进入这个距离才会开始行动。不加限制的话会变成全图追人")]
        [SerializeField] private float aggroRange = 10f;
        [Tooltip("超出这个距离就放弃、回到待机。要比 aggroRange 大，否则会在边界反复横跳")]
        [SerializeField] private float deAggroRange = 15f;

        [Header("移动")]
        [SerializeField] private float walkSpeed = 3.0f;
        [SerializeField] private float runSpeed = 5.0f;
        [SerializeField] private float stopDistance = 1.9f;
        [SerializeField] private float turnLerp = 9f;
        [SerializeField] private float gravity = -26f;

        [Header("决策")]
        [Tooltip("每隔这么久挑一个招式")]
        [SerializeField] private float decisionInterval = 3f;

        [Header("蓄力锁定")]
        [Tooltip("蓄力的最后这么久，方向锁死不再跟踪玩家（0.5s 蓄力 + 0.2s 锁定 = 前 0.3s 跟踪）")]
        [SerializeField] private float windupLockTime = 0.2f;

        [Header("普通攻击")]
        [SerializeField] private float attackRange = 2.4f;
        [SerializeField] private float attackDamage = 10f;
        [Tooltip("施法/前摇时长，统一 0.3 秒")]
        [SerializeField] private float attackWindup = 0.3f;

        [Header("盾击（唯一会打掉玩家武器的招式，且不可被打断）")]
        [Tooltip("头顶冒黄色感叹号的预警时长")]
        [SerializeField] private float bashTelegraph = 0.3f;
        [Tooltip("只有玩家贴到这么近才会用盾击 —— 它是贴脸瞬发，不冲刺")]
        [SerializeField] private float bashRange = 2.4f;
        [SerializeField] private float bashKnockbackGrids = 1.5f;

        [Header("冲刺斩")]
        [Tooltip("玩家在这个距离内才会放")]
        [SerializeField] private float dashSlashRange = 9f;
        [SerializeField] private float dashSlashWindup = 0.3f;
        [Tooltip("先向前冲刺这么远，到位后再放月牙")]
        [SerializeField] private float dashSlashDashDistance = 4f;
        [SerializeField] private float dashSlashDashTime = 0.28f;
        [SerializeField] private float dashSlashDamage = 12f;
        [Tooltip("月牙的半径")]
        [SerializeField] private float dashSlashRadius = 4.2f;
        [Tooltip("月牙张开的夹角(度)")]
        [SerializeField] private float dashSlashArc = 130f;
        [SerializeField] private float dashSlashKnockbackGrids = 2f;

        [Header("蓄力一击")]
        [SerializeField] private float chargedWindup = 0.3f;
        [SerializeField] private float chargedDashSpeed = 15f;
        [SerializeField] private float chargedDashTime = 0.45f;
        [Tooltip("劈砍命中判定距离")]
        [SerializeField] private float chargedHitRange = 1.9f;
        [SerializeField] private float chargedDamage = 14f;
        [Tooltip("流血持续时间")]
        [SerializeField] private float bleedDuration = 5f;
        [Tooltip("流血每秒伤害")]
        [SerializeField] private float bleedDps = 4f;
        [SerializeField] private float chargedKnockbackGrids = 5f;

        [Header("防御")]
        [Tooltip("被攻击时举盾格挡的概率，格挡则完全免伤")]
        [SerializeField, Range(0f, 1f)] private float blockChance = 0.3f;

        [Header("击退单位")]
        [Tooltip("1「格」等于多少世界单位。'2 格击退' 就是 2×这个值")]
        [SerializeField] private float gridUnit = 2f;

        [Header("受击反馈")]
        [SerializeField] private float flashDuration = 0.12f;

        [Header("僵直")]
        [Tooltip("被抓钩抓住时全程僵直；松开后还会再僵直这么久")]
        [SerializeField] private float grabbedStunDuration = 1.0f;
        [Tooltip("普通受击的僵直时间")]
        [SerializeField] private float hitStunDuration = 0.5f;
        [Tooltip("两次硬直之间的最短间隔。没有它的话，连招可以不断刷新 stunTimer 把敌人永久锁死")]
        [SerializeField] private float hitStunCooldown = 1.5f;

        [Header("击退")]
        [Tooltip("击退的衰减速率。要远大于行走的跟随速度，击退才像「被打飞」而不是「被推一下」")]
        [SerializeField] private float knockbackDecay = 45f;
        [Tooltip("击退的最低初速 —— 决定爆发感")]
        [SerializeField] private float knockbackMinSpeed = 18f;

        private enum Phase { Approach, Windup, Dashing, Recover }

        private CharacterController cc;
        private Animator animator;
        private PlayerCombat player;
        private PlayerHealth playerHealth;

        private float health;
        private float verticalVelocity;
        private float flashTimer;
        private bool alive = true;
        private bool aggro;
        private bool beingPulled;
        private float stunTimer;
        private float hitStunCdTimer;
        private float animSpeed;
        private Vector3 knockbackVelocity;

        private Phase phase = Phase.Approach;
        private EnemyMove pendingMove;
        private float decisionTimer;
        private float phaseTimer;
        private Vector3 dashDir;
        private Vector3 dashStartPos;
        private float lastDashTravelled;
        private int dashStuckFrames;
        private bool moveResolved;   // 本次招式的判定是否已结算

        private Renderer[] renderers;
        private Material[] normalMats;
        private Material flashMat;

        [SerializeField] private HealthBar healthBar;

        private static readonly int SpeedHash = Animator.StringToHash("Speed");
        private static readonly int AttackHash = Animator.StringToHash("Attack");
        private static readonly int HitHash = Animator.StringToHash("Hit");
        private static readonly int DeadHash = Animator.StringToHash("Dead");

        public bool IsAlive => alive;
        public Transform Transform => transform;
        public bool IsStunned => beingPulled || stunTimer > 0f;

        /// <summary>被抓钩拉拽时调用：停手、进僵直。不暂停的话 AI 的移动会和拉拽打架。</summary>
        public void SetPulled(bool pulled)
        {
            beingPulled = pulled;
            if (animator != null) animator.SetTrigger(HitHash);

            if (pulled)
            {
                // 抓钩可以打断大部分施法，但**盾击打断不了**（它已经贴脸了，给玩家一个"躲开"的硬规则）
                if (pendingMove != EnemyMove.ShieldBash) CancelCurrentMove();
            }
            else
            {
                stunTimer = Mathf.Max(stunTimer, grabbedStunDuration);
            }
        }

        private void Awake()
        {
            cc = GetComponent<CharacterController>();
            animator = GetComponentInChildren<Animator>();
            health = maxHealth;
            decisionTimer = decisionInterval;

            var all = GetComponentsInChildren<Renderer>(true);
            var mine = new System.Collections.Generic.List<Renderer>(all.Length);
            foreach (var r in all)
                if (r.GetComponentInParent<HealthBar>() == null) mine.Add(r);
            renderers = mine.ToArray();

            normalMats = new Material[renderers.Length];
            for (int i = 0; i < renderers.Length; i++) normalMats[i] = renderers[i].sharedMaterial;

            flashMat = PlaceholderArt.NewLit(Color.white, 0f);
            flashMat.name = "M_EnemyFlash";
        }

        private void OnEnable() => DamageableRegistry.Register(this);
        private void OnDisable() => DamageableRegistry.Unregister(this);

        private void Start()
        {
            ResolvePlayer();
            if (healthBar == null) healthBar = GetComponentInChildren<HealthBar>(true);
            RefreshBar();
        }

        public void AttachHealthBar(HealthBar hb)
        {
            healthBar = hb;
            RefreshBar();
        }

        private void RefreshBar()
        {
            if (healthBar != null) healthBar.SetFill(maxHealth > 0f ? health / maxHealth : 0f);
        }

        private void ResolvePlayer()
        {
            if (player != null) return;
            player = Object.FindFirstObjectByType<PlayerCombat>();
            if (player != null) playerHealth = player.GetComponent<PlayerHealth>();
        }

        // ---------------- 受击 ----------------

        public void TakeDamage(float amount, Vector3 hitPoint, Vector3 hitNormal)
        {
            if (!alive) return;

            // 举盾格挡：概率免伤，并给个明确的反馈
            if (Random.value < blockChance)
            {
                ArcaneBurst.Spawn(transform.position + Vector3.up * 1.0f, Vector3.up, 0.7f,
                    new Color(0.75f, 0.8f, 0.9f));
                Debug.Log("[My World] 敌人举盾格挡，本次免伤");
                return;
            }

            health -= amount;
            flashTimer = flashDuration;

            // 普通攻击**不能打断施法**：正在蓄力时不进僵直，让它把招式放完。
            // （只有抓钩能打断，见 SetPulled）
            //
            // 硬直带 CD：玩家一套连招四段，如果每段都刷新 stunTimer，敌人会被永久锁死
            // （一直僵直、一次手都出不了）。所以只有冷却好了才吃这次硬直 ——
            // 冷却期内的打击照常掉血、照常闪白，只是不再续硬直。
            if (phase != Phase.Windup && hitStunCdTimer <= 0f)
            {
                stunTimer = Mathf.Max(stunTimer, hitStunDuration);
                hitStunCdTimer = hitStunCooldown;
            }

            RefreshBar();
            if (animator != null && health > 0f) animator.SetTrigger(HitHash);

            if (health <= 0f) Die();
        }

        private void Die()
        {
            alive = false;
            health = 0f;
            if (animator != null) animator.SetBool(DeadHash, true);
            Destroy(gameObject, 4f);
        }

        /// <summary>
        /// 把敌人按指定**距离**击退。和玩家那套一路子：
        /// 由 s = v²/(2a) 反推初速和衰减，所以"击退 2 格"始终是 2 格，
        /// 而不是"初速越大飞得越远"。最低初速负责爆发感。
        /// </summary>
        public void ApplyKnockback(Vector3 direction, float distance)
        {
            Vector3 flat = new Vector3(direction.x, 0f, direction.z);
            if (flat.sqrMagnitude < 0.0001f) return;

            float d = Mathf.Max(0.1f, distance);
            float speed = Mathf.Max(knockbackMinSpeed, Mathf.Sqrt(2f * knockbackDecay * d));
            knockbackVelocity = flat.normalized * speed;
        }

        /// <summary>
        /// 推进击退位移。在 Update 里、**在僵直判断之前**调用 ——
        /// 被打飞的那段时间本来就在僵直里，若只在非僵直分支里推进，表现就变成"原地站着不动"。
        /// </summary>
        private void TickKnockback(float dt)
        {
            if (knockbackVelocity.sqrMagnitude <= 0.0001f) return;

            // CharacterController.Move 的位移会按 transform 缩放打折（敌人缩放 0.68），
            // 冲刺里也是这么补偿的，这里保持一致。
            float scale = Mathf.Max(0.01f, transform.lossyScale.y);
            Vector3 step = knockbackVelocity * (dt / scale);
            cc.Move(new Vector3(step.x, 0f, step.z));

            float sp = knockbackVelocity.magnitude;
            float drop = knockbackDecay * dt;
            knockbackVelocity = sp <= drop ? Vector3.zero : knockbackVelocity * ((sp - drop) / sp);
        }

        // ---------------- 主循环 ----------------

        private void Update()
        {
            float dt = Time.deltaTime;

            UpdateFlash(dt);

            if (!alive)
            {
                ApplyGravityOnly(dt);
                if (animator != null) animator.SetFloat(SpeedHash, 0f);
                return;
            }

            ResolvePlayer();
            if (stunTimer > 0f) stunTimer -= dt;
            if (hitStunCdTimer > 0f) hitStunCdTimer -= dt;

            // 击退位移要**在僵直判断之前**推进：被打飞的那段时间本身就在僵直里
            TickKnockback(dt);

            if (IsStunned)
            {
                ApplyGravityOnly(dt);
                SetAnimSpeed(0f, dt);
                return;
            }

            if (player == null) { ApplyGravityOnly(dt); return; }

            Vector3 toPlayer = player.transform.position - transform.position;
            toPlayer.y = 0f;
            float dist = toPlayer.magnitude;
            Vector3 dir = dist > 0.001f ? toPlayer / dist : transform.forward;

            // 仇恨开关
            if (!aggro && dist <= aggroRange) aggro = true;
            else if (aggro && dist > deAggroRange) aggro = false;

            if (!aggro)
            {
                phase = Phase.Approach;
                decisionTimer = decisionInterval;
                ApplyGravityOnly(dt);
                SetAnimSpeed(0f, dt);
                return;
            }

            switch (phase)
            {
                case Phase.Approach: TickApproach(dt, dist, dir); break;
                case Phase.Windup: TickWindup(dt, dir); break;
                case Phase.Dashing: TickDash(dt); break;
                case Phase.Recover: TickRecover(dt); break;
            }
        }

        private void TickApproach(float dt, float dist, Vector3 dir)
        {
            // 面向玩家
            FaceDir(dir, dt);

            decisionTimer -= dt;
            if (decisionTimer <= 0f)
            {
                BeginMove(dist, dir);
                return;
            }

            // 还没到决策点，就先走过去
            if (dist > stopDistance)
            {
                float speed = dist > 6f ? runSpeed : walkSpeed;
                Vector3 motion = dir * (speed * dt);
                cc.Move(new Vector3(motion.x, verticalVelocity * dt, motion.z));
                SetAnimSpeed(dist > 6f ? 1f : 0.5f, dt);
            }
            else
            {
                ApplyGravityOnly(dt);
                SetAnimSpeed(0f, dt);
            }
        }

        /// <summary>每 3 秒在这里选一个招式；按距离过滤掉够不到的。</summary>
        private void BeginMove(float dist, Vector3 dir)
        {
            var candidates = new System.Collections.Generic.List<EnemyMove>();
            candidates.Add(EnemyMove.ChargedStrike);                    // 任何仇恨距离都能冲过来
            if (dist <= bashRange) candidates.Add(EnemyMove.ShieldBash); // 盾击是贴脸的，远了不放
            if (dist <= dashSlashRange) candidates.Add(EnemyMove.DashSlash);
            if (dist <= attackRange) candidates.Add(EnemyMove.Melee);

            pendingMove = candidates[Random.Range(0, candidates.Count)];
            moveResolved = false;

            switch (pendingMove)
            {
                case EnemyMove.Melee:
                    phase = Phase.Windup;
                    phaseTimer = attackWindup;
                    break;

                case EnemyMove.ShieldBash:
                    // 头顶先冒黄色感叹号预警，给玩家反应时间
                    phase = Phase.Windup;
                    phaseTimer = bashTelegraph;
                    SkillVfx.Exclamation(transform, 3.0f, bashTelegraph);
                    break;

                case EnemyMove.DashSlash:
                    phase = Phase.Windup;
                    phaseTimer = dashSlashWindup;
                    SkillVfx.Charge(transform, 1.0f, dashSlashWindup, SkillVfx.ChargeColor);
                    break;

                case EnemyMove.ChargedStrike:
                    phase = Phase.Windup;
                    phaseTimer = chargedWindup;
                    SkillVfx.Charge(transform, 1.0f, chargedWindup, SkillVfx.HeavyColor);
                    break;
            }

            dashDir = dir;
        }

        private void TickWindup(float dt, Vector3 dir)
        {
            // 蓄力分两段：前面一直跟踪玩家，最后 windupLockTime 秒方向锁死。
            // 锁定是为了给玩家"躲开的窗口"——不然会一直黏着你，没有可玩性。
            if (phaseTimer > windupLockTime)
            {
                dashDir = dir;          // 跟踪玩家
                FaceDir(dir, dt);
            }
            // 锁定段：dashDir 和朝向都不再变

            ApplyGravityOnly(dt);
            SetAnimSpeed(0f, dt);

            phaseTimer -= dt;
            if (phaseTimer > 0f) return;

            switch (pendingMove)
            {
                case EnemyMove.Melee:
                    // 近身挥砍
                    if (animator != null) animator.SetTrigger(AttackHash);
                    SkillVfx.Slash(transform.position, transform.forward, attackRange + 0.6f, SkillVfx.ChargeColor);
                    if (Vector3.Distance(Flat(player.transform.position), Flat(transform.position)) <= attackRange)
                        playerHealth?.TakeDamage(attackDamage, transform.position);
                    EnterRecover(0.35f);
                    break;

                case EnemyMove.ShieldBash:
                    // 贴脸瞬发：不冲刺，预警一结束就地结算（盾击不可被打断）
                    if (animator != null) animator.SetTrigger(AttackHash);
                    if (Vector3.Distance(Flat(player.transform.position), Flat(transform.position)) <= bashRange)
                        ResolveShieldBash();
                    EnterRecover(0.4f);
                    break;

                case EnemyMove.DashSlash:
                    // 先沿锁定方向冲刺一段，落地后再放月牙（冲刺的结算放在 TickDash 末尾）
                    if (dashDir.sqrMagnitude < 0.0001f) dashDir = transform.forward;
                    dashDir = Flat(dashDir).normalized;
                    dashDir = FaceTowardPlayer(dashDir, dir);
                    transform.rotation = Quaternion.LookRotation(dashDir, Vector3.up);
                    if (animator != null) animator.SetTrigger(AttackHash);
                    BeginDash();
                    phase = Phase.Dashing;
                    phaseTimer = dashSlashDashTime;
                    break;

                case EnemyMove.ChargedStrike:
                    // 蓄力结束 → 沿锁定方向冲刺劈砍
                    if (dashDir.sqrMagnitude < 0.0001f) dashDir = transform.forward;
                    dashDir = Flat(dashDir).normalized;
                    dashDir = FaceTowardPlayer(dashDir, dir);
                    transform.rotation = Quaternion.LookRotation(dashDir, Vector3.up);
                    if (animator != null) animator.SetTrigger(AttackHash);
                    BeginDash();
                    phase = Phase.Dashing;
                    phaseTimer = chargedDashTime;
                    break;
            }
        }

        /// <summary>抓钩把敌人拽走 = 打断施法（清掉正在蓄的招式）。</summary>
        private void CancelCurrentMove()
        {
            phase = Phase.Approach;
            phaseTimer = 0f;
            moveResolved = false;
            decisionTimer = decisionInterval;
        }

        private void TickDash(float dt)
        {
            // 冲刺途中持续拖出斩击残影
            SkillVfx.Slash(transform.position, dashDir, 2.2f,
                pendingMove == EnemyMove.DashSlash ? SkillVfx.ChargeColor : SkillVfx.HeavyColor);

            // 冲刺斩按**实际位移**收尾，而不是速度×时间。
            // CharacterController.Move 的实际位移会被它所在 transform 的缩放打折（敌人缩放 0.68），
            // 用时间推算是走不准的 —— 实测标称 4 米只走了 1.06 米。
            float travelled = Flat(transform.position - dashStartPos).magnitude;
            float remain = float.MaxValue;
            bool distanceBased = pendingMove == EnemyMove.DashSlash;
            if (distanceBased) remain = Mathf.Max(0f, dashSlashDashDistance - travelled);

            float speed = CurrentDashSpeed();
            float stepLen = distanceBased ? Mathf.Min(speed * dt, remain) : speed * dt;

            // CharacterController.Move 的位移会**按 transform 缩放打折**（敌人缩放 0.68），
            // 所以这里除以缩放补偿，才能得到想要的世界位移。
            // 注意不能直接写 transform.position：其它阶段还在调 cc.Move，
            // 会把直接写入的位置覆盖回它内部维护的位置。
            float scale = Mathf.Max(0.01f, transform.lossyScale.y);
            Vector3 step = dashDir * (stepLen / scale);
            cc.Move(new Vector3(step.x, verticalVelocity * dt, step.z));
            SetAnimSpeed(1f, dt);

            // 蓄力一击：冲刺途中碰到玩家就结算
            if (pendingMove == EnemyMove.ChargedStrike && !moveResolved)
            {
                float d = Vector3.Distance(Flat(player.transform.position), Flat(transform.position));
                if (d <= CurrentHitRange())
                {
                    moveResolved = true;
                    ResolveChargedStrike();
                }
            }

            phaseTimer -= dt;

            bool finished;
            if (distanceBased)
            {
                // 被挡住（撞到玩家/墙）就别一直卡在冲刺状态：
                // 连续几帧没有前进就提前收尾，照样把月牙放出来
                if (travelled <= lastDashTravelled + 0.002f) dashStuckFrames++;
                else dashStuckFrames = 0;
                lastDashTravelled = travelled;

                finished = remain <= 0.01f || dashStuckFrames >= 3;
            }
            else
            {
                finished = phaseTimer <= 0f;
            }

            if (!finished) return;

            // 冲刺斩：冲到位置之后才放出月牙
            if (pendingMove == EnemyMove.DashSlash && !moveResolved)
            {
                moveResolved = true;
                SkillVfx.Crescent(transform.position, dashDir,
                    dashSlashRadius, dashSlashArc, SkillVfx.ChargeColor);
                ResolveArcHit(dashSlashRange, dashSlashArc, dashSlashDamage, dashSlashKnockbackGrids);
            }

            EnterRecover(0.5f);
        }

        private void TickRecover(float dt)
        {
            ApplyGravityOnly(dt);
            SetAnimSpeed(0f, dt);
            phaseTimer -= dt;
            if (phaseTimer <= 0f)
            {
                phase = Phase.Approach;
                decisionTimer = decisionInterval;   // 下一次决策再等 3 秒
            }
        }

        private void EnterRecover(float time)
        {
            phase = Phase.Recover;
            phaseTimer = time;
        }

        /// <summary>
        /// 冲刺方向修正：蓄力时锁定的方向如果**背离**玩家（比如敌人绕到了玩家背后，
        /// 那段时间的"朝向玩家"已经翻了过来），直接纠正过来，
        /// 否则会出现"蓄力完朝反方向冲走"。
        /// </summary>
        private Vector3 FaceTowardPlayer(Vector3 lockedDir, Vector3 dirToPlayer)
        {
            Vector3 d = Flat(dirToPlayer);
            if (d.sqrMagnitude < 0.0001f) return lockedDir;
            d.Normalize();

            // 锁定方向和现在"朝着玩家"的方向差了超过约 90°，说明锁反了
            if (Vector3.Dot(lockedDir, d) < 0.05f) return d;
            return lockedDir;
        }

        private void BeginDash()
        {
            dashStartPos = transform.position;
            lastDashTravelled = 0f;
            dashStuckFrames = 0;
        }

        /// <summary>冲刺速度。冲刺斩按"距离/时间"反推，保证正好冲 dashSlashDashDistance 那么远。</summary>
        private float CurrentDashSpeed()
        {
            if (pendingMove == EnemyMove.DashSlash)
                return dashSlashDashDistance / Mathf.Max(0.01f, dashSlashDashTime);
            return chargedDashSpeed;
        }

        private float CurrentHitRange() => chargedHitRange;

        // ---------------- 招式结算 ----------------

        /// <summary>盾击：只有这个会把玩家的主手武器打掉。</summary>
        private void ResolveShieldBash()
        {
            player.KnockOffMainHand();
            KnockPlayer(transform.forward, bashKnockbackGrids);
            ArcaneBurst.Spawn(Flat(player.transform.position) + Vector3.up * 1.0f, Vector3.up, 0.9f, SkillVfx.WarningColor);
        }

        /// <summary>蓄力一击：流血 5 秒 + 5 格击退。</summary>
        private void ResolveChargedStrike()
        {
            playerHealth?.TakeDamage(chargedDamage, transform.position);
            playerHealth?.ApplyBleed(bleedDuration, bleedDps);
            KnockPlayer(dashDir, chargedKnockbackGrids);
            ArcaneBurst.Spawn(Flat(player.transform.position) + Vector3.up * 1.0f, Vector3.up, 1.1f, SkillVfx.HeavyColor);
        }

        /// <summary>月牙范围判定：距离 + 夹角都在范围内才算命中。</summary>
        private void ResolveArcHit(float range, float arcDegrees, float damage, float knockbackGrids)
        {
            Vector3 to = Flat(player.transform.position) - Flat(transform.position);
            if (to.magnitude > range) return;
            if (Vector3.Angle(transform.forward, to) > arcDegrees * 0.5f) return;

            playerHealth?.TakeDamage(damage, transform.position);
            KnockPlayer(to, knockbackGrids);
        }

        private void KnockPlayer(Vector3 dir, float grids)
        {
            var ctrl = player.GetComponent<PlayerController8Dir>();
            if (ctrl != null) ctrl.ApplyKnockback(dir, grids * gridUnit);
        }

        // ---------------- 辅助 ----------------

        private static Vector3 Flat(Vector3 v) => new Vector3(v.x, 0f, v.z);

        private void FaceDir(Vector3 dir, float dt)
        {
            if (dir.sqrMagnitude < 0.0001f) return;
            float yaw = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
            transform.rotation = Quaternion.Euler(0f,
                Mathf.LerpAngle(transform.rotation.eulerAngles.y, yaw, 1f - Mathf.Exp(-turnLerp * dt)), 0f);
        }

        private void SetAnimSpeed(float target, float dt)
        {
            animSpeed = Mathf.MoveTowards(animSpeed, target, 6f * dt);
            if (animator != null) animator.SetFloat(SpeedHash, animSpeed);
        }

        private void ApplyGravityOnly(float dt)
        {
            if (cc == null) return;
            if (cc.isGrounded && verticalVelocity < 0f) verticalVelocity = -2f;
            verticalVelocity += gravity * dt;
            cc.Move(new Vector3(0f, verticalVelocity * dt, 0f));
        }

        private void UpdateFlash(float dt)
        {
            if (flashTimer <= 0f) return;

            flashTimer -= dt;
            bool on = flashTimer > 0f;
            for (int i = 0; i < renderers.Length; i++)
            {
                if (renderers[i] == null) continue;
                renderers[i].sharedMaterial = on ? flashMat : normalMats[i];
            }
        }

        private void OnDestroy()
        {
            if (flashMat != null) Destroy(flashMat);
        }
    }
}
