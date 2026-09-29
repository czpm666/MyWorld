using UnityEngine;

namespace MyWorld
{
    /// <summary>
    /// 法术命中/生成时的奥术爆花：一圈向外飞散的短线段 + 一个瞬间膨胀淡出的球壳。
    /// 和 HookSparks 一个思路——用图元拼，不依赖美术资源；活完自动销毁。
    /// </summary>
    public class ArcaneBurst : MonoBehaviour
    {
        private const int ShardCount = 12;

        private LineRenderer[] shards;
        private Vector3[] shardVel;
        private float[] shardLife;

        private Transform shell;
        private float shellLife;
        private float shellSize;

        [SerializeField] private float shardLifetime = 0.35f;
        [SerializeField] private float shellLifetime = 0.22f;

        /// <summary>默认青色（打墙、出生等）。</summary>
        public static void Spawn(Vector3 position, Vector3 normal, float scale)
        {
            Spawn(position, normal, scale, new Color(0.55f, 0.85f, 1f, 1f));
        }

        /// <summary>指定颜色。打敌人用红色，和打墙区分开。</summary>
        public static void Spawn(Vector3 position, Vector3 normal, float scale, Color color)
        {
            var go = new GameObject("ArcaneBurst");
            go.transform.position = position;
            go.AddComponent<ArcaneBurst>().Init(normal, Mathf.Max(scale, 0.1f), color);
        }

        private void Init(Vector3 normal, float scale, Color color)
        {
            Vector3 position = transform.position;
            if (normal.sqrMagnitude < 0.0001f) normal = Vector3.up;
            normal.Normalize();

            var mat = PlaceholderArt.GetGlowMaterial(color);
            shards = new LineRenderer[ShardCount];
            shardVel = new Vector3[ShardCount];
            shardLife = new float[ShardCount];

            var shardGo = new GameObject("Shards");
            shardGo.transform.SetParent(transform, false);

            for (int i = 0; i < ShardCount; i++)
            {
                var g = new GameObject("Shard" + i);
                g.transform.SetParent(shardGo.transform, false);
                var lr = g.AddComponent<LineRenderer>();
                lr.material = mat;
                lr.useWorldSpace = true;
                lr.numCapVertices = 0;
                lr.positionCount = 2;
                lr.startWidth = 0.12f * scale;
                lr.endWidth = 0f;
                lr.sortingOrder = 31;

                // 沿法线方向散开，带一点随机
                Vector3 d = (normal + Random.insideUnitSphere * 0.9f).normalized;
                shardVel[i] = d * Random.Range(5f, 11f) * scale;
                shardLife[i] = shardLifetime * Random.Range(0.7f, 1.15f);
                // 必须初始化两个端点，否则第一帧会从世界原点拉出一条长线
                lr.SetPosition(0, position);
                lr.SetPosition(1, position);
                shards[i] = lr;
            }

            // 膨胀球壳
            var sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            sphere.name = "Shell";
            PlaceholderArt.StripCollider(sphere);
            sphere.transform.SetParent(transform, false);
            var r = sphere.GetComponent<Renderer>();
            if (r != null) r.sharedMaterial = mat;
            shell = sphere.transform;
            shellSize = 2.2f * scale;
            shellLife = shellLifetime;
            shell.localScale = Vector3.one * 0.2f;
        }

        private void Update()
        {
            float dt = Time.deltaTime;
            bool alive = false;

            for (int i = 0; i < shards.Length; i++)
            {
                if (shardLife[i] <= 0f) continue;
                shardLife[i] -= dt;
                if (shardLife[i] <= 0f)
                {
                    shards[i].enabled = false;
                    continue;
                }
                alive = true;

                Vector3 tail = shards[i].GetPosition(0);
                Vector3 head = tail + shardVel[i] * dt;
                shards[i].SetPosition(0, head);
                shards[i].SetPosition(1, head - shardVel[i].normalized * 0.35f);
                shardVel[i] = Vector3.MoveTowards(shardVel[i], Vector3.zero, 14f * dt);
            }

            if (shell != null)
            {
                shellLife -= dt;
                if (shellLife > 0f)
                {
                    alive = true;
                    float k = 1f - Mathf.Clamp01(shellLife / shellLifetime);
                    shell.localScale = Vector3.one * Mathf.Lerp(0.2f, shellSize, k);
                }
                else
                {
                    shell.gameObject.SetActive(false);
                }
            }

            if (!alive) Destroy(gameObject);
        }
    }
}
