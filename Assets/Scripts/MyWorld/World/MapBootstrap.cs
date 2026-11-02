using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace MyWorld
{
    /// <summary>
    /// 新地图的基类：场景里只放一个挂子类组件的空物体，进 Play 时用 C# 现场生成整张地图。
    ///
    /// 为什么运行时生成而不是烘焙：新地图由 agent 写代码批量摆放（几百个物件），
    /// 烘焙进 .unity 会让场景文件巨大且难 diff；运行时生成的代价是首帧稍慢，可接受。
    ///
    /// 子类只需要实现 <see cref="BuildMapContent"/>；地面/边界/光照/玩家/相机/UI 由基类负责。
    /// </summary>
    public abstract class MapBootstrap : MonoBehaviour
    {
        [Header("地图")]
        [SerializeField] private MapId mapId = MapId.RoaTown;
        [SerializeField] private bool buildOnPlay = true;
        [Tooltip("已用 Tools/My World/烘焙地图进场景 把地图存成场景实体对象时勾上；" +
                 "进 Play 就不会再重复生成一遍（否则会和老地图叠在一起）")]
        [SerializeField] private bool bakedIntoScene = false;
        [Tooltip("传送过来时没带出生点名就用这个")]
        [SerializeField] private string defaultSpawnId = "start";
        [Tooltip("地图里没放 SpawnMarker 时的兜底落点")]
        [SerializeField] private Vector3 playerStart = new Vector3(0f, 0.2f, -10f);

        [Header("玩家资源（由 MapSceneSetup 在编辑器里填）")]
        [SerializeField] private GameObject characterPrefab;
        [Tooltip("顺序固定：法杖、剑、弓、抓钩、盾、魔法护手")]
        [SerializeField] private GameObject[] weaponPrefabs = new GameObject[6];
        [SerializeField] private GameObject npcPrefab;
        [SerializeField] private GameObject enemyPrefab;
        [SerializeField] private float characterScale = 0.68f;

        [Header("相机")]
        [SerializeField] private float camPitch = 52f;
        [SerializeField] private float camDistance = 22f;
        [SerializeField] private bool camPerspective = true;
        [SerializeField] private float camFieldOfView = 30f;
        [SerializeField] private float camOrthoSize = 9f;

        [Header("光照")]
        [SerializeField] private float sunYaw = -38f;
        // 46° 的斜射光会让 5 m 宽的街道整条落进阴影（实测王都街面 82% 是暗像素）。
        // 织梦岛的日照接近正午：太阳高、影子短、街面亮，靠 AO 和接触阴影出体积。
        [SerializeField] private float sunPitch = 58f;
        [SerializeField] private float sunIntensity = 1.45f;
        [SerializeField] private Color sunColor = new Color(1f, 0.95f, 0.86f);
        [Tooltip("阴影浓度。0.9 以上阴影接近全黑，玩具模型感要的是柔和的半透明影子。")]
        [SerializeField, Range(0f, 1f)] private float shadowStrength = 0.62f;
        [SerializeField] private Color ambientColor = new Color(0.50f, 0.54f, 0.60f);
        [SerializeField] private float shadowDistance = 140f;

        [Header("地面")]
        [Tooltip("地面尺寸（米）。地图内容应保持在这个范围内，边界墙在 ±groundSize/2")]
        [SerializeField] private int groundSize = 120;
        [SerializeField] private float boundaryHeight = 3.2f;
        [SerializeField] private string groundMaterial = "grass";

        private Transform worldRoot;
        private GameObject playerObject;
        private Camera mainCamera;
        private Transform playerTransform;

        // ---------- 给地图生成器用的公开入口 ----------
        public MapId MapId => mapId;
        public Transform World => worldRoot;
        public Transform PlayerTransform => playerTransform;
        public GameObject PlayerObject => playerObject;
        public Camera MainCamera => mainCamera;
        public GameObject CharacterPrefab => characterPrefab;
        public GameObject NpcPrefab => npcPrefab;
        public GameObject EnemyPrefab => enemyPrefab;
        public GameObject[] WeaponPrefabs => weaponPrefabs;
        public float CharacterScale => characterScale;
        public int GroundSize => groundSize;
        public string DefaultSpawnId => defaultSpawnId;

        private void Awake()
        {
            // 即使用烘焙好的场景，也先把 GameSession 起起来（它只管运行时单例，不会生成地图）
            GameSession.EnsureInitialized();
            Active = this;
            if (buildOnPlay && !bakedIntoScene) BuildAll();
        }

        /// <summary>当前场景里活着的 MapBootstrap。给运行时补内容（家具、装饰）用。</summary>
        public static MapBootstrap Active { get; private set; }

        /// <summary>生成整张地图。可重复调用（会先清空上一次的生成物）。</summary>
        public void BuildAll()
        {
            GameSession.EnsureInitialized();
            ClearGenerated();

            SetWorldLighting();

            // ⚠️ 必须挂到本对象下：`ClearGenerated()` 是按 `transform.Find("World")` 找旧世界的。
            //    曾经漏了 SetParent，导致 World 变成**场景根对象**、永远清不掉 ——
            //    Play 中只要发生一次域重载（队友改脚本）Awake 就会重跑，整座城市被建两遍
            //    （实测：两个根级 World、NPC/商店/Transform 全部翻倍且完全重叠）。
            worldRoot = new GameObject("World").transform;
            worldRoot.SetParent(transform, false);

            BuildEnvironment(worldRoot);
            BuildMapContent(worldRoot);
            BuildSystems(worldRoot);

            string spawnId = PickSpawnId();
            Vector3 spawnPos = ResolveSpawn(spawnId);
            BuildPlayer(spawnPos, spawnId);
            BuildCamera();
            BuildPostFx();
        }

        // ================= 子类实现 =================

        /// <summary>地图内容（建筑、道路、NPC、传送门、敌人……）。</summary>
        protected abstract void BuildMapContent(Transform world);

        /// <summary>地面与边界。默认草地 + 石墙；城市/村庄可以重写成石板/河流。</summary>
        protected virtual void BuildEnvironment(Transform world)
        {
            var groundRoot = new GameObject("Ground").transform;
            groundRoot.SetParent(world, false);
            var groundMat = MapMaterials.Get(groundMaterial);
            var ground = PlaceholderArt.Primitive(PrimitiveType.Cube, groundRoot, "Ground",
                new Vector3(0f, -0.5f, 0f), new Vector3(groundSize, 1f, groundSize), groundMat);
            // 地面必须保留 BoxCollider：玩家和敌人都是用 CharacterController + 重力落地，
            // 把地面碰撞体删掉会导致运行时生成的整张地图里所有角色直接往下掉。
            ground.GetComponent<BoxCollider>().isTrigger = false;

            BuildBoundary(world);
        }

        /// <summary>系统类物件（传送门总站、篝火等）。默认空。</summary>
        protected virtual void BuildSystems(Transform world)
        {
        }

        /// <summary>边界墙：四面，挡住玩家也避免看到地图外的虚空。</summary>
        protected void BuildBoundary(Transform world, float height = -1f)
        {
            if (height < 0f) height = boundaryHeight;
            var stone = MapMaterials.Get("stone_dark");
            var wallRoot = new GameObject("Boundary").transform;
            wallRoot.SetParent(world, false);
            float half = groundSize * 0.5f;
            float t = 1.2f;
            BuildWall(wallRoot, "WallNorth", new Vector3(0f, height * 0.5f, half), new Vector3(groundSize + t, height, t), stone);
            BuildWall(wallRoot, "WallSouth", new Vector3(0f, height * 0.5f, -half), new Vector3(groundSize + t, height, t), stone);
            BuildWall(wallRoot, "WallEast", new Vector3(half, height * 0.5f, 0f), new Vector3(t, height, groundSize + t), stone);
            BuildWall(wallRoot, "WallWest", new Vector3(-half, height * 0.5f, 0f), new Vector3(t, height, groundSize + t), stone);
        }

        private void BuildWall(Transform parent, string name, Vector3 center, Vector3 size, Material mat)
        {
            var root = new GameObject(name);
            root.transform.SetParent(parent, false);
            root.transform.localPosition = center;
            var mesh = PlaceholderArt.Primitive(PrimitiveType.Cube, root.transform, "Mesh", Vector3.zero, size, mat);
            PlaceholderArt.StripCollider(mesh);
            var col = root.AddComponent<BoxCollider>();
            col.size = size;
            PlaceholderArt.MakeFadeable(root, 0.2f);
        }

        // ================= 玩家 =================

        private string PickSpawnId()
        {
            string id;
            if (GameSession.TryConsumeSpawn(mapId, out id) && !string.IsNullOrEmpty(id)) return id;
            return defaultSpawnId;
        }

        protected virtual Vector3 ResolveSpawn(string spawnId)
        {
            if (!string.IsNullOrEmpty(spawnId))
            {
                var markers = worldRoot != null ? worldRoot.GetComponentsInChildren<SpawnMarker>() : null;
                if (markers != null)
                {
                    for (int i = 0; i < markers.Length; i++)
                        if (markers[i].id == spawnId) return markers[i].transform.position + Vector3.up * 0.2f;
                }
            }
            return playerStart;
        }

        private void BuildPlayer(Vector3 spawnPos, string spawnId)
        {
            var go = new GameObject("Player");
            go.transform.position = spawnPos;

            var cc = go.AddComponent<CharacterController>();
            cc.height = 1.7f;
            cc.radius = 0.34f;
            cc.center = new Vector3(0f, 0.85f, 0f);
            cc.slopeLimit = 50f;
            cc.stepOffset = 0.45f;
            cc.skinWidth = 0.03f;

            go.AddComponent<MyWorldInput>();
            go.AddComponent<PlayerController8Dir>();
            go.AddComponent<PlayerAim>();
            go.AddComponent<PlayerLockOn>();

            BuildCharacterVisual(go.transform);

            go.AddComponent<PlayerMage>();
            go.AddComponent<WeaponMount>();

            var grappleGo = new GameObject("Grapple");
            grappleGo.transform.SetParent(go.transform, false);
            var grappleSettings = grappleGo.AddComponent<GrappleSettings>();
            var grapple = go.AddComponent<GrappleWeapon>();
            grapple.SetSettings(grappleSettings);

            BuildLoadout(go);
            go.AddComponent<PlayerHealth>();
            go.AddComponent<PlayerCombat>();
            go.AddComponent<GameAudio>();
            go.AddComponent<PlayerInteractor>();   // 新地图上所有可交互物都靠它

            BuildUi(go);
            playerObject = go;
            playerTransform = go.transform;
        }

        private void BuildCharacterVisual(Transform parent)
        {
            if (characterPrefab == null)
            {
                Debug.LogWarning("[MapBootstrap] 没配 characterPrefab，玩家先用占位胶囊。");
                var body = PlaceholderArt.Primitive(PrimitiveType.Capsule, parent, "Body",
                    new Vector3(0f, 0.85f, 0f), new Vector3(0.68f, 0.85f, 0.68f),
                    MapMaterials.Solid("fallback_player", new Color(0.9f, 0.44f, 0.24f)));
                PlaceholderArt.StripCollider(body);
                return;
            }
            var visual = Instantiate(characterPrefab, parent);
            visual.name = "Character";
            visual.transform.localPosition = Vector3.zero;
            visual.transform.localRotation = Quaternion.identity;
            visual.transform.localScale = Vector3.one * characterScale;
        }

        private void BuildLoadout(GameObject player)
        {
            var loadout = player.AddComponent<WeaponLoadout>();
            var defs = WeaponDefs.CreateAll(weaponPrefabs);
            for (int i = 0; i < defs.Length; i++) loadout.RegisterOwned(defs[i]);

            WeaponDefinition main = defs[0];   // 法杖
            WeaponDefinition off = defs[3];    // 抓钩
            if (GameSession.HasEquipment)
            {
                var savedMain = WeaponDefs.Find(defs, GameSession.EquippedMain);
                var savedOff = WeaponDefs.Find(defs, GameSession.EquippedOff);
                if (savedMain != null) main = savedMain;
                if (savedOff != null) off = savedOff;
            }
            loadout.SetEquipped(main, off);
            loadout.SetUnarmed(WeaponDefs.Unarmed());
        }

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

            var bridge = player.AddComponent<SessionBridge>();
            bridge.Configure(player.GetComponent<PlayerHealth>(), player.GetComponent<WeaponLoadout>(), ui);
        }

        // ================= 相机 / 光照 / 后处理 =================

        private void BuildCamera()
        {
            var go = new GameObject("Main Camera");
            go.tag = "MainCamera";

            mainCamera = go.AddComponent<Camera>();
            if (Object.FindFirstObjectByType<AudioListener>() == null)
                go.AddComponent<AudioListener>();

            var rig = go.AddComponent<TopDownCameraRig>();
            rig.Configure(playerTransform);
            rig.ConfigureCamera(camPitch, camDistance, camPerspective, camFieldOfView, camOrthoSize);
            rig.ApplySetup();
        }

        private void BuildPostFx()
        {
            if (mainCamera == null) return;
            var camData = mainCamera.GetUniversalAdditionalCameraData();
            if (camData != null) camData.renderPostProcessing = true;

            var go = new GameObject("DioramaPostFx");
            go.AddComponent<Volume>();
            var fx = go.AddComponent<DioramaPostFx>();
            fx.Configure(camDistance);   // 景深对焦距离 = 相机到角色的距离
        }

        private void SetWorldLighting()
        {
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = ambientColor;
            QualitySettings.shadowDistance = shadowDistance;

            // 场景里往往已经放了一盏太阳（烘焙场景就是这样）。以前这里撞见现成的太阳
            // 就直接 return，于是 Inspector 上的 sunPitch / sunIntensity / sunColor 全部
            // 失效，实际生效的是场景里那盏 46° 的斜射光：街道整条落进阴影，实测截图
            // 80–97% 是暗像素，评审只能看见一片黑。现在不论场景里有没有太阳，都由这里
            // 接管参数——要改光照只改这一个地方。
            var sun = Object.FindFirstObjectByType<Light>();
            if (sun == null || sun.type != LightType.Directional)
            {
                var go = new GameObject("Sun");
                sun = go.AddComponent<Light>();
                sun.type = LightType.Directional;
            }
            sun.transform.rotation = Quaternion.Euler(sunPitch, sunYaw, 0f);
            sun.color = sunColor;
            sun.intensity = sunIntensity;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = shadowStrength;
        }

        // ================= 生成辅助（地图子类直接用） =================

        protected GameObject Prop(string name, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent != null ? parent : worldRoot, false);
            return go;
        }

        /// <summary>摆一个方盒。collider=true 时自带 BoxCollider（走不过去/打得到）。</summary>
        protected GameObject Box(Transform parent, string name, Vector3 pos, Vector3 size, Material mat,
            float yaw = 0f, bool collider = true, float fadeAlpha = -1f)
        {
            var go = PlaceholderArt.Primitive(PrimitiveType.Cube, parent, name, pos, size, mat);
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            if (!collider) PlaceholderArt.StripCollider(go);
            if (fadeAlpha >= 0f) PlaceholderArt.MakeFadeable(go, fadeAlpha);
            return go;
        }

        protected GameObject Cyl(Transform parent, string name, Vector3 pos, Vector3 size, Material mat,
            float yaw = 0f, bool collider = true)
        {
            var go = PlaceholderArt.Primitive(PrimitiveType.Cylinder, parent, name, pos, size, mat);
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            if (!collider) PlaceholderArt.StripCollider(go);
            return go;
        }

        protected GameObject Sphere(Transform parent, string name, Vector3 pos, Vector3 size, Material mat, bool collider = false)
        {
            var go = PlaceholderArt.Primitive(PrimitiveType.Sphere, parent, name, pos, size, mat);
            if (!collider) PlaceholderArt.StripCollider(go);
            return go;
        }

        protected SpawnMarker PlaceSpawn(string id, Vector3 pos, float yaw = 0f)
        {
            return SpawnMarker.Create(worldRoot, id, pos, yaw);
        }

        protected GameObject SpawnEnemy(Vector3 pos, float yaw = 0f)
        {
            if (enemyPrefab == null)
            {
                Debug.LogWarning("[MapBootstrap] 没配 enemyPrefab，跳过敌人生成。");
                return null;
            }
            var go = Instantiate(enemyPrefab, pos, Quaternion.Euler(0f, yaw, 0f));
            go.name = "Enemy";
            return go;
        }

        protected NpcActor SpawnNpc(NpcRole role, string name, Vector3 pos, float yaw = 0f,
            string[] lines = null, string shopId = null, string boardId = null, string talkCounter = null)
        {
            var prefab = npcPrefab != null ? npcPrefab : characterPrefab;
            return NpcFactory.Create(worldRoot, prefab, role, name, pos, yaw, lines, shopId, boardId, talkCounter);
        }

        /// <summary>清掉上次生成的内容（重复 BuildAll 时用；正常进 Play 只需一次）。</summary>
        protected void ClearGenerated()
        {
            // 主路径：World 是本对象的子物体（见 BuildAll 里的 SetParent）。
            var old = transform.Find("World");
            if (old != null)
            {
                if (Application.isPlaying) Destroy(old.gameObject);
                else DestroyImmediate(old.gameObject);
            }

            // 兜底：清掉历史/逻辑上遗留在**场景根**的同名对象。
            // 不能只靠 transform.Find —— 万一 worldRoot 又变成根对象（老版本存档、外部脚本改层级），
            // 就会静默地把世界建第二遍。
            var scene = gameObject.scene;
            if (scene.IsValid())
            {
                foreach (var root in scene.GetRootGameObjects())
                {
                    if (root == null || root == gameObject) continue;
                    if (root.name != "World" && root.name != "Player") continue;
                    if (Application.isPlaying) Destroy(root);
                    else DestroyImmediate(root);
                }
            }

            var oldPlayer = GameObject.Find("Player");
            if (oldPlayer != null && oldPlayer != gameObject) Destroy(oldPlayer);
        }
    }
}
