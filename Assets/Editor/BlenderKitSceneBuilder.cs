// 编辑器菜单：把 Blender 导出的整套 kit + medieval_layout.json 拼成一张可直接打开的城镇场景。
// 只新建一处场景，不碰任何已有场景 / 脚本。
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using MyWorld.Maps;

public static class BlenderKitSceneBuilder
{
    const string ScenePath = "Assets/Scenes/BlenderKitTown.unity";
    const string MatFolder = "Assets/Generated/MedievalKitBlender";
    const string GroundMatPath = MatFolder + "/M_BlenderKitTownGround.mat";

    [MenuItem("Tools/My World/用 Blender Kit 生成城镇场景", false, 60)]
    public static void BuildTown()
    {
        var layout = BlenderKitMapBuilder.LoadLayout(BlenderKitMapBuilder.DefaultLayoutFile);
        if (layout == null || layout.pieces == null || layout.pieces.Length == 0)
        {
            Debug.LogError("[BlenderKitTown] 布局为空，先确认 Assets/StreamingAssets/medieval_layout.json 存在。");
            return;
        }

        // 布局里写的还是合并前的 "tree"，这里按固定种子换成四个品种，保证每次结果一致。
        int trees = 0;
        var rnd = new System.Random(20261019);
        foreach (var p in layout.pieces)
        {
            if (p == null || p.prefab != "tree") continue;
            int k = rnd.Next(4);
            p.prefab = k == 0 ? "tree_broad"
                     : k == 1 ? "tree_conifer"
                     : k == 2 ? "tree_poplar"
                     : "tree_dead";
            trees++;
        }

        AppendDressing(layout);

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // 地面：300x300 草坪，免得物件看起来悬空
        var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Ground";
        ground.transform.position = Vector3.zero;
        ground.transform.localScale = new Vector3(30f, 1f, 30f);
        var gr = ground.GetComponent<Renderer>();
        if (gr != null) gr.sharedMaterial = GetOrCreateGroundMaterial();

        var root = new GameObject("BlenderKitTown");
        var built = BlenderKitMapBuilder.Build(
            root.transform, layout, BlenderKitMapBuilder.DefaultLayoutFile, "BlenderKit");

        // 铺装：布局里只有道具和房子，路面在 Blender 那边是程序化生成的，没导出成 kit 件。
        // 这里用同一套常量（RA=17 / RB=33 / SHW=3.8）在 Unity 侧补出来，否则房子看起来是撒在草地上。
        var paving = new GameObject("Paving");
        paving.transform.SetParent(root.transform, false);
        const string CobbleTex = "Assets/Art/Textures/kit_cobble.jpg";
        // Plane 的 UV：u 沿 +X、v 沿 +Z。横街与竖街的 tiling 必须分开，否则一边会被拉成长条。
        // tint 压到 0.5 上下：贴图本身偏白，1.0 直出在强日光下会糊成一片米色纸。
        var paveTint = new Color(0.54f, 0.52f, 0.49f);
        var cobbleX = GetOrCreateTexMat("M_KitCobbleX", CobbleTex, new Vector2(60f, 6f), 0.10f, paveTint);
        var cobbleZ = GetOrCreateTexMat("M_KitCobbleZ", CobbleTex, new Vector2(6f, 60f), 0.10f, paveTint);
        var flag = GetOrCreateTexMat("M_KitPlaza", CobbleTex, new Vector2(20f, 20f), 0.10f, paveTint);

        // 镇内底色：环街之间、广场与街之间有大片空地，直接露草地会变成一块块绿补丁。
        // 先铺一层踩实的夯土，缝隙读起来是空地而不是草坪；街道再从它上面压过去。
        var earth = GetOrCreateTexMat("M_KitTownEarth", CobbleTex, new Vector2(24f, 24f), 0.04f,
                                      new Color(0.33f, 0.28f, 0.22f));
        Pave("interior_earth", 0f, 0f, 92f, 92f, earth, paving.transform, 0.004f);

        const float RA = 17f, RB = 33f, SHW = 3.8f, SW = SHW * 2f + 1.6f, PLAZA = 13f, SPAN = 92f;
        Pave("plaza", 0f, 0f, PLAZA * 2f + 4.4f, PLAZA * 2f + 4.4f, flag, paving.transform, 0.012f);
        for (int ring = 0; ring < 2; ring++)
        {
            float r = ring == 0 ? RA : RB;
            Pave("ring" + ring + "_n", 0f, r, SPAN, SW, cobbleX, paving.transform, 0.018f);
            Pave("ring" + ring + "_s", 0f, -r, SPAN, SW, cobbleX, paving.transform, 0.018f);
            Pave("ring" + ring + "_e", r, 0f, SW, SPAN, cobbleZ, paving.transform, 0.018f);
            Pave("ring" + ring + "_w", -r, 0f, SW, SPAN, cobbleZ, paving.transform, 0.018f);
        }
        Pave("road_ns", 0f, 0f, SW, SPAN, cobbleZ, paving.transform, 0.024f);
        Pave("road_ew", 0f, 0f, SPAN, SW, cobbleX, paving.transform, 0.024f);

        // 城墙：Blender 那边的墙也是程序化生成的，同样没进 kit，这里按同一套常量补出来。
        var wallRoot = new GameObject("Walls");
        wallRoot.transform.SetParent(root.transform, false);
        var stone = GetOrCreateTexMat("M_KitWallStone", "Assets/Art/Textures/kit_stone_wall.jpg", new Vector2(20f, 2.6f), 0.18f,
                                      new Color(1.18f, 1.14f, 1.06f));
        const float WALL = 45f, WH = 5.2f, WT = 1.35f, GW = 9f;
        float half = GW * 0.5f;
        float seg = WALL - half;
        float mid = half + seg * 0.5f;

        for (int s = 0; s < 2; s++)
        {
            float sgn = s == 0 ? 1f : -1f;
            foreach (float axial in new[] { 1f, -1f })
            {
                // 南北两面：墙沿 X 方向
                Box("wall_ns", new Vector3(axial * mid, WH * 0.5f, sgn * WALL),
                    new Vector3(seg, WH, WT), stone, wallRoot.transform);
                // 东西两面：墙沿 Z 方向
                Box("wall_ew", new Vector3(sgn * WALL, WH * 0.5f, axial * mid),
                    new Vector3(WT, WH, seg), stone, wallRoot.transform);
            }
        }
        // 雉堞：沿每段墙顶每 2 m 一块
        for (int s = 0; s < 2; s++)
        {
            float sgn = s == 0 ? 1f : -1f;
            for (float t = -WALL + 1f; t <= WALL - 1f; t += 2f)
            {
                if (Mathf.Abs(t) < half + 0.8f) continue;   // 城门处断开
                Box("merlon", new Vector3(t, WH + 0.45f, sgn * WALL),
                    new Vector3(1.15f, 0.9f, WT), stone, wallRoot.transform);
                Box("merlon", new Vector3(sgn * WALL, WH + 0.45f, t),
                    new Vector3(WT, 0.9f, 1.15f), stone, wallRoot.transform);
            }
        }

        // 可进入的民居 / 商铺 / 旅店：用室内套件 prefab 摆到 A 环空档。
        // 必须在 MakePlayable 之前，场景里先有 EnterableHouse，运行时的 NPC 才找得到。
        BuildEnterableBuildings(root, built);

        // 变成可玩地图：场景根挂 BlenderKitTownMap（MapBootstrap 子类），
        // 进 Play 时复用 MapBootstrap 的玩家 / 俯视相机 / HUD 搭建逻辑。
        MakePlayable(root);

        // 太阳光
        var sunGo = new GameObject("Sun");
        var sun = sunGo.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.intensity = 1.05f;
        sun.color = new Color(1f, 0.96f, 0.88f);
        sun.shadows = LightShadows.Soft;
        sunGo.transform.rotation = Quaternion.Euler(50f, 34f, 0f);

        // 人口 / 氛围 / 传送门由各自的菜单脚本负责。重建场景会 NewScene，
        // 这里必须重新跑一遍，否则会把别的代理已经烙进场景的 NPC、后处理和传送门冲掉。
        KitTownPopulation.Populate();
        KitTownLook.ApplyLook();
        KitTownPortal.AddPortalToRoaTown();

        // 相机不烘焙进场景：进 Play 时由 MapBootstrap.BuildCamera() 生成跟着玩家走的
        // TopDownCameraRig。这里再放一台静态相机会变成两个 MainCamera，Game 视图随机用一台。

        EditorSceneManager.MarkSceneDirty(scene);
        Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
        bool ok = EditorSceneManager.SaveScene(scene, ScenePath);
        AssetDatabase.Refresh();

        Debug.Log("[BlenderKitTown] pieces=" + layout.pieces.Length +
                  " trees_remapped=" + trees +
                  " rootChildren=" + (built != null ? built.transform.childCount : -1) +
                  " saved=" + ok + " -> " + ScenePath);
    }

