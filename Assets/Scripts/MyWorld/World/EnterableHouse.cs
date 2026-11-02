using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld
{
    /// <summary>
    /// 让一栋房子"直接走进去"：玩家靠近门 → 门绕本地 Y 轴转开；玩家进到室内 → 屋顶整体淡出；
    /// 玩家离开 → 门关上、屋顶恢复。全程不加载任何场景，室内就是同一场景里的几何体。
    ///
    /// 为什么不用 FadeableObject：那个组件的可见性是 TopDownCameraRig 每帧按"是否挡住玩家"来写的。
    /// 如果屋顶也挂 FadeableObject，相机在玩家走到门口不再被挡时会把 SetVisible(true) 打回来，
    /// 和"进屋隐藏屋顶"抢同一批 sharedMaterial —— 表现就是屋顶在门口一明一暗地抖。
    /// 所以屋顶的可见性这里独占：复用 PlaceholderArt.NewTransparentVariant 造透明材质（URP 那套
    /// _Surface/_Blend/渲染队列的坑工程里已经踩平了），但写入者只有本组件一个。
    /// 需要共存的话把 suppressRoofFadeable 关掉，自己保证没人跟它抢。
    ///
    /// 状态是**每帧从玩家位置推导出来的**，不是靠 enter/exit 回调累加的：
    /// 触发体被禁用、玩家被瞬移、组件中途 enable/disable 都不会把状态卡在"门开着楼顶没了"。
    /// </summary>
    [DisallowMultipleComponent]
    public class EnterableHouse : MonoBehaviour
    {
        [Header("结构（留空则按名字自动找子物体）")]
        [Tooltip("屋顶根节点。进屋时它下面所有 Renderer 一起淡出")]
        [SerializeField] private Transform roofRoot;

        [Tooltip("门轴。门板是它的子物体，绕它自己的本地 Y 轴旋转")]
        [SerializeField] private Transform doorPivot;

        [Tooltip("室内触发体（isTrigger）。用它算出的包围盒判断玩家在不在屋里")]
        [SerializeField] private Collider interiorTrigger;

        [Header("自动装配")]
        [Tooltip("结构引用为空时，按名字（Roof / DoorPivot）在子物体里找")]
        [SerializeField] private bool autoResolve = true;

        [Tooltip("运行时销毁屋顶上的 FadeableObject，避免和俯视相机的遮挡淡出抢 sharedMaterial")]
        [SerializeField] private bool suppressRoofFadeable = true;

        [Header("屋顶淡出")]
        [Tooltip("进屋后屋顶保留的不透明度。0.06 基本看不见，但还留一点屋檐轮廓")]
        [Range(0f, 0.5f)]
        [SerializeField] private float roofFadedAlpha = 0.06f;

        [Tooltip("从全不透明淡到 roofFadedAlpha 需要几秒")]
        [Min(0.01f)]
        [SerializeField] private float roofFadeTime = 0.3f;

        [Header("门")]
        [Tooltip("开门角度（度）。95° 足够让门板完全贴到墙内侧")]
        [SerializeField] private float doorOpenAngle = 95f;

        [Tooltip("角速度（度/秒）")]
        [Min(1f)]
        [SerializeField] private float doorOpenSpeed = 260f;

        [Tooltip("0 = 自动判断朝室内开（默认）；1 / -1 = 强制方向，用来翻身时反着开")]
        [SerializeField] private float doorSwingSign = 0f;

        [Tooltip("玩家离门轴多近就开始开门（米）。留出走过门槛的时间，别等撞上门才开")]
        [Min(0f)]
        [SerializeField] private float doorOpenRadius = 2f;

        [Header("玩家")]
        [Tooltip("玩家 tag。本工程的玩家物体其实没打 tag，主要靠 PlayerHealth 认人，这里只是兜底")]
        [SerializeField] private string playerTag = "Player";

        [Tooltip("判断「在屋内」时额外探一下的高度（米）：脚底在门外、胸口在门内也算进屋")]
        [Min(0f)]
        [SerializeField] private float playerProbeHeight = 0.9f;

        [Header("轮询")]
        [Tooltip("状态轮询间隔（秒）。门/屋顶的插值仍然是每帧的，这里只是重算玩家在哪的间隔")]
        [Min(0.01f)]
        [SerializeField] private float pollInterval = 0.08f;

        [Tooltip("玩家引用丢了以后隔多久重找一次")]
        [Min(0.05f)]
        [SerializeField] private float playerSearchInterval = 0.5f;

        [Tooltip("打印每次进出/开关门的切换日志")]
        [SerializeField] private bool verboseLog = false;

        // ---------------- 运行时状态 ----------------
        private Transform player;                 // 缓存到的玩家
        private Transform explicitPlayer;         // 外部显式指定（测试/过场用）
        private float nextPlayerSearch;
        private float nextPoll;

        private bool inside;                      // 玩家在室内触发体里
        private bool nearDoor;                    // 玩家在开门半径内
        private bool prevOpenState;               // 上一帧的"门该不该开"，只用于日志

        private float swingSign = 1f;             // 实际生效的开门方向（±1）
        private bool swingSignResolved;
        private Vector3 doorLeafLocalOffset;      // 门板（自由端）相对门轴的本地偏移，用来判开门方向
        private bool doorLeafOffsetValid;

        private Quaternion doorRest;              // 关门时的本地旋转
        private bool doorRestValid;
        private float doorAngle;                  // 当前角度（逐帧朝 DoorTargetAngle 推进）
        private bool doorAngleApplied;
        private float appliedDoorAngle = -1f;     // 已经写进 doorPivot.localRotation 的那个角度

        private float roofAlpha = 1f;             // 当前屋顶不透明度
        private float appliedRoofAlpha = -1f;     // 已经写进材质的那个值
        private bool roofFaded;                   // 现在挂的是不是透明材质

        private Renderer[] roofRenderers;
        private Material[][] roofOpaqueMats;
        private Material[][] roofFadeMats;
        private ShadowCastingMode[] roofShadows;
        private bool roofCacheValid;
        private Transform roofCacheOwner;

        // ---------------- 公开只读状态（QA / 其他系统） ----------------
        public Transform RoofRoot { get { return roofRoot; } }
        public Transform DoorPivot { get { return doorPivot; } }
        public Collider InteriorTrigger { get { return interiorTrigger; } }

        /// <summary>玩家当前是否在室内。false 时屋顶恢复、门开始关。</summary>
        public bool PlayerInside { get { return inside; } }

        /// <summary>玩家是否已经进到"开门半径"里（门自己开的那段）。</summary>
        public bool PlayerNearDoor { get { return nearDoor; } }

        /// <summary>门当前实际角度（带方向的度数，0 = 关）。</summary>
        public float DoorAngle { get { return doorAngle; } }

        /// <summary>门正在朝哪个角度转。</summary>
        public float DoorTargetAngle
        {
            get { return (inside || nearDoor) ? doorOpenAngle * EffectiveSwingSign() : 0f; }
        }

        /// <summary>屋顶当前不透明度（1 = 全不透明）。</summary>
        public float RoofAlpha { get { return roofAlpha; } }

        /// <summary>屋顶现在是否挂着透明材质。</summary>
        public bool RoofTransparent { get { return roofFaded; } }

        /// <summary>实际生效的开门方向（±1）。手动给 doorSwingSign 时优先用手动值。</summary>
        public float EffectiveSwingSign()
        {
            if (Mathf.Abs(doorSwingSign) > 0.5f) return Mathf.Sign(doorSwingSign);
            if (!swingSignResolved) ComputeAutoSwingSign();   // Awake 之外被换过结构时兜底
            return swingSign;
        }

        // ---------------- 生命周期 ----------------

        private void Awake()
        {
            ResolveRefs();
            CaptureDoorRest();
            ComputeAutoSwingSign();
            EnsureRoofCache();
            roofAlpha = 1f;
            ApplyRoofAlpha(1f);
        }

        private void OnEnable()
        {
            // 重新启用时状态可能是脏的（上一次被 disable 时玩家正站在屋里），先回到确定态。
            doorAngle = 0f;
            doorAngleApplied = false;
            appliedDoorAngle = -1f;
            roofAlpha = 1f;
            appliedRoofAlpha = -1f;
            roofFaded = false;
            swingSignResolved = false;
            doorLeafOffsetValid = false;
            ApplyDoorAngle(0f, true);
            ApplyRoofAlpha(1f);
            nextPoll = 0f;
            nextPlayerSearch = 0f;
        }

        private void OnDisable()
        {
            // 被关掉时不能把房子留在"屋顶透明、门半开"的样子：恢复成静止态。
            // 材质数组本身留着，下次 enable 直接复用，不重建。
            RestoreVisuals();
        }

        private void OnDestroy()
        {
            ReleaseRoofMaterials();
        }

        private void Update()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;   // 暂停/编辑器检视时不做状态推进

            if (player == null && Time.time >= nextPlayerSearch)
                ResolvePlayer();

            if (Time.time >= nextPoll)
            {
                nextPoll = Time.time + pollInterval;
                PollPlayerState();
            }

            // 插值仍然是逐帧的：轮询间隔只决定"目标状态"多久重算一次。
            StepDoor(dt);
            StepRoof(dt);
        }

        // ---------------- 状态推导 ----------------

        private void PollPlayerState()
        {
            bool wasInside = inside;
            bool wasNear = nearDoor;

            if (player == null)
            {
                inside = false;
                nearDoor = false;
            }
            else
            {
                Vector3 p = player.position;
                inside = ComputeInside(p);
                nearDoor = ComputeNearDoor(p);
            }

            if (verboseLog && (wasInside != inside || wasNear != nearDoor))
            {
                Debug.Log(string.Format("[EnterableHouse] {0}: 室内={1} 门口={2} → 门目标 {3:F0}°，屋顶目标 α {4:F2}",
                    name, inside, nearDoor, DoorTargetAngle, inside ? roofFadedAlpha : 1f));
            }
        }

        /// <summary>玩家（脚底或胸口）是否落在室内触发体里。</summary>
        private bool ComputeInside(Vector3 playerPos)
        {
            if (interiorTrigger == null) return false;

            Bounds b = interiorTrigger.bounds;
            // 包围盒是按世界轴算的：房子不旋转时它就是准确的墙内空间。
            if (b.Contains(playerPos)) return true;
            if (playerProbeHeight > 0f && b.Contains(playerPos + Vector3.up * playerProbeHeight)) return true;
            return false;
        }

        /// <summary>玩家是否进到门轴周围 doorOpenRadius 的圈里（只看水平距离）。</summary>
        private bool ComputeNearDoor(Vector3 playerPos)
        {
            if (doorPivot == null) return false;
            if (doorOpenRadius <= 0f) return false;

            Vector3 a = playerPos;
            Vector3 b = doorPivot.position;
            a.y = 0f;
            b.y = 0f;
            return (a - b).sqrMagnitude <= doorOpenRadius * doorOpenRadius;
        }

        // ---------------- 门 ----------------

        private void CaptureDoorRest()
        {
            if (doorPivot == null)
            {
                doorRestValid = false;
                return;
            }
            doorRest = doorPivot.localRotation;
            doorRestValid = true;
        }

        /// <summary>
        /// 自动决定往哪边开：先量门板实际在门轴的哪一侧（门板渲染器包围盒中心转到门轴本地），
        /// 然后分别试 +角/-角，门板自由端朝"室内中心"转的那一侧就是正确符号。
        /// 不假设门板一定朝 +X，门轴放在左沿/右沿、门板朝 ±X 都能开对。
        /// </summary>
        private void ComputeAutoSwingSign()
        {
            swingSignResolved = false;
            swingSign = 1f;
            if (doorPivot == null) return;

            Vector3 toInterior = InteriorCenter() - doorPivot.position;
            toInterior.y = 0f;
            if (toInterior.sqrMagnitude < 0.0001f) return;

            Vector3 leafDir = ResolveDoorLeafLocalOffset();
            Vector3 toInteriorLocal = doorPivot.InverseTransformDirection(toInterior.normalized);
            toInteriorLocal.y = 0f;

            Vector3 plusEnd = Quaternion.AngleAxis(doorOpenAngle, Vector3.up) * leafDir;
            Vector3 minusEnd = Quaternion.AngleAxis(-doorOpenAngle, Vector3.up) * leafDir;
            swingSign = Vector3.Dot(plusEnd, toInteriorLocal) >= Vector3.Dot(minusEnd, toInteriorLocal) ? 1f : -1f;
            swingSignResolved = true;
        }

        /// <summary>门板相对门轴的本地方向（归一化，忽略高度）。量不到就退回本地 +X。</summary>
        private Vector3 ResolveDoorLeafLocalOffset()
        {
            if (doorLeafOffsetValid) return doorLeafLocalOffset;
            doorLeafOffsetValid = true;
            doorLeafLocalOffset = Vector3.right;
            if (doorPivot == null) return doorLeafLocalOffset;

            var renderers = doorPivot.GetComponentsInChildren<Renderer>(true);
            bool any = false;
            Bounds bounds = new Bounds(doorPivot.position, Vector3.zero);
            for (int i = 0; i < renderers.Length; i++)
            {
                var r = renderers[i];
                if (r == null || !r.enabled) continue;
                if (!r.gameObject.activeInHierarchy) continue;
                if (!any) { bounds = r.bounds; any = true; }
                else bounds.Encapsulate(r.bounds);
            }
            if (!any) return doorLeafLocalOffset;

            Vector3 local = doorPivot.InverseTransformPoint(bounds.center);
            local.y = 0f;
            if (local.sqrMagnitude < 0.0001f) return doorLeafLocalOffset;
            doorLeafLocalOffset = local.normalized;
            return doorLeafLocalOffset;
        }

        private void StepDoor(float dt)
        {
            if (doorPivot == null) return;
            if (!doorRestValid) CaptureDoorRest();

            float target = DoorTargetAngle;
            doorAngle = Mathf.MoveTowards(doorAngle, target, doorOpenSpeed * dt);
            ApplyDoorAngle(doorAngle, false);

            bool open = inside || nearDoor;
            if (verboseLog && open != prevOpenState)
            {
                prevOpenState = open;
                Debug.Log(string.Format("[EnterableHouse] {0}: {1}（目标 {2:F0}°）", name, open ? "开门" : "关门", target));
            }
        }

        private void ApplyDoorAngle(float angle, bool force)
        {
            if (doorPivot == null || !doorRestValid) return;
            // 注意：不能用 doorAngle 和 angle 比 —— 调用方传进来的就是 doorAngle 本身，
            // 那样从第二帧起永远相等，门会卡在 0°。
            if (!force && doorAngleApplied && Mathf.Abs(appliedDoorAngle - angle) < 0.0001f) return;

            doorAngle = angle;
            appliedDoorAngle = angle;
            doorAngleApplied = true;
            doorPivot.localRotation = doorRest * Quaternion.Euler(0f, angle, 0f);
        }

        // ---------------- 屋顶 ----------------

        private void StepRoof(float dt)
        {
            float target = inside ? roofFadedAlpha : 1f;
            float step = (1f / Mathf.Max(0.01f, roofFadeTime)) * dt;
            if (Mathf.Abs(roofAlpha - target) < 0.0001f)
            {
                roofAlpha = target;
            }
            else
            {
                roofAlpha = Mathf.MoveTowards(roofAlpha, target, step);
            }

            if (!Mathf.Approximately(roofAlpha, appliedRoofAlpha))
                ApplyRoofAlpha(roofAlpha);
        }

        /// <summary>
        /// 把不透明度写进材质。>= 0.999 时换回原始 sharedMaterials（保留不透明渲染路径和阴影），
        /// 否则挂透明变体并把阴影关掉 —— 否则屋顶在头顶上还在投一块影子，屋里亮不起来。
        /// </summary>
        private void ApplyRoofAlpha(float alpha)
        {
            EnsureRoofCache();
            if (!roofCacheValid) { appliedRoofAlpha = alpha; return; }

            bool wantOpaque = alpha >= 0.999f;

            for (int i = 0; i < roofRenderers.Length; i++)
            {
                var r = roofRenderers[i];
                if (r == null) continue;

                if (wantOpaque)
                {
                    if (roofFaded)
                    {
                        r.sharedMaterials = roofOpaqueMats[i];
                        r.shadowCastingMode = roofShadows[i];
                    }
                }
                else
                {
                    if (!roofFaded)
                    {
                        r.sharedMaterials = roofFadeMats[i];
                        r.shadowCastingMode = ShadowCastingMode.Off;
                    }
                    SetMaterialAlpha(roofFadeMats[i], alpha);
                }
            }

            roofFaded = !wantOpaque;
            appliedRoofAlpha = alpha;
        }

        private static void SetMaterialAlpha(Material[] mats, float alpha)
        {
            if (mats == null) return;
            float a = Mathf.Clamp01(alpha);

            for (int i = 0; i < mats.Length; i++)
            {
                var m = mats[i];
                if (m == null) continue;

                if (m.HasProperty("_BaseColor"))
                {
                    Color c = m.GetColor("_BaseColor");
                    if (!Mathf.Approximately(c.a, a))
                    {
                        c.a = a;
                        m.SetColor("_BaseColor", c);
                    }
                }
                Color col = m.color;
                if (!Mathf.Approximately(col.a, a))
                {
                    col.a = a;
                    m.color = col;
                }
            }
        }

        // ---------------- 引用 / 缓存 ----------------

        private void ResolveRefs()
        {
            if (autoResolve)
            {
                if (roofRoot == null) roofRoot = FindChildByName("Roof", "Roof_", "roof");
                if (doorPivot == null) doorPivot = FindChildByName("DoorPivot", "Door", "door");
                if (interiorTrigger == null) interiorTrigger = FindInteriorTrigger();
            }

            if (suppressRoofFadeable && roofRoot != null && Application.isPlaying)
                SuppressRoofFadeable();
        }

        /// <summary>按名字（大小写不敏感，支持前缀）在子物体里找第一个匹配的 Transform。</summary>
        private Transform FindChildByName(string exact, string prefix, string contains)
        {
            var all = GetComponentsInChildren<Transform>(true);
            Transform best = null;

            for (int i = 0; i < all.Length; i++)
            {
                var t = all[i];
                if (t == null || t == transform) continue;
                string n = t.name;
                if (string.Equals(n, exact, System.StringComparison.OrdinalIgnoreCase))
                {
                    best = t;
                    break;
                }
                if (best == null && n.StartsWith(prefix, System.StringComparison.OrdinalIgnoreCase))
                    best = t;
            }

            if (best != null) return best;

            // 兜底：包含关键字（比如 "RoofA"/"Door_Leaf" 这种不规范的命名）
            for (int i = 0; i < all.Length; i++)
            {
                var t = all[i];
                if (t == null || t == transform) continue;
                if (t.name.IndexOf(contains, System.StringComparison.OrdinalIgnoreCase) >= 0)
                    return t;
            }
            return null;
        }

        private Collider FindInteriorTrigger()
        {
            var cols = GetComponentsInChildren<Collider>(true);
            for (int i = 0; i < cols.Length; i++)
            {
                var c = cols[i];
                if (c == null || !c.isTrigger) continue;
                if (roofRoot != null && c.transform.IsChildOf(roofRoot)) continue;
                if (doorPivot != null && c.transform.IsChildOf(doorPivot)) continue;
                return c;
            }
            return null;
        }

        /// <summary>
        /// 屋顶上的 FadeableObject 会跟本组件抢 sharedMaterial（见类注释），
        /// 运行时直接销毁它。只在玩的时候做，编辑器里点房子不会掉组件。
        /// </summary>
        private void SuppressRoofFadeable()
        {
            var fades = roofRoot.GetComponentsInChildren<FadeableObject>(true);
            for (int i = 0; i < fades.Length; i++)
            {
                if (fades[i] == null) continue;
                if (verboseLog)
                    Debug.Log(string.Format("[EnterableHouse] {0}: 移除屋顶上的 FadeableObject（{1}）", name, fades[i].gameObject.name));
                Destroy(fades[i]);
            }
        }

        private void EnsureRoofCache()
        {
            if (roofRoot == null)
            {
                if (roofCacheValid) ReleaseRoofMaterials();
                roofCacheValid = false;
                return;
            }

            if (roofCacheValid && roofCacheOwner == roofRoot) return;
            if (roofCacheValid) ReleaseRoofMaterials();

            roofRenderers = roofRoot.GetComponentsInChildren<Renderer>(true);
            roofOpaqueMats = new Material[roofRenderers.Length][];
            roofFadeMats = new Material[roofRenderers.Length][];
            roofShadows = new ShadowCastingMode[roofRenderers.Length];

            for (int i = 0; i < roofRenderers.Length; i++)
            {
                var r = roofRenderers[i];
                if (r == null) continue;

                // 用 sharedMaterials 读写：renderer.material 会 clone 实例，换一次漏一份。
                var src = r.sharedMaterials;
                var opaque = new Material[src.Length];
                var fade = new Material[src.Length];
                for (int s = 0; s < src.Length; s++)
                {
                    opaque[s] = src[s];
                    fade[s] = src[s] != null ? PlaceholderArt.NewTransparentVariant(src[s], roofAlpha) : null;
                }
                roofOpaqueMats[i] = opaque;
                roofFadeMats[i] = fade;
                roofShadows[i] = r.shadowCastingMode;
            }

            roofCacheOwner = roofRoot;
            roofCacheValid = true;
            roofFaded = false;
        }

        private void ReleaseRoofMaterials()
        {
            if (roofFadeMats != null)
            {
                for (int i = 0; i < roofFadeMats.Length; i++)
                {
                    var arr = roofFadeMats[i];
                    if (arr == null) continue;
                    for (int s = 0; s < arr.Length; s++)
                    {
                        var m = arr[s];
                        if (m == null) continue;
                        if (Application.isPlaying) Destroy(m);
                        else DestroyImmediate(m);
                    }
                    roofFadeMats[i] = null;   // 同一批实例只销毁一次
                }
            }

            roofFadeMats = null;
            roofOpaqueMats = null;
            roofShadows = null;
            roofRenderers = null;
            roofCacheValid = false;
            roofCacheOwner = null;
            roofFaded = false;
        }

        // ---------------- 恢复 ----------------

        private void RestoreVisuals()
        {
            if (roofCacheValid)
            {
                for (int i = 0; i < roofRenderers.Length; i++)
                {
                    var r = roofRenderers[i];
                    if (r == null) continue;
                    r.sharedMaterials = roofOpaqueMats[i];
                    r.shadowCastingMode = roofShadows[i];
                }
            }

            roofAlpha = 1f;
            appliedRoofAlpha = -1f;
            roofFaded = false;
            doorAngle = 0f;
            doorAngleApplied = false;
            appliedDoorAngle = -1f;
            ApplyDoorAngle(0f, true);
        }

        // ---------------- 玩家 ----------------

        private void ResolvePlayer()
        {
            nextPlayerSearch = Time.time + playerSearchInterval;

            if (explicitPlayer != null)
            {
                player = explicitPlayer;
                return;
            }

            // 本工程玩家没打 tag，靠 PlayerHealth 认人（Enemy.cs 也是这么找玩家的）。
            var health = Object.FindFirstObjectByType<PlayerHealth>();
            if (health != null)
            {
                player = health.transform;
                return;
            }

            if (!string.IsNullOrEmpty(playerTag))
            {
                try
                {
                    var go = GameObject.FindGameObjectWithTag(playerTag);
                    if (go != null) { player = go.transform; return; }
                }
                catch (UnityException)
                {
                    // tag 没在 TagManager 里登记过：FindGameObjectWithTag 会抛，这里直接忽略。
                }
            }

            var named = GameObject.Find("Player");
            if (named != null) player = named.transform;
        }

        private bool IsPlayerCollider(Collider other)
        {
            if (other == null) return false;
            if (other.GetComponentInParent<PlayerHealth>() != null) return true;
            if (player == null) return false;
            return other.transform == player || other.transform.IsChildOf(player);
        }

        private void OnTriggerEnter(Collider other)
        {
            if (IsPlayerCollider(other))
            {
                nextPoll = 0f;
                PollPlayerState();
            }
        }

        private void OnTriggerExit(Collider other)
        {
            if (IsPlayerCollider(other))
            {
                nextPoll = 0f;
                PollPlayerState();
            }
        }

        // ---------------- 对外接口 ----------------

        /// <summary>编辑器装配 / 别的系统在运行时重建结构时用。</summary>
        public void Configure(Transform roof, Transform door, Collider trigger)
        {
            roofRoot = roof;
            doorPivot = door;
            interiorTrigger = trigger;
            swingSignResolved = false;
            doorLeafOffsetValid = false;

            ReleaseRoofMaterials();
            CaptureDoorRest();
            ComputeAutoSwingSign();

            // 编辑期（菜单装配）不建透明材质实例：它们不是资产、也不会被序列化，
            // 留到运行时由 Awake / OnEnable 建，免得编辑器里点几次菜单攒一堆孤儿 Material。
            if (isActiveAndEnabled && Application.isPlaying)
            {
                doorAngle = 0f;
                doorAngleApplied = false;
                appliedDoorAngle = -1f;
                ApplyDoorAngle(0f, true);
                roofAlpha = 1f;
                appliedRoofAlpha = -1f;
                ApplyRoofAlpha(1f);
                nextPoll = 0f;
            }
        }

        /// <summary>显式指定玩家（测试里想脱离 FindObjectOfType 的行为时用）。</summary>
        public void SetPlayer(Transform target)
        {
            explicitPlayer = target;
            player = target;
            nextPoll = 0f;
        }

        /// <summary>立刻重算一次玩家位置（瞬移后的测试用，不用等轮询）。</summary>
        public void RefreshNow()
        {
            if (player == null) { nextPlayerSearch = 0f; ResolvePlayer(); }
            nextPoll = 0f;
            PollPlayerState();
        }

        /// <summary>门轴给出的"室内中心"：优先用触发体，其次房子渲染包围盒。</summary>
        private Vector3 InteriorCenter()
        {
            if (interiorTrigger != null) return interiorTrigger.bounds.center;

            var rs = GetComponentsInChildren<Renderer>(true);
            if (rs.Length == 0) return transform.position + Vector3.up;

            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return b.center;
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            // Inspector 里改了角度/引用：清掉缓存，下次进入运行时按新值重建。
            // 注意要连透明实例一起销毁，只把标志位清零会留下没人引用的 Material。
            if (!Application.isPlaying)
            {
                swingSignResolved = false;
                doorLeafOffsetValid = false;
                ReleaseRoofMaterials();
            }
        }
#endif
    }
}
