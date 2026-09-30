using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 玩家的血量。有了它敌人的近战才有意义（否则被打什么都不发生）。
    ///
    /// 目前只做最小闭环：掉血 → 播受击动作 → 空血后原地复活。
    /// HUD 血条属于后面的界面系统，这里先把 Health / MaxHealth 暴露出去给它用。
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerHealth : MonoBehaviour
    {
        [Header("血量")]
        [SerializeField] private float maxHealth = 100f;
        [Tooltip("空血后多久复活(秒)")]
        [SerializeField] private float reviveDelay = 2.5f;

        [Header("受击无敌帧")]
        [Tooltip("这段时间内不再吃伤害，避免被连续攻击瞬间打死")]
        [SerializeField] private float invulnerableTime = 0.4f;

        [Header("受击僵直")]
        [Tooltip("被打中后的僵直时长。没有它，玩家按着 WASD 会立刻抵消掉击退位移")]
        [SerializeField] private float hitStun = 0.3f;

        [Header("流血")]
        [Tooltip("流血期间疾跑，流血伤害翻倍")]
        [SerializeField] private float sprintBleedMultiplier = 2f;
        [Tooltip("流血期间的移速倍率")]
        [SerializeField] private float bleedSpeedMultiplier = 0.85f;

        private float health;
        private float invulnerable;
        private float reviveTimer;
        private PlayerMage mage;
        private Vector3 spawnPoint;

        private float bleedTimer;
        private float bleedDps;
        private float bleedTick;
        private PlayerController8Dir movement;
        private PlayerCombat combat;
        private WeaponLoadout loadout;
        private bool bleedingApplied;

        /// <summary>是否正在流血。</summary>
        public bool IsBleeding => bleedTimer > 0f;

        public float Health => health;
        public float MaxHealth => maxHealth;
        public float HealthFraction => maxHealth > 0f ? Mathf.Clamp01(health / maxHealth) : 0f;
        public bool IsAlive => health > 0f;

        /// <summary>血量变化时触发，HUD 用它刷新。</summary>
        public event System.Action<float, float> HealthChanged;

        private void Awake()
        {
            mage = GetComponent<PlayerMage>();
            movement = GetComponent<PlayerController8Dir>();
            combat = GetComponent<PlayerCombat>();
            loadout = GetComponent<WeaponLoadout>();
            spawnPoint = transform.position;
            health = maxHealth;
        }

        private void Start()
        {
            // 烘焙场景里 Awake 的时序不可靠，这里再兜一次
            if (mage == null) mage = GetComponent<PlayerMage>();
            if (movement == null) movement = GetComponent<PlayerController8Dir>();
            HealthChanged?.Invoke(health, maxHealth);
        }

        /// <summary>挂上流血：持续 duration 秒，每秒 dps 点伤害。</summary>
        public void ApplyBleed(float duration, float dps)
        {
            bleedTimer = Mathf.Max(bleedTimer, duration);
            bleedDps = Mathf.Max(bleedDps, dps);
            bleedTick = 0f;
            SyncBleedState();
        }

        /// <summary>把"流血中"的副作用同步给移动组件（降速）。</summary>
        private void SyncBleedState()
        {
            bool now = IsBleeding;
            if (now == bleedingApplied) return;

            bleedingApplied = now;
            movement?.SetSpeedMultiplier(now ? bleedSpeedMultiplier : 1f);
        }

        private void TickBleed(float dt)
        {
            if (bleedTimer <= 0f)
            {
                SyncBleedState();
                return;
            }

            bleedTimer -= dt;
            if (bleedTimer <= 0f)
            {
                bleedDps = 0f;
                SyncBleedState();
                return;
            }

            // 疾跑时流血伤害翻倍 —— 逼玩家在流血时做取舍
            float dps = bleedDps;
            if (movement != null && movement.IsSprinting) dps *= sprintBleedMultiplier;

            // 按 0.5 秒一跳结算，别每帧都触发受击表现
            bleedTick += dt;
            if (bleedTick >= 0.5f)
            {
                bleedTick -= 0.5f;
                health = Mathf.Max(0f, health - dps * 0.5f);
                HealthChanged?.Invoke(health, maxHealth);
                if (health <= 0f)
                {
                    reviveTimer = reviveDelay;
                    Debug.Log("[My World] 玩家失血倒下");
                }
            }
        }

        public void TakeDamage(float amount, Vector3 fromPosition)
        {
            if (!IsAlive) return;
            if (invulnerable > 0f) return;

            GameAudio.PlayHurt();   // ⑤ 受击音（T-063）—— 真正吃到伤害时才响（上面两道门都已放行）

            // 举盾格挡：只挡正面来的伤害，按盾的倍率减伤
            // T-079 §⑦ 片 2：`blocked` **只在下面 80° 角检内部、真的减伤那一刻**置 true ——
            // 它是"**这次真被挡住了**"（事实），而 `combat.IsBlocking` 只是"**盾举着**"（意图）。
            // 侧后方挨打时这个变量保持 false → 走普通受击表现，不播 `Block_Hit`（G3 的反向判据）。
            bool blocked = false;
            if (combat == null) combat = GetComponent<PlayerCombat>();
            if (combat != null && combat.IsBlocking)
            {
                Vector3 toAttacker = fromPosition - transform.position;
                toAttacker.y = 0f;
                // 攻击者在正面 80° 内才算挡住
                if (Vector3.Angle(transform.forward, toAttacker) <= 80f)
                {
                    var shield = loadout != null ? loadout.OffHand : null;
                    float mult = shield != null ? shield.blockDamageMultiplier : 0.25f;
                    amount *= mult;
                    blocked = true;   // ★ 就在这一行置位：与减伤同层，不早不晚
                    ArcaneBurst.Spawn(transform.position + Vector3.up * 1.0f, Vector3.up, 0.7f,
                        new Color(0.8f, 0.85f, 0.95f));
                }
            }

            health = Mathf.Max(0f, health - amount);
            invulnerable = invulnerableTime;
            movement?.ApplyStun(hitStun);   // 僵直，让击退位移真的能打出来
            // T-079 §⑦ G2：**表现跟随事实** —— 真挡住 → 格挡受击；没挡住 → 普通受击。
            // 两支互斥（不是"两个都播、让 Animator 挑"）：同帧两个 Trigger 谁赢取决于 AnyState 顺序，
            // 那是不确定的，而且会让 `Block_Hit` 静默地永远播不出来。
            if (blocked) mage?.PlayBlockHit();
            else mage?.PlayHit();
            HealthChanged?.Invoke(health, maxHealth);

            if (health <= 0f)
            {
                reviveTimer = reviveDelay;
                Debug.Log("[My World] 玩家倒下，稍后复活");
            }
        }

        public void Heal(float amount)
        {
            if (!IsAlive) return;
            health = Mathf.Min(maxHealth, health + amount);
            HealthChanged?.Invoke(health, maxHealth);
        }

        private void Update()
        {
            float dt = Time.deltaTime;

            if (invulnerable > 0f) invulnerable -= dt;
            TickBleed(dt);

            if (!IsAlive)
            {
                reviveTimer -= dt;
                if (reviveTimer <= 0f) Revive();
            }
        }

        private void Revive()
        {
            health = maxHealth;
            invulnerable = 1.5f;
            bleedTimer = 0f;
            bleedDps = 0f;
            SyncBleedState();
            transform.position = spawnPoint;

            // CharacterController 会残留速度，清一下免得复活瞬间乱飘
            var ctrl = GetComponent<PlayerController8Dir>();
            if (ctrl != null)
            {
                ctrl.ClearExternalVelocity();
                ctrl.ClearReelFacing();
            }

            HealthChanged?.Invoke(health, maxHealth);
            Debug.Log("[My World] 玩家已复活");
        }
    }
}
