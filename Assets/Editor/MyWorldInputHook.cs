// MyWorldInputHook —— 可复用测试钩子（T-067）
//
// 依据：docs/artifacts/T-067/hook-spec.md（测试部规格）
// 分权：测试部出规格 → 工程部实现 → 测试部用它重写用例
//
// =====================================================================================
// ⚠️ 覆盖边界（规格 §6 —— 必须与实现一起读，不许省略）
// =====================================================================================
// **本钩子注入的是 `MyWorldInput` 的「输出状态」，它绕过了新输入系统的按键绑定。**
//
//   ✅ 能覆盖：`MyWorldInput` 的输出（10 个状态的值）
//   ✅ 能覆盖：`GameUi` 消费 `MenuPressed` → 菜单开关 → 分支跳转
//   ✅ 能覆盖：`PlayerCombat` 消费 `AttackHeld/Pressed` → 起手
//   ✅ 能覆盖：`PlayerController8Dir` 消费 `Move/Sprint/Jump`
//   ❌ **不能**覆盖：真实按键 → action map → 绑定（`<Keyboard>/tab` 等）
//   ❌ **不能**覆盖：`InputSystem` 配置 / Active Input Handling / 手柄映射
//   ❌ **不能**覆盖：`WasPressedThisFrame()` 的"只触发一帧"语义本身（回落是本钩子自己模拟的）
//
// ⭐ **结论（规格 §6 原话）**：
//   **判据 14 在钩子到位后能达到的覆盖层级 = "`MyWorldInput` 之后 的链路"。**
//   **"真实按键 → action"这一段仍为零覆盖**，需另行手段，或明确记为**已知空白**。
//   **不要让它看起来像"按键链路全测了"。**
//
//   具体后果：若 `<Keyboard>/tab` 的绑定被写错（例如写成 `<Keyboard>/backquote`），
//   **本钩子全绿、判据 14 全绿，而玩家根本开不了菜单。**
//
// =====================================================================================
// 实现手法（规格 §3）
// =====================================================================================
// **伪造属性输出层，绝不去动 `InputAction`。** 两条捷径都不通：
//   ① 只写属性 → `MyWorldInput.Update()`（:152-169）**每帧重算全部状态** → 注入当帧就被覆盖；
//   ② 写 `InputAction.ReadValue` → `WasPressedThisFrame()` 依赖输入系统的**内部帧状态**，
//      而 `InputSystem.Update()` 内部会重置它 —— 由测试侧操纵引擎内部帧状态是在和实现对赌。
//
// 故：**临时 `enabled = false`（停掉每帧重算） + 反射写 auto-property 的后备字段**。
//
// =====================================================================================
// 生命周期纪律（规格 §4 —— 与 `PauseGuard` 同一纪律）
// =====================================================================================
//  * `Acquire()` 找不到 `MyWorldInput` → **返回 false**，调用方**必须**判 `INCONCLUSIVE`，不许静默继续；
//  * `Release()` **必须完整还原**：组件 `enabled` + 10 个状态原值。
//    ⚠️ 只还原一部分、或忘了恢复 `enabled` → **整个游戏输入失灵**，
//    而现象是"按键没反应"，极易被误判成"绑定坏了"。
//  * **可重入**：重复 `Acquire()` 不破坏还原（用深度计数，只在最后一层 `Release()` 时真正还原）。
//
// ⚠️ **本文件是新增文件，未改动任何生产代码**（`MyWorldInput.cs` 等一行未动）。
//    **可整体删除**：删掉 `Assets/Editor/MyWorldInputHook.cs` 与其 `.meta` 即可，游戏照跑。
//
// 签名冻结说明（规格 §2）：§2 列出的签名**逐字实现、不得更改**。
//   本文件在 §2 之外**新增**了两项（按"只许新增"的规则，已报总控批准）：
//     * `ClearFrameState()`  —— §4.3 要求"回落时机必须明确"，本实现选**调用方显式回落**这一支；
//     * `SetMoveClamped(Vector2)` —— §5 建议的夹紧版本（与不夹紧的 `SetMove` 并存）。

#if UNITY_EDITOR
using System;
using System.Reflection;
using UnityEngine;

namespace MyWorldQa
{
    /// <summary>
    /// 可复用测试钩子：伪造 <see cref="MyWorld.MyWorldInput"/> 的输出状态。
    /// ⚠️ 它驱动的是 MyWorldInput 的【输出】，**绕过新输入系统的绑定** —— 覆盖边界见文件头。
    /// </summary>
    public static class MyWorldInputHook
    {
        private const string InputTypeName = "MyWorld.MyWorldInput";

