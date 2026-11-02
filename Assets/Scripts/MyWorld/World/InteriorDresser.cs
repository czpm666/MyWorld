using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MyWorld
{
    /// <summary>
    /// 给所有「可进入房屋」（EnterableHouse）现场摆家具 + 塞一个 NPC。
    ///
    /// 为什么放在运行时而不是编辑器里烘：
    ///   RoaTown 是 4700 万字节的烘焙场景，每次重新烘焙 3~5 分钟；而家具只是
    ///   十来个方块，运行时拼一遍不到 2 ms。这样 RoaTown / 村庄 / 学院 / kit 城镇
    ///   四张图上的房子一次全有家具，不需要逐张图重烘。
    ///
    /// 幂等：每栋房子盖完会在屋里留一个 "InteriorDressing" 子物体，重复调用直接跳过。
    /// </summary>
    public static class InteriorDresser
    {
        private const int MaxHousesPerScene = 64;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Boot()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
            Kick();
        }

        private static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            Kick();
        }

        private static void Kick()
        {
            var host = new GameObject("InteriorDresser");
            host.AddComponent<Runner>();
        }

        private sealed class Runner : MonoBehaviour
        {
            private IEnumerator Start()
            {
                // MapBootstrap 在 Awake/Start 里造房子，等它把 EnterableHouse 造出来再动手
                for (int frame = 0; frame < 600; frame++)
                {
                    var found = FindOwners();
                    if (found.Count > 0)
                    {
                        Dress(found);
                        Destroy(gameObject);
                        yield break;
                    }
                    yield return null;
                }
                Destroy(gameObject);
            }
        }

        private static List<EnterableHouse> FindOwners()
        {
            var list = new List<EnterableHouse>();
#if UNITY_2023_1_OR_NEWER
            var all = Object.FindObjectsByType<EnterableHouse>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
#else
            var all = Object.FindObjectsOfType<EnterableHouse>();
#endif
            for (int i = 0; i < all.Length && list.Count < MaxHousesPerScene; i++)
            {
                if (all[i] == null) continue;
                if (all[i].transform.Find("InteriorDressing") != null) continue;
                if (all[i].InteriorTrigger == null) continue;
                list.Add(all[i]);
            }
            return list;
        }

        private static void Dress(List<EnterableHouse> houses)
        {
            int total = 0;
            for (int i = 0; i < houses.Count; i++)
            {
                if (DressOne(houses[i], i)) total++;
            }
            if (total > 0)
            {
                Debug.Log("[InteriorDresser] 已布置 " + total + " / " + houses.Count + " 间可进入房屋");
            }
        }

        private static bool DressOne(EnterableHouse house, int index)
        {
            if (house == null || house.InteriorTrigger == null) return false;

            Bounds b = house.InteriorTrigger.bounds;
            float hx = b.extents.x;
            float hz = b.extents.z;
            if (hx < 1.4f || hz < 1.4f) return false;

            var root = new GameObject("InteriorDressing");
            root.transform.SetParent(house.transform, false);
            // 房子不旋转时世界包围盒 == 房子坐标系，直接按世界坐标摆，省得换算
            root.transform.position = new Vector3(b.center.x, b.min.y, b.center.z);
            root.transform.rotation = Quaternion.identity;

            // 门在 +Z 面，所以 +Z 这一条留出 1.0 m 走动空间
            float roomX = Mathf.Max(1.2f, hx - 0.55f);
            float roomZ = Mathf.Max(1.2f, hz - 1.05f);

            var rng = new System.Random(7919 + index * 31);
            var mats = FurnitureMaterials();

            // 地毯：先铺，别的都压在上面
            Prop(root.transform, "rug", new Vector3(0f, 0.02f, 0.15f),
                new Vector3(roomX * 1.15f, 0.02f, roomZ * 0.95f),
                Pick(mats.rug, rng), 0f, false);

            // 壁炉：靠 -X 墙
            float hearthX = -roomX + 0.35f;
            Prop(root.transform, "hearth", new Vector3(hearthX, 0.55f, 0f),
                new Vector3(0.7f, 1.1f, 1.5f), mats.stone, 0f, true);
            Prop(root.transform, "hearth_mouth", new Vector3(hearthX + 0.26f, 0.42f, 0f),
                new Vector3(0.22f, 0.62f, 0.92f), mats.ember, 0f, false);

            // 长桌 + 两条凳：靠房间中部偏 +Z
            float tableZ = roomZ * 0.34f;
            Prop(root.transform, "table_top", new Vector3(0.15f, 0.74f, tableZ),
                new Vector3(roomX * 0.95f, 0.09f, 0.72f), mats.wood, 0f, true);
            Prop(root.transform, "table_leg_a", new Vector3(-roomX * 0.35f, 0.36f, tableZ - 0.24f),
                new Vector3(0.1f, 0.72f, 0.1f), mats.wood, 0f, false);
            Prop(root.transform, "table_leg_b", new Vector3(roomX * 0.6f, 0.36f, tableZ - 0.24f),
                new Vector3(0.1f, 0.72f, 0.1f), mats.wood, 0f, false);
            Prop(root.transform, "table_leg_c", new Vector3(-roomX * 0.35f, 0.36f, tableZ + 0.24f),
                new Vector3(0.1f, 0.72f, 0.1f), mats.wood, 0f, false);
            Prop(root.transform, "table_leg_d", new Vector3(roomX * 0.6f, 0.36f, tableZ + 0.24f),
                new Vector3(0.1f, 0.72f, 0.1f), mats.wood, 0f, false);
            Prop(root.transform, "stool_a", new Vector3(-roomX * 0.2f, 0.24f, tableZ - 0.72f),
                new Vector3(0.42f, 0.48f, 0.42f), mats.wood, 0f, true);
            Prop(root.transform, "stool_b", new Vector3(roomX * 0.42f, 0.24f, tableZ + 0.7f),
                new Vector3(0.42f, 0.48f, 0.42f), mats.wood, 0f, true);
            Prop(root.transform, "candle", new Vector3(roomX * 0.1f, 0.86f, tableZ),
                new Vector3(0.13f, 0.2f, 0.13f), mats.ember, 0f, false);

            // 床：+X 远角
            float bedX = roomX - 0.95f;
            float bedZ = -roomZ + 1.0f;
            Prop(root.transform, "bed_frame", new Vector3(bedX, 0.24f, bedZ),
                new Vector3(1.05f, 0.44f, 2.0f), mats.wood, 0f, true);
            Prop(root.transform, "bed_mattress", new Vector3(bedX, 0.52f, bedZ),
                new Vector3(0.95f, 0.18f, 1.9f), mats.linen, 0f, false);
            Prop(root.transform, "bed_pillow", new Vector3(bedX, 0.64f, bedZ - 0.7f),
                new Vector3(0.7f, 0.14f, 0.36f), mats.linen, 0f, false);
            Prop(root.transform, "bed_quilt", new Vector3(bedX, 0.60f, bedZ + 0.45f),
                new Vector3(1.0f, 0.12f, 1.0f), Pick(mats.cloth, rng), 0f, false);

            // 架子：靠 -Z 墙
            Prop(root.transform, "shelf", new Vector3(-roomX * 0.35f, 0.95f, -roomZ + 0.22f),
                new Vector3(1.5f, 1.9f, 0.34f), mats.wood, 0f, true);
            Prop(root.transform, "shelf_a", new Vector3(-roomX * 0.35f, 0.62f, -roomZ + 0.22f),
                new Vector3(1.44f, 0.06f, 0.4f), mats.wood_dark, 0f, false);
            Prop(root.transform, "shelf_b", new Vector3(-roomX * 0.35f, 1.18f, -roomZ + 0.22f),
                new Vector3(1.44f, 0.06f, 0.4f), mats.wood_dark, 0f, false);

            // 木桶 / 木箱：+X 靠门那侧
            Prop(root.transform, "barrel", new Vector3(roomX * 0.75f, 0.42f, roomZ * 0.62f),
                new Vector3(0.56f, 0.84f, 0.56f), mats.wood_dark, (float)rng.NextDouble() * 30f, true);
            Prop(root.transform, "crate", new Vector3(roomX * 0.75f - 0.8f, 0.3f, roomZ * 0.78f),
                new Vector3(0.6f, 0.6f, 0.6f), mats.wood, (float)rng.NextDouble() * 40f, true);

            // 一个 NPC 站在桌边（面朝 -Z，也就是偏离门）
            SpawnNpc(root.transform, house, index, new Vector3(0.2f, 0f, tableZ - 1.15f));
            return true;
        }

        private static void SpawnNpc(Transform parent, EnterableHouse house, int index, Vector3 local)
        {
            var mb = MapBootstrap.Active;
            var prefab = mb != null ? (mb.NpcPrefab != null ? mb.NpcPrefab : mb.CharacterPrefab) : null;
            if (prefab == null) return;

            string[] lines = NpcLines(index);
            var actor = NpcFactory.Create(parent, prefab, NpcRole.Villager,
                "屋主" + (index + 1), parent.TransformPoint(local), 180f, lines, null, null, null);
            if (actor != null) actor.name = "NPC_Interior_" + index;
        }

        private static string[] NpcLines(int index)
        {
            switch (index % 4)
            {
                case 0: return new[] { "门没锁，进来避避风吧。", "壁炉里的柴是我早上劈的。" };
                case 1: return new[] { "这屋子是我祖父那辈盖的。", "房梁上还留着他的刻痕。" };
                case 2: return new[] { "王都来的货越来越贵了。", "你要是往北走，替我捎句话。" };
                default: return new[] { "坐吧，桌上有水。", "外头风大，别急着赶路。" };
            }
        }

        private struct Mats
        {
            public Material wood, wood_dark, stone, linen, ember;
            public Material[] cloth, rug;
        }

        private static Mats FurnitureMaterials()
        {
            var m = new Mats();
            m.wood = MapMaterials.Get("wood_light");
            m.wood_dark = MapMaterials.Get("wood_dark");
            m.stone = MapMaterials.Get("stone_light");
            m.linen = MapMaterials.Get("plaster_cream");
            m.ember = MapMaterials.Get("glow_warm");
            m.cloth = new[] { MapMaterials.Get("cloth_red"), MapMaterials.Get("cloth_blue"), MapMaterials.Get("cloth_green") };
            m.rug = new[] { MapMaterials.Get("cloth_red"), MapMaterials.Get("cloth_burgundy"), MapMaterials.Get("cloth_teal") };
            return m;
        }

        private static Material Pick(Material[] arr, System.Random rng)
        {
            if (arr == null || arr.Length == 0) return MapMaterials.Get("wood_light");
            var m = arr[rng.Next(arr.Length)];
            return m != null ? m : MapMaterials.Get("wood_light");
        }

        private static GameObject Prop(Transform parent, string name, Vector3 pos, Vector3 size,
            Material mat, float yaw, bool collider)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            go.transform.localScale = size;
            var mr = go.GetComponent<MeshRenderer>();
            if (mr != null && mat != null) mr.sharedMaterial = mat;
            if (!collider)
            {
                var col = go.GetComponent<Collider>();
                if (col != null) Object.Destroy(col);
            }
            return go;
        }
    }
}
