using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 可以被"淡出"的物体：挡住玩家视线时切到半透明材质，不再挡时切回不透明。
    /// 这是 2D 里"深度排序"要解决的问题在 3D 俯视下的等价物——不然墙和树会把玩家整个盖住。
    ///
    /// 材质是延迟创建的：AddComponent 会立刻触发 Awake，而外部 Configure 在其之后才调用，
    /// 所以不能在 Awake 里就把 fadedAlpha 烘进材质。
    /// </summary>
    [DisallowMultipleComponent]
    public class FadeableObject : MonoBehaviour
    {
        private float fadedAlpha = 0.25f;

        private Renderer[] renderers;
        private Material[] opaque;
        private Material[] faded;
        private bool initialized;
        private bool currentlyVisible = true;

        public void Configure(float alpha)
        {
            // 已经初始化过就不再改，避免运行中重建材质。
            if (initialized) return;
            fadedAlpha = Mathf.Clamp01(alpha);
        }

        private void EnsureInit()
        {
            if (initialized) return;
            initialized = true;

            renderers = GetComponentsInChildren<Renderer>(true);
            opaque = new Material[renderers.Length];
            faded = new Material[renderers.Length];

            for (int i = 0; i < renderers.Length; i++)
            {
                // 用 sharedMaterial 读原始材质；每个世界物体都是独立材质实例，交换不会串味。
                opaque[i] = renderers[i].sharedMaterial;
                faded[i] = opaque[i] != null
                    ? PlaceholderArt.NewTransparentVariant(opaque[i], fadedAlpha)
                    : null;
            }

            // 初始就是要求的"可见"状态，第一帧不必再交换一次材质。
            Apply(true);
        }

        /// <summary>每帧由相机调用：visible=false 时淡出。</summary>
        public void SetVisible(bool visible)
        {
            EnsureInit();
            if (visible == currentlyVisible) return;
            Apply(visible);
        }

        private void Apply(bool visible)
        {
            currentlyVisible = visible;
            for (int i = 0; i < renderers.Length; i++)
            {
                if (renderers[i] == null) continue;
                var target = visible ? opaque[i] : faded[i];
                if (target != null) renderers[i].sharedMaterial = target;
            }
        }

        private void OnDestroy()
        {
            // 运行时生成的材质没有别的引用，随物体一起销毁，避免泄漏。
            if (faded == null) return;
            for (int i = 0; i < faded.Length; i++)
                if (faded[i] != null) Destroy(faded[i]);
        }
    }
}
