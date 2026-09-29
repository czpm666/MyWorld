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

            transform.rotation = Quaternion.LookRotation(dir, Vector3.up);
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
            if (isEnemy) target.TakeDamage(damage, hit.point, hit.normal);

            Explode(hit.point, hit.normal, isEnemy);
        }

        private void Explode(Vector3 position, Vector3 normal, bool isEnemy)
        {
            ArcaneBurst.Spawn(position, normal, 0.5f, isEnemy ? EnemyHitColor : SurfaceHitColor);
            Destroy(gameObject);
        }
    }
}
