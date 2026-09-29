using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 武器使用入口：把输入分发到主手/副手的武器行为上。
    ///
    /// 左键 = 用**当前手**的武器（C 切换的是"当前操作哪只手"，不是换装备）
    /// 右键 = 用**副手**武器（按住持续，抓钩靠松手保留动量）
    /// 中键 = 锁定（在 PlayerLockOn 里处理）
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerCombat : MonoBehaviour
    {
        [Header("施法点")]
        [SerializeField] private float castHeight = 1.05f;
        [SerializeField] private float castForward = 0.6f;

        [Header("挥砍")]
        [Tooltip("挥砍检测的中心高度")]
        [SerializeField] private float meleeHeight = 1.0f;

        [Header("出手时转向鼠标")]
        [Tooltip("出手后这段时间内朝向交给鼠标，过了就回到 WASD 控制")]
        [SerializeField] private float aimTurnDuration = 0.45f;

        private WeaponLoadout loadout;
        private WeaponMount mount;
        private GrappleWeapon grapple;
        private PlayerMage mage;
        private MyWorldInput input;
        private PlayerLockOn lockOn;
        private PlayerAim aim;
        private PlayerController8Dir movement;
        private float cooldown;
        private float aimTurnTimer;

        /// <summary>是否正处于"出手转向鼠标"的窗口内（PlayerAim 靠它决定要不要接管朝向）。</summary>
        public bool AimingAtMouse => aimTurnTimer > 0f;

        // 挥砍刀光的颜色与形状参数已迁到 `SkillVfx`（T-010）：
        // 参数长在判定文件里，每次调刀光都要动这里，容易误伤判定。本文件不再持有视觉参数。

        [Header("连招")]
        [Tooltip("一套连招共 4 段：横劈 → 下劈 → 斜劈 → 突刺。" +
                 "这是两刀之间的最大间隔，超时后再按就从第一段重新开始")]
        [SerializeField] private float comboResetTime = 1.1f;

        /// <summary>已经起手、但还没到命中帧的那一刀。命中帧由动画事件回调消费。</summary>
        private WeaponDefinition pendingSwing;

        /// <summary>
        /// 那一刀是哪一段连招。必须在起手时**快照**下来：
        /// 命中帧是 0.2 秒后才回调的，若那时才读 comboStep，中途又按了一下就已经变成下一段了
        /// （击退会挂到错的那一刀上）。
        /// </summary>
        private int pendingStep = -1;

        /// <summary>当前连招推进到第几段（0..3）。</summary>
        private int comboStep;

        /// <summary>连招窗口剩余时间；归零后再出手就从第一段重来。</summary>
        private float comboWindow;

        private readonly Collider[] meleeHits = new Collider[24];
        private readonly HashSet<IDamageable> meleeDamaged = new HashSet<IDamageable>();

        /// <summary>
        /// 惰性补引用，而不是只在 Awake 里取一次。
        /// 这个组件是烘焙时 AddComponent 上去的，Awake 的调用时机不可靠
        /// （被 enabled=false 过、或烘焙/重载时序问题都可能让它没跑），
        /// 一旦没跑，所有 GetComponent 引用就全是 null，抓钩/攻击会静默失效。
        /// </summary>
        private void EnsureRefs()
        {
            if (loadout == null) loadout = GetComponent<WeaponLoadout>();
            if (mount == null) mount = GetComponentInChildren<WeaponMount>();
            if (grapple == null) grapple = GetComponent<GrappleWeapon>();
            if (mage == null) mage = GetComponent<PlayerMage>();
            if (input == null) input = GetComponent<MyWorldInput>();
            if (lockOn == null) lockOn = GetComponent<PlayerLockOn>();
            if (aim == null) aim = GetComponent<PlayerAim>();
            if (movement == null) movement = GetComponent<PlayerController8Dir>();
        }

        private void Start()
        {
            EnsureRefs();
            if (mount != null && loadout != null) mount.Refresh(loadout);
            if (grapple != null)
                grapple.Configure(GetComponent<PlayerController8Dir>(),
                    mount != null ? mount.OffHandSlot : null);
        }

        private void Update()
        {
            if (cooldown > 0f) cooldown -= Time.deltaTime;
            if (aimTurnTimer > 0f) aimTurnTimer -= Time.deltaTime;
            if (comboWindow > 0f) comboWindow -= Time.deltaTime;

            EnsureRefs();
            if (input == null || loadout == null) return;

            // 受击僵直期间不能出手，但抓钩该松还是要松（否则会一直挂着）
            bool stunned = movement != null && movement.IsStunned;
            if (grapple != null && grapple.IsBusy && (!input.OffHandHeld || stunned)) grapple.Release();
            if (stunned) return;

            var off = loadout.OffHand;
            bool shieldUp = off != null && off.kind == WeaponKind.Shield && input.OffHandHeld;
            IsBlocking = shieldUp;

            // 右键 = 副手。盾是"长按举盾"，不主动出手；其余副手按住即持续（抓钩）
            if (input.OffHandPressed && !shieldUp) Use(off);

            // 左键 = 主手。举盾时左键改成放盾击（用户规则：按住右键举盾 + 按左键 = 盾击）
            if (input.AttackHeld)
            {
                if (shieldUp)
                {
                    if (input.AttackPressed && cooldown <= 0f) ShieldBash(off);
                }
                else
                {
                    Use(loadout.MainHand);
                }
            }
        }

        /// <summary>使用一件武器。空手/冷却中会直接忽略。</summary>
        public void Use(WeaponDefinition weapon)
        {
            EnsureRefs();
            if (weapon == null) return;

            switch (weapon.kind)
            {
                case WeaponKind.Staff:
                case WeaponKind.Gauntlet:
                    if (cooldown <= 0f) CastSpell(weapon);
                    break;

                case WeaponKind.Sword:
                    if (cooldown <= 0f) SwingSword(weapon);
                    break;

                case WeaponKind.Grapple:
                    // 出手时也要转向鼠标，否则钩子会朝着"角色还没转过去的旧朝向"飞
                    aimTurnTimer = aimTurnDuration;
                    if (grapple != null) grapple.Fire(weapon, CurrentAimDirection());
                    break;

                case WeaponKind.Bow:
                    if (cooldown <= 0f) ShootArrow(weapon);
                    break;

                case WeaponKind.Shield:
                    // 盾的主动技能是盾击；平时右键是"举盾格挡"（见 Update）
                    if (cooldown <= 0f) ShieldBash(weapon);
                    break;
            }
        }

        // ---------------- 法术 ----------------

        private Vector3 CastOrigin => transform.position
                                      + Vector3.up * castHeight
                                      + transform.forward * castForward;

        /// <summary>当前该打的方向：锁定目标 > 鼠标 > 角色朝向。</summary>
        private Vector3 CurrentAimDirection()
        {
            if (lockOn != null && lockOn.IsLocked)
                return (lockOn.AimPoint - transform.position).normalized;
            if (aim != null && aim.HasMouseDirection)
                return aim.MouseDirection.normalized;
            return transform.forward;
        }

        private void CastSpell(WeaponDefinition weapon)
        {
            float cd = weapon.cooldown;
            float damage = weapon.damage;

            // 副手装魔法护手：施法更快，但伤害大幅降低
            if (loadout.HasGauntlet)
            {
                var g = loadout.OffHand;
                cd /= Mathf.Max(g.castSpeedMultiplier, 0.01f);
                damage *= g.castDamageMultiplier;
            }

            cooldown = cd;
            aimTurnTimer = aimTurnDuration;   // 出手瞬间把朝向交给鼠标
            mage?.PlayCast();

            // 弹道方向：锁定 > 鼠标 > 角色朝向。
            // 用鼠标方向而不是 transform.forward，是因为朝向要经过 Lerp 吸附，
            // 出手那一帧还没转到，照 forward 打会偏。
            Vector3 dir;
            if (lockOn != null && lockOn.IsLocked)
                dir = lockOn.AimPoint - CastOrigin;
            else if (aim != null && aim.HasMouseDirection)
                dir = aim.MouseDirection;
            else
                dir = transform.forward;
            if (dir.sqrMagnitude < 0.0001f) dir = transform.forward;

            SpellProjectile.Spawn(CastOrigin, dir.normalized, transform, damage);
        }

        // ---------------- 弓 ----------------

        private void ShootArrow(WeaponDefinition weapon)
        {
            cooldown = weapon.cooldown;
            aimTurnTimer = aimTurnDuration;   // 出手时转向鼠标
            mage?.PlayAttack();

            Vector3 dir = CurrentAimDirection();
            ArrowProjectile.Spawn(CastOrigin, dir, transform,
                weapon.damage, weapon.arrowSpeed, weapon.arrowLifeTime, weapon.arrowRadius);
        }

        // ---------------- 盾 ----------------

        /// <summary>举盾格挡中（右键按住 + 副手是盾）。PlayerHealth 用它减伤。</summary>
        public bool IsBlocking { get; private set; }

        /// <summary>盾击：把正面的敌人击退 + 造成伤害。</summary>
        private void ShieldBash(WeaponDefinition weapon)
        {
            cooldown = weapon.cooldown;
            aimTurnTimer = aimTurnDuration;
            mage?.PlayAttack();

            Vector3 center = transform.position + Vector3.up * meleeHeight;
            int count = Physics.OverlapSphereNonAlloc(
                center, weapon.shieldBashRange, meleeHits, ~0, QueryTriggerInteraction.Ignore);

            meleeDamaged.Clear();
            for (int i = 0; i < count; i++)
            {
                var col = meleeHits[i];
                if (col == null || col.transform.IsChildOf(transform)) continue;

                Vector3 to = col.transform.position - center;
                to.y = 0f;
                if (Vector3.Angle(transform.forward, to) > 80f) continue;   // 只打正面

                var target = col.GetComponentInParent<IDamageable>();
                if (target == null || !target.IsAlive) continue;
                if (!meleeDamaged.Add(target)) continue;

                target.TakeDamage(weapon.shieldBashDamage, col.ClosestPoint(center), Vector3.up);

                // 敌人自己负责被击退；这里直接推动它的位移
                var cc = col.GetComponentInParent<CharacterController>();
                if (cc != null && to.sqrMagnitude > 0.0001f)
                    cc.Move(to.normalized * (weapon.shieldBashKnockbackGrids * 2f) * 0.35f);
            }

            ArcaneBurst.Spawn(center + transform.forward * (weapon.shieldBashRange * 0.5f),
                transform.forward, 0.8f, new Color(0.8f, 0.85f, 0.95f));
            Debug.Log("[My World] 盾击");
        }

        // ---------------- 剑 ----------------

        private void SwingSword(WeaponDefinition weapon)
        {
            cooldown = weapon.cooldown;
            aimTurnTimer = aimTurnDuration;   // 挥砍同样先转向鼠标

            // 连招推进：在窗口内接着下一段，超时了就从第一段重来。
            // 用 % ComboLength 绕回来，所以第四段之后再按会回到横劈，循环成套。
            comboStep = comboWindow > 0f ? (comboStep + 1) % PlayerMage.ComboLength : 0;
            comboWindow = comboResetTime;

            pendingSwing = weapon;            // 伤害与特效推迟到命中帧，见 OnSlashImpact
            pendingStep = comboStep;          // 快照段位：命中帧回调时 comboStep 可能已经变了
            mage?.PlayAttack(comboStep);
        }

        /// <summary>
        /// 挥砍命中帧的回调。由攻击剪辑上的 AnimationEvent 触发
        /// （四段各自的时间不同，都是采样手臂角速度量出来的峰值帧），
        /// 经 `AnimEventRelay` 从 Animator 所在物体转发上来。
        ///
        /// **为什么挪到这里**：原先按键当帧就结算伤害并生成爆花，所以表现是
        /// "人还没挥、特效先炸出来"。现在按键只负责起手，命中帧才真正出手。
        /// </summary>
        public void OnSlashImpact()
        {
            var weapon = pendingSwing;
            int step = pendingStep;
            pendingSwing = null;
            pendingStep = -1;
            if (weapon == null) return;

            Vector3 center = transform.position + Vector3.up * meleeHeight;
            int count = Physics.OverlapSphereNonAlloc(
                center, weapon.meleeRange, meleeHits, ~0, QueryTriggerInteraction.Ignore);

            // 最后一段是突刺：命中的敌人要被打飞。先收集，扫完再推，免得边改位置边判定。
            bool finisher = step == PlayerMage.ComboLength - 1 && weapon.stabKnockbackGrids > 0f;

            meleeDamaged.Clear();
            for (int i = 0; i < count; i++)
            {
                var col = meleeHits[i];
                if (col == null || col.transform.IsChildOf(transform)) continue;

                Vector3 to = col.transform.position - center;
                to.y = 0f;
                if (Vector3.Angle(transform.forward, to) > weapon.meleeHalfAngle) continue;

                var target = col.GetComponentInParent<IDamageable>();
                if (target == null || !target.IsAlive) continue;
                if (!meleeDamaged.Add(target)) continue;   // 同一目标只打一次

                target.TakeDamage(weapon.damage, col.ClosestPoint(center), Vector3.up);

                if (finisher)
                {
                    var enemy = col.GetComponentInParent<Enemy>();
                    if (enemy != null)
                        enemy.ApplyKnockback(to.sqrMagnitude > 0.0001f ? to : transform.forward,
                                             weapon.stabKnockbackGrids * 2f);   // 1 格 = 2 米，和敌人技能同一套换算
                }
            }

            // 挥砍刀光：一段有厚度的弧带，形状／朝向／层宽／颜色全部在 SkillVfx 里。
            // 这里只把**判定**用的半径和半张角原样递过去，视觉参数一概不写在本文件。
            // ⚠️ 判定条件、范围、伤害、击退都不在这里动。
            SkillVfx.SwordSlash(center, transform.forward, weapon.meleeRange, weapon.meleeHalfAngle, finisher);
        }

        // ---------------- 掉武器 / 拾取 ----------------

        /// <summary>
        /// 主手武器被打掉（被抓钩命中、被盾击时由敌人调用）。
        /// 武器落在原地，谁都能捡，但捡到只进背包、不会自动装备。
        /// </summary>
        public void KnockOffMainHand()
        {
            if (loadout == null) return;

            var dropped = loadout.DropMainHand();
            if (dropped == null) return;

            if (mount != null) mount.Refresh(loadout);

            // 甩到侧后方足够远：必须超过 WeaponPickup 的拾取半径(1.6)，
            // 否则掉在脚下会被自己立刻吸走，别人根本没机会捡。
            Vector3 pos = transform.position + Vector3.up * 0.6f
                          + (transform.right * 1.7f) + (-transform.forward * 2.2f);
            WeaponPickup.Spawn(dropped, pos);
            Debug.Log($"[My World] 主手武器被打掉：{dropped.displayName}");
        }

        /// <summary>拾取一件武器到背包（不装备）。</summary>
        public void PickUp(WeaponDefinition weapon)
        {
            if (loadout == null || weapon == null) return;
            loadout.AddToBackpack(weapon);
            Debug.Log($"[My World] 拾取 {weapon.displayName} → 背包（共 {loadout.Backpack.Count} 件，未装备）");
        }
    }
}
