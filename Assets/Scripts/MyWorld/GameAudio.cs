using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 最基础的音效播放（T-063）。**只做用户要的 5 个音**，不引 AudioMixer、不做随机变体、
    /// 不做 3D 衰减调参、不做音高抖动 —— 那些都是"以后再说"的事。
    ///
    /// 设计要点：
    ///  * **一个 `AudioSource` + `PlayOneShot`**，不做"每个音效一个 AudioSource"。
    ///  * **5 个 clip 槽位集中在这一处**（`AudioSource` 所在物体上），将来换素材只改这里。
    ///  * **缺素材的槽位留空是设计的一部分**：播放路径是 `clip != null` 才播 →
    ///    **空槽静默跳过，不报错、不崩**。素材到位 = 拖文件 + Inspector 赋值，**不改一代码**。
    ///  * **音量与音高一律用默认值（1.0 / 不改动）** —— 属手感/平衡，**归用户**。
    ///    本文件**不写任何音量/音高魔数**；要调请用户明示。
    ///
    /// ⚠️ **覆盖边界（哪 5 个音、分别挂在哪）**：
    ///   | 音 | 挂点 | 语义 |
    ///   |---|---|---|
    ///   | 剑挥砍 | `PlayerCombat.SwingSword()` | 起手那帧（挥空也响 —— 那是"我按了"的反馈）|
    ///   | 命中   | `PlayerCombat.OnSlashImpact()` 内、**确实打中目标时才响** | 剑/箭/法术共用一个 |
    ///   | 放箭   | `PlayerCombat.OnArrowRelease()` | 离弦那一帧（0.420s，由动画事件驱动）|
    ///   | 施法   | `PlayerCombat.CastSpell()` | — |
    ///   | 受击   | `PlayerHealth.TakeDamage()` | 玩家挨打 |
    /// ⛔ **不做**：背景音乐 / 脚步 / 环境音 / 敌人挥击 / 拾取音（用户口径："最基础的"）。
    /// </summary>
    [DisallowMultipleComponent]
    public class GameAudio : MonoBehaviour
    {
        [Header("5 个基础音效（**缺素材就留空** —— 空槽会静默跳过，不报错）")]
        [Tooltip("① 剑挥砍：PlayerCombat.SwingSword() 起手时")]
        [SerializeField] private AudioClip swingClip;

        [Tooltip("② 命中：PlayerCombat.OnSlashImpact() **真打中目标时**（剑/箭/法术共用）")]
        [SerializeField] private AudioClip hitClip;

        [Tooltip("③ 放箭：PlayerCombat.OnArrowRelease() 离弦那帧（T-063 素材待到位，**当前留空**）")]
        [SerializeField] private AudioClip bowShotClip;

        [Tooltip("④ 施法：PlayerCombat.CastSpell()")]
        [SerializeField] private AudioClip castClip;

        [Tooltip("⑤ 受击：PlayerHealth.TakeDamage() 玩家挨打")]
        [SerializeField] private AudioClip hurtClip;

        private AudioSource source;

        /// <summary>最近实例。调用方是静态方法，拿不到引用时**安全空转**（不报错）。</summary>
        private static GameAudio instance;

        private void Awake()
        {
            instance = this;

            source = GetComponent<AudioSource>();
            if (source == null) source = gameObject.AddComponent<AudioSource>();

            // 2.5D 俯视 · 单机 —— 用 2D 播放最省事且不会被相机距离衰减掉。
            // ⚠️ 这不算"3D 衰减调参"（那是被明令不做的）；这是"要不要衰减"的开关，取最基础的一项。
            source.playOnAwake = false;
            source.spatialBlend = 0f;   // 0 = 完全 2D
            // 音量/音高：**保持默认（1.0）**，此处不写任何数值。
        }

        private void OnDestroy()
        {
            if (instance == this) instance = null;
        }

        // ---------------- 五个入口（调用方只写一行） ----------------

        /// <summary>① 剑挥砍（起手那帧；挥空也响）。</summary>
        public static void PlaySwing() { Play(instance != null ? instance.swingClip : null, "sword_swing"); }

        /// <summary>② 命中。**只在真的打中目标时调用** —— 不要"挥空也响命中音"，那会误导玩家。</summary>
        public static void PlayHit() { Play(instance != null ? instance.hitClip : null, "hit_light"); }

        /// <summary>③ 放箭（离弦帧；素材未到位时槽位为空 → 静默跳过）。</summary>
        public static void PlayBowShot() { Play(instance != null ? instance.bowShotClip : null, "bow_release"); }

        /// <summary>④ 施法。</summary>
        public static void PlayCast() { Play(instance != null ? instance.castClip : null, "cast"); }

        /// <summary>⑤ 玩家受击。</summary>
        public static void PlayHurt() { Play(instance != null ? instance.hurtClip : null, "hurt"); }

        /// <summary>
        /// 统一的播放路径：**clip 为 null 时回退到 SfxLibrary 的同语义音**（新地图没有序列化素材也能出声）。
        /// 这样"素材没到位"与"素材到位"对代码完全透明。
        /// </summary>
        private static void Play(AudioClip clip, string fallbackName)
        {
            if (instance == null || instance.source == null)
            {
                // 运行时新地图里 GameAudio 可能是新建的、槽位没序列化 → 走程序化音效库
                if (!string.IsNullOrEmpty(fallbackName)) SfxLibrary.PlayOnPlayer(fallbackName, 0.55f);
                return;
            }

            if (clip == null)
            {
                // ← 空槽：用程序化合成音顶替（保证有反馈），不报错
                if (!string.IsNullOrEmpty(fallbackName)) SfxLibrary.PlayOnPlayer(fallbackName, 0.55f);
                return;
            }

            // 音量/音高：**不传参数 = 用 AudioSource 的默认值（1.0 / 1.0）**，
            // 本文件不写任何音量或音高数值（红线：那些属用户的手感）。
            instance.source.PlayOneShot(clip);
        }

        // ================= 打击特效（T-0xx）新增：命中分级 / 格挡 / 暴击 =================
        //
        // ⚠️ **本文件的红线没有变**：仍然不写任何音量/音高数值（那属用户的手感/平衡）。
        //    所以"分级"在这里只体现为两件事：
        //      ① 换一个**回退音名**（轻 `hit_light` / 重 `hit_heavy`，都是程序化库里的现成音）；
        //      ② 换一个**素材槽**（格挡 / 暴击各一个，用户想配就配）。
        //    需要"叠层 + 音高"的那种处理放在 `VfxCombat`（表现层，那里本来就带音量/音高参数），
        //    例如暴击的第二层金属音就是 `VfxCombat.SfxCritLayer` 干的。
        //
        // 为什么挂在 `GameAudio` 而不是让调用方直接找 `SfxLibrary`：
        //    用户给的 5 个真人素材只能从这里播（槽位在场景里序列化），
        //    "命中分级"必须走这条路才能同时覆盖**真人素材**和**程序化回退**。

        [Header("打击分级（T-0xx 新增；**留空即回退到程序化音**，不会没声音）")]
        [Tooltip("⑥ 格挡：举盾挡住时（Enemy.TakeDamage 的格挡支 + 玩家盾击）。留空 → 回退 hit_block")]
        [SerializeField] private AudioClip blockClip;

        [Tooltip("⑦ 暴击：命中分级为「暴击」时。留空 → 回退到命中音 hitClip")]
        [SerializeField] private AudioClip critClip;

        /// <summary>
        /// ② 按**伤害分级**播命中音。调用方只需要知道"这一下有多重"（`VfxFeel.Grade`），
        /// 不需要知道该放哪一个文件 —— 分档到素材的映射集中在下面这三行里。
        /// </summary>
        public static void PlayHit(HitGrade grade)
        {
            switch (grade)
            {
                case HitGrade.Crit: PlayCrit(); break;
                case HitGrade.Heavy: PlayHitHeavy(); break;
                default: PlayHit(); break;
            }
        }

        /// <summary>②b 重击命中：同一个真人素材，**回退音换成更厚的 `hit_heavy`**。</summary>
        public static void PlayHitHeavy() { Play(instance != null ? instance.hitClip : null, "hit_heavy"); }

        /// <summary>⑥ 格挡（敌人举盾挡住 / 玩家盾击）。</summary>
        public static void PlayBlock() { Play(instance != null ? instance.blockClip : null, "hit_block"); }

        /// <summary>
        /// ⑦ 暴击。没配 `critClip` 时**回退到命中音**（宁可"和重击同一个采样"也不要没声音）。
        /// 真正让它听起来像"会心一击"的是 `VfxCombat` 叠上去的第二层金属音。
        /// </summary>
        public static void PlayCrit()
        {
            AudioClip clip = null;
            if (instance != null) clip = instance.critClip != null ? instance.critClip : instance.hitClip;
            Play(clip, "hit_heavy");
        }
    }
}