    // 布局里房子只占环街两侧，环 A 与环 B 之间的四块空地是空的。
    // 这里往那块草皮上补市集堆：摊位 / 桶 / 箱 / 袋子 / 手推车 / 树 / 灌木，再沿城墙外补一圈树。
    static void AppendDressing(BlenderKitLayout layout)
    {
        var rnd = new System.Random(773311);
        var list = new System.Collections.Generic.List<BlenderKitPiece>(layout.pieces);
        int id = 0;

        float[] quadrant = { 1f, -1f };
        foreach (float sx in quadrant)
        foreach (float sz in quadrant)
        {
            float cx = sx * 25f;
            float cz = sz * 25f;
            float yaw = Mathf.Atan2(-cx, -cz) * Mathf.Rad2Deg;   // 摊位朝广场中心

            list.Add(Piece("market_stall", cx + 0.6f, cz - 0.4f, yaw, "dress_stall_" + id++));

            for (int i = 0; i < 3; i++)
                list.Add(Piece("barrel", cx - 2.2f + i * 1.1f, cz + 2.0f, rnd.Next(0, 360), "dress_barrel_" + id++));
            for (int i = 0; i < 2; i++)
                list.Add(Piece("crate", cx + 2.1f, cz + 1.2f - i * 1.2f, rnd.Next(0, 360), "dress_crate_" + id++));

            list.Add(Piece("sack", cx - 1.4f, cz - 2.3f, rnd.Next(0, 360), "dress_sack_" + id++));
            list.Add(Piece("barrel_cluster", cx + 1.2f, cz + 2.6f, rnd.Next(0, 360), "dress_bc_" + id++));
            if (rnd.Next(2) == 0)
                list.Add(Piece("cart", cx + 2.4f, cz - 2.4f, yaw + 40f, "dress_cart_" + id++));

            list.Add(Piece("tree_broad", cx - 2.6f, cz - 2.6f, rnd.Next(0, 360), "dress_tree_" + id++));
            list.Add(Piece(rnd.Next(2) == 0 ? "tree_poplar" : "tree_conifer",
                           cx + 2.7f, cz + 2.7f, rnd.Next(0, 360), "dress_tree_" + id++));
            list.Add(Piece("bush", cx - 2.0f, cz + 2.6f, rnd.Next(0, 360), "dress_bush_" + id++));
        }

        // 沿街摆摊点：街很宽，只有房子会显得空荡。每 5.8 m 在街边放一件货，环 A / 环 B 都放。
        string[] streetKinds = { "barrel", "crate", "sack", "barrel_cluster", "crate_stack" };
        for (int ring = 0; ring < 2; ring++)
        {
            float r = ring == 0 ? 17f : 33f;
            for (int i = 0; i < 16; i++)
            {
                float t = -44f + i * 5.8f;
                float side = (i % 2 == 0) ? 1f : -1f;
                float off = r + side * 3.35f;
                string kind = streetKinds[rnd.Next(streetKinds.Length)];
                list.Add(Piece(kind, t, off, rnd.Next(0, 360), "street_ns_" + id++));
                string kind2 = streetKinds[rnd.Next(streetKinds.Length)];
                list.Add(Piece(kind2, off, t, rnd.Next(0, 360), "street_ew_" + id++));
            }
        }

        // 城墙外一圈树，把光秃秃的草地边缘挡掉
        for (int i = 0; i < 40; i++)
        {
            float a = i / 40f * Mathf.PI * 2f;
            float r = 50f + (i % 3) * 3.5f;
            float tx = Mathf.Cos(a) * r;
            float tz = Mathf.Sin(a) * r;
            string sp = i % 5 == 0 ? "tree_conifer" : (i % 7 == 0 ? "tree_poplar" : "tree_broad");
            list.Add(Piece(sp, tx, tz, rnd.Next(0, 360), "dress_ring_tree_" + id++));
        }

        layout.pieces = list.ToArray();
        Debug.Log("[BlenderKitTown] 补装饰件 " + id + "，总计 " + layout.pieces.Length + " 件");
    }

