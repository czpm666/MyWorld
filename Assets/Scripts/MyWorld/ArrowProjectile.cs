using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 弓箭的箭矢：直线飞行，命中可伤害目标就结算伤害。
    /// 造型用图元拼（细杆 + 箭头），和工程里其它占位特效一致。
    /// </summary>
    [DisallowMultipleComponent]
    public class ArrowProjectile : MonoBehaviour
    {
        [SerializeField] private float speed = 34f;
        [SerializeField] private float lifeTime = 2f;
        [SerializeField] private float damage = 18f;
        [Tooltip("判定半径。给一点粗细，高速飞行才不会从目标身边擦过去")]
        [SerializeField] private float hitRadius = 0.28f;

        private Vector3 dir;
        private Transform owner;
        private float life;

        private static readonly Color EnemyHitColor = new Color(1f, 0.22f, 0.18f, 1f);
        private static readonly Color SurfaceHitColor = new Color(0.9f, 0.85f, 0.6f, 1f);

        public static ArrowProjectile Spawn(Vector3 position, Vector3 direction, Transform owner,
            float damage, float speed, float lifeTime, float radius)
        {
            var go = new GameObject("Arrow");
            go.transform.position = position;

            var a = go.AddComponent<ArrowProjectile>();
            a.dir = direction.sqrMagnitude > 0.0001f ? direction.normalized : Vector3.forward;
            a.owner = owner;
            if (damage > 0f) a.damage = damage;
            if (speed > 0f) a.speed = speed;
            if (lifeTime > 0f) a.lifeTime = lifeTime;
            if (radius > 0f) a.hitRadius = radius;
            a.Build();
            return a;
        }

        private void Build()
        {
            var wood = PlaceholderArt.NewLit(new Color(0.45f, 0.32f, 0.20f), 0.1f);
            wood.name = "M_ArrowShaft";
            var metal = PlaceholderArt.NewLit(new Color(0.62f, 0.66f, 0.72f), 0.5f);
            metal.name = "M_ArrowHead";

            // 杆：细长的立方体，沿 +Z
            var shaft = GameObject.CreatePrimitive(PrimitiveType.Cube);
            shaft.name = "Shaft";
            PlaceholderArt.StripCollider(shaft);
            shaft.transform.SetParent(transform, false);
            shaft.transform.localScale = new Vector3(0.05f, 0.05f, 0.6f);
            shaft.GetComponent<Renderer>().sharedMaterial = wood;

            // 箭头
            var head = GameObject.CreatePrimitive(PrimitiveType.Cube);
            head.name = "Head";
            PlaceholderArt.StripCollider(head);
            head.transform.SetParent(transform, false);
            head.transform.localPosition = new Vector3(0f, 0f, 0.36f);
            head.transform.localScale = new Vector3(0.12f, 0.12f, 0.18f);
            head.GetComponent<Renderer>().sharedMaterial = metal;

            // 箭风：一条细长的白线拖尾（把"弓"和其它武器区分开）
            var wind = gameObject.AddComponent<TrailRenderer>();
            wind.time = 0.16f;
            wind.startWidth = 0.09f;
            wind.endWidth = 0f;
            wind.minVertexDistance = 0.05f;
            wind.material = PlaceholderArt.GetVertexColorMaterial();
            wind.startColor = new Color(0.95f, 0.97f, 1f, 0.55f);
            wind.endColor = new Color(0.85f, 0.9f, 1f, 0f);
            wind.sortingOrder = 29;

            transform.rotation = Quaternion.LookRotation(dir, Vector3.up);

            // 离弦瞬间的弦风 + 光斑（VfxCombat 语义层；同时触发程序化弓弦音）
            VfxCombat.ArrowRelease(transform.position, dir);
        }

        private void Update()
        {
            float dt = Time.deltaTime;
            life += dt;
            if (life > lifeTime)
            {
                Explode(transform.position, -dir, false);
                return;
            }

            Vector3 step = dir * (speed * dt);
            float dist = step.magnitude;

            if (dist > 0.0001f)
            {
                // 用球体扫描而不是细射线：高速飞行的箭不能从目标身边擦过去
                if (Physics.SphereCast(transform.position, hitRadius, dir, out RaycastHit hit, dist,
                        ~0, QueryTriggerInteraction.Ignore))
                {
                    if (!(owner != null && hit.collider.transform.IsChildOf(owner)))
                    {
                        HandleHit(hit);
                        return;
                    }
                }
            }

            transform.position += step;
        }

        private void HandleHit(RaycastHit hit)
        {
            var target = hit.collider.GetComponentInParent<IDamageable>();
            bool isEnemy = target != null && target.IsAlive;
            if (isEnemy)
            {
                target.TakeDamage(damage, hit.point, hit.normal);

                // 打击特效（vfx-dev，T-0xx）：受击方**按伤害分级**踉跄一下（箭把它顶得往后一挫）。
                // 方向 = 本箭的飞行方向（水平化）—— 与命中特效的火花同向，不会"特效往前、人往后飞"。
                var enemy = hit.collider.GetComponentInParent<Enemy>();
                if (enemy != null)
                    enemy.ApplyKnockback(new Vector3(dir.x, 0f, dir.z), VfxFeel.KnockbackDistance(damage));
            }

            Explode(hit.point, hit.normal, isEnemy);
        }

        private void Explode(Vector3 position, Vector3 normal, bool isEnemy)
        {
            // 打击特效（vfx-dev，T-0xx）：把**真实碰撞点 + 受击法线 + 弹道方向 + 伤害**一起递下去。
            //   * `position` = 射线/球扫的 `hit.point`（真实碰撞点，不是目标的 transform.position）；
            //   * `dir`      = 本箭的飞行方向 → 木屑/血花沿它往前钻，冲击环垂直于它立起来；
            //   * `damage`   → 分级（轻/重/暴）：粒子量、顿帧、震屏、飘字全按它查同一张表。
            // 打中敌人时 `damage` 就是真实伤害；打墙时传 -1（不飘数字、不顿帧）。
            VfxCombat.ArrowImpact(position, normal, dir, isEnemy ? damage : -1f, isEnemy);

            ArcaneBurst.Spawn(position, normal, 0.5f, isEnemy ? EnemyHitColor : SurfaceHitColor);
            Destroy(gameObject);
        }
    }
}
