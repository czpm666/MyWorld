using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 法师的奥术弹：从施法点沿角色朝向飞出，命中可伤害目标就结算伤害并炸开。
    /// 外形用图元 + Unlit 自发光 + 拖尾 + 点光拼出来，不依赖任何美术资源。
    /// </summary>
    [DisallowMultipleComponent]
    public class SpellProjectile : MonoBehaviour
    {
        [Header("弹道")]
        [SerializeField] private float speed = 24f;
        [SerializeField] private float lifeTime = 2.5f;
        [SerializeField] private float damage = 24f;

        private Vector3 dir;
        private Transform owner;
        private float life;
        private TrailRenderer trail;

        // 飞行中撒下的紫青光斑（每 0.045s 一颗，走共享粒子池）
        private float sparkTimer;
        private static readonly Color MagicTrailColor = new Color(0.55f, 0.85f, 1f);

        /// <summary>damage &lt;= 0 时用预制体上的默认值（护手会把伤害压低，所以允许外部指定）。</summary>
        public static SpellProjectile Spawn(Vector3 position, Vector3 direction, Transform owner, float damage = -1f)
        {
            var go = new GameObject("SpellOrb");
            go.transform.position = position;

            var p = go.AddComponent<SpellProjectile>();
            p.dir = direction.sqrMagnitude > 0.0001f ? direction.normalized : Vector3.forward;
            p.owner = owner;
            if (damage > 0f) p.damage = damage;
            p.Build();
            return p;
        }

        private void Build()
        {
            // 弹体：一个小球；碰撞用脚本里的射线，不需要物理刚体。
            var core = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            core.name = "Core";
            core.transform.SetParent(transform, false);
            core.transform.localScale = Vector3.one * 0.34f;
            PlaceholderArt.StripCollider(core);   // 命中判定走脚本射线，不需要碰撞体
            var r = core.GetComponent<Renderer>();
            if (r != null) r.sharedMaterial = PlaceholderArt.GetGlowMaterial();

            // 拖尾：让高速飞行的弹体有轨迹（比原来更宽更久，是"法术"的辨识度）
            trail = gameObject.AddComponent<TrailRenderer>();
            trail.time = 0.30f;
            trail.startWidth = 0.42f;
            trail.endWidth = 0f;
            trail.minVertexDistance = 0.05f;
            trail.material = PlaceholderArt.GetGlowMaterial();
            trail.startColor = new Color(0.62f, 0.88f, 1f, 0.95f);
            trail.endColor = new Color(0.45f, 0.35f, 1f, 0f);
            trail.sortingOrder = 30;

            // 点光：让弹体真的照亮地面，是"法术"感的关键
            var lightGo = new GameObject("Glow");
            lightGo.transform.SetParent(transform, false);
            var l = lightGo.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = new Color(0.6f, 0.85f, 1f);
            l.range = 6f;
            l.intensity = 3.5f;

            // 弹体外层光晕：比核心大一圈，颜色偏紫（法杖辨识度）
            var halo = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            halo.name = "Halo";
            halo.transform.SetParent(transform, false);
            halo.transform.localScale = Vector3.one * 0.62f;
            PlaceholderArt.StripCollider(halo);
            var haloRenderer = halo.GetComponent<Renderer>();
            if (haloRenderer != null)
                haloRenderer.sharedMaterial = PlaceholderArt.GetGlowMaterial(new Color(0.62f, 0.45f, 1f, 0.35f));

            // 出生：紫青符文环 + 光斑（法杖施法辨识度，走 VfxCombat 语义层）
            VfxCombat.CastFormation(transform.position, dir, MagicTrailColor);

            // 出生时也来一小圈爆花，避免"凭空出现"
            ArcaneBurst.Spawn(transform.position, dir, 0.5f);
        }

        private void Update()
        {
            float dt = Time.deltaTime;
            life += dt;
            if (life > lifeTime)
            {
                Explode(transform.position, -dir, hitSomething: false);
                return;
            }

            Vector3 step = dir * (speed * dt);
            float dist = step.magnitude;

            // 飞行时持续撒紫青光斑（有"彗尾"感；走共享池，无 Instantiate）
            sparkTimer -= dt;
            if (sparkTimer <= 0f && VfxHub.Instance != null)
            {
                sparkTimer = 0.045f;
                VfxHub hub = VfxHub.Instance;
                hub.Burst(hub.Glow, transform.position, -dir, 1, 0.3f, 1.0f, 80f,
                    Color.Lerp(MagicTrailColor, VfxCombat.RuneColor, 0.5f), 0.06f, 0.13f, 0.15f, 0.30f, 0.2f, 0.05f);
            }

            // 用射线检测这一帧的位移，避免高速穿过薄目标
            if (dist > 0.0001f &&
                Physics.Raycast(transform.position, dir, out RaycastHit hit, dist, ~0,
                    QueryTriggerInteraction.Ignore))
            {
                // 别打到自己
                bool isSelf = owner != null && hit.collider.transform.IsChildOf(owner);
                if (!isSelf)
                {
                    HandleHit(hit);
                    return;
                }
            }

            transform.position += step;
        }

        private void HandleHit(RaycastHit hit)
        {
            var target = hit.collider.GetComponentInParent<IDamageable>();
            bool hitEnemy = target != null && target.IsAlive;

            if (hitEnemy)
            {
                target.TakeDamage(damage, hit.point, hit.normal);

                // 打击特效（vfx-dev，T-0xx）：受击方**按伤害分级**踉跄一下。
                // 法术比箭重，所以同样的伤害档位下推进更远（表在 VfxFeel.KnockbackGrids）。
                var enemy = hit.collider.GetComponentInParent<Enemy>();
                if (enemy != null)
                    enemy.ApplyKnockback(new Vector3(dir.x, 0f, dir.z), VfxFeel.KnockbackDistance(damage));
            }

            Explode(hit.point, hit.normal, hitSomething: true, hitEnemy: hitEnemy);
        }

        /// <summary>命中敌人爆红色，打墙/地面爆青色，一眼能分清打没打中。</summary>
        private static readonly Color EnemyHitColor = new Color(1f, 0.22f, 0.18f, 1f);
        private static readonly Color SurfaceHitColor = new Color(0.55f, 0.85f, 1f, 1f);

        private void Explode(Vector3 position, Vector3 normal, bool hitSomething, bool hitEnemy = false)
        {
            // 打击特效（vfx-dev，T-0xx）：**真实碰撞点 + 受击法线 + 弹道方向 + 伤害**一起递下去。
            //   * `position` = 射线 `hit.point`（真实碰撞点，不是目标的 transform.position）；
            //   * `dir`      = 本弹的飞行方向 → 火花沿它继续往前钻，冲击环垂直于它立起来；
            //   * `damage`   → 分级（轻/重/暴）；打墙/超时自爆传 -1（只放特效，不顿帧不飘字）。
            VfxCombat.SpellImpact(position, normal, dir, hitEnemy ? damage : -1f, hitEnemy);

            ArcaneBurst.Spawn(position, normal, hitSomething ? 1f : 0.6f,
                hitEnemy ? EnemyHitColor : SurfaceHitColor);
            Destroy(gameObject);
        }
    }
}
