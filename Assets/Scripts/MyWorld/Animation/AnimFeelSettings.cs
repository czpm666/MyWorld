using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **手感参数的唯一集中点**（本轮动画手感改造新增）。
    ///
    /// 资产位置：`Assets/Scripts/MyWorld/Animation/Resources/AnimFeelSettings.asset`
    /// 打开方式：菜单 `Tools > My World > 动画手感参数`（没有就自动创建）。
    /// 运行时由 <see cref="Active"/> 懒加载；**资产不存在也不会报错**，用代码里的默认值跑。
    ///
    /// 🔴 **为什么参数放在 ScriptableObject，而不是挂在 `PlayerController8Dir` 的
    /// `[SerializeField]` 上**：场景 `Assets/Scenes/MyWorld.unity` 里那份组件实例
    /// **已经序列化过一轮**了 —— 只有**新增**字段会吃到代码里的默认值，
    /// **改老字段的默认值对已存在的场景实例完全无效**（改完在编辑器里看不出任何变化，
    /// 这类"改了等于没改"的静默失败本项目吃过多次）。放进 Resources 资产就绕开了这条：
    /// 值由资产给出，改资产 = 立刻生效，**不需要动场景**（场景是别人的写入范围）。
    ///
    /// ⚠️ 本类**只描述"动画怎么播"**：不碰伤害、冷却、判定距离、位移速度上限。
    /// </summary>
    [CreateAssetMenu(menuName = "My World/动画手感参数", fileName = "AnimFeelSettings")]
    public class AnimFeelSettings : ScriptableObject
    {
        /// <summary>Resources 下的资产名（不带扩展名）。</summary>
        public const string ResourceName = "AnimFeelSettings";

        private static AnimFeelSettings active;

        /// <summary>
        /// 全局生效的一份参数。优先用 Resources 资产；找不到就用一份**内存临时实例**
        /// （字段默认值 = 本类里写的默认值），**不会**写盘、不会在编辑器里留下垃圾资产。
        /// </summary>
        public static AnimFeelSettings Active
        {
            get
            {
                if (active != null) return active;

                active = Resources.Load<AnimFeelSettings>(ResourceName);
                if (active == null)
                {
                    active = CreateInstance<AnimFeelSettings>();
                    active.hideFlags = HideFlags.HideAndDontSave;
                }
                return active;
            }
        }

        // =====================================================================
        // ① 移动动画节奏：这段剪辑在 **1.0 倍速**下"自带"的地面速度（单位/秒）
        // =====================================================================
        // 🔴 这几个数是**实测**出来的，不是拍的 —— 用 `AnimationMode.SampleAnimationClip`
        //    在 MageCharacter 预制体上逐帧采样 `toes.l/toes.r/foot.l/foot.r`，
        //    取"脚掌贴地那一小段"在角色本地空间里的反向速度（脚不动 = 人前进多少）。
        //    实测：Walk ≈ 0.79~0.88、Run ≈ 3.61~3.63（踝）、Walk_Back ≈ 0.78~0.87、
        //    Run_Strafe_L ≈ 3.53~3.62、Run_Strafe_R ≈ 3.50~3.54。
        //
        // ⚠️ 对比一下玩法速度（`PlayerController8Dir.walkSpeed = 5.5` / `runSpeed = 9.5`）：
        //    角色的"走路速度"需要 Walk 剪辑 **6.5 倍速**才不滑步 —— 那不是走路，是踩缝纫机。
        //    所以满速移动时**正确的剪辑是 Run**（5.5 / 3.6 = 1.53 倍速，完全合理）。
        //    Walk 剪辑只在低速/被减速时才该出现。

        [Header("① 移动剪辑节奏（1.0 倍速下的地面速度，单位/秒）")]
        [Tooltip("Walk.anim 自带的速度。实测 ≈0.83（30fps / 32 帧 / 步幅 ≈0.40m）")]
        public float walkClipSpeed = 0.85f;

        [Tooltip("Run.anim 自带的速度。实测 ≈3.62（脚跟触地那一段的踝关节反向速度）")]
        public float runClipSpeed = 3.60f;

        [Tooltip("Run_Strafe_L/R.anim 自带的速度。实测 ≈3.55")]
        public float strafeClipSpeed = 3.55f;

        [Tooltip("Walk_Back.anim 自带的速度。实测 ≈0.83 —— 原版没有退跑剪辑，后退满速时必然还有滑步")]
        public float backClipSpeed = 0.85f;

        // =====================================================================
        // ② 播放倍率钳制 / 平滑
        // =====================================================================
        [Header("② 播放倍率钳制与平滑")]
        [Tooltip("播放倍率下限。绝不能到 0 —— Animator.speed = 0 会把整个动画冻住")]
        public float minPlayback = 0.35f;

        [Tooltip("播放倍率上限。2.7 = 冲刺 9.5 / Run 3.6 = 2.64 刚好装得下（脚底零打滑）；调小会在冲刺时重新出现滑步")]
        public float maxPlayback = 2.70f;

        [Tooltip("Animator.speed 向目标收敛的速率（单位/秒）。越大越跟手，越小越平滑")]
        public float playbackLerp = 45f;

        // =====================================================================
        // ③ Speed 参数归一化
        // =====================================================================
        [Header("③ Speed 参数归一化")]
        [Tooltip("实际水平速度 / 这个值 = 喂给 Animator 的 Speed 参数。默认 2.2 是**算出来的**：\n"
                 + "控制器里两个阈值写死为 0.15 / 0.75，乘 2.2 就是 0.33 m/s / 1.65 m/s ——\n"
                 + "也就是说 Walk 剪辑只负责 0.33~1.65 m/s（倍率 0.39~1.94×，全程不打滑），\n"
                 + "1.65 m/s 以上交给 Run（倍率最大 9.5/3.6 = 2.64×，同样不打滑）。\n"
                 + "⚠️ 摇杆推满就是 5.5 m/s，所以「推满 = Run」，Walk 只在减速/轻推摇杆时出现")]
        public float speedParamFullSpeed = 2.2f;

        // =====================================================================
        // ④ 连招分级：轻重靠**播放倍率**区分（值越小越"沉"）
        // =====================================================================
        // 四段用的剪辑本来就不同（横劈/下劈/斜劈/突刺），但长度被统一裁到 0.6s，
        // 于是四刀在**节奏上**完全一样 —— 打起来像连按同一个键。
        // 给不同的播放倍率之后：第一刀"快、脆"，最后一刀"慢、沉"，
        // 手感上立刻分得出轻击和终结技（这是动画里的常规做法：轻击 snap、重击 drag）。
        // ⚠️ 剪辑上的 `OnSlashImpact` 命中事件会跟着倍率提前/推后 —— 重击命中更晚，是有意的。
        [Header("④ 连招分级（播放倍率：轻 → 重）")]
        [Tooltip("第 1 段（横劈）：轻、脆，最快")]
        public float comboPlayback0 = 1.20f;

        [Tooltip("第 2 段（下劈）")]
        public float comboPlayback1 = 1.05f;

        [Tooltip("第 3 段（斜劈）")]
        public float comboPlayback2 = 0.95f;

        [Tooltip("第 4 段（突刺，终结技）：最慢最沉")]
        public float comboPlayback3 = 0.80f;

        // =====================================================================
        // ⑤ 其它动作
        // =====================================================================
        [Header("⑤ 施法 / 弓 / 空手 / 受击")]
        [Tooltip("施法（Cast，0.933s）。>1 缩短起手念咒，出手更立刻")]
        public float castPlayback = 1.15f;

        [Tooltip("射箭（BowShot）。⚠️ 剪辑上有 `OnArrowRelease` 事件，倍率会改变箭离弦的时刻")]
        public float bowShotPlayback = 1.00f;

        [Tooltip("空手拳脚（Punch_A/Punch_B/Kick）。这三条剪辑很长（1.47~1.67s），\n"
                 + "1.0 倍速下一拳要 1.5 秒 —— 倍率是空手手感的主要旋钮")]
        public float unarmedPlayback = 1.60f;

        [Tooltip("受击（Hit，0.667s）。>1 让僵直更快过去")]
        public float hitPlayback = 1.15f;

        // =====================================================================
        // ⑥ 起步 / 转身
        // =====================================================================
        [Header("⑥ 起步 / 转身")]
        [Tooltip("起步加成：静止那一瞬间加速度额外乘 (1 + accelKick)，随速度升高回到 1×。\n"
                 + "线性加速的观感是「先慢后突然到顶」，这一项把起步头几十毫秒拉快 —— 就是「加速曲线」")]
        public float accelKick = 0.35f;

        [Tooltip("转身减速：朝向差 180° 时目标速度乘 (1 - turnSpeedPenalty)。0 = 关掉")]
        public float turnSpeedPenalty = 0.18f;

        /// <summary>连招第 <paramref name="step"/> 段的播放倍率（0..3，越界自动夹紧）。</summary>
        public float ComboPlayback(int step)
        {
            switch (step)
            {
                case 0: return comboPlayback0;
                case 1: return comboPlayback1;
                case 2: return comboPlayback2;
                default: return comboPlayback3;
            }
        }

        /// <summary>把所有倍率夹进 [minPlayback, maxPlayback]，兜住手滑填 0 或负数。</summary>
        public float Clamp(float playback)
        {
            float lo = Mathf.Max(0.05f, minPlayback);
            float hi = Mathf.Max(lo, maxPlayback);
            return Mathf.Clamp(playback, lo, hi);
        }
    }
}