        /// <summary>10 个对外状态（规格 §1 的全集）。名字必须与 `MyWorldInput` 的属性名逐字一致。</summary>
        private static readonly string[] StateNames =
        {
            "Move", "Sprint",
            "AttackPressed", "AttackHeld",
            "LockOnPressed", "OffHandPressed", "OffHandHeld",
            "JumpPressed", "MenuPressed", "SettingsPressed",
        };

        /// <summary>本帧型（`WasPressedThisFrame` 语义）的状态名 —— `ClearFrameState()` 只回落这些。</summary>
        private static readonly string[] FrameTypeNames =
        {
            "AttackPressed", "LockOnPressed", "OffHandPressed", "JumpPressed",
            "MenuPressed", "SettingsPressed",
        };

        private static int s_depth;                  // 重入深度：0 = 未接管
        private static bool s_savedEnabled;          // 接管前组件的 enabled
        private static object[] s_savedValues;       // 接管前 10 个状态的原值
        private static Component s_input;            // MyWorldInput 组件实例（用 Component 避免硬引用）

        /// <summary>当前是否处于接管状态（供断言/自查用）。</summary>
        public static bool IsAcquired { get { return s_depth > 0; } }

        // ---------------------------------------------------------------- 生命周期

        /// <summary>
        /// 开始接管输入。记录当前是否 enabled / 各状态原值，供 <see cref="Release"/> 还原。
        /// 返回 false = 场景里找不到 MyWorldInput（**调用方必须当作 INCONCLUSIVE 处理**）。
        /// </summary>
        public static bool Acquire()
        {
            if (s_depth > 0)
            {
                // 可重入：不重新记录原值，否则会把"已注入的值"当成原值记下来，Release 就还原不回去了。
                s_depth++;
                return true;
            }

            var t = FindType(InputTypeName);
            if (t == null) return false;

            var found = UnityEngine.Object.FindFirstObjectByType(t) as Component;
            if (found == null) return false;

            s_input = found;
            s_savedEnabled = found is Behaviour ? ((Behaviour)found).enabled : true;
            s_savedValues = new object[StateNames.Length];
            for (int i = 0; i < StateNames.Length; i++)
                s_savedValues[i] = ReadState(t, found, StateNames[i]);

            // 停掉每帧重算 —— 这是整个手法成立的前提（见文件头 §3）。
            if (found is Behaviour) ((Behaviour)found).enabled = false;

            s_depth = 1;
            return true;
        }

        /// <summary>
        /// 释放并**完整还原**：组件 enabled 恢复、所有注入状态回到 <see cref="Acquire"/> 时的原值。
        /// 必须在每条用例的每一条 return 路径上调用（与 `PauseGuard` 同一纪律）。
        /// </summary>
        public static void Release()
        {
            if (s_depth <= 0) return;

            s_depth--;
            if (s_depth > 0) return;   // 还在重入的外层，先不还原

            if (s_input != null)
            {
                var t = s_input.GetType();
                if (s_savedValues != null)
                {
                    for (int i = 0; i < StateNames.Length; i++)
                        WriteState(t, s_input, StateNames[i], s_savedValues[i]);
                }
                if (s_input is Behaviour) ((Behaviour)s_input).enabled = s_savedEnabled;
            }

            s_input = null;
            s_savedValues = null;
        }

        // ---------------------------------------------------------------- 注入：本帧型

        /// <summary>伪造 MenuPressed（= Tab）。**只置位** —— `Step()` 之后请调用 <see cref="ClearFrameState"/>。</summary>
        public static void PressMenu() { SetState("MenuPressed", true); }
        /// <summary>伪造 SettingsPressed（= Esc）。</summary>
        public static void PressSettings() { SetState("SettingsPressed", true); }
        /// <summary>伪造 AttackPressed（= 左键本帧按下）。</summary>
        public static void PressAttack() { SetState("AttackPressed", true); }
        /// <summary>伪造 OffHandPressed（= 右键本帧按下）。</summary>
        public static void PressOffHand() { SetState("OffHandPressed", true); }
        /// <summary>伪造 JumpPressed（= 空格）。</summary>
        public static void PressJump() { SetState("JumpPressed", true); }
        /// <summary>伪造 LockOnPressed（= Q）。</summary>
        public static void PressLockOn() { SetState("LockOnPressed", true); }

        /// <summary>
        /// 把全部**本帧型**状态回落为 false（保持型不受影响）。
        ///
        /// ⚠️ **回落时机必须明确**（规格 §4.3）：本实现选"**由调用方在 `Step()` 之后显式调用**"。
        /// 为什么必须回落：真实语义是 `WasPressedThisFrame()` —— **只在一帧为真**；
        /// 若一直保持 true，`GameUi.Update()` 的切换（`SetMenuOpen(!IsOpen)`）会**每帧翻转**，
        /// 制造出"注入了一帧却生效了十帧"的假象。
        /// </summary>
        public static void ClearFrameState()
        {
            for (int i = 0; i < FrameTypeNames.Length; i++)
                SetState(FrameTypeNames[i], false);
        }

