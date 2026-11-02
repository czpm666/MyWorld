using System;
using System.Collections.Generic;
using UnityEngine;

namespace MyWorld
{
    public enum VfxAmbientKind
    {
        Lamp,        // 路灯 / 火把 / 灯笼
        Campfire,    // 篝火
        Fountain,    // 喷泉
        RuneCircle,  // 魔法阵（地面符文环）
        Portal,      // 传送门
    }

    /// <summary>
    /// **环境粒子的自动挂载点**：VfxAmbient.ScanScene() 在场景加载后按物体名匹配（lamp/campfire/fountain/
    /// magiccircle/portal...），给命中的物体挂上本组件。所有对象都是运行时生成/查找，**不依赖旧场景序列化引用**，
    /// 新地图只要按约定命名就会自动生效；找不到也不报错（旧工程本身就几乎没有这些道具）。
    ///
    /// 性能：每个点每 0.1~0.9 秒才发 1~2 个粒子，走 VfxHub 的共享粒子池；灯光上限 8 盏，防止满屏实时灯。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VfxAmbientPoint : MonoBehaviour
    {
        public VfxAmbientKind kind;

        float emitTimer;
        float lightTimer;
        float phase;
        float flickerSeed;
        Light lamp;
        float baseIntensity;
        LineRenderer runeRing;
        AudioSource loopSource;
        bool started;

        public void Setup(VfxAmbientKind k)
        {
            kind = k;
            phase = UnityEngine.Random.value * 10f;
            flickerSeed = UnityEngine.Random.value * 50f;
            AddLightIfBudget();
            if (kind == VfxAmbientKind.RuneCircle) BuildRuneRing();
            if (kind == VfxAmbientKind.Portal || kind == VfxAmbientKind.RuneCircle) AddLoopAmbience();
            started = true;
        }

        void AddLightIfBudget()
        {
            if (VfxAmbient.ReserveLight() == false) return;

            baseIntensity = kind == VfxAmbientKind.Campfire ? 1.7f : 1.1f;
            Color c = kind == VfxAmbientKind.Campfire
                ? new Color(1f, 0.62f, 0.28f)
                : (kind == VfxAmbientKind.Portal
                    ? new Color(0.62f, 0.5f, 1f)
                    : new Color(1f, 0.8f, 0.5f));
            float range = kind == VfxAmbientKind.Campfire ? 6.5f : 4.5f;

            var go = new GameObject("VfxLight");
            go.transform.SetParent(transform, false);
            lamp = go.AddComponent<Light>();
            lamp.type = LightType.Point;
            lamp.color = c;
            lamp.range = range;
            lamp.intensity = baseIntensity;
            lamp.shadows = LightShadows.None;
            lamp.renderMode = LightRenderMode.ForceVertex;
        }

        void BuildRuneRing()
        {
            var go = new GameObject("VfxRuneRing");
            go.transform.SetParent(transform, false);
            go.transform.localPosition = new Vector3(0f, 0.04f, 0f);

            var lr = go.AddComponent<LineRenderer>();
            lr.useWorldSpace = false;
            lr.loop = true;
            lr.material = PlaceholderArt.GetVertexColorMaterial();
            lr.numCapVertices = 0;
            lr.textureMode = LineTextureMode.Stretch;
            lr.alignment = LineAlignment.TransformZ;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            lr.sortingOrder = 30;

            const int seg = 48;
            lr.positionCount = seg;
            float radius = kind == VfxAmbientKind.Portal ? 0.9f : 1.15f;
            for (int i = 0; i < seg; i++)
            {
                float a = i / (float)seg * Mathf.PI * 2f;
                lr.SetPosition(i, new Vector3(Mathf.Cos(a) * radius, 0f, Mathf.Sin(a) * radius));
            }
            Color c = kind == VfxAmbientKind.Portal
                ? new Color(0.7f, 0.5f, 1f, 0.75f)
                : new Color(0.62f, 0.45f, 1f, 0.55f);
            lr.startColor = c;
            lr.endColor = c;
            lr.widthMultiplier = 0.035f;
            runeRing = lr;
        }

        void AddLoopAmbience()
        {
            if (!VfxAmbient.ReserveLoop()) return;

            loopSource = gameObject.AddComponent<AudioSource>();
            loopSource.playOnAwake = false;
            loopSource.loop = true;
            loopSource.spatialBlend = 1f;
            loopSource.rolloffMode = AudioRolloffMode.Linear;
            loopSource.minDistance = 3f;
            loopSource.maxDistance = 16f;
            loopSource.dopplerLevel = 0f;
            loopSource.volume = kind == VfxAmbientKind.Portal ? 0.22f : 0.12f;
            loopSource.clip = SfxLibrary.LoadClip(kind == VfxAmbientKind.Portal ? "portal" : "magic_hum");
            if (loopSource.clip != null) loopSource.Play();
        }

        void Update()
        {
            if (!started || VfxHub.Instance == null) return;

            emitTimer -= Time.deltaTime;
            lightTimer -= Time.deltaTime;
            if (emitTimer > 0f) return;
            emitTimer = 0.10f;

            switch (kind)
            {
                case VfxAmbientKind.Lamp: TickLamp(); break;
                case VfxAmbientKind.Campfire: TickCampfire(); break;
                case VfxAmbientKind.Fountain: TickFountain(); break;
                case VfxAmbientKind.RuneCircle: TickRuneCircle(); break;
                case VfxAmbientKind.Portal: TickPortal(); break;
            }
        }

        void TickLamp()
        {
            VfxHub hub = VfxHub.Instance;
            Color warm = new Color(1f, 0.78f, 0.45f, 0.55f);
            if (UnityEngine.Random.value < 0.55f)
            {
                hub.Burst(hub.Glow, transform.position + Vector3.up * 0.25f, Vector3.up, 1,
                    0.05f, 0.2f, 40f, warm, 0.06f, 0.12f, 0.5f, 0.9f, 0.15f, 0.12f);
            }
            if (lamp != null)
            {
                float flicker = 0.9f + 0.12f * Mathf.Sin(Time.time * 7.3f + flickerSeed)
                    + 0.05f * Mathf.Sin(Time.time * 17.1f + flickerSeed * 2f);
                lamp.intensity = baseIntensity * flicker;
            }
        }

        void TickCampfire()
        {
            VfxHub hub = VfxHub.Instance;
            // 火星：向上飞、受重力下落（Spark 池带 +0.65 重力）
            hub.Burst(hub.Spark, transform.position + Vector3.up * 0.25f, Vector3.up,
                UnityEngine.Random.value < 0.5f ? 1 : 2, 1.2f, 2.6f, 30f,
                new Color(1f, 0.62f, 0.18f, 0.9f), 0.035f, 0.08f, 0.5f, 1.0f, 0.3f, 0.15f);
            if (UnityEngine.Random.value < 0.16f)
            {
                hub.Burst(hub.Smoke, transform.position + Vector3.up * 0.6f, Vector3.up, 1,
                    0.2f, 0.6f, 40f, new Color(0.45f, 0.44f, 0.42f, 0.35f),
                    0.25f, 0.45f, 0.9f, 1.6f, 0.5f, 0.2f);
            }
            if (lamp != null && lightTimer <= 0f)
            {
                lightTimer = 0.06f;
                float flicker = 0.82f + 0.18f * Mathf.Sin(Time.time * 11.4f + flickerSeed)
                    + 0.08f * Mathf.Sin(Time.time * 23.7f + flickerSeed * 3f);
                lamp.intensity = baseIntensity * Mathf.Max(0.55f, flicker);
            }
        }

        void TickFountain()
        {
            VfxHub hub = VfxHub.Instance;
            // 水滴：用 Spark 池（有重力，会自然下落成弧线）
            Vector3 origin = transform.position + Vector3.up * 0.55f;
            Vector3 side = UnityEngine.Random.insideUnitSphere;
            side.y = 0f;
            hub.Burst(hub.Spark, origin, Vector3.up, 1, 1.4f, 2.2f, 18f,
                new Color(0.72f, 0.86f, 1f, 0.7f), 0.03f, 0.06f, 0.5f, 0.8f, 0.9f, 0.03f);
            if (UnityEngine.Random.value < 0.22f)
            {
                hub.Burst(hub.Dust, origin + Vector3.up * 0.1f, Vector3.up, 1,
                    0.1f, 0.4f, 40f, new Color(0.8f, 0.9f, 1f, 0.25f),
                    0.10f, 0.18f, 0.4f, 0.8f, 0.2f, 0.1f);
            }
        }

        void TickRuneCircle()
        {
            VfxHub hub = VfxHub.Instance;
            if (runeRing != null)
            {
                Transform t = runeRing.transform;
                t.Rotate(0f, 8f * Time.deltaTime, 0f, Space.Self);
                float pulse = 0.45f + 0.25f * Mathf.Sin(Time.time * 1.5f + phase);
                Color c = kind == VfxAmbientKind.Portal
                    ? new Color(0.7f, 0.5f, 1f, pulse)
                    : new Color(0.62f, 0.45f, 1f, pulse);
                runeRing.startColor = c;
                runeRing.endColor = c;
            }
            if (UnityEngine.Random.value < 0.12f)
            {
                hub.Burst(hub.Glow, transform.position + Vector3.up * 0.35f, Vector3.up, 1,
                    0.3f, 1.0f, 60f, new Color(0.75f, 0.6f, 1f, 0.7f),
                    0.05f, 0.11f, 0.6f, 1.1f, 0.8f, 0.25f);
            }
        }

        void TickPortal()
        {
            VfxHub hub = VfxHub.Instance;
            Vector3 center = transform.position + Vector3.up * 1.0f;
            if (UnityEngine.Random.value < 0.35f)
            {
                hub.Burst(hub.Glow, center, Vector3.up, 1, 0.3f, 1.2f, 70f,
                    new Color(0.7f, 0.55f, 1f, 0.65f), 0.08f, 0.18f, 0.7f, 1.3f, 1.0f, 0.3f);
            }
            if (runeRing != null)
            {
                runeRing.transform.Rotate(0f, 20f * Time.deltaTime, 0f, Space.Self);
            }
        }
    }

