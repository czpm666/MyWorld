using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace MyWorld
{
    // ============================================================================================
    // 放置工具：网格吸附 / 朝向 / 挂接。地图生成器在 Play 中按坐标摆放时用这套，避免手算角度。
    // ============================================================================================
    public static class KitMath
    {
        /// <summary>吸附格（米）。0.5 对齐广场石板与街道中线；改它会改变全部摆放手感，慎动。</summary>
        public static float Grid = 0.5f;

        public static Vector3 Snap(Vector3 p)
        {
            float g = Mathf.Max(0.01f, Grid);
            return new Vector3(Mathf.Round(p.x / g) * g, p.y, Mathf.Round(p.z / g) * g);
        }

        /// <summary>让物体正面（+Z）朝向目标点的 yaw。地图里摆房子/摊位常用。</summary>
        public static float YawTo(Vector3 from, Vector3 to)
        {
            Vector3 d = to - from;
            d.y = 0f;
            if (d.sqrMagnitude < 1e-6f) return 0f;
            return Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
        }

        public static void Place(Transform parent, GameObject go, Vector3 pos, float yaw)
        {
            if (go == null) return;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
        }

        /// <summary>把角度吸附到 step 度一档，房子挨街排布时用，避免歪得不像手摆。</summary>
        public static float SnapYaw(float yaw, float step = 15f)
        {
            if (step <= 0.01f) return yaw;
            return Mathf.Round(yaw / step) * step;
        }

        /// <summary>极坐标取点（喷泉、石圈、魔法阵、城墙拐角）。deg=0 → +Z。</summary>
        public static Vector3 OnCircle(float radius, float deg)
        {
            float r = deg * Mathf.Deg2Rad;
            return new Vector3(Mathf.Sin(r) * radius, 0f, Mathf.Cos(r) * radius);
        }
    }

    // ============================================================================================
    // 民居参数。默认值是"一层带坡顶小民居"，两层请传 Floors=2（WallHeight 是单层层高）。
    // 用静态工厂拿预设，比一个个字段赋值省事，也保证同一张图里的房子风格统一。
    // ============================================================================================
    [Serializable]
    public class HouseSpec
    {
        public float Width = 6f;
        public float Depth = 5f;
        /// <summary>单层层高（米）。门高 2.1，所以别低于 2.6。</summary>
        public float WallHeight = 3.2f;
        public float RoofHeight = 2.4f;
        /// <summary>MapMaterials 材质名。</summary>
        public string Wall = "plaster_warm";
        public string Roof = "roof_terracotta";
        public string Timber = "timber_dark";
        public bool Chimney = true;
        public bool Balcony = false;
        public bool Sign = false;
        /// <summary>垂直于墙面的挑出招牌（酒馆常用）；与 Sign 可同时用。</summary>
        public bool HangingSign = false;
        public string SignText = "";
        public int Floors = 1;
        public float Yaw = 0f;
        public bool Collider = true;

        // ---- 以下为契约之外的微调项（都有安全默认，map 不管也行）----
        /// <summary>屋檐出挑（米）。0.35~0.55 是"立体书"气质的安全区间。</summary>
        public float Overhang = 0.45f;
        /// <summary>屋脊沿宽度方向（默认）：正面看到长屋檐、两侧看到山墙。false = 山墙朝街。</summary>
        public bool RidgeAlongWidth = true;
        /// <summary>是否给整栋房子挂 FadeableObject（相机遮挡时淡出）。地图构件多时可关掉省材质。</summary>
        public bool Fadeable = true;
        /// <summary>同一位置重复生成时保持一致的随机种子；0 = 由位置推导。</summary>
        public int Seed = 0;
        /// <summary>门是否开在正面（+Z）。false = 只留后门洞装饰，用于背街面。</summary>
        public bool DoorOnFront = true;
        /// <summary>是否在墙面随机挂灯/花箱等小装饰。</summary>
        public bool Trim = true;

        public static HouseSpec Cottage()
        {
            return new HouseSpec
            {
                Width = 5.4f, Depth = 4.4f, WallHeight = 3.0f, RoofHeight = 2.3f,
                Wall = "plaster_cream", Roof = "roof_thatch", Timber = "timber_mid",
                Chimney = true, Overhang = 0.5f,
            };
        }

        public static HouseSpec Townhouse()
        {
            return new HouseSpec
            {
                Width = 6.2f, Depth = 5.2f, WallHeight = 3.1f, RoofHeight = 2.5f, Floors = 2,
                Wall = "plaster_warm", Roof = "roof_terracotta", Timber = "timber_dark",
                Chimney = true, Balcony = true, Sign = true, SignText = "杂货",
            };
        }

        public static HouseSpec Villa()
        {
            return new HouseSpec
            {
                Width = 8.5f, Depth = 6.5f, WallHeight = 3.4f, RoofHeight = 3.0f, Floors = 2,
                Wall = "plaster_white", Roof = "roof_burgundy", Timber = "timber_mid",
                Chimney = true, Balcony = true, Overhang = 0.5f,
            };
        }

        public HouseSpec Clone()
        {
            return (HouseSpec)MemberwiseClone();
        }
    }

    // ============================================================================================
    // 基础原语。全部运行期可用（不碰 AssetDatabase/Resources），返回 GameObject 都带子树/碰撞。
    //
    // ⚠️ 参数顺序约定（与 OVERHAUL-PLAN §4 草案不同，map agent 以本文件为准）：
    //    Box(parent, name, size, pos, mat, yaw, collider, fadeAlpha)
    //    Cyl(parent, name, radius, height, pos, mat, segments, collider)
    //  位置是父节点的**局部坐标**，yaw 是额外局部朝向（父节点朝向之上叠加）。
    // ============================================================================================
    public static class Kit
    {
        public const float HumanHeight = 1.5f;   // 角色身高参照（做门/窗/招牌比例时用）
        public const float DoorHeight = 2.1f;

        // ---------------------------------------------------------------- 生命周期工具
        public static void Kill(UnityEngine.Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) UnityEngine.Object.Destroy(o);
            else UnityEngine.Object.DestroyImmediate(o);
        }

        static GameObject NewGo(Transform parent, string name)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            return go;
        }

        static Vector3 Sized(Vector3 size)
        {
            return new Vector3(Mathf.Max(0.002f, size.x), Mathf.Max(0.002f, size.y), Mathf.Max(0.002f, size.z));
        }

        static void SetMat(GameObject go, Material mat)
        {
            if (mat == null) return;
            var r = go.GetComponent<Renderer>();
            if (r != null) r.sharedMaterial = mat;
        }

        static T FindOrAdd<T>(GameObject go) where T : Component
        {
            var c = go.GetComponent<T>();
            if (c == null) c = go.AddComponent<T>();
            return c;
        }

        // ---------------------------------------------------------------- 方盒
        public static GameObject Box(Transform parent, string name, Vector3 size, Vector3 pos, Material mat,
            float yaw = 0f, bool collider = true, float? fadeAlpha = null)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            go.transform.localScale = Sized(size);
            SetMat(go, mat);
            if (!collider) Kill(go.GetComponent<Collider>());
            if (fadeAlpha.HasValue) MakeFadeable(go, fadeAlpha.Value);
            return go;
        }

        /// <summary>任意旋转的方盒（山墙支撑、斜梁、车轮、折页等）。</summary>
        public static GameObject BoxRot(Transform parent, string name, Vector3 size, Vector3 pos, Quaternion rot,
            Material mat, bool collider = false)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localRotation = rot;
            go.transform.localScale = Sized(size);
            SetMat(go, mat);
            if (!collider) Kill(go.GetComponent<Collider>());
            return go;
        }

        /// <summary>米制 UV 的方板：带程序化纹理的表面（遮阳棚、瓦片、木板门）用这个，
        /// 因为 Cube 图元的 UV 是 0..1，纹理会整块拉伸。碰撞体为 MeshCollider。</summary>
        public static GameObject Slab(Transform parent, string name, Vector3 size, Vector3 pos, Material mat,
            float yaw = 0f, bool collider = false)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            var mesh = KitGeo.BoxMesh(Sized(size), Vector2.zero);
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = mesh;
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            if (collider)
            {
                var mc = FindOrAdd<MeshCollider>(go);
                mc.sharedMesh = mesh;
            }
            return go;
        }

        // ---------------------------------------------------------------- 圆柱 / 圆锥
        // ⚠️ 这两个 mesh **必须缓存**。2026-10-18 编辑器原生崩溃（`Mesh.SetUVs` 里
        //    `Mesh:SetArrayForChannelImpl_Injected` 炸掉整个 Unity 进程）的根因就是这里：
        //    `Kit.Cyl` / `Kit.CylRot` 每调用一次就 `new Mesh` + SetVertices/SetUVs/Recalculate，
        //    而树干/木桶/水井/灯柱/干草堆全是圆柱 —— 一次 `Awake` 里几千个 Mesh 分配，
        //    把原生内存压爆。（`SphereMesh` 早就缓存了，圆柱/圆锥漏了。）
        //    这里的 mesh 全程按**单位尺寸**使用（缩放交给 transform.localScale），
        //    所以同一 segments 的 mesh 可以安全地在所有物件间共享。
        static readonly Dictionary<int, Mesh> CylMeshes = new Dictionary<int, Mesh>();
        static readonly Dictionary<int, Mesh> ConeMeshes = new Dictionary<int, Mesh>();

        static Mesh CylMesh(int segments)
        {
            int key = Mathf.Max(3, segments);
            Mesh m;
            if (CylMeshes.TryGetValue(key, out m) && m != null) return m;
            m = KitGeo.CylinderMesh(key);
            CylMeshes[key] = m;
            return m;
        }

        static Mesh ConeMesh(int segments)
        {
            int key = Mathf.Max(3, segments);
            Mesh m;
            if (ConeMeshes.TryGetValue(key, out m) && m != null) return m;
            m = KitGeo.ConeMesh(key);
            ConeMeshes[key] = m;
            return m;
        }

        /// <summary>低多边形圆柱（10 边形是"手办感"的甜点）。径向缩放由 radius 决定。</summary>
        public static GameObject Cyl(Transform parent, string name, float radius, float height, Vector3 pos,
            Material mat, int segments = 10, bool collider = true)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = CylMesh(segments);
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            go.transform.localScale = new Vector3(radius * 2f, height * 0.5f, radius * 2f);
            if (collider) AttachCapsule(go, radius, height, 1);
            return go;
        }

        /// <summary>任意旋转的圆柱（横放的木桶/车轮/炮管）。</summary>
        public static GameObject CylRot(Transform parent, string name, float radius, float height, Vector3 pos,
            Quaternion rot, Material mat, int segments = 10, bool collider = false)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            go.transform.localRotation = rot;
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = CylMesh(segments);
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            go.transform.localScale = new Vector3(radius * 2f, height * 0.5f, radius * 2f);
            if (collider) AttachCapsule(go, radius, height, 1);
            return go;
        }

        static void AttachCapsule(GameObject go, float radius, float height, int dir)
        {
            // CapsuleCollider 的半径/高度是"未缩放本地空间"的量，会随 transform 缩放；
            // 圆柱网格本地半径 0.5、高 2，所以这里传 0.5 / 2 让世界尺寸等于 radius/height。
            var cc = FindOrAdd<CapsuleCollider>(go);
            cc.direction = dir;
            cc.radius = 0.5f;
            cc.height = 2f;
        }

        public static GameObject Cone(Transform parent, string name, float radius, float height, Vector3 pos,
            Material mat, int segments = 8, bool collider = false)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = ConeMesh(segments);
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            go.transform.localScale = new Vector3(radius * 2f, height, radius * 2f);
            if (collider) AttachCapsule(go, radius, height, 1);
            return go;
        }

        public static GameObject ConeRot(Transform parent, string name, float radius, float height, Vector3 pos,
            Quaternion rot, Material mat, int segments = 8)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            go.transform.localRotation = rot;
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = ConeMesh(segments);
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            go.transform.localScale = new Vector3(radius * 2f, height, radius * 2f);
            return go;
        }

        // ---------------------------------------------------------------- 球 / 椭球
        static readonly Dictionary<int, Mesh> SphereMeshes = new Dictionary<int, Mesh>();

        static Mesh SphereMesh(int segments)
        {
            Mesh m;
            int key = Mathf.Max(4, segments);
            if (SphereMeshes.TryGetValue(key, out m) && m != null) return m;
            m = KitGeo.SphereMesh(key);
            SphereMeshes[key] = m;
            return m;
        }

        public static GameObject Sphere(Transform parent, string name, float radius, Vector3 pos, Material mat,
            bool collider = false, int segments = 10)
        {
            return Sphere(parent, name, new Vector3(radius * 2f, radius * 2f, radius * 2f), pos, mat, collider, segments);
        }

        public static GameObject Sphere(Transform parent, string name, Vector3 size, Vector3 pos, Material mat,
            bool collider = false, int segments = 10)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = SphereMesh(segments);
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            go.transform.localScale = Sized(size);
            if (collider)
            {
                var sc = FindOrAdd<SphereCollider>(go);
                sc.radius = 0.5f;
            }
            return go;
        }

        // ---------------------------------------------------------------- 自定义网格
        public static GameObject Mesh(Transform parent, string name, Mesh mesh, Vector3 pos, Material mat,
            bool collider = true)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = mesh;
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            if (collider && mesh != null)
            {
                var mc = FindOrAdd<MeshCollider>(go);
                mc.sharedMesh = mesh;
            }
            return go;
        }

        public static GameObject MeshRot(Transform parent, string name, Mesh mesh, Vector3 pos, Quaternion rot,
            Material mat, bool collider = false)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            go.transform.localRotation = rot;
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = mesh;
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            if (collider && mesh != null)
            {
                var mc = FindOrAdd<MeshCollider>(go);
                mc.sharedMesh = mesh;
            }
            return go;
        }

        // ---------------------------------------------------------------- 屋顶
        /// <summary>
        /// 人字坡屋顶（脊沿 X 轴，坡面朝 ±Z）。局部原点 = 檐口高度中心，脊高 = height。
        /// 出檐会让檐口继续往下斜 overhang*height/(depth/2) 米，这是真实坡屋顶的样子（不是悬空方块）。
        /// UV 以米为单位，所以瓦片纹理不会被拉长。
        /// </summary>
        public static Mesh GableRoofMesh(float width, float depth, float height, float overhang)
        {
            return GableRoofMesh(width, depth, height, overhang, 0.14f);
        }

        public static Mesh GableRoofMesh(float width, float depth, float height, float overhang, float thickness)
        {
            width = Mathf.Max(0.5f, width);
            depth = Mathf.Max(0.5f, depth);
            height = Mathf.Max(0.3f, height);
            overhang = Mathf.Max(0f, overhang);
            thickness = Mathf.Max(0.04f, thickness);

            var v = new List<Vector3>(96);
            var t = new List<int>(144);
            var uv = new List<Vector2>(96);

            float halfD = depth * 0.5f;
            float tan = height / halfD;
            float dOut = halfD + overhang;
            float eaveDrop = overhang * tan;
            float slopeLen = Mathf.Sqrt(dOut * dOut + (height + eaveDrop) * (height + eaveDrop));
            float angDeg = Mathf.Atan2(height + eaveDrop, dOut) * Mathf.Rad2Deg;
            float slabW = width + overhang * 2f;

            for (int side = 0; side < 2; side++)
            {
                float sign = side == 0 ? 1f : -1f;
                Quaternion rot = Quaternion.Euler(angDeg * sign, 0f, 0f);
                Vector3 center = new Vector3(0f, (height - eaveDrop) * 0.5f, sign * dOut * 0.5f);
                KitGeo.AddBox(v, t, uv, center, new Vector3(slabW, thickness, slopeLen), rot);
            }
            return KitGeo.ToMesh("KitGableRoof", v, t, uv);
        }

        /// <summary>四坡金字塔屋顶。原点 = 檐口中心，塔尖高 height。</summary>
        public static Mesh PyramidRoofMesh(float width, float depth, float height)
        {
            var v = new List<Vector3>(32);
            var t = new List<int>(48);
            var uv = new List<Vector2>(32);
            float hw = Mathf.Max(0.3f, width) * 0.5f;
            float hd = Mathf.Max(0.3f, depth) * 0.5f;
            float h = Mathf.Max(0.2f, height);
            Vector3 a = new Vector3(-hw, 0f, hd);
            Vector3 b = new Vector3(hw, 0f, hd);
            Vector3 c = new Vector3(hw, 0f, -hd);
            Vector3 d = new Vector3(-hw, 0f, -hd);
            Vector3 p = new Vector3(0f, h, 0f);
            KitGeo.AddTri(v, t, uv, a, b, p);
            KitGeo.AddTri(v, t, uv, b, c, p);
            KitGeo.AddTri(v, t, uv, c, d, p);
            KitGeo.AddTri(v, t, uv, d, a, p);
            KitGeo.AddQuad(v, t, uv, d, c, b, a); // 底面朝下
            return KitGeo.ToMesh("KitPyramidRoof", v, t, uv);
        }

        /// <summary>
        /// 实心山墙三角（带厚度）。局部：三角在 XY 平面，底边 y=0 跨 X，顶点 (0,spanHalfHeight)。
        /// 房子山墙在 ±X 面时用 yaw=90 摆。
        /// </summary>
        public static GameObject GableFace(Transform parent, string name, float span, float height, float thickness,
            Vector3 pos, Material mat, float yaw = 0f)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            var mesh = KitGeo.GablePrismMesh(Mathf.Max(0.3f, span), Mathf.Max(0.2f, height), Mathf.Max(0.05f, thickness));
            var mf = FindOrAdd<MeshFilter>(go);
            mf.sharedMesh = mesh;
            var mr = FindOrAdd<MeshRenderer>(go);
            if (mat != null) mr.sharedMaterial = mat;
            return go;
        }

        // ---------------------------------------------------------------- 灯与文字
        /// <summary>真实点光源（有数量上限：一张图 ≤8 个，路灯/火盆/魔法阵点睛用）。</summary>
        public static GameObject PointLight(Transform parent, Vector3 pos, Color color, float range, float intensity)
        {
            var go = NewGo(parent, "PointLight");
            go.transform.localPosition = pos;
            var l = FindOrAdd<Light>(go);
            l.type = LightType.Point;
            l.color = color;
            l.range = Mathf.Max(0.5f, range);
            l.intensity = Mathf.Max(0f, intensity);
            l.shadows = LightShadows.None;   // 2.5D 俯视 + 性能优先，点光不投影
            return go;
        }

        static Font _font;
        static bool _fontFailed;

        public static Font SignFont()
        {
            if (_font != null) return _font;
            if (_fontFailed) return null;
            try
            {
                _font = Font.CreateDynamicFontFromOSFont(
                    new[] { "Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial" }, 64);
            }
            catch (Exception) { _font = null; }
            if (_font == null)
            {
                try { _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); }
                catch (Exception) { _font = null; }
            }
            if (_font == null) _fontFailed = true;
            return _font;
        }

        /// <summary>
        /// 世界空间文字（招牌/路牌）。自动按 maxWidth/maxHeight 缩放，保证在 2.5D 相机距离下看得清。
        /// 返回的 TextMesh 正面朝局部 +Z。
        /// </summary>
        public static GameObject SignText(Transform parent, string text, Vector3 pos, float yaw, Color color,
            float maxWidth = 1.0f, float maxHeight = 0.35f, int sortingOrder = 0)
        {
            var go = NewGo(parent, "Text");
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            if (string.IsNullOrEmpty(text)) return go;

            var font = SignFont();
            var tm = FindOrAdd<TextMesh>(go);
            tm.text = text;
            tm.font = font;
            tm.fontSize = 64;
            tm.characterSize = 0.1f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = color;

            var mr = FindOrAdd<MeshRenderer>(go);
            if (font != null) mr.sharedMaterial = font.material;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;

            var fit = FindOrAdd<KitAutoFitText>(go);
            fit.Configure(mr, maxWidth, maxHeight);
            return go;
        }

        /// <summary>
        /// 世界招牌：Unlit 牌面 + 深色木边框 + 自动缩放文字。牌面正面朝局部 +Z。
        /// bg 默认米白布色；fg 可选（默认墨色）。
        /// </summary>
        public static GameObject SignBoard(Transform parent, string text, Vector3 pos, float yaw,
            float width = 1.2f, float height = 0.5f, Color? bg = null, Color? fg = null)
        {
            width = Mathf.Max(0.25f, width);
            height = Mathf.Max(0.15f, height);
            var root = Pivot(parent, "SignBoard", pos, yaw);
            Color b = bg ?? MapMaterials.ClothCream;
            Color f = fg ?? KitPalette.Ink;
            var board = KitMat.Unlit("kit_signbg_" + ColorUtility.ToHtmlStringRGB(b), b);
            Box(root.transform, "Board", new Vector3(width, height, 0.06f), Vector3.zero, board, 0f, false);
            var frame = KitMat.Timber("timber_dark");
            const float ft = 0.07f;
            Box(root.transform, "FrameT", new Vector3(width + ft * 2f, ft, 0.09f),
                new Vector3(0f, height * 0.5f + ft * 0.5f, 0f), frame, 0f, false);
            Box(root.transform, "FrameB", new Vector3(width + ft * 2f, ft, 0.09f),
                new Vector3(0f, -height * 0.5f - ft * 0.5f, 0f), frame, 0f, false);
            Box(root.transform, "FrameL", new Vector3(ft, height + ft * 2f, 0.09f),
                new Vector3(-width * 0.5f - ft * 0.5f, 0f, 0f), frame, 0f, false);
            Box(root.transform, "FrameR", new Vector3(ft, height + ft * 2f, 0.09f),
                new Vector3(width * 0.5f + ft * 0.5f, 0f, 0f), frame, 0f, false);
            SignText(root.transform, text, new Vector3(0f, 0f, 0.048f), 0f, f, width * 0.86f, height * 0.62f);
            return root;
        }

        // ---------------------------------------------------------------- 淡出
        public static FadeableObject MakeFadeable(GameObject go, float fadedAlpha = 0.22f)
        {
            if (go == null) return null;
            var f = FindOrAdd<FadeableObject>(go);
            f.Configure(fadedAlpha);
            return f;
        }

        // ---------------------------------------------------------------- 小工具（给 KitArchitecture / KitProps 复用）
        internal static GameObject Pivot(Transform parent, string name, Vector3 pos, float yaw = 0f)
        {
            var go = NewGo(parent, name);
            go.transform.localPosition = pos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            return go;
        }

        /// <summary>不可见的碰撞盒：只挡人不渲染。建筑/栅栏/摊位整件只留一个，压 GameObject 数量。</summary>
        internal static GameObject Blocker(Transform parent, string name, Vector3 size, Vector3 pos)
        {
            var go = Box(parent, name, size, pos, null, 0f, true);
            var mr = go.GetComponent<MeshRenderer>();
            if (mr != null) mr.enabled = false;
            return go;
        }

        /// <summary>一小段等距斜撑（木筋墙、栏杆、支架用）。axisFace: 0=±Z 面(绕 Z 转), 1=±X 面(绕 X 转)。</summary>
        internal static GameObject Brace(Transform parent, string name, Vector3 pos, float length, float thick,
            float angleDeg, int faceAxis, Material mat)
        {
            Quaternion rot = faceAxis == 0
                ? Quaternion.Euler(0f, 0f, angleDeg)
                : Quaternion.Euler(angleDeg, 0f, 0f);
            return BoxRot(parent, name, new Vector3(thick, thick, length), pos, rot, mat, false);
        }

        /// <summary>烟囱冒的烟：几团半透明球，越往上越大越淡。静态摆放，2.5D 下足够像。</summary>
        internal static void Smoke(Transform parent, Vector3 basePos, Color tint, int puffs = 4, float scale = 0.24f)
        {
            for (int i = 0; i < puffs; i++)
            {
                float k = (i + 1f) / puffs;
                float r = scale * (0.65f + k * 1.1f);
                float alpha = Mathf.Lerp(0.34f, 0.08f, k);
                var mat = KitMat.Transparent("kit_smoke_" + tint.ToString("F2") + "_" + i, tint, alpha);
                float drift = Mathf.Sin(i * 1.7f) * 0.1f * (i + 1);
                Sphere(parent, "Smoke" + i, r,
                    basePos + new Vector3(drift, k * 0.62f, drift * 0.6f), mat, false, 8);
            }
        }

        /// <summary>
        /// 把整栋建筑的 Renderer 按材质合并成少量网格，用于性能吃紧的地图（可选）。
        /// 会丢掉子物体碰撞体，并在根上补一个包围盒 BoxCollider。返回合并后剩余的可视物体数。
        /// </summary>
        public static int Optimize(GameObject root, bool addRootCollider = true)
        {
            if (root == null) return 0;
            var renderers = root.GetComponentsInChildren<MeshRenderer>(true);
            if (renderers.Length == 0) return 0;

            var byMat = new Dictionary<Material, List<CombineInstance>>();
            foreach (var r in renderers)
            {
                var mf = r.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                var mat = r.sharedMaterial;
                if (mat == null) continue;
                List<CombineInstance> list;
                if (!byMat.TryGetValue(mat, out list))
                {
                    list = new List<CombineInstance>();
                    byMat[mat] = list;
                }
                list.Add(new CombineInstance
                {
                    mesh = mf.sharedMesh,
                    transform = root.transform.worldToLocalMatrix * r.transform.localToWorldMatrix,
                });
            }

            var bounds = new Bounds(root.transform.position, Vector3.one);
            bool hasBounds = false;
            foreach (var r in renderers)
            {
                if (!hasBounds) { bounds = r.bounds; hasBounds = true; }
                else bounds.Encapsulate(r.bounds);
            }

            // 先记下要删的子物体，再合并（避免边遍历边销毁）
            var kids = new List<GameObject>();
            foreach (var r in renderers)
            {
                var go = r.gameObject;
                if (go != root) kids.Add(go);
            }
            foreach (var go in kids) Kill(go);
            foreach (var c in root.GetComponentsInChildren<Collider>(true))
                if (c.gameObject != root) Kill(c);

            var holder = Pivot(root.transform, "Batched", Vector3.zero);
            int count = 0;
            foreach (var kv in byMat)
            {
                if (kv.Value.Count == 0) continue;
                var mesh = new Mesh { name = "KitBatch_" + count };
                mesh.indexFormat = IndexFormat.UInt32;
                mesh.CombineMeshes(kv.Value.ToArray(), true, true);
                mesh.RecalculateBounds();
                var go = NewGo(holder.transform, "Batch" + count);
                var mf = FindOrAdd<MeshFilter>(go);
                mf.sharedMesh = mesh;
                var mr = FindOrAdd<MeshRenderer>(go);
                mr.sharedMaterial = kv.Key;
                count++;
            }

            if (addRootCollider && hasBounds)
            {
                Vector3 local = root.transform.InverseTransformPoint(bounds.center);
                var bc = FindOrAdd<BoxCollider>(root);
                bc.center = local;
                bc.size = bounds.size;
            }
            return count;
        }
    }

    // ============================================================================================
    // 确定性随机：同一位置/种子生成的细节（窗户分布、木筋角度）永远一致，重开 Play 不会变样。
    // ============================================================================================
    internal struct KitRand
    {
        uint s;

        public KitRand(int seed)
        {
            s = (uint)(seed * 747796405 + 2891336453);
            if (s == 0u) s = 0x9E3779B9u;
        }

        public uint Next()
        {
            s ^= s << 13;
            s ^= s >> 17;
            s ^= s << 5;
            return s;
        }

        public float Value
        {
            get { return (Next() & 0xFFFFFFu) / 16777215f; }
        }

        public float Range(float a, float b)
        {
            return a + (b - a) * Value;
        }

        public int Range(int a, int b)
        {
            if (b <= a) return a;
            return a + (int)(Next() % (uint)(b - a + 1));
        }

        public bool Chance(float p)
        {
            return Value < p;
        }

        public static int SeedFrom(Vector3 p, int extra)
        {
            int h = 17;
            h = h * 31 + Mathf.RoundToInt(p.x * 10f);
            h = h * 31 + Mathf.RoundToInt(p.y * 10f);
            h = h * 31 + Mathf.RoundToInt(p.z * 10f);
            h = h * 31 + extra;
            return h;
        }
    }

    // ============================================================================================
    // 几何构建：自带米制 UV 的方盒 / 三角柱 / 圆柱 / 球 / 圆锥，全部平面着色（低多边形手办感）。
    // ============================================================================================
    internal static class KitGeo
    {
        public static Vector2 Proj(Vector3 p, Vector3 n)
        {
            if (Mathf.Abs(n.y) >= Mathf.Abs(n.x) && Mathf.Abs(n.y) >= Mathf.Abs(n.z)) return new Vector2(p.x, p.z);
            if (Mathf.Abs(n.x) >= Mathf.Abs(n.z)) return new Vector2(p.z, p.y);
            return new Vector2(p.x, p.y);
        }

        public static void AddQuad(List<Vector3> v, List<int> t, List<Vector2> uv,
            Vector3 a, Vector3 b, Vector3 c, Vector3 d)
        {
            Vector3 n = Vector3.Cross(b - a, c - a);
            int i = v.Count;
            v.Add(a); v.Add(b); v.Add(c); v.Add(d);
            uv.Add(Proj(a, n)); uv.Add(Proj(b, n)); uv.Add(Proj(c, n)); uv.Add(Proj(d, n));
            t.Add(i); t.Add(i + 1); t.Add(i + 2);
            t.Add(i); t.Add(i + 2); t.Add(i + 3);
        }

        public static void AddTri(List<Vector3> v, List<int> t, List<Vector2> uv, Vector3 a, Vector3 b, Vector3 c)
        {
            Vector3 n = Vector3.Cross(b - a, c - a);
            int i = v.Count;
            v.Add(a); v.Add(b); v.Add(c);
            uv.Add(Proj(a, n)); uv.Add(Proj(b, n)); uv.Add(Proj(c, n));
            t.Add(i); t.Add(i + 1); t.Add(i + 2);
        }

        /// <summary>米制 UV 方盒。uvScale 用于给纹理额外的平铺倍数（0 = 1 米一循环）。</summary>
        public static void AddBox(List<Vector3> v, List<int> t, List<Vector2> uv,
            Vector3 center, Vector3 size, Quaternion rot, Vector2 uvScale = default(Vector2))
        {
            if (uvScale == default(Vector2)) uvScale = Vector2.one;
            Vector3 h = size * 0.5f;
            Vector3 P(float x, float y, float z)
            {
                return center + rot * new Vector3(x * h.x, y * h.y, z * h.z);
            }
            // 六个面，绕序保证法线朝外（背面剔除下可见）
            AddQuad(v, t, uv, P(1, -1, 1), P(1, -1, -1), P(1, 1, -1), P(1, 1, 1));    // +X
            AddQuad(v, t, uv, P(-1, -1, -1), P(-1, -1, 1), P(-1, 1, 1), P(-1, 1, -1)); // -X
            AddQuad(v, t, uv, P(-1, 1, 1), P(1, 1, 1), P(1, 1, -1), P(-1, 1, -1));     // +Y
            AddQuad(v, t, uv, P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)); // -Y
            AddQuad(v, t, uv, P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1));     // +Z
            AddQuad(v, t, uv, P(1, -1, -1), P(-1, -1, -1), P(-1, 1, -1), P(1, 1, -1)); // -Z
            if (uvScale != Vector2.one) ScaleUv(uv, uv.Count - 24, 24, uvScale);
        }

        static void ScaleUv(List<Vector2> uv, int start, int count, Vector2 s)
        {
            for (int i = start; i < start + count && i < uv.Count; i++) uv[i] = new Vector2(uv[i].x * s.x, uv[i].y * s.y);
        }

        public static Mesh BoxMesh(Vector3 size, Vector2 uvScale)
        {
            var v = new List<Vector3>(24);
            var t = new List<int>(36);
            var uv = new List<Vector2>(24);
            AddBox(v, t, uv, Vector3.zero, size, Quaternion.identity, uvScale);
            return ToMesh("KitBox", v, t, uv);
        }

        /// <summary>三角柱（山墙）：底边跨 X、y=0，顶点 (0,height)，厚度沿 Z。</summary>
        public static Mesh GablePrismMesh(float span, float height, float thickness)
        {
            var v = new List<Vector3>(24);
            var t = new List<int>(36);
            var uv = new List<Vector2>(24);
            float hs = span * 0.5f;
            float ht = thickness * 0.5f;
            Vector3 lf = new Vector3(-hs, 0f, ht);
            Vector3 rf = new Vector3(hs, 0f, ht);
            Vector3 tf = new Vector3(0f, height, ht);
            Vector3 lb = new Vector3(-hs, 0f, -ht);
            Vector3 rb = new Vector3(hs, 0f, -ht);
            Vector3 tb = new Vector3(0f, height, -ht);
            AddTri(v, t, uv, lf, rf, tf);    // +Z
            AddTri(v, t, uv, rb, lb, tb);    // -Z
            AddQuad(v, t, uv, lb, rb, rf, lf);   // 底面
            AddQuad(v, t, uv, lf, rf, tf, tf);   // 斜边（退化也没关系，几乎看不见）
            return ToMesh("KitGablePrism", v, t, uv);
        }

        public static Mesh CylinderMesh(int segments)
        {
            var v = new List<Vector3>(segments * 8);
            var t = new List<int>(segments * 12);
            var uv = new List<Vector2>(segments * 8);
            float r = 0.5f;
            float y0 = -1f, y1 = 1f;
            for (int i = 0; i < segments; i++)
            {
                float a0 = (i / (float)segments) * Mathf.PI * 2f;
                float a1 = ((i + 1) / (float)segments) * Mathf.PI * 2f;
                Vector3 p0 = new Vector3(Mathf.Sin(a0) * r, y0, Mathf.Cos(a0) * r);
                Vector3 p1 = new Vector3(Mathf.Sin(a1) * r, y0, Mathf.Cos(a1) * r);
                Vector3 p2 = new Vector3(Mathf.Sin(a1) * r, y1, Mathf.Cos(a1) * r);
                Vector3 p3 = new Vector3(Mathf.Sin(a0) * r, y1, Mathf.Cos(a0) * r);
                AddQuad(v, t, uv, p0, p1, p2, p3);
                // 顶/底盖（扇形）：顶面朝 +Y，底盖绕序反过来朝 -Y
                AddTri(v, t, uv, new Vector3(0f, y1, 0f), p3, p2);
                AddTri(v, t, uv, new Vector3(0f, y0, 0f), p1, p0);
            }
            return ToMesh("KitCyl" + segments, v, t, uv);
        }

        public static Mesh ConeMesh(int segments)
        {
            var v = new List<Vector3>(segments * 6);
            var t = new List<int>(segments * 8);
            var uv = new List<Vector2>(segments * 6);
            float r = 0.5f;
            Vector3 apex = new Vector3(0f, 1f, 0f);
            for (int i = 0; i < segments; i++)
            {
                float a0 = (i / (float)segments) * Mathf.PI * 2f;
                float a1 = ((i + 1) / (float)segments) * Mathf.PI * 2f;
                Vector3 p0 = new Vector3(Mathf.Sin(a0) * r, 0f, Mathf.Cos(a0) * r);
                Vector3 p1 = new Vector3(Mathf.Sin(a1) * r, 0f, Mathf.Cos(a1) * r);
                AddTri(v, t, uv, p0, p1, apex);
                AddTri(v, t, uv, Vector3.zero, p1, p0); // 底盖朝下
            }
            return ToMesh("KitCone" + segments, v, t, uv);
        }

        /// <summary>低多边形 UV 球（平面着色）。本地半径 0.5，所以 scale=直径。</summary>
        public static Mesh SphereMesh(int segments)
        {
            int rings = Mathf.Max(3, segments / 2);
            var v = new List<Vector3>(segments * rings * 4);
            var t = new List<int>(segments * rings * 6);
            var uv = new List<Vector2>(segments * rings * 4);
            float r = 0.5f;
            for (int j = 0; j < rings; j++)
            {
                float v0 = j / (float)rings;
                float v1 = (j + 1) / (float)rings;
                float phi0 = (v0 - 0.5f) * Mathf.PI;
                float phi1 = (v1 - 0.5f) * Mathf.PI;
                float y0 = Mathf.Sin(phi0) * r;
                float y1 = Mathf.Sin(phi1) * r;
                float r0 = Mathf.Cos(phi0) * r;
                float r1 = Mathf.Cos(phi1) * r;
                for (int i = 0; i < segments; i++)
                {
                    float a0 = (i / (float)segments) * Mathf.PI * 2f;
                    float a1 = ((i + 1) / (float)segments) * Mathf.PI * 2f;
                    Vector3 p0 = new Vector3(Mathf.Sin(a0) * r0, y0, Mathf.Cos(a0) * r0);
                    Vector3 p1 = new Vector3(Mathf.Sin(a1) * r0, y0, Mathf.Cos(a1) * r0);
                    Vector3 p2 = new Vector3(Mathf.Sin(a1) * r1, y1, Mathf.Cos(a1) * r1);
                    Vector3 p3 = new Vector3(Mathf.Sin(a0) * r1, y1, Mathf.Cos(a0) * r1);
                    if (r0 < 1e-5f) AddTri(v, t, uv, p0, p2, p3);
                    else if (r1 < 1e-5f) AddTri(v, t, uv, p0, p1, p3);
                    else AddQuad(v, t, uv, p0, p1, p2, p3);
                }
            }
            return ToMesh("KitSphere" + segments, v, t, uv);
        }

        public static Mesh ToMesh(string name, List<Vector3> v, List<int> t, List<Vector2> uv)
        {
            var m = new Mesh { name = name };
            m.indexFormat = v.Count > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16;
            m.SetVertices(v);
            m.SetUVs(0, uv);
            m.SetTriangles(t, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }
    }

    // ============================================================================================
    // 材质与程序化纹理。全部走 MapMaterials（不 new 自定义 shader、不 import 资产）；
    // 带纹理的材质用 "kit_*" 独立缓存键，避免污染 map 共用的具名材质。
    // ============================================================================================
    internal static class KitMat
    {
        static readonly Dictionary<string, Material> Cache = new Dictionary<string, Material>(64);
        static readonly Dictionary<string, Texture2D> TexCache = new Dictionary<string, Texture2D>(16);

        public static Material Get(string key)
        {
            return MapMaterials.Get(key);
        }

        public static Material Solid(string key, Color c, float smooth = 0.15f)
        {
            return MapMaterials.Solid(key, c, smooth);
        }

        public static Material Emi(string key, Color c, float intensity = 1.6f)
        {
            return MapMaterials.Emissive(key, c, intensity);
        }

        public static Material Unlit(string key, Color c)
        {
            return MapMaterials.Unlit(key, c);
        }

        public static Material Transparent(string key, Color c, float alpha = 0.5f)
        {
            return MapMaterials.Transparent(key, c, alpha);
        }

        /// <summary>带程序化贴图的材质：tint 乘在贴图上（贴图做成灰阶明暗，颜色交给 tint）。</summary>
        public static Material Tex(string key, Color tint, Texture2D tex, float metersPerTile)
        {
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = MapMaterials.Solid(key, tint, 0.12f);
            if (m != null)
            {
                float s = 1f / Mathf.Max(0.05f, metersPerTile);
                if (m.HasProperty("_BaseMap"))
                {
                    m.SetTexture("_BaseMap", tex);
                    m.SetTextureScale("_BaseMap", new Vector2(s, s));
                }
                m.mainTexture = tex;
                m.mainTextureScale = new Vector2(s, s);
            }
            Cache[key] = m;
            return m;
        }

        // ---------------- 具名"带纹理"材质族 ----------------
        public static Material Wall(string wallKey)
        {
            return Tex("kit_wall_" + wallKey, KitPalette.Of(wallKey), TexPlaster(), 2.2f);
        }

        public static Material Roof(string roofKey)
        {
            if (roofKey == "roof_thatch")
                return Tex("kit_roof_thatch", KitPalette.Of(roofKey), TexThatch(), 1.4f);
            return Tex("kit_roof_" + roofKey, KitPalette.Of(roofKey), TexRoofTiles(), 1.15f);
        }

        public static Material Timber(string timberKey)
        {
            return Tex("kit_timber_" + timberKey, KitPalette.Of(timberKey), TexWood(), 1.6f);
        }

        public static Material Awning(string clothKey)
        {
            Color c = KitPalette.Of(clothKey);
            return Tex("kit_awning_" + clothKey, Color.white, TexStripes(c, KitPalette.Lighten(c, 0.55f)), 0.95f);
        }

        public static Material Cloth(string clothKey)
        {
            Color c = KitPalette.Of(clothKey);
            return Tex("kit_cloth_" + clothKey, c, TexWeave(), 0.8f);
        }

        public static Material Stone(string stoneKey)
        {
            return Tex("kit_stone_" + stoneKey, KitPalette.Of(stoneKey), TexStone(), 1.6f);
        }

        /// <summary>带木纹的任意木质色（门板、推车板、栅栏）。</summary>
        public static Material WoodTinted(string colorKey)
        {
            return Tex("kit_woodtint_" + colorKey, KitPalette.Of(colorKey), TexWood(), 1.4f);
        }

        // ---------------- 纹理生成（一次性，静态缓存） ----------------
        static Texture2D MakeTex(string name, int w, int h, Func<int, int, Color> f)
        {
            var t = new Texture2D(w, h, TextureFormat.RGBA32, true)
            {
                wrapMode = TextureWrapMode.Repeat,
                filterMode = FilterMode.Bilinear,
                anisoLevel = 4,
                name = name,
            };
            var px = new Color[w * h];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    px[y * w + x] = f(x, y);
            t.SetPixels(px);
            t.Apply(true);
            return t;
        }

        static Texture2D TexRoofTiles()
        {
            Texture2D t;
            if (TexCache.TryGetValue("roof", out t)) return t;
            const int S = 64;
            const int rows = 4;
            const int cols = 4;
            float rowH = (float)S / rows;
            float colW = (float)S / cols;
            t = MakeTex("KitTexRoofTiles", S, S, (x, y) =>
            {
                int row = Mathf.FloorToInt(y / rowH);
                float fy = (y - row * rowH) / rowH;
                int col = Mathf.FloorToInt(x / colW);
                float fx = (x - col * colW) / colW;
                float shade = 0.88f + 0.1f * Mathf.PerlinNoise(col * 0.83f + 0.37f, row * 0.91f);
                // 每片瓦上缘压暗 + 下缘提亮，形成瓦片层叠的"鱼鳞"感
                shade *= Mathf.Lerp(1.05f, 0.72f, Mathf.SmoothStep(0f, 1f, (fy - 0.78f) / 0.22f));
                // 竖缝
                if (fx < 0.07f || fx > 0.93f) shade *= 0.82f;
                // 瓦片底部一层薄高光
                if (fy < 0.06f) shade *= 1.08f;
                shade = Mathf.Clamp(shade, 0.4f, 1.2f);
                return new Color(shade, shade, shade, 1f);
            });
            TexCache["roof"] = t;
            return t;
        }

        static Texture2D TexThatch()
        {
            Texture2D t;
            if (TexCache.TryGetValue("thatch", out t)) return t;
            const int S = 64;
            t = MakeTex("KitTexThatch", S, S, (x, y) =>
            {
                float n = Mathf.PerlinNoise(x * 0.45f, y * 0.09f);
                float streak = Mathf.PerlinNoise(x * 0.9f + 5f, y * 0.04f);
                float shade = 0.78f + 0.22f * n + 0.08f * (streak - 0.5f);
                if (y % 8 < 1) shade *= 0.82f;  // 横向捆扎层
                shade = Mathf.Clamp(shade, 0.45f, 1.15f);
                return new Color(shade, shade, shade, 1f);
            });
            TexCache["thatch"] = t;
            return t;
        }

        static Texture2D TexPlaster()
        {
            Texture2D t;
            if (TexCache.TryGetValue("plaster", out t)) return t;
            const int S = 64;
            t = MakeTex("KitTexPlaster", S, S, (x, y) =>
            {
                float n = Mathf.PerlinNoise(x * 0.13f, y * 0.13f);
                float n2 = Mathf.PerlinNoise(x * 0.55f + 11f, y * 0.55f + 7f);
                float shade = 0.94f + 0.055f * n + 0.025f * (n2 - 0.5f);
                return new Color(shade, shade, shade, 1f);
            });
            TexCache["plaster"] = t;
            return t;
        }

        static Texture2D TexWood()
        {
            Texture2D t;
            if (TexCache.TryGetValue("wood", out t)) return t;
            const int S = 32;
            const int H = 64;
            t = MakeTex("KitTexWood", S, H, (x, y) =>
            {
                float grain = Mathf.PerlinNoise(x * 0.55f + 3f, y * 0.045f);
                float fine = Mathf.PerlinNoise(x * 1.4f, y * 0.15f);
                float shade = 0.84f + 0.14f * grain + 0.05f * (fine - 0.5f);
                if (Mathf.Abs(Mathf.Sin(y * 0.11f + grain * 4f)) > 0.965f) shade *= 0.78f; // 木纹裂缝
                shade = Mathf.Clamp(shade, 0.45f, 1.1f);
                return new Color(shade, shade, shade, 1f);
            });
            TexCache["wood"] = t;
            return t;
        }

        static Texture2D TexStone()
        {
            Texture2D t;
            if (TexCache.TryGetValue("stone", out t)) return t;
            const int S = 64;
            t = MakeTex("KitTexStone", S, S, (x, y) =>
            {
                int row = y / 16;
                float off = (row % 2 == 0) ? 0f : 0.5f;
                float bx = Mathf.Repeat((x / 32f + off), 1f);
                float shade = 0.9f + 0.1f * Mathf.PerlinNoise(x * 0.2f, y * 0.2f);
                if (y % 16 == 0) shade *= 0.74f;       // 横缝
                if (bx < 0.045f) shade *= 0.8f;        // 竖缝
                shade = Mathf.Clamp(shade, 0.45f, 1.1f);
                return new Color(shade, shade, shade, 1f);
            });
            TexCache["stone"] = t;
            return t;
        }

        static Texture2D TexStripes(Color a, Color b)
        {
            string key = "stripe_" + ColorUtility.ToHtmlStringRGB(a) + "_" + ColorUtility.ToHtmlStringRGB(b);
            Texture2D t;
            if (TexCache.TryGetValue(key, out t)) return t;
            const int S = 32;
            t = MakeTex("KitTexStripe", S, S, (x, y) =>
            {
                int band = x / 8;
                Color c = (band % 2 == 0) ? a : b;
                float shade = 0.94f + 0.06f * Mathf.PerlinNoise(x * 0.6f, y * 0.6f);
                return new Color(c.r * shade, c.g * shade, c.b * shade, 1f);
            });
            TexCache[key] = t;
            return t;
        }

        static Texture2D TexWeave()
        {
            Texture2D t;
            if (TexCache.TryGetValue("weave", out t)) return t;
            const int S = 32;
            t = MakeTex("KitTexWeave", S, S, (x, y) =>
            {
                float weave = ((x / 2 + y / 2) % 2 == 0) ? 1.03f : 0.97f;
                float shade = weave * (0.95f + 0.05f * Mathf.PerlinNoise(x * 0.4f, y * 0.4f));
                return new Color(shade, shade, shade, 1f);
            });
            TexCache["weave"] = t;
            return t;
        }
    }

    // ============================================================================================
    // 色板：把 MapMaterials 的具名材质映射回颜色，供程序化纹理的 tint 用。
    // ============================================================================================
    internal static class KitPalette
    {
        public static readonly Color Ink = MapMaterials.Hex("#2B1D14");
        public static readonly Color InkSoft = MapMaterials.Hex("#4A3222");
        public static readonly Color Parchment = MapMaterials.Hex("#E8D5B0");

        public static Color Of(string key)
        {
            if (string.IsNullOrEmpty(key)) return MapMaterials.StoneWall;
            // 墙面
            if (key.StartsWith("plaster_", StringComparison.Ordinal))
            {
                switch (key)
                {
                    case "plaster_warm": return MapMaterials.PlasterWarm;
                    case "plaster_cream": return MapMaterials.PlasterCream;
                    case "plaster_ochre": return MapMaterials.PlasterOchre;
                    case "plaster_grey": return MapMaterials.PlasterGrey;
                    case "plaster_salmon": return MapMaterials.PlasterSalmon;
                    case "plaster_white": return MapMaterials.PlasterWhite;
                }
            }
            switch (key)
            {
                // 木筋 / 木
                case "timber_dark": return MapMaterials.TimberDark;
                case "timber_mid": return MapMaterials.TimberMid;
                case "timber_light": return MapMaterials.TimberLight;
                case "wood_plank": return MapMaterials.WoodPlank;
                case "wood_dark": return MapMaterials.WoodDark;
                case "wood_barrel": return MapMaterials.WoodBarrel;
                case "wood_light": return MapMaterials.WoodLight;
                // 屋顶
                case "roof_terracotta": return MapMaterials.RoofTerracotta;
                case "roof_slate": return MapMaterials.RoofSlate;
                case "roof_teal": return MapMaterials.RoofTeal;
                case "roof_burgundy": return MapMaterials.RoofBurgundy;
                case "roof_thatch": return MapMaterials.RoofThatch;
                case "roof_blue": return MapMaterials.RoofBlue;
                // 石
                case "stone_wall": return MapMaterials.StoneWall;
                case "stone_dark": return MapMaterials.StoneDark;
                case "stone_light": return MapMaterials.StoneLight;
                case "cobble": return MapMaterials.Cobble;
                case "brick": return MapMaterials.Brick;
                case "marble": return MapMaterials.Marble;
                // 布
                case "cloth_red": return MapMaterials.ClothRed;
                case "cloth_blue": return MapMaterials.ClothBlue;
                case "cloth_green": return MapMaterials.ClothGreen;
                case "cloth_purple": return MapMaterials.ClothPurple;
                case "cloth_cream": return MapMaterials.ClothCream;
                case "cloth_teal": return MapMaterials.ClothTeal;
                case "cloth_orange": return MapMaterials.ClothOrange;
                // 金属
                case "iron": return MapMaterials.IronDark;
                case "iron_grey": return MapMaterials.IronGrey;
                case "steel": return MapMaterials.Steel;
                case "gold": return MapMaterials.Gold;
                case "bronze": return MapMaterials.Bronze;
                case "copper": return MapMaterials.Copper;
            }
            return MapMaterials.StoneWall;
        }

        public static Color Darken(Color c, float f)
        {
            return new Color(c.r * (1f - f), c.g * (1f - f), c.b * (1f - f), c.a);
        }

        public static Color Lighten(Color c, float f)
        {
            return new Color(c.r + (1f - c.r) * f, c.g + (1f - c.g) * f, c.b + (1f - c.b) * f, c.a);
        }

        public static Color Lerp(Color a, Color b, float t)
        {
            return Color.Lerp(a, b, t);
        }
    }
}
