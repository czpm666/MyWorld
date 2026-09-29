using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 抓钩（参照 PEAK 的绳索枪）。行为**按"出手时在地面还是空中"分四种**：
    ///
    ///   地面 + 固定物(墙/树/石) → 只把自己**拽一下**，不会飞过去
    ///   地面 + 敌人/可移动物   → 把目标**拉到面前**
    ///   空中 + 固定物          → 自己**飞过去**，飞行距离由**离地高度**决定（越高越远）
    ///   空中 + 敌人            → 敌人只被**挪一点**（不拉到面前），主要作用是自己飞向它当锚点，
    ///                            飞行距离 = 空中对墙距离 × airFlightEnemyFactor（默认一半）
    ///
    /// 飞行途中松开右键 → 立刻脱钩，**保留当时动量**，之后按 PlayerController8Dir.momentumDecay 逐渐衰减。
    /// 拉拽期间 WASD 不参与（想改方向只能松手）。
    ///
    /// 所有参数在 GrappleSettings 组件上（Player → Grapple），不在这里。
    /// </summary>
    [DisallowMultipleComponent]
    public class GrappleWeapon : MonoBehaviour
    {
        private enum State { Idle, Flying, ReelingSelf }

        private State state;
        private PlayerController8Dir controller;

        // 参数来源：Player → Grapple 上的那个组件
        [SerializeField] private GrappleSettings settings;

        private Vector3 hookOrigin;
        private Vector3 hookDir;
        private float hookTravel;
        private float hookSpeed;
        private Vector3 anchor;

        // 出手时的状态，决定走哪条规则
        private bool firedFromAir;
        private float firedHeight;

        // 本次"把自己拉过去"的限制
        private Vector3 reelStart;
        private float reelLimit;
        private float reelSpeed;
        private bool reelIsTug;
        private float reelMomentumCarry;

        // 被拽的目标（和上面的自我拉拽可以同时进行：空中钩敌人时两个都发生）
        private Transform pulledTarget;
        private Rigidbody pulledBody;
        private CharacterController pulledController;
        private bool pulledPartial;
        private float pullSpeed;

        private LineRenderer rope;
        private Transform hookVisual;
        private Transform muzzle;

        [Header("抓取判定")]
        [Tooltip("钩头的判定半径。给一点粗细，高速飞行时才不会从目标身边擦过去")]
        [SerializeField] private float hookRadius = 0.35f;

        public bool IsBusy => state != State.Idle || pulledTarget != null;

        /// <summary>绳索起点（副手武器的枪口）。</summary>
        public Transform Muzzle => muzzle;

        public void SetSettings(GrappleSettings s) => settings = s;

        public void Configure(PlayerController8Dir ctrl, Transform muzzlePoint)
        {
            controller = ctrl;
            muzzle = muzzlePoint;
            BuildVisuals();
        }

        private void BuildVisuals()
        {
            if (rope == null)
            {
                var g = new GameObject("GrappleRope");
                g.transform.SetParent(transform, false);
                rope = g.AddComponent<LineRenderer>();
                rope.material = PlaceholderArt.NewColoredMaterial(new Color(0.93f, 0.68f, 0.16f));
                rope.widthMultiplier = 0.055f;
                rope.positionCount = 0;
                rope.useWorldSpace = true;
                rope.numCapVertices = 3;
                rope.textureMode = LineTextureMode.Stretch;
            }

            if (hookVisual == null)
            {
                var root = new GameObject("HookHead");
                var dark = PlaceholderArt.NewLit(new Color(0.20f, 0.21f, 0.24f), 0.5f);
                dark.name = "M_Hook";
                PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Core",
                    Vector3.zero, Vector3.one * 0.16f, dark);
                for (int i = 0; i < 3; i++)
                {
                    float a = i * 120f;
                    Quaternion rot = Quaternion.Euler(0f, a, 0f) * Quaternion.Euler(35f, 0f, 0f);
                    var claw = PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Claw" + i,
                        new Vector3(0f, 0f, -0.10f), new Vector3(0.05f, 0.05f, 0.16f), dark);
                    claw.transform.localRotation = rot;
                    claw.transform.localPosition = new Vector3(0f, 0f, -0.10f) + rot * new Vector3(0f, 0f, -0.06f);
                }
                foreach (var c in root.GetComponentsInChildren<Collider>()) Destroy(c);
                root.SetActive(false);
                hookVisual = root.transform;
            }
        }

        // ---------------- 发射 / 松手 ----------------

        /// <summary>
        /// 按下副手键：发射钩头。
        /// direction 由 PlayerCombat 传入（平时是鼠标方向），这样钩子不会朝着"角色还没转过去的旧朝向"飞。
        /// </summary>
        public bool Fire(WeaponDefinition weapon, Vector3 direction)
        {
            if (weapon == null || weapon.kind != WeaponKind.Grapple) return false;
            if (state != State.Idle) return false;
            if (settings == null) return false;

            state = State.Flying;
            hookSpeed = settings.hookSpeedStart;
            hookTravel = 0f;

            // 出手瞬间就把"地面还是空中、多高"定下来，飞行途中不再变
            firedFromAir = controller != null && controller.IsAirborne;
            firedHeight = firedFromAir && controller != null ? controller.HeightAboveGround : 0f;

            hookDir = direction.sqrMagnitude > 0.0001f ? direction.normalized : transform.forward;
            hookOrigin = MuzzlePosition();

            if (hookVisual != null)
            {
                hookVisual.gameObject.SetActive(true);
                hookVisual.position = hookOrigin;
            }
            ArcaneBurst.Spawn(hookOrigin, hookDir, 0.35f);
            return true;
        }

        /// <summary>松开副手键 / 钩索用完：脱钩，**保留当时动量**（切成惯性滑行）。</summary>
        public void Release()
        {
            if (state == State.ReelingSelf && settings != null)
                controller?.HandOffMomentum(settings.releaseMomentumCarry);

            EndPull();
            EndGrapple();
        }

        private void EndGrapple()
        {
            state = State.Idle;
            controller?.ClearReelFacing();
            if (rope != null) rope.positionCount = 0;
            if (hookVisual != null) hookVisual.gameObject.SetActive(false);
        }

        private Vector3 MuzzlePosition()
        {
            if (muzzle != null) return muzzle.position;
            return transform.position + Vector3.up * 1.05f + transform.forward * 0.6f;
        }

        // ---------------- 每帧 ----------------

        private void Update()
        {
            float dt = Time.deltaTime;

            // 模拟放在 Update 而不是 FixedUpdate：钩头是逐帧射线推进的，
            // 跟着渲染帧走才不会和视觉脱节；而且 Step() 不驱动固定步进，放那边没法验证。
            if (state == State.Flying) FlyHook(dt);
            else if (state == State.ReelingSelf) ReelSelf(dt);
            // 拉目标和拉自己可以同时发生（空中钩敌人就是这种）
            if (pulledTarget != null) UpdatePull(dt);

            if (!IsBusy)
            {
                // 拉拽/钩索都结束了就收绳。
                // 少了这一步，把敌人拉到面前后绳子会僵在半空（指向敌人原来的位置）。
                if (rope != null && rope.positionCount > 0) rope.positionCount = 0;
                return;
            }

            if (rope != null)
            {
                Vector3 from = MuzzlePosition();
                Vector3 to = state == State.Flying
                    ? (hookVisual != null ? hookVisual.position : anchor)
                    : (pulledTarget != null && state == State.Idle ? pulledTarget.position : anchor);
                rope.positionCount = 2;
                rope.SetPosition(0, from);
                rope.SetPosition(1, to);
            }
        }

        // ---------------- 钩头飞行 ----------------

        private void FlyHook(float dt)
        {
            hookSpeed = Mathf.Min(hookSpeed + settings.hookAccel * dt, settings.hookSpeedMax);

            Vector3 prev = hookOrigin + hookDir * hookTravel;
            hookTravel += hookSpeed * dt;
            Vector3 next = hookOrigin + hookDir * hookTravel;

            Vector3 seg = next - prev;
            float dist = seg.magnitude;
            if (dist > 0.0001f)
            {
                // 用**球体扫描**而不是细射线：钩头每帧要跨 1 米以上，
                // 零粗细的射线很容易从敌人身边擦过去（实测它一路飞了 10 米打到石台）。
                // 给一点半径，抓取才可靠。
                if (Physics.SphereCast(prev, hookRadius, seg / dist, out RaycastHit hit, dist,
                        ~0, QueryTriggerInteraction.Ignore))
                {
                    if (!hit.collider.transform.IsChildOf(transform))
                    {
                        OnHookHit(hit);
                        return;
                    }
                }
            }

            if (hookVisual != null) hookVisual.position = next;

            if (hookTravel > settings.hookRange) Release();   // 超过最大长度就收枪
        }

        /// <summary>命中敌人时的特效颜色（和打墙的青色区分开）。</summary>
        private static readonly Color EnemyHitColor = new Color(1f, 0.22f, 0.18f, 1f);

        private void OnHookHit(RaycastHit hit)
        {
            anchor = hit.point;

            var damageable = hit.collider.GetComponentInParent<IDamageable>();
            var body = hit.collider.attachedRigidbody;
            bool movable = damageable != null || (body != null && !body.isKinematic);

            if (hookVisual != null)
            {
                if (movable)
                {
                    // 抓到可移动目标：钩头**收掉**。
                    // 留着的话目标被拉过来时会从钩子上穿过去，看着像钩子插进了身体里。
                    hookVisual.gameObject.SetActive(false);
                }
                else
                {
                    hookVisual.position = hit.point;
                    hookVisual.rotation = Quaternion.LookRotation(-hit.normal);
                }
            }

            // 打敌人 = 红色，打墙/树/石头 = 青色
            ArcaneBurst.Spawn(hit.point, hit.normal, 0.6f, movable ? EnemyHitColor : new Color(0.55f, 0.85f, 1f));

            if (!movable)
            {
                // 墙 / 树 / 石头
                if (firedFromAir)
                    BeginReel(AirFlightDistance(firedHeight), isTug: false, settings.flightMomentumCarry);
                else
                    BeginReel(settings.groundTugDistance, isTug: true, settings.tugMomentumCarry);
                return;
            }

            // 敌人 / 可移动物
            if (firedFromAir)
            {
                // 空中：敌人只挪一点（不拉到面前），同时自己飞向它当锚点，距离是对墙的一半
                BeginPull(damageable, hit.collider, partial: true);
                BeginReel(AirFlightDistance(firedHeight) * Mathf.Max(0f, settings.airFlightEnemyFactor),
                    isTug: false, settings.flightMomentumCarry);
            }
            else
            {
                BeginPull(damageable, hit.collider, partial: false);   // 地面：拉到面前
            }
        }

        /// <summary>离地越高飞得越远。</summary>
        private float AirFlightDistance(float height)
        {
            return Mathf.Clamp(settings.airFlightBase + height * settings.airFlightPerHeight,
                               settings.airFlightBase, settings.airFlightMax);
        }

        // ---------------- 把自己拉过去（限制距离） ----------------

        private void BeginReel(float distance, bool isTug, float momentumCarry)
        {
            Vector3 to = anchor - transform.position;
            to.y = 0f;
            float toAnchor = to.magnitude;

            // 别飞过锚点，也至少飞一点点
            float maxTravel = Mathf.Max(0.1f, toAnchor - settings.reelStopPadding);
            reelLimit = Mathf.Clamp(distance, 0.1f, maxTravel);
            reelStart = transform.position;
            reelIsTug = isTug;
            reelMomentumCarry = momentumCarry;
            reelSpeed = isTug ? settings.groundTugSpeed : settings.reelSpeedStart;
            state = State.ReelingSelf;

            if (toAnchor > 0.001f)
            {
                Vector3 dir = to / toAnchor;
                controller?.SetExternalVelocity(dir * reelSpeed);
                controller?.SetReelFacing(dir);   // 朝着被拽的方向，避免倒着飞的动画
            }
        }

        private void ReelSelf(float dt)
        {
            Vector3 to = anchor - transform.position;
            to.y = 0f;
            float dist = to.magnitude;

            Vector3 flatStart = new Vector3(reelStart.x, 0f, reelStart.z);
            Vector3 flatNow = new Vector3(transform.position.x, 0f, transform.position.z);
            float traveled = (flatNow - flatStart).magnitude;

            bool arrived = dist <= settings.reelStopPadding;
            bool usedUp = traveled >= reelLimit;

            if (arrived || usedUp)
            {
                if (arrived)
                {
                    controller?.SetExternalVelocity(Vector3.zero);   // 到地方了 → 停下
                    controller?.ClearExternalVelocity();
                }
                else
                {
                    controller?.HandOffMomentum(reelMomentumCarry);  // 距离用完 → 按比例留惯性
                }

                ArcaneBurst.Spawn(arrived ? anchor : transform.position, Vector3.up, 0.7f);
                EndGrapple();
                return;
            }

            if (!reelIsTug)   // 短拽不加速，保持"一下拽过去"的干脆感
                reelSpeed = Mathf.Min(reelSpeed + settings.reelAccel * dt, settings.reelSpeedMax);

            float speed = Mathf.Min(reelSpeed, dist / dt);
            controller?.SetExternalVelocity((to / Mathf.Max(dist, 0.0001f)) * speed);
        }

        // ---------------- 把目标拉过来 ----------------

        private void BeginPull(IDamageable damageable, Collider col, bool partial)
        {
            // 抓住目标 = 钩头飞行结束。不置 Idle 的话，FlyHook 会继续推进钩头，
            // 到绳长上限时触发 Release()，把正在进行的拉拽也一起中断（敌人只被拽一点点就停）。
            state = State.Idle;

            var go = damageable != null ? damageable.Transform.gameObject : col.attachedRigidbody.gameObject;

            pulledTarget = go.transform;
            pulledBody = go.GetComponent<Rigidbody>();
            pulledController = go.GetComponent<CharacterController>();
            pulledPartial = partial;
            pullSpeed = settings.pullTargetSpeedStart;

            // 有 AI 的目标（敌人）先让它停手，否则它每帧的移动会和这里的拉拽打架
            var enemy = go.GetComponent<Enemy>();
            if (enemy != null) enemy.SetPulled(true);
        }

        private void UpdatePull(float dt)
        {
            if (pulledTarget == null) return;

            // 空中钩敌人时只挪到"不面前"的位置就停手
            float stop = pulledPartial ? settings.airPullStopDistance : settings.pullTargetStopDistance;

            Vector3 to = transform.position - pulledTarget.position;
            to.y = 0f;
            float dist = to.magnitude;

            if (dist <= stop)
            {
                EndPull();
                ArcaneBurst.Spawn(pulledTarget.position + Vector3.up, Vector3.up, 0.5f);
                return;
            }

            pullSpeed = Mathf.Min(pullSpeed + settings.pullTargetAccel * dt, settings.pullTargetMaxSpeed);
            Vector3 dir = to / Mathf.Max(dist, 0.0001f);
            float speed = Mathf.Min(pullSpeed, dist / dt);
            Vector3 step = dir * (speed * dt);

            // 分三种情况挪目标，顺序不能反：
            // 1) CharacterController（敌人）—— 必须用 cc.Move()，
            //    直接写 transform.position 会被它内部维护的位置覆盖，表现为"完全拉不动"。
            // 2) 动态刚体 —— 给速度，交给物理。
            // 3) 什么都没有（木桩）—— 直接写 transform。
            if (pulledController != null && pulledController.enabled)
                pulledController.Move(step);
            else if (pulledBody != null && !pulledBody.isKinematic)
                pulledBody.linearVelocity = dir * speed;
            else
                pulledTarget.position += step;
        }

        private void EndPull()
        {
            if (pulledTarget != null)
            {
                var enemy = pulledTarget.GetComponent<Enemy>();
                if (enemy != null) enemy.SetPulled(false);
            }
            pulledTarget = null;
            pulledBody = null;
            pulledController = null;
            pullSpeed = 0f;
        }

        private void OnDisable()
        {
            Release();
        }
    }
}