    /// <summary>环境粒子自动扫描器（由 VfxDirector 在每张地图加载后调用）。</summary>
    public static class VfxAmbient
    {
        static int lightsThisScan;
        static int loopsThisScan;
        const int MaxLightsPerScan = 8;
        const int MaxLoopsPerScan = 3;
        static readonly List<Transform> candidates = new List<Transform>(64);

        public static bool ReserveLight()
        {
            if (lightsThisScan >= MaxLightsPerScan) return false;
            lightsThisScan++;
            return true;
        }

        public static bool ReserveLoop()
        {
            if (loopsThisScan >= MaxLoopsPerScan) return false;
            loopsThisScan++;
            return true;
        }

        /// <summary>扫描当前场景并给命名的道具挂上环境特效。返回新增数量。</summary>
        public static int ScanScene()
        {
            if (!Application.isPlaying) return 0;

            lightsThisScan = 0;
            loopsThisScan = 0;
            candidates.Clear();

            Transform[] all = UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsSortMode.None);
            for (int i = 0; i < all.Length; i++)
            {
                Transform t = all[i];
                if (t == null) continue;
                if (t.GetComponent<VfxAmbientPoint>() != null) continue;
                if (KindFromName(t.name) == null) continue;
                if (t.GetComponentInParent<VfxAmbientPoint>() != null) continue;
                candidates.Add(t);
            }

