using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld
{
    /// <summary>
    /// **粒子池**：一个场景里常驻若干组 ParticleSystem，全部参数在运行时用 C# 配置（不依赖 prefab / 场景序列化）。
    ///
    /// 池化做法：`emission` 永久关闭，只通过 `EmitParams` 手动发射；粒子自然死亡后槽位自动复用，
    /// 所以密集战斗里 GameObject 数量恒定（不会每帧 Instantiate/Destroy → 无每帧 GC）。
    /// 颜色/大小/寿命都走 EmitParams，因此**同一个池能同时画不同颜色的火花**。
    /// </summary>
    public sealed class VfxPool
    {
        public readonly string Name;
        public readonly ParticleSystem Ps;
        readonly ParticleSystemRenderer renderer;
        ParticleSystem.EmitParams emit = new ParticleSystem.EmitParams();

        public int Active
        {
            get { return Ps != null ? Ps.particleCount : 0; }
        }

        public VfxPool(string name, Transform parent, Texture2D texture, bool additive, int maxParticles,
            float gravity, float damping, bool stretch, float lengthScale = 1.0f)
        {
            Name = name;

            var go = new GameObject("Pool_" + name);
            go.transform.SetParent(parent, false);

            Ps = go.AddComponent<ParticleSystem>();
            // AddComponent 会让系统立刻自播；此时改 duration 会报
            // "Setting the duration while system is still playing is not supported"。
            // 先彻底停掉（清空），再配各模块，最后靠 Emit() 手动发射。
            Ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // ---- 主模块：世界空间 + 手动发射 ----
            var main = Ps.main;
            main.duration = 1f;
            main.loop = true;
            main.prewarm = false;
            main.playOnAwake = false;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startLifetime = 0.4f;
            main.startSpeed = 0f;
            main.startSize = 0.1f;
            main.startColor = Color.white;
            main.maxParticles = Mathf.Max(16, maxParticles);
            main.gravityModifier = gravity;
            main.scalingMode = ParticleSystemScalingMode.Hierarchy;
            main.useUnscaledTime = false;

            var emission = Ps.emission;
            emission.enabled = false;          // 完全靠 Emit() 发射

            var shape = Ps.shape;
            shape.enabled = false;

            // ---- 全池统一的淡出曲线（颜色由 EmitParams.startColor 决定，这里只乘 alpha） ----
            var col = Ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(
                new[]
                {
                    new GradientColorKey(Color.white, 0f),
                    new GradientColorKey(Color.white, 1f),
                },
                new[]
                {
                    new GradientAlphaKey(1f, 0f),
                    new GradientAlphaKey(0.9f, 0.25f),
                    new GradientAlphaKey(0.45f, 0.65f),
                    new GradientAlphaKey(0f, 1f),
                });
            col.color = new ParticleSystem.MinMaxGradient(grad);

            // ---- 阻尼：让火花飞出去后快速减速（limitVelocityOverLifetime.dampen） ----
            if (damping > 0.0001f)
            {
                var limit = Ps.limitVelocityOverLifetime;
                limit.enabled = true;
                limit.dampen = Mathf.Clamp01(damping);
                limit.limit = 0f;
                limit.multiplyDragByParticleSize = false;
                limit.multiplyDragByParticleVelocity = false;
            }

            // ---- 渲染：默认 view billboard；火花用 stretch ----
            renderer = go.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = stretch ? ParticleSystemRenderMode.Stretch : ParticleSystemRenderMode.Billboard;
            if (stretch)
            {
                renderer.velocityScale = 0.055f;
                renderer.lengthScale = Mathf.Max(0.2f, lengthScale);
            }
            renderer.material = VfxMaterials.GetParticleMaterial(texture, additive);
            renderer.sortingOrder = 30;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
            renderer.alignment = ParticleSystemRenderSpace.View;

            // 先 Play 起来（没有 emission，不会有粒子），后续手动 Emit
            Ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            Ps.Play();
        }

        /// <summary>发一个粒子。</summary>
        public void Emit(Vector3 position, Vector3 velocity, Color color, float size, float lifetime)
        {
            if (Ps == null) return;
            if (lifetime <= 0f) lifetime = 0.1f;
            if (size <= 0f) size = 0.01f;

            emit.position = position;
            emit.velocity = velocity;
            emit.startColor = color;
            emit.startSize = size;
            emit.startLifetime = lifetime;
            emit.rotation = Random.Range(0f, Mathf.PI * 2f);
            Ps.Emit(emit, 1);
        }

        public void Clear()
        {
            if (Ps != null) Ps.Clear();
        }
    }
}
