using UnityEngine;
using UnityEngine.InputSystem;

namespace MyWorld
{
    /// <summary>
    /// 提供"鼠标指向"这个方向（射线与角色所在水平面求交，对正交/透视、任意俯角都成立），
    /// 并**只在释放技能/攻击的那一刻**把它交给角色转向。
    ///
    /// 平时朝向由 WASD 决定（PlayerController8Dir 的默认行为），
    /// 只有 PlayerCombat 说"正在出手"时（combo）才转向鼠标——
    /// 这样走路是 8 方向手感，打人时又能精确瞄鼠标。
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerAim : MonoBehaviour
    {
        private PlayerController8Dir controller;
        private PlayerCombat combat;
        private Camera cam;

        /// <summary>鼠标在世界水平面上的指向（未归一化为零向量时有效）。</summary>
        public Vector3 MouseDirection { get; private set; }

        /// <summary>鼠标指向是否有效（鼠标设备存在且不在脚下）。</summary>
        public bool HasMouseDirection { get; private set; }

        /// <summary>鼠标射线与角色所在水平面的交点（锁定用它选"离鼠标最近"的目标）。</summary>
        public Vector3 MouseWorldPoint { get; private set; }

        private void Awake()
        {
            controller = GetComponent<PlayerController8Dir>();
            combat = GetComponent<PlayerCombat>();
        }

        private void Update()
        {
            HasMouseDirection = false;
            if (controller == null) return;

            if (cam == null) cam = Camera.main;
            if (cam == null) return;

            var mouse = Mouse.current;
            if (mouse == null)
            {
                controller.ClearAimFacing();
                return;
            }

            Vector2 screen = mouse.position.ReadValue();
            Ray ray = cam.ScreenPointToRay(new Vector3(screen.x, screen.y, 0f));

            var plane = new Plane(Vector3.up, transform.position);
            if (!plane.Raycast(ray, out float dist)) return;

            Vector3 point = ray.GetPoint(dist);
            MouseWorldPoint = point;

            Vector3 dir = new Vector3(point.x - transform.position.x, 0f, point.z - transform.position.z);
            if (dir.sqrMagnitude < 0.0004f) return;   // 鼠标就在脚下，方向没意义

            MouseDirection = dir;
            HasMouseDirection = true;

            // 只有正在出手时才把朝向交给鼠标；平时清掉，让朝向回到 WASD
            if (combat != null && combat.AimingAtMouse)
                controller.SetAimFacing(dir);
            else
                controller.ClearAimFacing();
        }
    }
}