            // 由浅到深挂载：父物体先挂，子物体自然被 GetComponentInParent 过滤掉
            candidates.Sort((a, b) => Depth(a).CompareTo(Depth(b)));

            int added = 0;
            for (int i = 0; i < candidates.Count && added < 80; i++)
            {
                Transform t = candidates[i];
                if (t == null || t.GetComponentInParent<VfxAmbientPoint>() != null) continue;

                VfxAmbientKind? kind = KindFromName(t.name);
                if (kind == null) continue;

                var point = t.gameObject.AddComponent<VfxAmbientPoint>();
                point.Setup(kind.Value);
                added++;
            }
            return added;
        }

        static int Depth(Transform t)
        {
            int d = 0;
            while (t.parent != null && d < 32)
            {
                d++;
                t = t.parent;
            }
            return d;
        }

        static VfxAmbientKind? KindFromName(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            string n = name.ToLowerInvariant();

            if (n.Contains("campfire") || n.Contains("bonfire") || n.Contains("firepit") || n.Contains("fire_pit"))
                return VfxAmbientKind.Campfire;
            if (n.Contains("fountain") || n.Contains("waterjet") || n.Contains("water_jet"))
                return VfxAmbientKind.Fountain;
            if (n.Contains("magiccircle") || n.Contains("magic_circle") || n.Contains("magic circle")
                || n.Contains("runecircle") || n.Contains("rune_circle") || n.Contains("runiccircle")
                || n.Contains("summoncircle") || n.Contains("teleportcircle"))
                return VfxAmbientKind.RuneCircle;
            if (n.Contains("portal") || n.Contains("gateway") || n.Contains("warpgate"))
                return VfxAmbientKind.Portal;
            if (n.Contains("lamp") || n.Contains("lantern") || n.Contains("torch")
                || n.Contains("brazier") || n.Contains("streetlight") || n.Contains("street_light")
                || n.Contains("candle"))
                return VfxAmbientKind.Lamp;

            return null;
        }

        /// <summary>治疗事件（供治疗点/泉水调用）。</summary>
        public static void Heal(Vector3 position)
        {
            VfxCombat.PlayerHeal(position);
        }

        /// <summary>传送门事件（供传送门调用）。</summary>
        public static void Portal(Vector3 position)
        {
            VfxCombat.PortalAt(position);
        }
    }
}
