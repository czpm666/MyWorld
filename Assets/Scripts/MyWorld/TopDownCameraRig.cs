using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 织梦岛那种斜俯视相机：固定俯角、正交投影、平滑跟随。
    ///
    /// 相机 yaw 固定为 0 很关键——这样屏幕上方永远等于世界 +Z，
    /// WASD 才能直接映射到世界四方向，角色朝向也才能稳定地吸附到 8 个方向。
    /// 如果给相机加 yaw，操作方向就会相对于世界变成斜的，8 方向感会散掉。
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
        [Tooltip("跟随的平滑速度，越大越跟手")]
        [SerializeField] private float followLerp = 7.5f;
        [Tooltip("观察点相对角色脚下的抬高量，让角色略偏屏幕下方，前方看得更多")]
        [SerializeField] private Vector3 lookOffset = new Vector3(0f, 1f, 0f);

        [Header("遮挡淡出")]
        [SerializeField] private bool enableOcclusionFade = true;

        // 必须序列化：烘焙后场景重载时，这个引用得从场景文件里恢复，
        // 否则运行时 target 为 null，机位会按世界原点算，角色直接掉出画面。
        [SerializeField] private Transform target;

        private Camera cam;
        private Vector3 camOffset;
        private Quaternion camRotation;
        private Vector3 smoothPos;

        private readonly RaycastHit[] hitBuffer = new RaycastHit[32];
        private readonly HashSet<FadeableObject> fadedNow = new HashSet<FadeableObject>();
        private readonly HashSet<FadeableObject> fadedPrev = new HashSet<FadeableObject>();

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

            cam.orthographic = !perspective;
            if (perspective) cam.fieldOfView = fieldOfView;
            else cam.orthographicSize = orthographicSize;

            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.53f, 0.72f, 0.83f);   // 偏亮的天空色，配 diorama 更清爽

            // 裁剪面贴近实际可见范围。相机在 distance 处、场景纵深约 ±halfD，
            // 留出余量即可，范围太宽只会浪费深度精度。
            cam.nearClipPlane = 2f;
            cam.farClipPlane = Mathf.Max(distance * 2.5f, 60f);

            camRotation = Quaternion.Euler(pitch, 0f, 0f);
            // 朝角色后上方退开：back 绕 X 轴旋转 pitch，得到 (0, sin, -cos) 方向的偏移。
            camOffset = camRotation * (Vector3.back * distance);

            transform.SetPositionAndRotation(
                (target != null ? target.position : Vector3.zero) + lookOffset + camOffset,
                camRotation);
            smoothPos = transform.position;
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
        /// 从相机朝玩家打一条射线，把中途挡住的物体淡出；上一帧淡出、这一帧不再挡的恢复。
        /// </summary>
        private void UpdateOcclusionFade(Vector3 focus)
        {
            fadedNow.Clear();

            Vector3 origin = transform.position;
            Vector3 toFocus = focus - origin;
            float dist = toFocus.magnitude;

            if (dist > 0.001f)
            {
                Vector3 dir = toFocus / dist;
                int count = Physics.RaycastNonAlloc(origin, dir, hitBuffer, dist, ~0, QueryTriggerInteraction.Ignore);
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

        private void OnDrawGizmosSelected()
        {
            if (target == null) return;
            Gizmos.color = Color.yellow;
            Gizmos.DrawLine(transform.position, target.position + lookOffset);
        }
    }
}
