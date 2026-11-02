using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// T-091：玩家外观切换（**只换材质贴图，不换模型、不动骨骼**）。
    ///
    /// 背景：用户反馈「人物模型太少了」。实测 `Assets/ThirdParty/KayKit_Adventurers/` 里
    /// `knight_texture.png` / `rogue_texture.png` **一直存在但零引用** —— 它们和 `mage_texture.png`
    /// 是同一套 1024×1024 UV 布局（未占用区掩码一致度 99.5%，同机位渲染三个人形完整不拉伸），
    /// 所以「更丰富的人物外观」不需要新模型、不需要重定向，换贴图就够。
    ///
    /// 材质资产由 `Tools > My World/生成外观材质（骑士 · 游侠）` 生成到
    /// `Assets/Scripts/MyWorld/Animation/Resources/Appearance/`，本类用 `Resources.Load` 取。
    ///
    /// ⚠️ **本类不写任何动画参数**，只碰 Renderer 的 `sharedMaterial`；
    ///    也**不接 UI 入口**（UI 不在动画负责人的写入范围，入口由 Lead 统一安排）。
    ///    将来 UI 只要调 <see cref="Apply"/> 即可。
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerAppearance : MonoBehaviour
    {
        /// <summary>外观序号 —— **必须与 `AppearanceSetup.Variants` 的顺序对齐**。</summary>
        public const int LookMage = 0;
        public const int LookKnight = 1;
        public const int LookRogue = 2;

        /// <summary>外观名（给 UI 显示用）。下标 = 上面的常量。</summary>
        public static readonly string[] LookNames = { "法师", "骑士", "游侠" };

        private const string ResourceDir = "Appearance/";
        /// <summary>变体材质名（不含目录）—— 与 `AppearanceSetup.Variants` 逐字一致。</summary>
        private static readonly string[] VariantNames = { "M_Knight", "M_Rogue" };

        private static Material[] _variants;

        [SerializeField] private int look = LookMage;

        /// <summary>第一次换外观前缓存下来的「哪些 Renderer、原本是什么材质」，用于切回法师时还原。</summary>
        private readonly System.Collections.Generic.List<Renderer> _swapped = new();
        private readonly System.Collections.Generic.List<Material> _originals = new();

        /// <summary>当前外观序号。</summary>
        public int Look => look;

        private void Start()
        {
            // 场景里序列化过的 look 不是 0 就套用；是 0 时什么都不做（保持预制体原材质）。
            if (look != LookMage) Apply(look);
        }

        /// <summary>
        /// 切换外观。0 = 法师（恢复原始材质），1 = 骑士，2 = 游侠。
        /// 取不到变体材质时**静默保持原样**（不报错、不换空气材质）。
        /// </summary>
        public void Apply(int index)
        {
            var animator = GetComponentInChildren<Animator>();
            if (animator == null) return;

            int want = Mathf.Clamp(index, LookMage, LookNames.Length - 1);

            // 切回法师：还原第一次换外观前缓存的原始材质。
            // ⚠️ 这里以前是「MaterialFor(0) 返回 null → 直接 return」，结果「法师→骑士→法师」
            //    只把 look 写回 0、画面仍停在骑士材质上，状态和画面不一致。
            if (want == LookMage)
            {
                RestoreOriginals();
                look = LookMage;
                return;
            }

            var skin = MaterialFor(want);
            if (skin == null) return;   // 变体没生成：**不写 look**，免得又要出现状态与画面不一致

            var renderers = animator.GetComponentsInChildren<Renderer>(true);
            CaptureOriginals(renderers);   // 只在第一次换外观前抓一次
            for (int i = 0; i < renderers.Length; i++)
            {
                var r = renderers[i];
                if (!CanSkin(r)) continue;
                r.sharedMaterial = skin;
            }

            look = want;   // 成功套用后才改状态
        }

        /// <summary>哪些 Renderer 允许换材质：跳过粒子/线框/拖尾和没有材质的。</summary>
        private static bool CanSkin(Renderer r)
        {
            if (r == null) return false;
            if (r is ParticleSystemRenderer || r is LineRenderer || r is TrailRenderer) return false;
            return r.sharedMaterial != null;
        }

        /// <summary>
        /// 记录「这次准备替换的 Renderer 及其原材质」。只在第一次换外观前抓，
        /// 之后一直复用这份清单，保证还原时不多不少正好是当初被替换的那批。
        /// </summary>
        private void CaptureOriginals(Renderer[] renderers)
        {
            if (_swapped.Count > 0) return;   // 已经抓过，别覆盖成变体材质

            for (int i = 0; i < renderers.Length; i++)
            {
                var r = renderers[i];
                if (!CanSkin(r)) continue;
                _swapped.Add(r);
                _originals.Add(r.sharedMaterial);
            }
        }

        /// <summary>把当初被换掉的材质原样贴回去。没换过外观时是空操作。</summary>
        private void RestoreOriginals()
        {
            for (int i = 0; i < _swapped.Count; i++)
            {
                var r = _swapped[i];
                if (r == null) continue;   // 被销毁的忽略
                r.sharedMaterial = _originals[i];
            }
        }

        private static Material MaterialFor(int index)
        {
            if (index <= LookMage) return null;
            int slot = index - 1;
            if (slot < 0 || slot >= VariantNames.Length) return null;

            if (_variants == null) _variants = new Material[VariantNames.Length];
            if (_variants[slot] == null)
            {
                _variants[slot] = Resources.Load<Material>(ResourceDir + VariantNames[slot]);
                if (_variants[slot] == null)
                {
                    Debug.LogWarning("[外观] 没找到 Resources/" + ResourceDir + VariantNames[slot]
                                     + "，先跑 Tools > My World/生成外观材质（骑士 · 游侠）。");
                }
            }
            return _variants[slot];
        }
    }
}