    // 传 Unity 的 (X, Z) 和 Y 轴朝向；内部换算回 Blender 世界坐标（Z-up）
    static BlenderKitPiece Piece(string prefab, float ux, float uz, float yaw, string name)
    {
        return new BlenderKitPiece
        {
            prefab = prefab,
            pos = new[] { ux, -uz, 0f },
            rot_z = yaw,
            name = name
        };
    }

    // ================= 可进入建筑 =================

    /// <summary>
    /// A 环（半径 24）沿街摆 8 栋可进入建筑：6 栋民居 + 1 商铺 + 1 旅店，
    /// 每 45° 一栋，门（本地 +Z）统一朝广场中心。
    ///
    /// 原来的 5 栋 A 环装饰房（A_out_house_*）会和这些体积更大的可进入房子重叠，
    /// 所以整批移掉；B 环（半径 40）的装饰房保留，天际线还在。
    /// 商铺 / 旅店沿用 Blender 导出的 interior_shop_a / interior_inn_a 外壳，
    /// 与民居使用同一套门洞契约（+Z 门、铰链 x=0.525、z=2.50），
    /// 所以 InteriorKitImporter.BuildPrefab 的装配参数不用改。
    /// </summary>
    static void BuildEnterableBuildings(GameObject townRoot, GameObject kitRoot)
    {
        var house = MyWorldEditorTools.InteriorKitImporter.EnsurePrefab("interior_house_a", "InteriorHouse_A");
        var shop = MyWorldEditorTools.InteriorKitImporter.EnsurePrefab("interior_shop_a", "InteriorShop_A");
        var inn = MyWorldEditorTools.InteriorKitImporter.EnsurePrefab("interior_inn_a", "InteriorInn_A");
        if (house == null || shop == null || inn == null)
        {
            Debug.LogError("[BlenderKitTown] 可进入建筑 prefab 缺失（house/shop/inn），本批不摆。先跑 室内③ / ③b。");
            return;
        }

        // 移掉 A 环的装饰房；按名字前缀识别，B 环的 B_out_house_* 不受影响。
        int removed = 0;
        if (kitRoot != null)
        {
            for (int i = kitRoot.transform.childCount - 1; i >= 0; i--)
            {
                var c = kitRoot.transform.GetChild(i);
                if (c.name.StartsWith("A_out_house_", System.StringComparison.Ordinal))
                {
                    Object.DestroyImmediate(c.gameObject);
                    removed++;
                }
            }
        }

        var host = new GameObject("EnterableHouses");
        host.transform.SetParent(townRoot.transform, false);

        // 角度按 +X 为 0°、逆时针到 +Z（Unity 的 yaw 绕 Y）。rotY = 270° - angle 让门朝内。
        string[] labels =
        {
            "InteriorHouse_01", "InteriorHouse_02", "InteriorShop_A", "InteriorHouse_03",
            "InteriorInn_A", "InteriorHouse_04", "InteriorHouse_05", "InteriorHouse_06",
        };
        string[] kinds =
        {
            "house", "house", "shop", "house", "inn", "house", "house", "house",
        };
        float[] angles = { -135f, -90f, -45f, 0f, 45f, 90f, 135f, 180f };

        var doorWorld = new Vector3[labels.Length];
        for (int i = 0; i < labels.Length; i++)
        {
            var prefab = kinds[i] == "shop" ? shop : (kinds[i] == "inn" ? inn : house);
            var inst = PrefabUtility.InstantiatePrefab(prefab, townRoot.scene) as GameObject;
            if (inst == null)
            {
                Debug.LogError("[BlenderKitTown] 实例化失败：" + labels[i]);
                continue;
            }

            inst.name = labels[i];
            inst.transform.SetParent(host.transform, false);
            float rad = angles[i] * Mathf.Deg2Rad;
            inst.transform.localPosition = new Vector3(Mathf.Cos(rad) * 24f, 0f, Mathf.Sin(rad) * 24f);
            inst.transform.localRotation = Quaternion.Euler(0f, 270f - angles[i], 0f);
            inst.transform.localScale = Vector3.one;

            // 门轴契约与 InteriorKitImporter 一致：本地 (0.525, 0, 2.50)。
            doorWorld[i] = inst.transform.TransformPoint(new Vector3(0.525f, 0f, 2.50f));

            if (inst.GetComponent<MyWorld.EnterableHouse>() == null)
                Debug.LogWarning("[BlenderKitTown] " + labels[i] + " 上没有 EnterableHouse（prefab 没装配？）");
        }

        // 清掉正堵在门口的市集杂物（A 环的装饰摊位是按 24m 环随手撒的，
        // 其中一两个正好落在新门的 1-3m 内）。只清 A_out_furn_*，不动 B 环和铺装。
        int cleared = 0;
        if (kitRoot != null)
        {
            for (int i = kitRoot.transform.childCount - 1; i >= 0; i--)
            {
                var c = kitRoot.transform.GetChild(i);
                if (!c.name.StartsWith("A_out_furn_", System.StringComparison.Ordinal)) continue;
                for (int d = 0; d < doorWorld.Length; d++)
                {
                    Vector3 a = c.position; a.y = 0f;
                    Vector3 b = doorWorld[d]; b.y = 0f;
                    if ((a - b).sqrMagnitude <= 3.5f * 3.5f)
                    {
                        Object.DestroyImmediate(c.gameObject);
                        cleared++;
                        break;
                    }
                }
            }
        }

        Debug.Log("[BlenderKitTown] 可进入建筑 " + labels.Length + " 栋（民居 6 / 商铺 1 / 旅店 1），" +
                  "移除 A 环装饰房 " + removed + " 栋，清门口杂物 " + cleared + " 件");
    }

