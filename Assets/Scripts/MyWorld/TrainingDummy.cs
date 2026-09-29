using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 带血条的木桩，用来测试法术伤害。
    /// 被打中会闪白并掉血，血量归零后倒下沉一小会儿再满血复活——
    /// 测试用的假人不需要真死，能反复打才方便调参。
    /// </summary>
    public class TrainingDummy : MonoBehaviour, IDamageable
    {
        [Header("血量")]
        [SerializeField] private float maxHealth = 100f;

        [Header("受击反馈")]
        [SerializeField] private float flashDuration = 0.12f;
        [SerializeField] private float respawnDelay = 1.6f;

        private float health;
        private float flashTimer;
        private float downTimer;
        private bool alive = true;

        private Renderer[] renderers;
        private Material[] normalMats;
        private Material flashMat;
        private Vector3 standingScale;

        // 必须序列化：烘焙后运行时这个引用要从场景文件恢复，否则 Refresh 静默失效。
        [SerializeField] private HealthBar bar;

        public bool IsAlive => alive;
        public Transform Transform => transform;

        private void OnEnable() => DamageableRegistry.Register(this);
        private void OnDisable() => DamageableRegistry.Unregister(this);

        private void Awake()
        {
            health = maxHealth;
            standingScale = transform.localScale;
            if (bar == null) bar = GetComponentInChildren<HealthBar>(true);

            // 只收集木桩自己的网格：血条也是子物体，一起闪白会把血条也刷成白的。
            var all = GetComponentsInChildren<Renderer>(true);
            var mine = new System.Collections.Generic.List<Renderer>(all.Length);
            foreach (var r in all)
            {
                if (r.GetComponentInParent<HealthBar>() != null) continue;
                mine.Add(r);
            }
            renderers = mine.ToArray();

            normalMats = new Material[renderers.Length];
            for (int i = 0; i < renderers.Length; i++)
                normalMats[i] = renderers[i].sharedMaterial;

            flashMat = PlaceholderArt.NewLit(Color.white, 0f);
            flashMat.name = "M_DummyFlash";
        }

        /// <summary>由生成器调用：接上血条。</summary>
        public void AttachHealthBar(HealthBar hb)
        {
            bar = hb;
            Refresh();
        }

        private void Start()
        {
            // 必须有这一步：编辑期烘焙时 Unity 不会调 Awake/Start，
            // 那时 health 还是默认的 0，算出来的血条会被当成"空血"存进场景。
            // 运行时 Start 再刷一次，把烘焙时存坏的状态纠正回来。
            Refresh();
        }

        public void TakeDamage(float amount, Vector3 hitPoint, Vector3 hitNormal)
        {
            if (!alive) return;

            health -= amount;
            flashTimer = flashDuration;
            Refresh();

            if (health <= 0f) GoDown();
        }

        private void GoDown()
        {
            alive = false;
            health = 0f;
            downTimer = respawnDelay;
            // "倒下"用一个压倒的缩放表示，比做死亡动画省事，测试场景里足够读
            transform.localScale = new Vector3(standingScale.x, standingScale.y * 0.18f, standingScale.z);
        }

        private void Respawn()
        {
            alive = true;
            health = maxHealth;
            transform.localScale = standingScale;
            Refresh();
        }

        private void Refresh()
        {
            if (bar != null) bar.SetFill(maxHealth > 0f ? health / maxHealth : 0f);
        }

        private void Update()
        {
            if (flashTimer > 0f)
            {
                flashTimer -= Time.deltaTime;
                if (flashTimer <= 0f) RestoreMaterials();
            }

            if (!alive)
            {
                downTimer -= Time.deltaTime;
                if (downTimer <= 0f) Respawn();
            }
        }

        private void LateUpdate()
        {
            // 受击闪白：把材质换成纯白，一小会儿后换回来
            if (flashTimer > 0f)
            {
                for (int i = 0; i < renderers.Length; i++)
                    if (renderers[i] != null) renderers[i].sharedMaterial = flashMat;
            }
        }

        private void RestoreMaterials()
        {
            for (int i = 0; i < renderers.Length; i++)
                if (renderers[i] != null) renderers[i].sharedMaterial = normalMats[i];
        }

        private void OnDestroy()
        {
            if (flashMat != null) Destroy(flashMat);
        }
    }
}
