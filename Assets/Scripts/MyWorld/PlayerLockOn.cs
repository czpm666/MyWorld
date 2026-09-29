using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 鼠标右键锁定最近的敌人（切换式：按一下锁定，再按一下解锁）。
    ///
    /// 重要设计取舍：**锁定不转相机**。
    /// 这个项目里"屏幕上方 = 世界 +Z"是 WASD 映射成立的前提，相机一转，
    /// 屏幕上的方向就和世界方向错开，8 方向操作会整个歪掉。
    /// 所以这里的锁定 = 角色转向目标 + 法术自动瞄准目标，相机保持固定俯角。
    ///
    /// 锁定时角色仍然可以用 WASD 自由移动（等于侧移），朝向始终盯着目标。
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerLockOn : MonoBehaviour
    {
        [Header("选目标")]
        [Tooltip("锁定范围：目标离玩家不能超过这个距离")]
        [SerializeField] private float lockRange = 20f;
        [Tooltip("超出这个距离就自动解锁")]
        [SerializeField] private float breakRange = 30f;

        [Header("瞄准")]
        [Tooltip("瞄准目标身上这个高度，别对着脚底打")]
        [SerializeField] private float aimHeight = 1.2f;

        [Header("标记")]
        [SerializeField] private float markerHeight = 3.1f;
        [SerializeField] private float markerSize = 0.34f;
        [SerializeField] private Color markerColor = new Color(1f, 0.82f, 0.25f);

        [Header("脚下红圈")]
        [SerializeField] private float ringRadius = 0.75f;
        [SerializeField] private float ringWidth = 0.09f;
        [SerializeField] private Color ringColor = new Color(0.95f, 0.18f, 0.16f);

        private MyWorldInput input;
        private PlayerController8Dir move;
        private PlayerAim aim;
        private Transform marker;
        private Transform ring;

        /// <summary>当前锁定的目标，没有则为 null。</summary>
        public Transform Current { get; private set; }

        public bool IsLocked => Current != null;

        /// <summary>法术应当飞向的点：锁定目标时指向它，否则指向角色正前方。</summary>
        public Vector3 AimPoint => IsLocked
            ? Current.position + Vector3.up * aimHeight
            : transform.position + transform.forward;

        private void Awake()
        {
            input = GetComponent<MyWorldInput>();
            move = GetComponent<PlayerController8Dir>();
            aim = GetComponent<PlayerAim>();
            BuildMarker();
            BuildRing();
        }

        /// <summary>脚下的红圈：一个用 LineRenderer 画的闭合圆环，平贴在地面上。</summary>
        private void BuildRing()
        {
            var go = new GameObject("LockRing");
            var lr = go.AddComponent<LineRenderer>();
            lr.material = PlaceholderArt.NewColoredMaterial(ringColor);
            lr.widthMultiplier = ringWidth;
            lr.useWorldSpace = false;   // 用本地坐标画圆，物体摆到目标脚下即可
            lr.loop = true;
            lr.numCapVertices = 0;

            const int segments = 48;
            lr.positionCount = segments;
            for (int i = 0; i < segments; i++)
            {
                float a = i / (float)segments * Mathf.PI * 2f;
                lr.SetPosition(i, new Vector3(Mathf.Cos(a) * ringRadius, 0f, Mathf.Sin(a) * ringRadius));
            }

            go.SetActive(false);
            ring = go.transform;
        }

        private void BuildMarker()
        {
            // 菱形标记：一个绕两轴转 45° 的方块，悬在目标头顶上下浮动。
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = "LockMarker";
            PlaceholderArt.StripCollider(go);

            var mat = PlaceholderArt.NewLit(markerColor, 0.2f);
            mat.name = "M_LockMarker";
            go.GetComponent<Renderer>().sharedMaterial = mat;

            go.transform.localScale = Vector3.one * markerSize;
            go.transform.rotation = Quaternion.Euler(45f, 0f, 45f);
            go.SetActive(false);
            marker = go.transform;
        }

        /// <summary>切换锁定/解锁。公开是为了让 UI 按钮、AI 或测试脚本也能驱动它。</summary>
        public void Toggle()
        {
            if (IsLocked) Unlock();
            else Lock();
        }

        private void Update()
        {
            if (input != null && input.LockOnPressed) Toggle();

            // 目标死了/跑太远/被销毁 → 自动改锁下一个可锁目标；一个都没有才解锁。
            // （直接解锁的话，打连招时会突然失去锁定，很难受）
            if (IsLocked && !IsTargetValid())
            {
                var next = FindBestTarget();
                if (next != null)
                {
                    Current = next.Transform;
                    UpdateMarker();
                }
                else
                {
                    Unlock();
                }
            }

            if (IsLocked)
            {
                move?.SetForcedFacing(Current.position - transform.position);
                UpdateMarker();
            }
        }

        private void Lock()
        {
            var target = FindBestTarget();
            if (target == null) return;   // 范围内没有目标，按了没反应

            Current = target.Transform;
            UpdateMarker();
            if (marker != null) marker.gameObject.SetActive(true);
            if (ring != null) ring.gameObject.SetActive(true);
        }

        private void Unlock()
        {
            Current = null;
            move?.ClearForcedFacing();
            if (marker != null) marker.gameObject.SetActive(false);
            if (ring != null) ring.gameObject.SetActive(false);
        }

        private bool IsTargetValid()
        {
            if (Current == null) return false;

            // 目标被销毁时 Unity 的假 null 会让这条判定成立
            if (!Current) return false;

            float dist = Vector3.Distance(transform.position, Current.position);
            if (dist > breakRange) return false;

            var d = Current.GetComponentInParent<IDamageable>();
            return d == null || d.IsAlive;
        }

        /// <summary>
        /// 在所有登记的可伤害目标里挑**离鼠标最近**的那个（不是离玩家最近、也不是面朝方向）。
        /// 仍然要求目标在玩家 lockRange 之内，避免鼠标指到天边把半个地图外的敌人锁上。
        /// </summary>
        private IDamageable FindBestTarget()
        {
            IDamageable best = null;
            float bestScore = float.MaxValue;

            Vector3 origin = transform.position;
            // 鼠标没指到有效位置时（比如没插鼠标）退回到"离玩家最近"
            bool useMouse = aim != null && aim.HasMouseDirection;
            Vector3 mousePoint = useMouse ? aim.MouseWorldPoint : origin;

            var all = DamageableRegistry.Targets;

            // 倒着遍历：FindBestTarget 可能被目标死亡等时机触发，
            // 正序 + 可能发生的注销容易漏掉元素，倒序更稳。
            for (int i = all.Count - 1; i >= 0; i--)
            {
                var t = all[i];
                if (t == null || !t.IsAlive || t.Transform == null) continue;

                Vector3 pos = t.Transform.position;

                // 离玩家太远的不要（用水平距离，别把高度算进去）
                Vector3 to = pos - origin;
                to.y = 0f;
                if (to.magnitude > lockRange) continue;

                float score;
                if (useMouse)
                {
                    Vector3 fromMouse = pos - mousePoint;
                    fromMouse.y = 0f;
                    score = fromMouse.magnitude;
                }
                else
                {
                    score = to.magnitude;
                }

                if (score < bestScore)
                {
                    bestScore = score;
                    best = t;
                }
            }

            return best;
        }

        private void UpdateMarker()
        {
            if (Current == null) return;

            if (marker != null)
            {
                float bob = Mathf.Sin(Time.time * 4f) * 0.12f;
                marker.position = Current.position + Vector3.up * (markerHeight + bob);
                marker.Rotate(Vector3.up, 90f * Time.deltaTime, Space.World);
            }

            if (ring != null)
            {
                // 贴地画、保持水平。抬高一点点避免和地面共面闪烁；小幅脉动让它更显眼。
                float pulse = 1f + Mathf.Sin(Time.time * 5f) * 0.06f;
                ring.position = Current.position + Vector3.up * 0.06f;
                ring.rotation = Quaternion.identity;
                ring.localScale = new Vector3(pulse, 1f, pulse);
            }
        }

        private void OnDisable()
        {
            // 组件被关掉/对象被销毁时别把玩家卡在"被强制朝向"的状态
            move?.ClearForcedFacing();
        }

        private void OnDestroy()
        {
            if (marker != null) Destroy(marker.gameObject);
        }
    }
}