        // ---------------------------------------------------------------- 注入：保持型

        /// <summary>
        /// 直接写 `Move`（**不夹紧**，调用方自负）。用于测试"超长向量会不会被下游正确处理"。
        /// 多数用例想要的是 <see cref="SetMoveClamped"/>。
        /// </summary>
        public static void SetMove(Vector2 v) { SetState("Move", v); }

        /// <summary>
        /// 复刻 `MyWorldInput` 真实实现对对角线的夹紧（`MyWorldInput.cs:156`：长度 &gt; 1 时归一化）。
        /// **默认推荐用这个** —— 绝大多数用例想模拟的是"玩家真的推了摇杆"。
        /// </summary>
        public static void SetMoveClamped(Vector2 v)
        {
            Vector2 outV = v;
            if (v.sqrMagnitude > 1f) outV = v.normalized;
            SetState("Move", outV);
        }

        public static void SetSprint(bool on) { SetState("Sprint", on); }
        public static void SetAttackHeld(bool on) { SetState("AttackHeld", on); }
        public static void SetOffHandHeld(bool on) { SetState("OffHandHeld", on); }

        // ---------------------------------------------------------------- 注入：通用/逃生口

        /// <summary>一次性写任意状态（未指定的参数保持当前值）。</summary>
        public static void Set(bool? menu = null, bool? settings = null, bool? attackPressed = null,
                              bool? attackHeld = null, bool? offHandPressed = null, bool? offHandHeld = null,
                              bool? jumpPressed = null, bool? lockOnPressed = null, bool? sprint = null,
                              Vector2? move = null)
        {
            if (menu.HasValue) SetState("MenuPressed", menu.Value);
            if (settings.HasValue) SetState("SettingsPressed", settings.Value);
            if (attackPressed.HasValue) SetState("AttackPressed", attackPressed.Value);
            if (attackHeld.HasValue) SetState("AttackHeld", attackHeld.Value);
            if (offHandPressed.HasValue) SetState("OffHandPressed", offHandPressed.Value);
            if (offHandHeld.HasValue) SetState("OffHandHeld", offHandHeld.Value);
            if (jumpPressed.HasValue) SetState("JumpPressed", jumpPressed.Value);
            if (lockOnPressed.HasValue) SetState("LockOnPressed", lockOnPressed.Value);
            if (sprint.HasValue) SetState("Sprint", sprint.Value);
            if (move.HasValue) SetState("Move", move.Value);
        }

        // ---------------------------------------------------------------- 反射实现

        private static Type FindType(string fullName)
        {
            var assemblies = AppDomain.CurrentDomain.GetAssemblies();
            for (int i = 0; i < assemblies.Length; i++)
            {
                var t = assemblies[i].GetType(fullName, false);
                if (t != null) return t;
            }
            return null;
        }

        /// <summary>
        /// 读状态。两条路都试：后备字段优先（不依赖 setter 可见性），失败则退到属性。
        /// </summary>
        private static object ReadState(Type t, object inst, string name)
        {
            var f = t.GetField("<" + name + ">k__BackingField",
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (f != null) return f.GetValue(inst);

            var p = t.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            return p != null ? p.GetValue(inst, null) : null;
        }

        /// <summary>
        /// 写状态。**必须写后备字段**：`{ get; private set; }` 的 setter 是私有的。
        /// （规格 §3 说 `GetProperty + SetValue` 也可行且测试部已验证；这里以后备字段为主路径，
        ///  因为它不依赖 setter 的可见性规则，跨版本更稳。两条路都保留。）
        /// </summary>
        private static void WriteState(Type t, object inst, string name, object value)
        {
            if (inst == null) return;

            var f = t.GetField("<" + name + ">k__BackingField",
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (f != null) { f.SetValue(inst, value); return; }

            var p = t.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (p != null && p.CanWrite) { p.SetValue(inst, value, null); return; }

            Debug.LogWarning("[MyWorldInputHook] 找不到可写目标: " + name
                             + " —— 钩子未生效，调用方应判 INCONCLUSIVE。");
        }

        private static void SetState(string name, object value)
        {
            if (s_input == null)
            {
                Debug.LogWarning("[MyWorldInputHook] 尚未 Acquire()，忽略注入: " + name);
                return;
            }
            WriteState(s_input.GetType(), s_input, name, value);
        }
    }
}
#endif
