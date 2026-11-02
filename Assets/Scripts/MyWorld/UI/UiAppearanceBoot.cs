using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld.UI
{
    /// <summary>
    /// 外观切换的运行时守护（T-092：装备页「法师 / 骑士 / 游侠」按钮的落地端）。
    ///
    /// 只做两件事，**不修改 PlayerAppearance 的代码**：
    ///   1. 场景加载后把存档里的外观（<see cref="GameSession.Appearance"/>）套到新玩家身上 ——
    ///      PlayerAppearance 只在自己 Start() 里读序列化字段，新场景的玩家一定是法师，
    ///      所以必须由这边补一次。玩家可能比场景晚一帧生成，找不到就下一帧再试。
    ///   2. 给 `PlayerAppearance.Apply(0)` 补兜底：它取 0 号材质时 `MaterialFor` 返回 null 直接 return，
    ///      **材质不还原、但 look 已经被写回 0**。所以这里在第一次切到非法师外观前缓存原
    ///      `sharedMaterial`，选回法师时自己还原（幂等：动画线若也补了还原，两边不冲突）。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class UiAppearanceBoot : MonoBehaviour
    {
        /// <summary>玩家还没生成时的重试帧数上限。</summary>
        private const int RetryFrames = 8;

        private static UiAppearanceBoot instance;

        /// <summary>原材质缓存：只在第一次切到非法师外观前抓一次。</summary>
        private readonly Dictionary<Renderer, Material> originals = new Dictionary<Renderer, Material>();

        /// <summary>缓存对应的玩家；换场景换了玩家就清空重抓。</summary>
        private PlayerAppearance bound;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Boot()
        {
            var boot = Ensure();
            boot.StartCoroutine(boot.ApplyWhenPlayerReady());   // 首个场景不触发 sceneLoaded
        }

        private static UiAppearanceBoot Ensure()
        {
            if (instance != null) return instance;
            var go = new GameObject("UiAppearanceBoot");
            DontDestroyOnLoad(go);
            instance = go.AddComponent<UiAppearanceBoot>();
            SceneManager.sceneLoaded += instance.OnSceneLoaded;
            return instance;
        }

        private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            if (!isActiveAndEnabled) return;   // 关掉 domain reload 时旧实例可能已被销毁
            StartCoroutine(ApplyWhenPlayerReady());
        }

        /// <summary>UI 点按钮后调它：立刻把当前存档外观套上（找不到玩家就交给重试）。</summary>
        public static void ApplySaved()
        {
            var boot = Ensure();
            if (boot.ApplyNow()) return;
            boot.StartCoroutine(boot.ApplyWhenPlayerReady());
        }

        private IEnumerator ApplyWhenPlayerReady()
        {
            for (int i = 0; i <= RetryFrames; i++)
            {
                if (ApplyNow()) yield break;
                yield return null;   // 等下一帧：玩家 / 骨骼可能还在生成
            }
        }

        private bool ApplyNow()
        {
            var pa = FindFirstObjectByType<PlayerAppearance>();
            if (pa == null) return false;
            ApplyLook(pa, GameSession.Appearance);
            return true;
        }

        private void ApplyLook(PlayerAppearance pa, int index)
        {
            if (pa != bound) { bound = pa; originals.Clear(); }   // 换玩家就重抓原材质
            if (originals.Count == 0) CaptureOriginal(pa);
            pa.Apply(index);
            if (index <= PlayerAppearance.LookMage) RestoreOriginal();
        }

        /// <summary>缓存「法师原材质」。过滤规则与 PlayerAppearance.Apply 保持一致。</summary>
        private void CaptureOriginal(PlayerAppearance pa)
        {
            var animator = pa.GetComponentInChildren<Animator>();
            if (animator == null) return;
            var renderers = animator.GetComponentsInChildren<Renderer>(true);
            for (int i = 0; i < renderers.Length; i++)
            {
                var r = renderers[i];
                if (r == null) continue;
                // 只换"有贴图的蒙皮/网格"，粒子、线框、标记一律跳过（与 Apply 同规则）
                if (r is ParticleSystemRenderer || r is LineRenderer || r is TrailRenderer) continue;
                if (r.sharedMaterial == null) continue;
                originals[r] = r.sharedMaterial;
            }
        }

        private void RestoreOriginal()
        {
            foreach (var pair in originals)
                if (pair.Key != null) pair.Key.sharedMaterial = pair.Value;
        }
    }
}
