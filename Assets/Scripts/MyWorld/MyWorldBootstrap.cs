using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace MyWorld
{
    /// <summary>
    /// 世界生成器。两种用法：
    ///
    /// **烘焙（推荐，默认）**：菜单 Tools → My World → 重建世界内容，在编辑期就把所有对象
    /// 生成成场景里的真实物体，材质/贴图/后处理存成 Assets 下的资源。之后可以在 Hierarchy 里
    /// 直接选中、拖动、删除，也可以逐个把图元换成导入的模型。此时 buildOnPlay 为 false，Play 不再生成。
    ///
    /// **运行时生成（buildOnPlay = true）**：Play 时才搭出世界，场景里只有一个空壳。适合纯代码定义关卡，
    /// 但编辑期看不到任何东西、也没法手工摆。
    ///
    /// 布局是手写的固定坐标而不是随机生成，方便一眼看出移动和碰撞对不对。
    /// </summary>
    [DisallowMultipleComponent]
    public class MyWorldBootstrap : MonoBehaviour
    {
        /// <summary>生成出来的场景根物体名字，重建前按这些名字清理旧的。</summary>
        public static readonly string[] GeneratedRootNames =
        {
            "World", "Sun", "Player", "Main Camera", "DioramaPostFx", "UI",
        };

        [Header("生成时机")]
        [Tooltip("Play 时是否重新生成整个世界。烘焙过的场景应当关掉，否则会生成两份")]
        [SerializeField] private bool buildOnPlay = false;

        [Header("世界")]
        [Tooltip("围墙围出的可达区域边长")]
        [SerializeField] private float playAreaSize = 56f;
        [Tooltip("地面边长。要比可达区域大一圈，否则走到边上镜头会露出地面外沿（相机不夹取，只能靠地面铺够大）")]
        [SerializeField] private float groundSize = 96f;
        [Tooltip("地面网格一格的边长")]
        [SerializeField] private float gridCellSize = 2f;
        [Tooltip("边界围墙高度，防止走出世界")]
        [SerializeField] private float boundaryHeight = 3f;

        [Header("玩家")]
        [SerializeField] private Vector3 playerStart = new Vector3(0f, 0.2f, -12f);
        [SerializeField] private float playerHeight = 1.7f;
        [SerializeField] private float playerRadius = 0.34f;
        [Tooltip("法师角色预制体（KayKit）。换角色只要换这个引用")]
        [SerializeField] private GameObject characterPrefab;
        [Tooltip("角色模型缩放。模型自带高度不一定和 CharacterController 匹配，用它对齐")]
        [SerializeField] private float characterScale = 0.68f;

        [Header("武器（由烘焙器自动填入）")]
        [SerializeField] private GameObject swordPrefab;
        [SerializeField] private GameObject staffPrefab;
        [SerializeField] private GameObject bowPrefab;
        [SerializeField] private GameObject shieldPrefab;
        [SerializeField] private GameObject ropeGunPrefab;
        [SerializeField] private GameObject gauntletPrefab;

        [Header("木桩")]
        [SerializeField] private bool buildDummies = true;

        [Header("敌人")]
        [Tooltip("敌人角色预制体（KayKit 蛮兵），由烘焙器自动填入")]
        [SerializeField] private GameObject enemyPrefab;
        [Tooltip("生成几个敌人")]
        [SerializeField] private int enemyCount = 3;

        [Header("相机")]
        [Tooltip("俯角：越大越接近正上方")]
        [SerializeField] private float camPitch = 52f;
        [Tooltip("相机到角色的距离，同时也是景深对焦距离")]
        [SerializeField] private float camDistance = 34f;
        [Tooltip("透视(长焦窄 FOV)：景深才正常，也是织梦岛重制版的做法")]
        [SerializeField] private bool camPerspective = true;
        [Tooltip("透视视场角。halfV = camDistance * tan(fov/2)，当前 34*tan15° ≈ 9 单位")]
        [SerializeField] private float camFieldOfView = 30f;
        [Tooltip("正交半高，仅 camPerspective=false 时生效")]
        [SerializeField] private float camOrthoSize = 9f;

        [Header("光照")]
        [SerializeField] private float sunYaw = -38f;
        [SerializeField] private float sunPitch = 46f;
        [SerializeField] private Color sunColor = new Color(1f, 0.96f, 0.88f);
        [SerializeField] private float sunIntensity = 1.15f;
        [SerializeField] private float shadowDistance = 70f;

        [Header("后处理")]
        [SerializeField] private bool enableDioramaPostFx = true;

        [Header("配色(占位)")]
        [SerializeField] private Color grassColor = new Color(0.36f, 0.62f, 0.28f);
        [SerializeField] private Color grassLineColor = new Color(0.30f, 0.54f, 0.23f);
        [SerializeField] private Color stoneColor = new Color(0.68f, 0.62f, 0.50f);
        [SerializeField] private Color roofColor = new Color(0.74f, 0.35f, 0.28f);
        [SerializeField] private Color trunkColor = new Color(0.42f, 0.30f, 0.20f);
        [SerializeField] private Color foliageColor = new Color(0.24f, 0.52f, 0.26f);
        [SerializeField] private Color rockColor = new Color(0.55f, 0.55f, 0.57f);
        [SerializeField] private Color waterColor = new Color(0.26f, 0.50f, 0.72f);
        [SerializeField] private Color hedgeColor = new Color(0.28f, 0.47f, 0.24f);
        [SerializeField] private Color playerColor = new Color(0.90f, 0.44f, 0.24f);

        private Transform worldRoot;
        private Camera cam;

        private Material grassMat, stoneMat, roofMat, trunkMat, foliageMat, rockMat, waterMat, hedgeMat;

        private void Start()
        {
            if (buildOnPlay) BuildAll();
        }

        /// <summary>
        /// 生成整套世界：光照、地形、道具、玩家、相机、后处理。
        /// 运行时有 buildOnPlay 把关；编辑期由 MyWorldBaker 直接调用（同时也用它做烘焙）。
        /// </summary>
        public void BuildAll()
        {
            BuildMaterials();
            BuildWorld();
            BuildLight();

            GameObject player = BuildPlayer();
            BuildCamera(player.transform);
            BuildPostFx();
        }

        /// <summary>清掉上一次生成出来的场景根物体，重建前先调用，避免叠出两份。</summary>
        public void ClearGenerated()
        {
            foreach (string n in GeneratedRootNames)
            {
                var go = GameObject.Find(n);
                int guard = 0;
                while (go != null && guard++ < 100)
                {
                    SafeDestroy(go);
                    go = GameObject.Find(n);
                }
            }
        }

        private static void SafeDestroy(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Object.Destroy(o);
            else Object.DestroyImmediate(o);
        }

        /// <summary>
        /// 材质名是有意义的：烘焙时每种材质会被存成 Assets/Generated/Materials 下的一个资源，
        /// 名字直接决定文件名，所以别用默认的（默认是着色器名，全都会重名）。
        /// </summary>
        private void BuildMaterials()
        {
            // 地面用一个大方块 + 方格贴图：没有参照物的话人会感觉不到自己在移动。
            // 贴图自带 8 格，所以重复次数 = 地面边长 / (格子边长 * 8)。
            grassMat = PlaceholderArt.NewGridMaterial(
                grassColor, grassLineColor, groundSize / (gridCellSize * 8f));
            grassMat.name = "M_Grass";

            stoneMat = PlaceholderArt.NewLit(stoneColor, 0.1f);
            stoneMat.name = "M_Stone";
            roofMat = PlaceholderArt.NewLit(roofColor, 0.14f);
            roofMat.name = "M_Roof";
            trunkMat = PlaceholderArt.NewLit(trunkColor, 0.05f);
            trunkMat.name = "M_Trunk";
            foliageMat = PlaceholderArt.NewLit(foliageColor, 0.05f);
            foliageMat.name = "M_Foliage";
            rockMat = PlaceholderArt.NewLit(rockColor, 0.18f);
            rockMat.name = "M_Rock";
            waterMat = PlaceholderArt.NewLit(waterColor, 0.72f);
            waterMat.name = "M_Water";
            hedgeMat = PlaceholderArt.NewLit(hedgeColor, 0.05f);
            hedgeMat.name = "M_Hedge";
        }

        // ---------------- 世界 ----------------

        private void BuildWorld()
        {
            // 所有生成物都放在场景根下（不挂在 bootstrap 下面）：
            // 相机固定 yaw=0 依赖世界坐标，一旦被有旋转的父节点带着走，8 方向就会错位。
            worldRoot = new GameObject("World").transform;

            BuildGround();
            BuildBoundary();
            BuildLandmarks();
            BuildHouses();
            BuildHedges();
            BuildTrees();
            BuildRocks();
            if (buildDummies) BuildDummies();
            BuildEnemies();
        }

        /// <summary>生成敌人。位置避开房子/树篱，保证它们有路能走过来。</summary>
        private void BuildEnemies()
        {
            if (enemyPrefab == null || enemyCount <= 0) return;

            Vector3[] spots =
            {
                new Vector3(-14f, 0f, -16f), new Vector3(14f, 0f, -16f),
                new Vector3(0f, 0f, 20f), new Vector3(-18f, 0f, 8f),
                new Vector3(18f, 0f, -18f), new Vector3(8f, 0f, 16f),
            };

            var root = NewProp("Enemies", Vector3.zero);
            for (int i = 0; i < Mathf.Min(enemyCount, spots.Length); i++)
            {
                var inst = Instantiate(enemyPrefab, spots[i], Quaternion.identity, root.transform);
                inst.name = "Enemy" + i;

                // 敌人也要能被抓钩拉、被锁定、被打血，所以给它一个血条
                var enemy = inst.GetComponent<Enemy>();
                if (enemy == null) enemy = inst.AddComponent<Enemy>();

                // 敌人要自己走路、还得撞墙，所以配个和身体匹配的 CharacterController。
                // 注意：CharacterController 会**跟随 transform 缩放**，而敌人根节点缩放 0.68，
                // 所以这里要除以缩放，才能得到想要的世界尺寸（否则 1.95 会变成 1.33，目标小一圈抓不到）。
                var ecc = inst.GetComponent<CharacterController>();
                if (ecc == null) ecc = inst.AddComponent<CharacterController>();
                float s = Mathf.Max(0.01f, inst.transform.lossyScale.y);
                ecc.height = 1.9f / s;
                ecc.radius = 0.45f / s;
                ecc.center = new Vector3(0f, 0.95f / s, 0f);
                ecc.slopeLimit = 50f;
                ecc.stepOffset = 0.4f / s;
                ecc.skinWidth = 0.03f / s;

                var bar = HealthBar.Attach(inst.transform, 2.6f, new Color(0.9f, 0.3f, 0.28f));
                enemy.AttachHealthBar(bar);
            }
        }

        /// <summary>
        /// 一排带血条的木桩，摆在出生点正前方，方便一进来就能试法术。
        /// 位置避开了房子和树篱，保证有开阔的射击走廊。
        /// </summary>
        private void BuildDummies()
        {
            Vector3[] spots =
            {
                new Vector3(-5.5f, 0f, -5.5f), new Vector3(-1.8f, 0f, -5.5f),
                new Vector3(1.8f, 0f, -5.5f),  new Vector3(5.5f, 0f, -5.5f),
            };

            var root = NewProp("Dummies", Vector3.zero);
            var woodMat = PlaceholderArt.NewLit(new Color(0.48f, 0.33f, 0.20f), 0.1f);
            woodMat.name = "M_DummyWood";
            var headMat = PlaceholderArt.NewLit(new Color(0.62f, 0.48f, 0.32f), 0.1f);
            headMat.name = "M_DummyHead";

            for (int i = 0; i < spots.Length; i++)
            {
                var d = NewProp("Dummy" + i, spots[i], root);

                // 立柱：Cylinder 图元高 2、直径 1，缩放后半径 0.26、高 2.3
                PlaceholderArt.Primitive(PrimitiveType.Cylinder, d.transform, "Post",
                    new Vector3(0f, 1.15f, 0f), new Vector3(0.52f, 1.15f, 0.52f), woodMat);

                // 横臂：给个"人形"轮廓，也让命中判定宽一点
                PlaceholderArt.Primitive(PrimitiveType.Cube, d.transform, "Arm",
                    new Vector3(0f, 1.6f, 0f), new Vector3(1.7f, 0.18f, 0.2f), woodMat);

                // 头
                PlaceholderArt.Primitive(PrimitiveType.Sphere, d.transform, "Head",
                    new Vector3(0f, 2.35f, 0f), new Vector3(0.55f, 0.55f, 0.55f), headMat);

                // 加一个比外形大一圈的碰撞箱：木桩本身很细（半径 0.26），
                // 而抓钩的钩头是一条射线，细柱子很容易擦过去抓不到。
                var hitbox = d.AddComponent<CapsuleCollider>();
                hitbox.radius = 0.7f;
                hitbox.height = 2.6f;
                hitbox.center = new Vector3(0f, 1.3f, 0f);
                hitbox.direction = 1;   // Y 轴

                // 木桩不做遮挡淡出：FadeableObject 和受击闪白都要换材质，两套会互相打架，
                // 而且木桩很矮，本来也挡不住视线。
                var dummy = d.AddComponent<TrainingDummy>();
                var bar = HealthBar.Attach(d.transform, 2.85f, new Color(0.35f, 0.85f, 0.4f));
                dummy.AttachHealthBar(bar);
            }
        }

        private void BuildGround()
        {
            // 立方体厚 1，中心下沉 0.5 让顶面正好落在 y=0。
            PlaceholderArt.Primitive(PrimitiveType.Cube, worldRoot, "Ground",
                new Vector3(0f, -0.5f, 0f),
                new Vector3(groundSize, 1f, groundSize),
                grassMat);
        }

        private void BuildBoundary()
        {
            float h = boundaryHeight;
            float half = playAreaSize * 0.5f;
            float t = 1.2f;
            float len = playAreaSize + t;

            // 每面墙各自一个淡出组：共用一组的话，任意一面挡视线会把四面一起变透明。
            BuildFadeableBox("WallNorth", new Vector3(0f, h * 0.5f, half), new Vector3(len, h, t), stoneMat, 0.18f);
            BuildFadeableBox("WallSouth", new Vector3(0f, h * 0.5f, -half), new Vector3(len, h, t), stoneMat, 0.18f);
            BuildFadeableBox("WallEast", new Vector3(half, h * 0.5f, 0f), new Vector3(t, h, len), stoneMat, 0.18f);
            BuildFadeableBox("WallWest", new Vector3(-half, h * 0.5f, 0f), new Vector3(t, h, len), stoneMat, 0.18f);
        }

        private void BuildLandmarks()
        {
            // 一个小水塘，给俯视图加个色块对比。
            var pond = NewProp("Pond", new Vector3(18f, 0f, 18f));
            AddBox(pond, "Water", new Vector3(0f, 0.06f, 0f), new Vector3(8f, 0.12f, 8f), waterMat);

            // 一座矮台，用来确认角色确实站在地面上而不是浮空。
            var plinth = NewProp("Plinth", new Vector3(-16f, 0f, -2f));
            AddBox(plinth, "Base", new Vector3(0f, 0.25f, 0f), new Vector3(5f, 0.5f, 5f), stoneMat);
            PlaceholderArt.MakeFadeable(plinth, 0.3f);
        }

        private void BuildHouses()
        {
            BuildHouse(new Vector3(-10f, 0f, 6f), new Vector3(7f, 3.2f, 5.5f));
            BuildHouse(new Vector3(9f, 0f, 8f), new Vector3(6f, 3.0f, 6f));
            BuildHouse(new Vector3(-7f, 0f, -9f), new Vector3(5.5f, 2.8f, 4.5f));
            BuildHouse(new Vector3(11f, 0f, -6f), new Vector3(5f, 3.4f, 5f));
        }

        private void BuildHouse(Vector3 center, Vector3 size)
        {
            var root = NewProp("House", center);
            AddBox(root, "Body", new Vector3(0f, size.y * 0.5f, 0f), size, stoneMat);
            // 屋顶比墙体稍微出挑一圈，读起来才像房子。
            AddBox(root, "Roof", new Vector3(0f, size.y + 0.18f, 0f),
                new Vector3(size.x + 0.6f, 0.36f, size.z + 0.6f), roofMat);
            PlaceholderArt.MakeFadeable(root, 0.2f);
        }

        private void BuildHedges()
        {
            // 低矮树篱：高度刚好到角色腰，用来感受"能挡住"和"能绕过去"。
            BuildFadeableBox("Hedge0", new Vector3(-4f, 0.45f, -3f), new Vector3(10f, 0.9f, 0.7f), hedgeMat, 0.28f);
            BuildFadeableBox("Hedge1", new Vector3(1f, 0.45f, 1f), new Vector3(0.7f, 0.9f, 8f), hedgeMat, 0.28f);
            BuildFadeableBox("Hedge2", new Vector3(4f, 0.45f, -11f), new Vector3(9f, 0.9f, 0.7f), hedgeMat, 0.28f);
            BuildFadeableBox("Hedge3", new Vector3(-13f, 0.45f, 12f), new Vector3(0.7f, 0.9f, 7f), hedgeMat, 0.28f);
        }

        private void BuildTrees()
        {
            Vector3[] spots =
            {
                new Vector3(-18f, 0f, -14f), new Vector3(-14f, 0f, 12f), new Vector3(-21f, 0f, 3f),
                new Vector3(16f, 0f, 15f), new Vector3(20f, 0f, -13f), new Vector3(14f, 0f, 2f),
                new Vector3(-3f, 0f, 16f), new Vector3(4f, 0f, 18f), new Vector3(-16f, 0f, 19f),
                new Vector3(21f, 0f, 6f), new Vector3(2f, 0f, -18f), new Vector3(-11f, 0f, -17f),
                new Vector3(-24f, 0f, -6f), new Vector3(24f, 0f, 12f),
            };

            var root = NewProp("Trees", Vector3.zero);
            for (int i = 0; i < spots.Length; i++)
            {
                var treeRoot = NewProp("Tree" + i, spots[i], root);
                AddBox(treeRoot, "Trunk", new Vector3(0f, 0.9f, 0f), new Vector3(0.44f, 1.8f, 0.44f), trunkMat);
                AddBox(treeRoot, "Foliage", new Vector3(0f, 2.5f, 0f), new Vector3(3.1f, 2.6f, 3.1f), foliageMat);
                AddBox(treeRoot, "FoliageTop", new Vector3(0f, 3.9f, 0f), new Vector3(2.0f, 1.6f, 2.0f), foliageMat);
                PlaceholderArt.MakeFadeable(treeRoot, 0.2f);
            }
        }

        private void BuildRocks()
        {
            Vector3[] spots =
            {
                new Vector3(6f, 0f, -14f), new Vector3(-6f, 0f, 14f), new Vector3(17f, 0f, -3f),
                new Vector3(-19f, 0f, -9f), new Vector3(13f, 0f, -17f), new Vector3(-1f, 0f, 9f),
                new Vector3(23f, 0f, -2f), new Vector3(-9f, 0f, 20f),
            };

            var root = NewProp("Rocks", Vector3.zero);
            for (int i = 0; i < spots.Length; i++)
            {
                var rockRoot = NewProp("Rock" + i, spots[i], root);
                float s = 1.1f + (i % 3) * 0.35f;
                AddBox(rockRoot, "Rock", new Vector3(0f, s * 0.3f, 0f), new Vector3(s, s * 0.6f, s * 0.85f), rockMat);
                rockRoot.transform.localRotation = Quaternion.Euler(0f, i * 37f, 0f);
                PlaceholderArt.MakeFadeable(rockRoot, 0.3f);
            }
        }

        // ---------------- 图元辅助 ----------------

        /// <summary>建一个带淡出组件的道具根节点（子网格共用一次淡出切换）。</summary>
        private GameObject NewProp(string name, Vector3 position, GameObject parent = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent != null ? parent.transform : worldRoot, false);
            go.transform.localPosition = position;
            return go;
        }

        /// <summary>在道具根节点下摆一个立方体（图元自带 BoxCollider，正好当碰撞用）。</summary>
        private GameObject AddBox(GameObject parent, string name, Vector3 localPos, Vector3 size, Material mat)
        {
            return PlaceholderArt.Primitive(PrimitiveType.Cube, parent.transform, name, localPos, size, mat);
        }

        /// <summary>摆放一个独立的、可单独淡出的方块（自己就是一个道具根节点）。</summary>
        private void BuildFadeableBox(string name, Vector3 center, Vector3 size, Material mat, float fadedAlpha)
        {
            var root = NewProp(name, center);
            AddBox(root, "Mesh", Vector3.zero, size, mat);
            PlaceholderArt.MakeFadeable(root, fadedAlpha);
        }

        // ---------------- 光照 ----------------

        private void BuildLight()
        {
            // 环境光给一个偏冷的底色，让背光面不至于死黑。
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.42f, 0.46f, 0.52f);
            QualitySettings.shadowDistance = shadowDistance;

            var go = new GameObject("Sun");
            go.transform.rotation = Quaternion.Euler(sunPitch, sunYaw, 0f);

            var light = go.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = sunColor;
            light.intensity = sunIntensity;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.72f;
        }

        // ---------------- 玩家 ----------------

        private GameObject BuildPlayer()
        {
            var go = new GameObject("Player");
            go.transform.position = playerStart;

            // 根节点放 CharacterController 和逻辑，视觉挂在子节点上，转动根节点即可换朝向。
            var cc = go.AddComponent<CharacterController>();
            cc.height = playerHeight;
            cc.radius = playerRadius;
            cc.center = new Vector3(0f, playerHeight * 0.5f, 0f);
            cc.slopeLimit = 50f;
            cc.stepOffset = 0.4f;
            cc.skinWidth = 0.03f;

            go.AddComponent<MyWorldInput>();
            go.AddComponent<PlayerController8Dir>();
            go.AddComponent<PlayerAim>();      // 朝向跟随鼠标
            go.AddComponent<PlayerLockOn>();   // Q 锁定

            BuildCharacterVisual(go.transform);

            go.AddComponent<PlayerMage>();     // 只驱动 Animator
            go.AddComponent<WeaponMount>();    // 把武器挂到 handslot.r / handslot.l

            // 抓钩参数单独一个子物体，方便在 Hierarchy 里点开就调（不和其他参数混在一起）
            var grappleGo = new GameObject("Grapple");
            grappleGo.transform.SetParent(go.transform, false);
            var grappleSettings = grappleGo.AddComponent<GrappleSettings>();
            var grapple = go.AddComponent<GrappleWeapon>();
            grapple.SetSettings(grappleSettings);

            BuildLoadout(go);
            go.AddComponent<PlayerHealth>();   // 敌人近战要打这个
            go.AddComponent<PlayerCombat>();   // 输入分发 + 各武器行为

            BuildUi(go);
            return go;
        }

        /// <summary>
        /// 界面根节点。UI 是在运行时用代码搭的（不生成 UI 资源文件），
        /// 这里只放一个挂着 GameUi 的空物体，并把玩家身上的引用接好。
        /// 引用必须落在**序列化字段**上，否则烘焙后重载会变 null。
        /// </summary>
        private void BuildUi(GameObject player)
        {
            var go = new GameObject("UI");
            var ui = go.AddComponent<GameUi>();
            ui.Configure(
                player.GetComponent<MyWorldInput>(),
                player.GetComponent<WeaponLoadout>(),
                player.GetComponentInChildren<WeaponMount>(),
                player.GetComponent<PlayerCombat>(),
                player.GetComponent<PlayerHealth>());
        }

        /// <summary>
        /// 把六把武器全部登记成"已拥有"，默认装备主手法杖 + 副手抓钩。
        /// 换武器在 Tab → 武器页里点选（两槽各只能装一件；弓和盾互斥）。
        /// </summary>
        private void BuildLoadout(GameObject player)
        {
            var loadout = player.AddComponent<WeaponLoadout>();

            // ---- 主手 ----
            var staff = new WeaponDefinition
            {
                displayName = "法杖", kind = WeaponKind.Staff, slot = HandSlot.MainHand,
                model = staffPrefab, damage = 26f, cooldown = 0.55f,
            };
            var sword = new WeaponDefinition
            {
                displayName = "剑", kind = WeaponKind.Sword, slot = HandSlot.MainHand,
                model = swordPrefab, damage = 20f, cooldown = 0.66f,
                meleeRange = 2.0f, meleeHalfAngle = 65f,
                // 连招四段：横劈 → 下劈 → 斜劈 → 突刺。最后一段突刺把敌人打飞 2 格（4 米）。
                stabKnockbackGrids = 2f,
            };
            var bow = new WeaponDefinition
            {
                displayName = "弓", kind = WeaponKind.Bow, slot = HandSlot.MainHand,
                model = bowPrefab, damage = 18f, cooldown = 0.7f,
                arrowSpeed = 34f, arrowLifeTime = 1.6f,
            };

            // ---- 副手 ----
            // 抓钩的行为参数不在这里 —— 在 Player → Grapple 的 GrappleSettings 组件上
            var grapple = new WeaponDefinition
            {
                displayName = "抓钩", kind = WeaponKind.Grapple, slot = HandSlot.OffHand,
                model = ropeGunPrefab, cooldown = 0.3f,
            };
            var shield = new WeaponDefinition
            {
                displayName = "盾", kind = WeaponKind.Shield, slot = HandSlot.OffHand,
                model = shieldPrefab, cooldown = 0.6f,
                shieldBashDamage = 6f, shieldBashKnockbackGrids = 2f, shieldBashRange = 2.6f,
                blockDamageMultiplier = 0.25f,
            };
            var gauntlet = new WeaponDefinition
            {
                displayName = "魔法护手", kind = WeaponKind.Gauntlet, slot = HandSlot.OffHand,
                model = gauntletPrefab, cooldown = 0.35f, damage = 18f,
                castSpeedMultiplier = 1.5f, castDamageMultiplier = 0.3f,
            };

            loadout.RegisterOwned(staff);
            loadout.RegisterOwned(sword);
            loadout.RegisterOwned(bow);
            loadout.RegisterOwned(grapple);
            loadout.RegisterOwned(shield);
            loadout.RegisterOwned(gauntlet);

            loadout.SetEquipped(staff, grapple);
        }

        /// <summary>
        /// 生成角色外观。编辑期要走 PrefabUtility 才能保住预制体连接（换模型方便），
        /// 运行时直接 Instantiate。没配预制体时退回到原来的占位胶囊，免得整个场景起不来。
        /// </summary>
        private void BuildCharacterVisual(Transform parent)
        {
            if (characterPrefab == null)
            {
                Debug.LogWarning("[My World] 没配 characterPrefab，玩家先用占位胶囊。");
                var fallbackMat = PlaceholderArt.NewLit(playerColor, 0.12f);
                fallbackMat.name = "M_PlayerBody";
                var body = PlaceholderArt.Primitive(PrimitiveType.Capsule, parent, "Body",
                    new Vector3(0f, playerHeight * 0.5f, 0f),
                    new Vector3(playerRadius * 2f, playerHeight * 0.5f, playerRadius * 2f),
                    fallbackMat);
                PlaceholderArt.StripCollider(body);
                return;
            }

            GameObject visual;
#if UNITY_EDITOR
            if (!Application.isPlaying)
                visual = (GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(characterPrefab, parent);
            else
                visual = Instantiate(characterPrefab, parent);
#else
            visual = Instantiate(characterPrefab, parent);
#endif
            visual.name = "Character";
            visual.transform.localPosition = Vector3.zero;
            visual.transform.localRotation = Quaternion.identity;
            visual.transform.localScale = Vector3.one * characterScale;
        }

        // ---------------- 相机 ----------------

        private void BuildCamera(Transform target)
        {
            var go = new GameObject("Main Camera");
            go.tag = "MainCamera";

            cam = go.AddComponent<Camera>();
            if (Object.FindFirstObjectByType<AudioListener>() == null)
                go.AddComponent<AudioListener>();

            var rig = go.AddComponent<TopDownCameraRig>();
            rig.Configure(target);
            rig.ConfigureCamera(camPitch, camDistance, camPerspective, camFieldOfView, camOrthoSize);
            // 立刻摆好机位：编辑期烘焙时不会跑 Start，不主动调用的话相机在场景里是默认状态。
            rig.ApplySetup();
        }

        // ---------------- 后处理 ----------------

        private void BuildPostFx()
        {
            if (cam == null) return;

            // 相机必须显式打开后处理，否则挂了 Volume 也不会生效。
            var camData = cam.GetUniversalAdditionalCameraData();
            if (camData != null) camData.renderPostProcessing = enableDioramaPostFx;

            if (!enableDioramaPostFx) return;

            var go = new GameObject("DioramaPostFx");
            go.AddComponent<Volume>();
            var fx = go.AddComponent<DioramaPostFx>();
            // 对焦距离取相机到角色的距离，正好让角色所在的平面最清晰、前后发虚。
            fx.Configure(camDistance);
        }
    }
}
