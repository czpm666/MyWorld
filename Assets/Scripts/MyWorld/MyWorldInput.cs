using UnityEngine;
using UnityEngine.InputSystem;

namespace MyWorld
{
    /// <summary>
    /// 输入收敛层：把键盘/手柄的移动输入统一成一条已夹紧的二维向量。
    ///
    /// 注意：本项目 Player Settings 里的 Active Input Handling 是 "Input System Package (New)"，
    /// 旧的 UnityEngine.Input 类在这里是**不可用**的（调用会抛异常），只能用 InputAction。
    /// 这里在代码里直接构建 InputAction，不依赖 .inputactions 资源，免得还要在 Inspector 里拖引用。
    /// </summary>
    [DisallowMultipleComponent]
    public class MyWorldInput : MonoBehaviour
    {
        private InputAction moveAction;
        private InputAction sprintAction;
        private InputAction attackAction;
        private InputAction lockOnAction;
        private InputAction offHandAction;
        private InputAction jumpAction;
        private InputAction menuAction;
        private InputAction settingsAction;

        /// <summary>移动输入，长度已被夹到 ≤1。屏幕上方 = +Z 方向。</summary>
        public Vector2 Move { get; private set; }

        /// <summary>本帧是否有移动输入。</summary>
        public bool HasMove => Move.sqrMagnitude > 0.0001f;

        /// <summary>Shift 是否按住（疾跑）。</summary>
        public bool Sprint { get; private set; }

        /// <summary>本帧是否按下了左键（攻击）。只在按下的那一帧为 true。</summary>
        public bool AttackPressed { get; private set; }

        /// <summary>左键是否按住。按住就自动连发，不用一下下点。</summary>
        public bool AttackHeld { get; private set; }

        /// <summary>本帧是否按下了中键（锁定/解锁）。切换式，只在按下的那一帧为 true。</summary>
        public bool LockOnPressed { get; private set; }

        /// <summary>右键：用副手武器。本帧按下。</summary>
        public bool OffHandPressed { get; private set; }

        /// <summary>右键是否按住（抓钩要"按住拉、松手保留动量"）。</summary>
        public bool OffHandHeld { get; private set; }

        /// <summary>本帧是否按下了跳跃（空格）。</summary>
        public bool JumpPressed { get; private set; }

        /// <summary>本帧是否按下了 Tab（开关菜单）。</summary>
        public bool MenuPressed { get; private set; }

        /// <summary>本帧是否按下了 Esc（直接打开设置页）。</summary>
        public bool SettingsPressed { get; private set; }

        private void Awake()
        {
            moveAction = new InputAction("Move", InputActionType.Value);

            // 键盘 WASD / 方向键：合成二维向量，对角线会得到长度 √2，用的时候夹紧。
            moveAction.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/w")
                .With("Down", "<Keyboard>/s")
                .With("Left", "<Keyboard>/a")
                .With("Right", "<Keyboard>/d");

            moveAction.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/upArrow")
                .With("Down", "<Keyboard>/downArrow")
                .With("Left", "<Keyboard>/leftArrow")
                .With("Right", "<Keyboard>/rightArrow");

            // 手柄左摇杆：保留模拟量，推得浅就走得慢。
            moveAction.AddBinding("<Gamepad>/leftStick");

            // 疾跑：Shift 按住即可（左右都认），手柄用左摇杆按下。
            sprintAction = new InputAction("Sprint", InputActionType.Button);
            sprintAction.AddBinding("<Keyboard>/leftShift");
            sprintAction.AddBinding("<Keyboard>/rightShift");
            sprintAction.AddBinding("<Gamepad>/leftStickPress");

            // 攻击：鼠标左键，手柄用 X/方块。
            attackAction = new InputAction("Attack", InputActionType.Button);
            attackAction.AddBinding("<Mouse>/leftButton");
            attackAction.AddBinding("<Gamepad>/buttonWest");

            // 锁定：Q（切换式）。不用鼠标键是因为左右键已经分别给主手/副手了。
            lockOnAction = new InputAction("LockOn", InputActionType.Button);
            lockOnAction.AddBinding("<Keyboard>/q");
            lockOnAction.AddBinding("<Gamepad>/rightStickPress");

            // 副手武器：鼠标右键（按住生效，抓钩靠松手保留动量），手柄用右扳机。
            offHandAction = new InputAction("OffHand", InputActionType.Button);
            offHandAction.AddBinding("<Mouse>/rightButton");
            offHandAction.AddBinding("<Gamepad>/rightTrigger");

            // 跳跃：空格，手柄 A/叉。
            jumpAction = new InputAction("Jump", InputActionType.Button);
            jumpAction.AddBinding("<Keyboard>/space");
            jumpAction.AddBinding("<Gamepad>/buttonSouth");

            // 菜单：Tab，手柄 Start。
            menuAction = new InputAction("Menu", InputActionType.Button);
            menuAction.AddBinding("<Keyboard>/tab");
            menuAction.AddBinding("<Gamepad>/start");

            // 设置：Esc 直接跳到设置页
            settingsAction = new InputAction("Settings", InputActionType.Button);
            settingsAction.AddBinding("<Keyboard>/escape");
            settingsAction.AddBinding("<Gamepad>/select");

            moveAction.Enable();
            sprintAction.Enable();
            attackAction.Enable();
            lockOnAction.Enable();
            offHandAction.Enable();
            jumpAction.Enable();
            menuAction.Enable();
            settingsAction.Enable();
        }

        private void OnDisable()
        {
            Move = Vector2.zero;
            Sprint = false;
            AttackPressed = false;
            AttackHeld = false;
            LockOnPressed = false;
            OffHandPressed = false;
            OffHandHeld = false;
            JumpPressed = false;
            MenuPressed = false;
            SettingsPressed = false;
        }

        private void OnDestroy()
        {
            foreach (var a in new[] { moveAction, sprintAction, attackAction, lockOnAction, offHandAction, jumpAction, menuAction, settingsAction })
            {
                a?.Disable();
                a?.Dispose();
            }
            moveAction = sprintAction = attackAction = lockOnAction = offHandAction = jumpAction = menuAction = settingsAction = null;
        }

        private void Update()
        {
            Vector2 raw = moveAction != null ? moveAction.ReadValue<Vector2>() : Vector2.zero;
            // 键盘对角线是 √2，夹到 1；手柄摇杆本来就 ≤1，保持模拟量不被放大。
            if (raw.sqrMagnitude > 1f) raw = raw.normalized;
            Move = raw;

            Sprint = sprintAction != null && sprintAction.IsPressed();
            // WasPressedThisFrame 保证一次点击只触发一次攻击，不会因为按住而连发。
            AttackPressed = attackAction != null && attackAction.WasPressedThisFrame();
            AttackHeld = attackAction != null && attackAction.IsPressed();
            LockOnPressed = lockOnAction != null && lockOnAction.WasPressedThisFrame();
            OffHandPressed = offHandAction != null && offHandAction.WasPressedThisFrame();
            OffHandHeld = offHandAction != null && offHandAction.IsPressed();
            JumpPressed = jumpAction != null && jumpAction.WasPressedThisFrame();
            MenuPressed = menuAction != null && menuAction.WasPressedThisFrame();
            SettingsPressed = settingsAction != null && settingsAction.WasPressedThisFrame();
        }
    }
}
