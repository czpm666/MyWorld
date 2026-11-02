using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// **抓钩表现增强**：给抓钩对象挂一个装饰组件（由 VfxDirector / VfxCombat 自动挂，不修改 GrappleWeapon）。
    ///
    /// 做的事：
    ///   * 钩头飞行时喷风线/火花（辨识度）
    ///   * 钩爪咬住的瞬间播金属命中特效（GrappleHit）
    ///   * 绳索叠一层"金色能量光"（第二根 LineRenderer 跟随原绳点位，宽度更粗、加色）
    ///   * 拉拽自己的过程中脚下扬尘（GrapplePull）
    /// 全部走 VfxHub 的共享池，零 Instantiate。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxGrappleDecorator : MonoBehaviour
    {
        LineRenderer rope;
        LineRenderer glowRope;
        Transform hook;

        Vector3 lastHookPos;
        Vector3 lastKnownHookPos;
        float hookSparkTimer;
        float pullDustTimer;
        float lastHookSpeed;
        bool hookWasActive;
        bool resolved;

        void Start()
        {
            Resolve();
        }

        void Resolve()
        {
            if (resolved) return;
            resolved = true;

            LineRenderer[] lines = GetComponentsInChildren<LineRenderer>(true);
            for (int i = 0; i < lines.Length; i++)
            {
                if (lines[i] != null && lines[i].gameObject.name == "GrappleRope")
                {
                    rope = lines[i];
                    break;
                }
            }
            if (rope == null && lines.Length > 0) rope = lines[0];

            Transform[] all = GetComponentsInChildren<Transform>(true);
            for (int i = 0; i < all.Length; i++)
            {
                if (all[i] != null && all[i].name == "HookHead")
                {
                    hook = all[i];
                    break;
                }
            }

            if (rope != null && glowRope == null)
            {
                var go = new GameObject("VfxRopeGlow");
                go.transform.SetParent(rope.transform, false);

                glowRope = go.AddComponent<LineRenderer>();
                glowRope.useWorldSpace = true;
                glowRope.positionCount = 0;
                glowRope.material = PlaceholderArt.GetVertexColorMaterial();
                glowRope.numCapVertices = 2;
                glowRope.textureMode = LineTextureMode.Stretch;
                glowRope.alignment = LineAlignment.View;
                glowRope.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                glowRope.receiveShadows = false;
                glowRope.sortingOrder = 29;
                glowRope.widthMultiplier = 0.14f;
            }
        }

        void Update()
        {
            if (VfxHub.Instance == null) return;
            if (!resolved) Resolve();
            if (rope == null) return;

            float dt = Mathf.Max(0.0001f, Time.deltaTime);
            VfxHub hub = VfxHub.Instance;

            // ---- 钩头飞行 / 命中 ----
            if (hook != null)
            {
                bool active = hook.gameObject.activeInHierarchy;
                Vector3 hp = hook.position;

                if (active)
                {
                    if (!hookWasActive) lastHookPos = hp;

                    Vector3 vel = (hp - lastHookPos) / dt;
                    float speed = vel.magnitude;
                    lastHookPos = hp;

                    hookSparkTimer -= dt;
                    if (speed > 1.5f && hookSparkTimer <= 0f)
                    {
                        hookSparkTimer = 0.025f;
                        hub.Burst(hub.Streak, hp, vel, 1, 1.5f, 3.0f, 25f,
                            new Color(1f, 0.85f, 0.55f, 0.55f), 0.03f, 0.06f, 0.08f, 0.16f, 0f, 0.03f);
                    }

                    // 从"在飞"变成"停住" = 咬住
                    if (lastHookSpeed > 2.5f && speed < 0.35f)
                    {
                        VfxCombat.GrappleHit(hp, Vector3.up);
                    }
                    lastHookSpeed = speed;
                }
                else if (hookWasActive)
                {
                    VfxCombat.GrappleRelease(lastKnownHookPos);
                    lastHookSpeed = 0f;
                }

                lastKnownHookPos = hp;
                hookWasActive = active;
            }

            // ---- 绳索能量光 ----
            if (glowRope != null)
            {
                int count = rope.positionCount;
                if (count >= 2)
                {
                    glowRope.positionCount = count;
                    for (int i = 0; i < count; i++)
                    {
                        glowRope.SetPosition(i, rope.GetPosition(i));
                    }
                    float pulse = 0.55f + 0.25f * Mathf.Sin(Time.unscaledTime * 9f);
                    glowRope.startColor = new Color(1f, 0.88f, 0.45f, 0.28f * pulse);
                    glowRope.endColor = new Color(1f, 0.72f, 0.25f, 0.10f);
                    glowRope.widthMultiplier = Mathf.Max(0.06f, rope.widthMultiplier * 2.4f);
                }
                else
                {
                    glowRope.positionCount = 0;
                }
            }

            // ---- 拉拽扬尘 ----
            if (hook != null && hook.gameObject.activeInHierarchy)
            {
                pullDustTimer -= dt;
                if (pullDustTimer <= 0f)
                {
                    pullDustTimer = 0.14f;
                    Transform player = SfxLibrary.LocalPlayer();
                    if (player != null)
                    {
                        VfxCombat.GrapplePull(player.position);
                    }
                }
            }
        }
    }
}