    // ================= 可玩化 =================

    /// <summary>
    /// 给场景根挂 <see cref="MyWorld.Maps.BlenderKitTownMap"/>，并把 MapBootstrap 的
    /// 私有序列化字段填好（和 MapSceneSetup 生成罗亚市场景时用的是同一套字段）。
    ///
    /// 这些字段必须落进 .unity：进 Play 后 MapBootstrap.Awake 会读它们来生成玩家、
    /// 武器、HUD 和相机，运行时没有别的地方能补。
    /// </summary>
    static void MakePlayable(GameObject root)
    {
        var map = root.AddComponent<MyWorld.Maps.BlenderKitTownMap>();
        var so = new SerializedObject(map);

        SetBool(so, "buildOnPlay", true);
        SetBool(so, "bakedIntoScene", false);
        SetVector3(so, "playerStart", new Vector3(0f, 0.2f, -11f));

        // 玩家 / NPC / 敌人：用工程里已有的 KayKit 预制体
        SetObject(so, "characterPrefab", LoadPrefab("Assets/ThirdParty/KayKit_Adventurers/MageCharacter.prefab"));
        SetObject(so, "npcPrefab", LoadPrefab("Assets/ThirdParty/KayKit_Adventurers/NpcCharacter.prefab"));
        SetObject(so, "enemyPrefab", LoadPrefab("Assets/ThirdParty/KayKit_Adventurers/Enemies/EnemyBarbarian.prefab"));

        // 顺序必须与 MapBootstrap.BuildLoadout / WeaponDefs.CreateAll 对应：
        // 法杖、剑、弓、抓钩、盾、魔法护手
        string[] weaponPaths =
        {
            "Assets/ThirdParty/KayKit_Adventurers/Weapons/W_Staff.prefab",
            "Assets/ThirdParty/KayKit_Adventurers/Weapons/W_Sword.prefab",
            "Assets/ThirdParty/KayKit_Adventurers/Weapons/W_Bow.prefab",
            "Assets/ThirdParty/KayKit_Adventurers/Weapons/W_RopeGun.prefab",
            "Assets/ThirdParty/KayKit_Adventurers/Weapons/W_Shield.prefab",
            "Assets/ThirdParty/KayKit_Adventurers/Weapons/W_Gauntlet.prefab",
        };
        var weaponProp = so.FindProperty("weaponPrefabs");
        if (weaponProp != null)
        {
            weaponProp.arraySize = weaponPaths.Length;
            for (int i = 0; i < weaponPaths.Length; i++)
                weaponProp.GetArrayElementAtIndex(i).objectReferenceValue = LoadPrefab(weaponPaths[i]);
        }

        // 相机：和罗亚市同一套 3/4 俯视（pitch 52 / 长焦 30°），距离略拉远以看清广场。
        SetFloat(so, "camPitch", 52f);
        SetFloat(so, "camDistance", 26f);
        SetBool(so, "camPerspective", true);
        SetFloat(so, "camFieldOfView", 30f);

        so.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(map);
    }

