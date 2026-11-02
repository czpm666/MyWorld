using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 织梦岛那种斜俯视相机 + 一个可旋转的第三人称模式，两套机位共用同一份跟随/遮挡淡出逻辑。
    ///
    /// **模式 0 = 俯视（默认）**：相机 yaw 恒为 0 —— 这样屏幕上方永远等于世界 +Z，
    /// WASD 才能直接映射到世界四方向，角色朝向也才能稳定地吸附到 8 个方向。
    /// 一旦 yaw ≠ 0，操作方向就会相对于世界变成斜的，8 方向感会散掉。
    /// ⇒ 所以**模式 0 下这条不变式一字不改**，它也是"不按键时手感与历史逐位一致"的实现方式。
    ///
    /// **模式 1 = 第三人称（`V` 切换）**：俯角更平、距离更近、`,/.` 转 yaw、滚轮缩放。
    /// 这种模式下 yaw 可以不为 0，于是"屏幕方向 = 世界方向"不再成立 ——
    /// 当前 yaw 通过静态量 <see cref="MovementYaw"/> 交给 `PlayerController8Dir`，
    /// 由它把 WASD 换算成**相对相机**的世界方向（W 永远 = 往画面里走）。
    /// `MovementYaw == 0` 时那条换算是**恒等映射**，所以模式 0 的数值路径完全没变。
    ///
    /// 另外负责"遮挡淡出"：把挡在相机和玩家之间的物体切成半透明。
    /// </summary>
    [DisallowMultipleComponent]
    public class TopDownCameraRig : MonoBehaviour
    {
        [Header("相机")]
        [Tooltip("俯角，越大越接近正上方往下看")]
        [SerializeField] private float pitch = 52f;
        [Tooltip("相机到观察点的距离")]
        [SerializeField] private float distance = 34f;
        [Tooltip("用透视(长焦窄 FOV)而不是正交。URP 的景深在正交相机下 CoC 算错，会整屏糊掉；透视下才正常")]
        [SerializeField] private bool perspective = true;
        [Tooltip("透视时的垂直视场角。配合 distance 决定看到多大范围：halfV = distance * tan(fov/2)")]
        [SerializeField] private float fieldOfView = 30f;
        [Tooltip("正交时的垂直半高，仅 perspective=false 时生效")]
        [SerializeField] private float orthographicSize = 9f;
        [Tooltip("用 RenderSettings.skybox 当天空（大地图/王都要），关掉则用纯色。小地图默认纯色")]
        [SerializeField] private bool useSkybox = false;
        /// <summary>大地图/王都要真天空盒；场景脚本在 Start 里打开它。</summary>
        public bool UseSkybox
        {
            get { return useSkybox; }
            set { useSkybox = value; }
        }

        [Tooltip("跟随的平滑速度，越大越跟手")]
        [SerializeField] private float followLerp = 7.5f;
        [Tooltip("观察点相对角色脚下的抬高量，让角色略偏屏幕下方，前方看得更多")]
        [SerializeField] private Vector3 lookOffset = new Vector3(0f, 1f, 0f);

        [Header("遮挡淡出")]
        [SerializeField] private bool enableOcclusionFade = true;
        [Tooltip("遮挡检测在玩家周围横向扩开多少米再采样。0 = 只测玩家包围盒本身。1.2 ≈ 角色轮廓外一米多，能把「擦着角色挡住半个画面」的建筑也淡掉，又不至于把整条街变透明")]
        [SerializeField] private float occlusionPadding = 1.2f;
        [Tooltip("遮挡采样点数：1 = 只打中心一条（旧行为），3 = +头/脚，5 = +屏幕左右，7 = +屏幕前后。任一采样点被挡即淡出")]
        [SerializeField] private int occlusionSamples = 7;

        // ---------------- 第三人称模式（V 切换） ----------------
        // ⚠️ 下面这些是**新增**字段，所以场景里已经烘焙过的那份组件会直接吃代码默认值，
        //    不会破坏"默认模式 0、参数与历史一致"这条要求。反之：**不要改上面那批老字段的默认值**。

        [Header("第三人称模式（V 切换）")]
        [Tooltip("第三人称俯角：越小越平视。18~28 是用户要的区间")]
        [SerializeField] private float thirdPersonPitch = 24f;
        [Tooltip("第三人称默认距离（滚轮可以在这个基础上缩放）")]
        [SerializeField] private float thirdPersonDistance = 8.5f;
        [Tooltip("第三人称垂直视场角")]
        [SerializeField] private float thirdPersonFieldOfView = 45f;
        [Tooltip("滚轮缩放的最近距离")]
        [SerializeField] private float minThirdPersonDistance = 5f;
        [Tooltip("滚轮缩放的最远距离")]
        [SerializeField] private float maxThirdPersonDistance = 14f;
        [Tooltip("滚轮一格改变多少距离")]
        [SerializeField] private float zoomStep = 0.9f;
        [Tooltip("旋转速度(度/秒)")]
        [SerializeField] private float rotateSpeed = 110f;
        [Tooltip("模式切换 / 旋转 / 缩放的平滑速度，越大越快。沿用 followLerp 那套指数插值")]
        [SerializeField] private float modeLerp = 6f;
        [Tooltip("第三人称的近裁剪面。比俯视的近得多：相机贴到墙上时俯视那个 2 会把墙切掉，直接看穿世界")]
        [SerializeField] private float thirdPersonNearClip = 0.3f;

        /// <summary>俯视模式下的近裁剪面，**与历史实现完全一致**（原来是硬编码的 2f）。</summary>
        private const float TopDownNearClip = 2f;

        /// <summary>
        /// 远裁剪面下限。2.5D 小场景 60 就够；王国大地图 / 王都这种公里级场景必须把它抬到
        /// 4 km 级，否则相机的 far 每帧都被算回 60，站在城南看不到城北（用户要求"不要限制视野距离"）。
        /// </summary>
        public float minFarClip = 60f;

        // 必须序列化：烘焙后场景重载时，这个引用得从场景文件里恢复，
        // 否则运行时 target 为 null，机位会按世界原点算，角色直接掉出画面。
        [SerializeField] private Transform target;

        private Camera cam;
        private Vector3 camOffset;
        private Quaternion camRotation;
        private Vector3 smoothPos;

        // ---- 模式状态 ----
        private CameraMode mode = CameraMode.TopDown;   // 默认必须是 0（俯视）
        private float yawInput;        // 玩家用 `,/.` 转出来的目标 yaw（度）
        private float yawCurrent;      // 平滑后的 yaw（度）；模式 0 下精确保持 0
        private float zoomDistance;    // 第三人称当前距离（滚轮改它）

        // 平滑中的机位参数。模式 0 下它们精确等于上面那几个老字段 → 数值路径与历史一致。
        private float curPitch;
        private float curDistance;
        private float curFov;

        // 我上一次真正写进 Camera 组件的值。用它做"只在变化时写"，
        // 避免每帧回写相机参数（那会和编辑器探针/震屏之类的改动打架）。
        private float appliedFov = float.NaN;
        private float appliedOrthoSize = float.NaN;
        private float appliedNear = float.NaN;
        private float appliedFar = float.NaN;

        private MyWorldInput input;

        private readonly RaycastHit[] hitBuffer = new RaycastHit[32];
        private readonly HashSet<FadeableObject> fadedNow = new HashSet<FadeableObject>();
        private readonly HashSet<FadeableObject> fadedPrev = new HashSet<FadeableObject>();

        // 玩家碰撞体缓存：遮挡采样要用它的包围盒，而 GetComponent 不适合每帧调。
        private Collider targetCollider;
        private Transform targetColliderOwner;

        /// <summary>相机模式。0 = 俯视（默认，历史手感），1 = 第三人称。</summary>
        public enum CameraMode
        {
            TopDown = 0,
            ThirdPerson = 1,
        }

        /// <summary>
        /// **当前 yaw（度）—— 供 `PlayerController8Dir` 把 WASD 换算成世界方向。**
        /// 模式 0 下**精确为 0**（不做任何浮点运算的恒等映射），所以默认手感与历史逐位一致。
        /// 静态是因为角色在 Update 里要用它、而相机不在角色层级下；本组件销毁时会清回 0。
        /// </summary>
        public static float MovementYaw { get; private set; }

        /// <summary>当前相机模式。</summary>
        public CameraMode Mode => mode;

        /// <summary>相机到观察点的距离，等于 distance。景深的对焦距离直接用它。</summary>
        public float FocusDistance => distance;

        public void Configure(Transform followTarget)
        {
            target = followTarget;
        }

        public void ConfigureCamera(
            float newPitch, float newDistance,
            bool usePerspective, float newFov, float newOrtho)
        {
            pitch = newPitch;
            distance = newDistance;
            perspective = usePerspective;
            fieldOfView = newFov;
            orthographicSize = newOrtho;
        }

        private void Start()
        {
            ApplySetup();
        }

        /// <summary>
        /// 把当前参数应用到相机组件并摆好初始机位。
        /// 运行时由 Start 调用；编辑期烘焙时由编辑器直接调用（编辑期不会跑 Start）。
        /// </summary>
        public void ApplySetup()
        {
            cam = GetComponent<Camera>();
            if (cam == null) cam = gameObject.AddComponent<Camera>();

            // 起始状态：模式 0 直接用那几个历史字段（数值路径一字不改）；
            // 若序列化成了模式 1，就直接落在第三人称目标值上（烘焙时不做入场过渡）。
            bool third = mode == CameraMode.ThirdPerson;
            zoomDistance = Mathf.Clamp(thirdPersonDistance, minThirdPersonDistance, maxThirdPersonDistance);
            yawCurrent = third ? Mathf.Repeat(yawInput, 360f) : 0f;
            curPitch = third ? thirdPersonPitch : pitch;
            curDistance = third ? zoomDistance : distance;
            curFov = third ? thirdPersonFieldOfView : fieldOfView;

            // 小地图场景用纯色天空（diorama 更清爽）；大地图/王都要真天空盒，
            // 否则 3 km 的地平线会撞在一块死色板上。由场景脚本把 useSkybox 置 true。
            if (useSkybox && RenderSettings.skybox != null)
            {
                cam.clearFlags = CameraClearFlags.Skybox;
            }
            else
            {
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0.53f, 0.72f, 0.83f);   // 偏亮的天空色，配 diorama 更清爽
            }
            ApplyProjection(third);

            camRotation = Quaternion.Euler(curPitch, yawCurrent, 0f);
            // 朝角色后上方退开：back 绕 X 轴旋转 pitch，得到 (0, sin, -cos) 方向的偏移。
            camOffset = camRotation * (Vector3.back * curDistance);

            transform.SetPositionAndRotation(
                (target != null ? target.position : Vector3.zero) + lookOffset + camOffset,
                camRotation);
            smoothPos = transform.position;

            MovementYaw = yawCurrent;
        }

        // ---------------- 模式切换 / 旋转 / 缩放 ----------------

        /// <summary>直接设定相机模式（键 `V` 之外，也给设置界面或测试留一个入口）。</summary>
        public void SetMode(CameraMode newMode)
        {
            mode = newMode;
        }

        /// <summary>俯视 ⇄ 第三人称。</summary>
        public void ToggleMode()
        {
            mode = mode == CameraMode.TopDown ? CameraMode.ThirdPerson : CameraMode.TopDown;
        }

        private void Update()
        {
            ReadCameraInput();
            AdvanceRig(Time.deltaTime);
        }

        /// <summary>
        /// 读相机自己的输入。`MyWorldInput` 挂在玩家身上（相机不在它下面），
        /// 所以顺着 `target` 拿一次并缓存 —— 不用 FindFirstObjectByType，也不引入执行顺序依赖。
        /// </summary>
        private void ReadCameraInput()
        {
            if (input == null && target != null) input = target.GetComponent<MyWorldInput>();
            if (input == null) return;

            if (input.CameraTogglePressed) ToggleMode();

            // 旋转 / 缩放**只在第三人称生效**：俯视模式的 yaw 必须是精确的 0（见 MovementYaw 的说明）。
            if (mode != CameraMode.ThirdPerson) return;

            yawInput = Mathf.Repeat(yawInput + input.CameraRotate * rotateSpeed * Time.deltaTime, 360f);
            zoomDistance = Mathf.Clamp(
                zoomDistance - input.CameraZoom * zoomStep, minThirdPersonDistance, maxThirdPersonDistance);
        }

        /// <summary>
        /// 把 yaw 和"模式相关的三个量"（俯角 / 距离 / FOV）朝当前模式的目标值收敛，并据此算出机位。
        ///
        /// 平滑沿用 `followLerp` 那套 `1 - exp(-k·dt)` 指数插值 → 切换是"滑过去"，不瞬移。
        /// 收敛到 0.02 以内就**精确落位**：指数插值永远差一点点，不落位的话
        /// 模式 0 的 curPitch/curDistance/curFov 会永远不等于历史字段，数值路径就不再逐位一致了。
        /// </summary>
        private void AdvanceRig(float dt)
        {
            bool third = mode == CameraMode.ThirdPerson;
            float goalYaw = third ? yawInput : 0f;
            float goalPitch = third ? thirdPersonPitch : pitch;
            float goalDistance = third ? zoomDistance : distance;
            float goalFov = third ? thirdPersonFieldOfView : fieldOfView;

            float k = 1f - Mathf.Exp(-Mathf.Max(modeLerp, 0.01f) * dt);

            yawCurrent = SnapAngle(Mathf.LerpAngle(yawCurrent, goalYaw, k), goalYaw);
            curPitch = SnapValue(Mathf.Lerp(curPitch, goalPitch, k), goalPitch);
            curDistance = SnapValue(Mathf.Lerp(curDistance, goalDistance, k), goalDistance);
            curFov = SnapValue(Mathf.Lerp(curFov, goalFov, k), goalFov);

            MovementYaw = yawCurrent;

            camRotation = Quaternion.Euler(curPitch, yawCurrent, 0f);
            camOffset = camRotation * (Vector3.back * curDistance);

            ApplyProjection(third);
        }

        /// <summary>收敛到位（差 &lt; 0.02）就精确落位，见 <see cref="AdvanceRig"/>。</summary>
        private static float SnapValue(float value, float goal)
        {
            return Mathf.Abs(value - goal) < 0.02f ? goal : value;
        }

        private static float SnapAngle(float angle, float goal)
        {
            return Mathf.Abs(Mathf.DeltaAngle(angle, goal)) < 0.02f ? goal : angle;
        }

        /// <summary>
        /// 把当前（可能正在过渡中的）机位参数写进 Camera 组件。
        /// **只在值真的变了的时候写** —— 模式 0 下这些值恒等于历史常量，所以运行时的写入行为
        /// 与历史一致（= 一帧都不写），也不会和编辑器探针 / 震屏之类外部改动打架。
        /// </summary>
        private void ApplyProjection(bool third)
        {
            if (cam == null) return;

            if (cam.orthographic != !perspective) cam.orthographic = !perspective;

            if (perspective)
            {
                if (!Mathf.Approximately(appliedFov, curFov)) { appliedFov = curFov; cam.fieldOfView = curFov; }
            }
            else if (!Mathf.Approximately(appliedOrthoSize, orthographicSize))
            {
                appliedOrthoSize = orthographicSize;
                cam.orthographicSize = orthographicSize;
            }

            // 裁剪面贴近实际可见范围。相机在 distance 处、场景纵深约 ±halfD，
            // 留出余量即可，范围太宽只会浪费深度精度。
            float near = third ? thirdPersonNearClip : TopDownNearClip;
            if (!Mathf.Approximately(appliedNear, near)) { appliedNear = near; cam.nearClipPlane = near; }

            float far = Mathf.Max(curDistance * 2.5f, minFarClip);
            if (!Mathf.Approximately(appliedFar, far)) { appliedFar = far; cam.farClipPlane = far; }
        }

        private void OnDisable()
        {
            // 静态量必须清干净：否则换场景后、本组件 Update 还没跑的那几帧里，
            // 角色会按上一个场景残留的 yaw 走路 —— 而且不报任何错（本项目最怕的静默失败）。
            MovementYaw = 0f;
        }

        private void LateUpdate()
        {
            if (target == null) return;

            Vector3 focus = target.position + lookOffset;
            Vector3 desired = focus + camOffset;
            smoothPos = Vector3.Lerp(smoothPos, desired, 1f - Mathf.Exp(-followLerp * Time.deltaTime));

            // 不做位移夹取：相机一旦被夹住而朝向不变，射线就不再穿过角色，
            // 角色会直接掉出画面（这正是之前"玩家不见了"的原因）。
            // 想不看到世界外沿，就让地面比可达区域大一圈，而不是夹相机。
            transform.SetPositionAndRotation(smoothPos, camRotation);

            if (enableOcclusionFade) UpdateOcclusionFade(focus);
        }

        /// <summary>
        /// 把挡在相机和玩家之间的物体淡出；上一帧淡出、这一帧不再挡的恢复。
        ///
        /// **不是一条射线**：只打"相机→观察点中心"一条线时，一栋挡住画面左半边的大房子
        /// （中心线正好从它旁边擦过去）完全不会被淡出 —— 而 2.5D 俯视下这正是最常见的遮挡形态。
        /// 所以改成一簇采样点：玩家包围盒的中心 + 头/脚 + 屏幕左右 + 屏幕前后，
        /// **任一采样点被挡就淡出**。采样半径由 occlusionPadding 控制：宁可漏掉一点，
        /// 也不要把半条街都变成半透明（那比挡住更难看，而且会暴露背后的空洞）。
        /// </summary>
        private void UpdateOcclusionFade(Vector3 focus)
        {
            fadedNow.Clear();

            Vector3 origin = transform.position;

            // 采样基准：优先用玩家碰撞体包围盒的中心（贴地角色时它比 lookOffset 更准）。
            Vector3 center = focus;
            float halfY = 0.75f;
            Collider body = ResolveTargetCollider();
            if (body != null)
            {
                Bounds b = body.bounds;
                center = b.center;
                halfY = Mathf.Max(0.3f, b.extents.y * 0.7f);
            }

            // 采样方向用相机坐标系：屏幕的左右/上下就是相机的 local X/Y，
            // 这样"画面被挡了多少"和采样点覆盖的范围才是一致的。
            Vector3 right = camRotation * Vector3.right;
            Vector3 up = camRotation * Vector3.up;
            Vector3 forward = camRotation * Vector3.forward;
            float pad = Mathf.Max(0f, occlusionPadding);

            int samples = Mathf.Clamp(occlusionSamples, 1, 7);
            CastOccluders(origin, center);                                  // 1：身体中心（旧行为）
            if (samples >= 3)
            {
                CastOccluders(origin, center + up * halfY);                 // 3：+ 头
                CastOccluders(origin, center - up * halfY);                 //    + 脚
            }
            if (samples >= 5)
            {
                CastOccluders(origin, center + right * pad);                // 5：+ 屏幕左
                CastOccluders(origin, center - right * pad);                //    + 屏幕右
            }
            if (samples >= 7)
            {
                CastOccluders(origin, center + forward * pad);              // 7：+ 屏幕前
                CastOccluders(origin, center - forward * pad);              //    + 屏幕后
            }

            // 先把上一帧淡出、这一帧不再挡的恢复成不透明
            foreach (var f in fadedPrev)
            {
                if (f == null) continue;
                if (!fadedNow.Contains(f)) f.SetVisible(true);
            }

            foreach (var f in fadedNow)
            {
                if (f == null) continue;
                f.SetVisible(false);
            }

            fadedPrev.Clear();
            foreach (var f in fadedNow) fadedPrev.Add(f);
        }

        /// <summary>
        /// 朝一个采样点打一条射线，命中的可淡出物放进 fadedNow。
        /// 射线只到采样点为止 —— 所以玩家身后/画面之外的东西不会被误淡。
        /// </summary>
        private void CastOccluders(Vector3 origin, Vector3 point)
        {
            Vector3 dir = point - origin;
            float dist = dir.magnitude;
            if (dist < 0.05f) return;

            int count = Physics.RaycastNonAlloc(origin, dir / dist, hitBuffer, dist, ~0,
                QueryTriggerInteraction.Ignore);
            for (int i = 0; i < count; i++)
            {
                var hit = hitBuffer[i];
                if (hit.collider == null) continue;
                // 打到玩家自己不算遮挡
                if (target != null && hit.collider.transform.IsChildOf(target)) continue;

                var fadeable = hit.collider.GetComponentInParent<FadeableObject>();
                if (fadeable != null) fadedNow.Add(fadeable);
            }
        }

        /// <summary>玩家身上的碰撞体（采样要用它的包围盒）。带缓存，目标换了会重新取。</summary>
        private Collider ResolveTargetCollider()
        {
            if (target == null)
            {
                targetCollider = null;
                targetColliderOwner = null;
                return null;
            }
            if (targetColliderOwner != target)
            {
                targetColliderOwner = target;
                targetCollider = target.GetComponent<Collider>();
            }
            return targetCollider;
        }

        private void OnDrawGizmosSelected()
        {
            if (target == null) return;
            Gizmos.color = Color.yellow;
            Gizmos.DrawLine(transform.position, target.position + lookOffset);
        }
    }
}