    static GameObject LoadPrefab(string path)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if (prefab == null) Debug.LogError("[BlenderKitTown] 缺少预制体：" + path);
        return prefab;
    }

    static void SetObject(SerializedObject so, string field, Object value)
    {
        var p = so.FindProperty(field);
        if (p == null) { Debug.LogError("[BlenderKitTown] 没有字段 " + field); return; }
        p.objectReferenceValue = value;
    }

    static void SetBool(SerializedObject so, string field, bool value)
    {
        var p = so.FindProperty(field);
        if (p != null) p.boolValue = value;
    }

    static void SetFloat(SerializedObject so, string field, float value)
    {
        var p = so.FindProperty(field);
        if (p != null) p.floatValue = value;
    }

    static void SetVector3(SerializedObject so, string field, Vector3 value)
    {
        var p = so.FindProperty(field);
        if (p != null) p.vector3Value = value;
    }

    static Material GetOrCreateGroundMaterial()
    {
        return GetOrCreateMat("M_BlenderKitTownGround", new Color(0.34f, 0.42f, 0.23f), 0.06f);
    }

    // 方块：Cube 原始尺寸 1x1x1，所以缩放就是米的尺寸
    static void Box(string name, Vector3 center, Vector3 size,
                    Material mat, Transform parent)
    {
        var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
        go.name = name;
        go.transform.SetParent(parent, false);
        go.transform.position = center;
        go.transform.localScale = size;
        var r = go.GetComponent<Renderer>();
        if (r != null) r.sharedMaterial = mat;
    }

    // 铺一块地砖：Plane 原始尺寸 10x10，所以缩放 = 米 / 10
    static void Pave(string name, float cx, float cz, float w, float d,
                     Material mat, Transform parent, float y)
    {
        var go = GameObject.CreatePrimitive(PrimitiveType.Plane);
        go.name = name;
        var col = go.GetComponent<Collider>();
        if (col != null) UnityEngine.Object.DestroyImmediate(col);
        go.transform.SetParent(parent, false);
        go.transform.position = new Vector3(cx, y, cz);
        go.transform.localScale = new Vector3(w / 10f, 1f, d / 10f);
        var r = go.GetComponent<Renderer>();
        if (r != null) r.sharedMaterial = mat;
    }

    // 用真实 CC0 贴图做材质；贴图是先铺在原始 UV 上的，所以按用途给不同 tiling
    static Material GetOrCreateTexMat(string assetName, string texPath, Vector2 tiling, float smoothness, Color? tint = null)
    {
        string path = MatFolder + "/" + assetName + ".mat";
        var shader = Shader.Find("Universal Render Pipeline/Lit");
        if (shader == null) shader = Shader.Find("Standard");

        var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (existing != null)
        {
            existing.SetTextureScale("_BaseMap", tiling);   // 已存在的资产也要重设 tiling
            if (existing.HasProperty("_BaseColor")) existing.SetColor("_BaseColor", tint ?? Color.white);
            EditorUtility.SetDirty(existing);
            return existing;
        }
        var m = new Material(shader) { name = assetName };

        var imp = AssetImporter.GetAtPath(texPath) as TextureImporter;
        if (imp != null)
        {
            imp.wrapMode = TextureWrapMode.Repeat;
            imp.textureType = TextureImporterType.Default;
            imp.sRGBTexture = true;
            imp.SaveAndReimport();
        }

        var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
        if (tex != null)
        {
            m.SetTexture("_BaseMap", tex);
            m.SetTextureScale("_BaseMap", tiling);
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", tint ?? Color.white);
        }
        else
        {
            m.color = new Color(0.5f, 0.5f, 0.5f);
        }
        if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", smoothness);
        if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", 0f);

        Directory.CreateDirectory(MatFolder);
        AssetDatabase.CreateAsset(m, path);
        AssetDatabase.SaveAssets();
        return m;
    }
    static Material GetOrCreateMat(string assetName, Color tint, float smoothness)
    {
        string path = MatFolder + "/" + assetName + ".mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m != null) return m;

        var shader = Shader.Find("Universal Render Pipeline/Lit");
        if (shader == null) shader = Shader.Find("Standard");
        m = new Material(shader) { name = assetName };
        m.color = tint;
        if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", smoothness);
        if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", 0f);

        Directory.CreateDirectory(MatFolder);
        AssetDatabase.CreateAsset(m, path);
        AssetDatabase.SaveAssets();
        return m;
    }
}
