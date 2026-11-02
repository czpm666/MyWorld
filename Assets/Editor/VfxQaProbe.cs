// VFX QA 探针（vfx-dev）：把「打击特效与命中反馈」的验收标准变成**可复现的客观断言**。
//
//   菜单 1  Tools/VFX QA/自检（编辑期，不开 Play）
//           → 纯逻辑自检（分级表自洽、点阵字形有墨、击退随伤害单调）。
//             不需要进 Play、不需要场景里有任何物体。结果写 Assets/Screenshots/vfx_qa_editmode_report.txt
//
//   菜单 2  Tools/VFX QA/Capture Showcase   （**需要先进 Play 模式**）
//           → 把玩家挪到敌人旁边，按 轻/重/暴 三档 + 法术/箭矢/格挡/玩家受击 各打一次，
//             每段截图一张 + 采集客观指标，最后写 Assets/Screenshots/vfx_qa_report.txt
//             报告里有 **VERDICT 段**：每条验收标准一行 PASS/FAIL，FAIL 会写出实测值。
//
// 注意：这是临时测试脚本，QA 完成后应删除，不属于正式运行时模块。
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEngine;
using MyWorld;

public static class VfxQaProbe
{
    // ==================== 菜单 1：编辑期自检 ====================

    [MenuItem("Tools/VFX QA/自检（编辑期，不开 Play）")]
    public static void EditModeSelfTest()
    {
        var sb = new StringBuilder();
        int fail = 0;

        sb.AppendLine("VFX QA — 编辑期自检（不需要 Play 模式）");
        sb.AppendLine("unity=" + Application.unityVersion + "  time=" + System.DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
        sb.AppendLine();

        // ---------- 1) 飘字点阵图集 ----------
        string textReport;
        bool textOk = VfxTextPool.SelfTest(out textReport);
        sb.Append(textReport);
        if (!textOk) fail++;

        // ---------- 2) 分级表自洽 ----------
        sb.AppendLine();
        sb.AppendLine("VfxFeel 分级表自洽性");
        fail += CheckTable(sb, "hitStopSeconds", VfxFeel.HitStopSeconds);
        fail += CheckTable(sb, "shakeAmplitude", VfxFeel.ShakeAmplitude);
        fail += CheckTable(sb, "shakeSeconds", VfxFeel.ShakeSeconds);
        fail += CheckTable(sb, "effectScale", VfxFeel.EffectScale);
        fail += CheckTable(sb, "flashSeconds", VfxFeel.FlashSeconds);
        fail += CheckTable(sb, "stunScale", VfxFeel.StunScale);
        fail += CheckTable(sb, "knockbackGrids", VfxFeel.KnockbackGrids);
        fail += CheckTable(sb, "textScale", VfxFeel.TextScale);
        sb.AppendLine("  闪色每档各不相同: " + Describe(AllDistinct(VfxFeel.FlashColor)));
        if (!AllDistinct(VfxFeel.FlashColor)) fail++;

        // ---------- 3) 分级随伤害单调 ----------
        sb.AppendLine();
        sb.AppendLine("分级随伤害单调（轻 < 重 < 暴）");
        float h = VfxFeel.HeavyDamage;
        float c = VfxFeel.CritDamage;
        // CheckGrade 为了断言确定会把 CritChance 关成 0，这里先存后还 ——
        // 不让一次自检顺带改掉"用户调好的暴击概率"。
        float savedCritChance = VfxFeel.CritChance;
        fail += CheckGrade(sb, h * 0.5f, HitGrade.Light, "轻击样本 " + (h * 0.5f).ToString("F1"));
        fail += CheckGrade(sb, (h + c) * 0.5f, HitGrade.Heavy, "重击样本 " + ((h + c) * 0.5f).ToString("F1"));
        fail += CheckGrade(sb, c + 1f, HitGrade.Crit, "暴击样本 " + (c + 1f).ToString("F1"));
        VfxFeel.CritChance = savedCritChance;

        // 击退距离必须随伤害不减
        float last = -1f;
        bool kbOk = true;
        for (float d = 1f; d <= 80f; d += 1f)
        {
            float kb = VfxFeel.KnockbackDistance(d);
            if (kb < last - 0.0001f) { kbOk = false; break; }
            last = kb;
        }
        sb.AppendLine("  击退距离随伤害不减: " + Describe(kbOk) + "（1→80 伤害逐一比对）");
        if (!kbOk) fail++;

        // 三件套的档位单调（重的一下必须更狠）
        bool stopDurMono = VfxFeel.HitStopFor(HitGrade.Light) < VfxFeel.HitStopFor(HitGrade.Heavy)
                           && VfxFeel.HitStopFor(HitGrade.Heavy) < VfxFeel.HitStopFor(HitGrade.Crit);
        // 深度是**递减**的（0.10 → 0.06 → 0.035）：timeScale 压得越低顿得越死。
        // 单独断言这一条，是因为"只分级时长、不分级深度"曾经真的发生过 —— 三档都冻到同一个倍速，
        // 手感一模一样，Play 模式判定 ④ 的 MinTimeScale 也分不出来。
        bool stopDepMono = VfxFeel.HitStopDepthFor(HitGrade.Light) > VfxFeel.HitStopDepthFor(HitGrade.Heavy)
                           && VfxFeel.HitStopDepthFor(HitGrade.Heavy) > VfxFeel.HitStopDepthFor(HitGrade.Crit)
                           && VfxFeel.HitStopDepthFor(HitGrade.Crit) > 0.005f;
        bool shakeMono = VfxFeel.ShakeAmpFor(HitGrade.Light) < VfxFeel.ShakeAmpFor(HitGrade.Heavy)
                         && VfxFeel.ShakeAmpFor(HitGrade.Heavy) < VfxFeel.ShakeAmpFor(HitGrade.Crit);
        bool fxMono = VfxFeel.EffectScaleFor(HitGrade.Light) < VfxFeel.EffectScaleFor(HitGrade.Heavy)
                      && VfxFeel.EffectScaleFor(HitGrade.Heavy) < VfxFeel.EffectScaleFor(HitGrade.Crit);
        bool mono = stopDurMono && stopDepMono && shakeMono && fxMono;
        sb.AppendLine("  顿帧时长 三档严格递增: " + Describe(stopDurMono) + "  ["
                      + Join(new[] { VfxFeel.HitStopFor(HitGrade.Light), VfxFeel.HitStopFor(HitGrade.Heavy), VfxFeel.HitStopFor(HitGrade.Crit) }) + "]");
        sb.AppendLine("  顿帧深度 三档严格递减（越小顿得越死）: " + Describe(stopDepMono) + "  ["
                      + Join(new[] { VfxFeel.HitStopDepthFor(HitGrade.Light), VfxFeel.HitStopDepthFor(HitGrade.Heavy), VfxFeel.HitStopDepthFor(HitGrade.Crit) }) + "]");
        sb.AppendLine("  震屏幅度三档严格递增: " + Describe(shakeMono) + "   粒子量三档严格递增: " + Describe(fxMono));
        sb.AppendLine("  顿帧(时长+深度)/震屏/粒子量 全部严格单调: " + Describe(mono));
        if (!mono) fail++;

        // ---------- 4) Inspector 组件的出厂值必须和 VfxFeel 的出厂值一致 ----------
        // `VfxHub.Awake()` 会 `AddComponent<VfxFeelSettings>()`，组件的**字段初始化值**经 `Apply()`
        // 写回静态表。两边一旦不同步，Inspector 里抄的那一份就会**静默覆盖** `VfxFeel` 的出厂值。
        // 这个坑真的踩过：`KnockbackGrids` 在 VfxFeel 里改成 0.18/0.45/0.85，运行时却被组件改回旧值。
        sb.AppendLine();
        sb.AppendLine("Inspector 组件默认值 vs VfxFeel 出厂值");
        float[][] before = SnapshotFeel();
        var probeGo = new GameObject("[VfxFeelDefaultsProbe]");
        var probe = probeGo.AddComponent<VfxFeelSettings>();
        probe.Apply();                       // 显式调用：编辑期不保证 Awake 会跑
        float[][] after = SnapshotFeel();
        bool sameDefaults = SameFeel(before, after);
        if (Application.isPlaying) Object.Destroy(probeGo); else Object.DestroyImmediate(probeGo);
        VfxFeel.ResetToDefaults();           // Apply() 已经把静态表覆盖过一遍，恢复出厂
        sb.AppendLine("  组件 Apply() 后静态表保持不变: " + Describe(sameDefaults));
        if (!sameDefaults)
        {
            for (int i = 0; i < before.Length; i++)
                if (!SameFeel(new[] { before[i] }, new[] { after[i] }))
                    sb.AppendLine("    MISMATCH " + FeelTableNames[i]
                                  + "  VfxFeel=[" + Join(before[i]) + "]  组件=[" + Join(after[i]) + "]");
            fail++;
        }

        sb.AppendLine();
        sb.AppendLine(fail == 0 ? "EDIT-MODE VERDICT: PASS (0 fail)" : "EDIT-MODE VERDICT: FAIL (" + fail + " fail)");

        Write("vfx_qa_editmode_report.txt", sb.ToString());
        if (fail == 0) Debug.Log("[VfxQaProbe] 编辑期自检 PASS\n" + sb);
        else Debug.LogError("[VfxQaProbe] 编辑期自检 FAIL (" + fail + ")\n" + sb);
    }

    static int CheckTable(StringBuilder sb, string name, float[] t)
    {
        if (t == null || t.Length < 3) { sb.AppendLine("  FAIL " + name + " 长度 < 3"); return 1; }
        bool increasing = t[0] < t[1] && t[1] < t[2];
        bool positive = t[0] > 0f && t[1] > 0f && t[2] > 0f;
        sb.AppendLine("  " + name + " = [" + t[0].ToString("F3") + ", " + t[1].ToString("F3") + ", "
                      + t[2].ToString("F3") + "]  递增=" + Describe(increasing) + " 全正=" + Describe(positive));
        return (increasing && positive) ? 0 : 1;
    }

    static int CheckGrade(StringBuilder sb, float damage, HitGrade expected, string label)
    {
        VfxFeel.ForceGradeIndex = -1;
        VfxFeel.CritChance = 0f;                       // 关掉随机，让断言确定
        HitGrade got = VfxFeel.DeterministicGrade(damage);
        bool ok = got == expected;
        sb.AppendLine("  " + label + " → " + got + "（期望 " + expected + "）" + (ok ? " OK" : " FAIL"));
        return ok ? 0 : 1;
    }

    /// <summary>与 <see cref="SnapshotFeel"/> 一一对应的表名，用于打印 MISMATCH。</summary>
    static readonly string[] FeelTableNames =
    {
        "hitStopSeconds", "hitStopDepth", "shakeAmplitude", "shakeSeconds", "effectScale",
        "flashSeconds", "stunScale", "knockbackGrids", "textScale",
        "heavyDamage", "critDamage", "textLife"
    };

    /// <summary>快照 <see cref="VfxFeel"/> 的全部出厂表（含 3 个标量，包成长度 1 的数组统一比较）。</summary>
    static float[][] SnapshotFeel()
    {
        return new[]
        {
            (float[])VfxFeel.HitStopSeconds.Clone(),
            (float[])VfxFeel.HitStopDepth.Clone(),
            (float[])VfxFeel.ShakeAmplitude.Clone(),
            (float[])VfxFeel.ShakeSeconds.Clone(),
            (float[])VfxFeel.EffectScale.Clone(),
            (float[])VfxFeel.FlashSeconds.Clone(),
            (float[])VfxFeel.StunScale.Clone(),
            (float[])VfxFeel.KnockbackGrids.Clone(),
            (float[])VfxFeel.TextScale.Clone(),
            new[] { VfxFeel.HeavyDamage },
            new[] { VfxFeel.CritDamage },
            new[] { VfxFeel.TextLife },
        };
    }

    static bool SameFeel(float[][] a, float[][] b)
    {
        for (int i = 0; i < a.Length; i++)
        {
            if (a[i].Length != b[i].Length) return false;
            for (int j = 0; j < a[i].Length; j++)
                if (Mathf.Abs(a[i][j] - b[i][j]) > 0.0001f) return false;
        }
        return true;
    }

    static string Join(float[] v)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < v.Length; i++)
        {
            if (i > 0) sb.Append(",");
            sb.Append(v[i].ToString("F3"));
        }
        return sb.ToString();
    }

    static bool AllDistinct(Color[] colors)
    {
        for (int i = 0; i < colors.Length; i++)
            for (int j = i + 1; j < colors.Length; j++)
                if (Mathf.Abs(colors[i].r - colors[j].r) + Mathf.Abs(colors[i].g - colors[j].g)
                    + Mathf.Abs(colors[i].b - colors[j].b) < 0.02f) return false;
        return true;
    }

    static string Describe(bool b) { return b ? "YES" : "NO"; }

    // ==================== 菜单 2：Play 模式截图 + 采样 ====================

    [MenuItem("Tools/VFX QA/Capture Showcase")]
    public static void CaptureShowcase()
    {
        if (!EditorApplication.isPlaying)
        {
            Debug.LogError("[VfxQaProbe] 需要先进入 Play 模式");
            return;
        }
        if (Object.FindFirstObjectByType<VfxQaProbeRunner>() != null)
        {
            Debug.LogWarning("[VfxQaProbe] 已经有一个探针在跑");
            return;
        }
        var go = new GameObject("[VfxQaProbeRunner]");
        go.AddComponent<VfxQaProbeRunner>();
    }

    // ==================== 菜单 3：剑影自审（4 帧连拍） ====================

    [MenuItem("Tools/VFX QA/Capture Slash Review（剑影 4 帧连拍）")]
    public static void CaptureSlashReview()
    {
        if (!EditorApplication.isPlaying)
        {
            Debug.LogError("[VfxQaProbe] 需要先进入 Play 模式");
            return;
        }
        if (Object.FindFirstObjectByType<SlashReviewRunner>() != null)
        {
            Debug.LogWarning("[VfxQaProbe] 剑影自审已经在跑");
            return;
        }
        var go = new GameObject("[SlashReviewRunner]");
        go.AddComponent<SlashReviewRunner>();
    }

    internal static void Write(string fileName, string content)
    {
        Directory.CreateDirectory(Path.Combine(Application.dataPath, "Screenshots"));
        File.WriteAllText(Path.Combine("Assets/Screenshots", fileName), content);
    }
}

public sealed class VfxQaProbeRunner : MonoBehaviour
{
    const string ShotDir = "Assets/Screenshots";

    /// <summary>
    /// 采样期间 PNG 的**暂存目录**（不在 `Assets/` 下）。
    ///
    /// 为什么必须暂存：往 `Assets/` 里写 PNG 会触发资源导入，而这个导入在 Play 模式下
    /// 可能带出 `StopAssetImportingV2(ForceSynchronousImport | ForceDomainReload)` ——
    /// 域重载会**直接掐断 Play 会话**。实测：7 张图刚写完 Unity 就重载了程序集，
    /// 而 `WriteReport()` 是 `Start()` 的最后一步，结果整份报告没写出来。
    /// 写 `Temp/` 不触发导入，采样全程无打扰；等报告落盘后由 `PublishShots()` 一次性发布。
    /// </summary>
    const string StageDir = "Temp/vfx_qa";

    /// <summary>一段采样的观测量。每条验收标准都能从中读出数字，不靠人眼。</summary>
    internal sealed class Sample
    {
        public string Name;
        public float Started;              // 这一段开始的 realtimeSinceStartup（Duration 的基准）
        public float MinTimeScale = 99f;
        public float MaxShake;
        public int MaxParticles;
        public int MaxRings;
        public int MaxTexts;
        public int TransientsPeak;
        public float Duration;

        // 命中几何（来自 VfxCombat.LastImpact）
        public bool HasImpact;
        public VfxCombat.ImpactKind Kind;
        public HitGrade Grade;
        public float Damage;
        public float HitPointDistanceToCenter = -1f;   // 真实碰撞点离敌人 transform.position 多远
        public float HitPointSideDot = -2f;            // 碰撞点在"朝攻击者那一侧"的余弦
        public float DirectionDot = -2f;               // 命中方向 vs 期望攻击方向的余弦
    }

    readonly List<Sample> samples = new List<Sample>();
    readonly StringBuilder log = new StringBuilder();
    readonly List<string> verdicts = new List<string>();

    /// <summary>每张截图的客观体检结果（亮度均值 / 对比度 / 字节数），写进报告用。</summary>
    readonly List<string> shotStats = new List<string>();
    int shotCount;          // 一共要截几张
    int flatShots;          // 其中"没出图 / 全灰 / 空白"的张数 —— 判定 ⑨ 全靠它

    /// <summary>
    /// 截图：**故意不用 `ScreenCapture.CaptureScreenshot`**。
    ///
    /// 实测（town-dev 和 lead 都踩过）：编辑器窗口在后台或最小化时，`ScreenCapture` 系
    /// 会返回**全灰/空白图** —— 那等于白跑一个全队共享的 Play 窗口。这里改成把相机手动渲到
    /// RenderTexture 再 `ReadPixels` + `EncodeToPNG` 落盘，不依赖 Game View 的焦点与窗口状态。
    ///
    /// 两个坑都处理了：
    ///   * **颜色空间**：本项目是 Linear（`ProjectSettings.asset` 里 `m_ActiveColorSpace: 1`），
    ///     RT 必须显式按 sRGB 建，否则读回来的是线性值，PNG 会整体发灰发暗。
    ///   * **空白图自证**：顺手算这张图的亮度均值与对比度（标准差）。全灰图的 std ≈ 0，
    ///     会被报告里的判定 ⑨ 直接抓成 FAIL —— 而不是让人对着 7 张灰图反推哪里错了。
    ///
    /// 注意：Screen Space - Overlay 的 UI **不会**出现在 `cam.Render()` 的结果里
    /// （它由最后的屏幕合成画上去）。对"看特效"来说这反而更好，画面里没有 HUD 挡着。
    /// </summary>
    void Shot(string path)
    {
        shotCount++;

        Camera cam = Camera.main;
        if (cam == null)
        {
            flatShots++;
            shotStats.Add(Path.GetFileName(path) + "  mean=n/a std=n/a bytes=0  <-- 场景里没有 Camera.main");
            Debug.LogWarning("[VfxQaProbe] 场景里没有 Camera.main，跳过截图 " + path);
            return;
        }

        const int W = 1280, H = 720;
        RenderTexture rt = RenderTexture.GetTemporary(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        RenderTexture prevActive = RenderTexture.active;
        RenderTexture prevTarget = cam.targetTexture;

        try
        {
            cam.targetTexture = rt;
            cam.Render();                       // 手动渲一帧，不经过 Game View
            RenderTexture.active = rt;

            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply(false, false);

            Color32[] px = tex.GetPixels32();
            double sum = 0.0, sumSq = 0.0;
            int n = 0;
            for (int i = 0; i < px.Length; i += 7)          // 抽样：每 7 个像素取 1 个
            {
                float luma = (px[i].r * 0.299f + px[i].g * 0.587f + px[i].b * 0.114f) / 255f;
                sum += luma;
                sumSq += luma * luma;
                n++;
            }
            float mean = n > 0 ? (float)(sum / n) : 0f;
            float meanSq = n > 0 ? (float)(sumSq / n) : 0f;
            float std = Mathf.Sqrt(Mathf.Max(0f, meanSq - mean * mean));

            byte[] png = tex.EncodeToPNG();
            Object.Destroy(tex);

            string head = Path.GetFileName(path) + "  mean=" + mean.ToString("F3") + " std=" + std.ToString("F3");

            if (png == null || png.Length == 0)
            {
                flatShots++;
                shotStats.Add(head + " bytes=0  <-- EncodeToPNG 返回空");
                Debug.LogWarning("[VfxQaProbe] EncodeToPNG 返回空: " + path);
                return;
            }

            // 先写 Temp/，不直接写 Assets/：往 Assets/ 写 PNG 会触发资源导入，
            // 在 Play 模式下可能带出 ForceDomainReload 掐断整个 Play 会话。
            // 采样全部结束、报告落盘之后，由 PublishShots() 再发布到 Assets/Screenshots/。
            Directory.CreateDirectory(StageDir);
            File.WriteAllBytes(Path.Combine(StageDir, Path.GetFileName(path)), png);
            if (std < 0.02f)
            {
                flatShots++;
                shotStats.Add(head + " bytes=" + png.Length + "  <-- 对比度过低，疑似全灰/空白图");
                Debug.LogWarning("[VfxQaProbe] 截图疑似全灰/空白（对比度 " + std.ToString("F4") + "）: " + path);
            }
            else
            {
                shotStats.Add(head + " bytes=" + png.Length);
            }
        }
        catch (System.Exception e)
        {
            flatShots++;
            shotStats.Add(Path.GetFileName(path) + " 截图抛异常: " + e.Message);
            Debug.LogError("[VfxQaProbe] 截图失败 " + path + ": " + e);
        }
        finally
        {
            cam.targetTexture = prevTarget;
            RenderTexture.active = prevActive;
            RenderTexture.ReleaseTemporary(rt);
        }
    }

    PlayerCombat combat;
    Enemy enemy;              // 场景里真实存在的敌人（优先用它，保真度最高）
    Transform hitTarget;      // 实际被命中的目标：真敌人，或探针临时造的可命中标靶
    VfxQaTarget dummy;        // hitTarget 是标靶时才非 null
    GameObject dummyGo;
    bool usingDummy;
    Transform pt;
    Vector3 forward;
    int textCapacity;

    IEnumerator Start()
    {
        Directory.CreateDirectory(Path.Combine(Application.dataPath, "Screenshots"));
        yield return new WaitForSecondsRealtime(0.5f);

        PlayerHealth player = Object.FindFirstObjectByType<PlayerHealth>();
        if (player == null)
        {
            Debug.LogError("[VfxQaProbe] 场景里找不到 PlayerHealth");
            yield break;
        }
        combat = player.GetComponent<PlayerCombat>();

        pt = player.transform;
        enemy = FirstAliveEnemy(pt, 40f);
        usingDummy = enemy == null;
        if (usingDummy)
        {
            // 这个场景里没有活着的敌人（例如正在跑某个地图场景）。为了不白白浪费一个
            // **全局共享的 Play 窗口**，探针自己造一个「最小可命中标靶」：
            // 胶囊碰撞体 + 最小 IDamageable 实现。
            //
            // ⚠️ 这不是"绕过真实路径"：`PlayerCombat.OnSlashImpact` 的判定球照常查到它，
            //    `Collider.ClosestPoint(判定中心)` 给出的仍然是**真实碰撞点**。
            //    唯一少掉的是 `Enemy` 自己的表现（闪色/僵直/BloodColor 血花）——
            //    报告里会写明这一次的目标是标靶，不会假装测过敌人。
            dummyGo = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            dummyGo.name = "[VfxQaTarget]";
            Vector3 pos = pt.position + pt.forward * 2.2f;
            pos.y = pt.position.y + 1.0f;              // 胶囊高 2，让底边贴地
            dummyGo.transform.position = pos;
            dummyGo.transform.localScale = new Vector3(0.8f, 1.0f, 0.8f);
            var dr = dummyGo.GetComponent<Renderer>();
            if (dr != null) dr.sharedMaterial = PlaceholderArt.NewLit(new Color(0.52f, 0.50f, 0.60f));
            dummy = dummyGo.AddComponent<VfxQaTarget>();
            hitTarget = dummyGo.transform;
            Debug.LogWarning("[VfxQaProbe] 场景里没有活着的敌人 → 用临时标靶 [VfxQaTarget] 采样（结束时销毁）");
        }
        else
        {
            hitTarget = enemy.transform;
        }

        // 站到目标旁边（1.8m），让镜头能同时看到玩家与命中点
        Vector3 toPlayer = pt.position - hitTarget.position;
        toPlayer.y = 0f;
        if (toPlayer.sqrMagnitude < 0.01f) toPlayer = Vector3.forward;
        float keepY = pt.position.y;                       // 目标的中轴高度≠地面高度（标靶尤其明显）
        pt.position = hitTarget.position + toPlayer.normalized * 1.8f;
        pt.position = new Vector3(pt.position.x, keepY, pt.position.z);   // 别把玩家顶到半空
        yield return new WaitForSecondsRealtime(0.4f);
        pt.rotation = Quaternion.LookRotation(new Vector3(
            hitTarget.position.x - pt.position.x, 0f,
            hitTarget.position.z - pt.position.z));
        yield return new WaitForSecondsRealtime(0.2f);
        forward = pt.forward;

        textCapacity = VfxHub.Instance != null && VfxHub.Instance.Text != null
            ? VfxHub.Instance.Text.Capacity : -1;

        // 全局放慢，方便截图抓到"命中瞬间"（真实游戏里是正常速度）
        Time.timeScale = 0.25f;

        // ---------- 近战三档：走 **PlayerCombat.OnSlashImpact 真实入口** ----------
        for (int g = 0; g < 3; g++)
        {
            string name = g == 0 ? "melee_light" : (g == 1 ? "melee_heavy" : "melee_crit");
            yield return MeleeSample(g, name);
            yield return new WaitForSecondsRealtime(0.35f);   // 等上一次的余韵散掉
        }

        // ---------- 法术：真实 SpellProjectile 飞到敌人身上 ----------
        yield return RangedSample("spell_crit", 2, true);

        // ---------- 箭矢：真实 ArrowProjectile 飞到敌人身上 ----------
        yield return RangedSample("arrow_crit", 2, false);

        // ---------- 格挡：SkillVfx.BlockArc（敌人格挡的真实入口） ----------
        yield return BlockSample();

        // ---------- 玩家受击：VfxCombat.PlayerHurt（VfxDirector 的真实入口） ----------
        yield return PlayerHurtSample();

        // ---------- 回收检查：一口气打 30 下，看一次性特效物体是否回落到 0 ----------
        yield return RecycleCheck();

        Time.timeScale = 1f;
        VfxFeel.ForceGradeIndex = -1;
        WriteReport(player);
        Debug.Log("[VfxQaProbe] 完成，报告写到 " + ShotDir + "/vfx_qa_report.txt");
        Destroy(gameObject);
    }

    /// <summary>
    /// 安全网。**Play 模式是全队共享的资源**，所以探针不管怎么退出都必须把全局状态还原：
    ///   * `Time.timeScale` —— 探针会把它压到 0.25 抓命中帧；一旦中途抛异常/被强杀，
    ///     不还原就会把整个编辑器留在慢动作里，别人接手时一脸懵；
    ///   * `VfxFeel.ForceGradeIndex` —— 强制档位会污染后续所有采样；
    ///   * 临时标靶 —— 别在场景里留一个来路不明的胶囊。
    /// </summary>
    void OnDestroy()
    {
        Time.timeScale = 1f;
        VfxFeel.ForceGradeIndex = -1;
        if (dummyGo != null) Destroy(dummyGo);
    }

    // ==================== 各段采样 ====================

    IEnumerator MeleeSample(int gradeIndex, string name)
    {
        var s = NewSample(name);
        VfxFeel.ForceGradeIndex = gradeIndex;

        // 走真实路径：`Use()` 起手 → `OnSlashImpact()` 命中帧。
        // 这样测的是 **PlayerCombat 自己算出来的真实碰撞点**，不是探针另算一个点。
        bool real = TryRealMeleeSwing();

        if (!real)
        {
            // 兜底：手上没剑（比如起始武器是法杖）→ 探针复刻 PlayerCombat 的查询，
            // 但仍然用 `Collider.ClosestPoint(判定中心)` 这个**真实碰撞点**。
            Vector3 center = pt.position + Vector3.up * 1.2f;
            Vector3 hp = ProbeClosestPoint(center, 2.4f, out Vector3 nrm);
            SkillVfx.SwordSlash(center, forward, 2.4f, 65f, gradeIndex + 1,
                hp, Flat(forward), DamageFor(gradeIndex), nrm);
        }

        yield return null;
        yield return null;
        Shot(Path.Combine(ShotDir, "vfx_" + name + ".png"));
        yield return Collect(s, 0.40f);

        s.HasImpact = VfxCombat.LastImpact.Kind == VfxCombat.ImpactKind.Melee;
        s.Kind = VfxCombat.LastImpact.Kind;
        FillGeometry(s);
        s.Name = name + (real ? "(real PlayerCombat path)" : "(probe-replicated path)");
    }

    IEnumerator RangedSample(string name, int gradeIndex, bool spell)
    {
        var s = NewSample(name);
        VfxFeel.ForceGradeIndex = gradeIndex;

        Vector3 origin = pt.position + Vector3.up * 1.2f + forward * 0.6f;
        Vector3 aimPoint = hitTarget.position + Vector3.up * 0.9f;
        Vector3 dir = (aimPoint - origin).normalized;
        int frame0 = Time.frameCount;

        if (spell) SpellProjectile.Spawn(origin, dir, pt, DamageFor(gradeIndex));
        else ArrowProjectile.Spawn(origin, dir, pt, DamageFor(gradeIndex), 34f, 2f, 0.28f);

        // 等它真的打中（弹速 24~34 m/s，1.8m 只需 ~0.06s 游戏时间）
        var want = spell ? VfxCombat.ImpactKind.Spell : VfxCombat.ImpactKind.Arrow;
        float t0 = Time.realtimeSinceStartup;
        while (Time.realtimeSinceStartup - t0 < 1.5f)
        {
            if (VfxCombat.LastImpact.Frame >= frame0 && VfxCombat.LastImpact.Kind == want) break;
            SampleTick(s);
            yield return null;
        }

        yield return null;
        Shot(Path.Combine(ShotDir, "vfx_" + name + ".png"));
        yield return Collect(s, 0.35f);

        s.HasImpact = VfxCombat.LastImpact.Kind == want;
        s.Kind = VfxCombat.LastImpact.Kind;
        FillGeometry(s);
    }

    IEnumerator BlockSample()
    {
        var s = NewSample("block");
        VfxFeel.ForceGradeIndex = 1;
        int frame0 = Time.frameCount;

        Vector3 anchor = hitTarget.position + Vector3.up * 1.0f
                         + Flat(pt.position - hitTarget.position).normalized * 0.35f;
        SkillVfx.BlockArc(anchor, Flat(pt.position - hitTarget.position).normalized, null,
            DamageFor(1));

        yield return null;
        yield return null;
        Shot(Path.Combine(ShotDir, "vfx_block.png"));
        yield return Collect(s, 0.35f);

        s.HasImpact = VfxCombat.LastImpact.Frame >= frame0
                      && VfxCombat.LastImpact.Kind == VfxCombat.ImpactKind.Block;
        s.Kind = VfxCombat.LastImpact.Kind;
        FillGeometry(s);
    }

    IEnumerator PlayerHurtSample()
    {
        var s = NewSample("player_hurt");
        VfxFeel.ForceGradeIndex = 2;
        Vector3 pos = pt.position;
        VfxCombat.PlayerHurt(pos, DamageFor(2));
        yield return null;
        yield return null;
        Shot(Path.Combine(ShotDir, "vfx_player_hurt.png"));
        yield return Collect(s, 0.30f);
        s.Kind = VfxCombat.ImpactKind.None;
        s.Grade = HitGrade.Crit;
    }

    /// <summary>
    /// 回收检查：连续 30 次命中（同一帧），验证
    ///   ① 粒子/飘字**不扩容**（都走预建的池）；
    ///   ② 一次性特效物体（月牙/盾弧）在 1.5s 后**回落到 0**（没有泄漏）。
    /// </summary>
    IEnumerator RecycleCheck()
    {
        var s = NewSample("recycle_x30");
        int beforeObjects = CountObjects();
        int beforeTexts = VfxHub.Instance.Text != null ? VfxHub.Instance.Text.SpawnedTotal : -1;

        VfxFeel.ForceGradeIndex = 2;
        for (int i = 0; i < 30; i++)
        {
            Vector3 p = hitTarget.position + Vector3.up * (0.7f + 0.02f * i);
            VfxCombat.MeleeImpact(p, Flat(forward), Flat(forward),
                40f, VfxCombat.SwordColor);
        }

        yield return Collect(s, 0.30f);

        float t0 = Time.realtimeSinceStartup;
        while (Time.realtimeSinceStartup - t0 < 1.6f) { SampleTick(s); yield return null; }

        int afterObjects = CountObjects();
        int alive = VfxHub.TransientsAlive;
        int spawned = VfxHub.Instance.Text != null ? VfxHub.Instance.Text.SpawnedTotal : -1;
        int reused = VfxHub.Instance.Text != null ? VfxHub.Instance.Text.ReusedTotal : -1;

        log.AppendLine();
        log.AppendLine("recycle check (30 impacts in one frame)");
        log.AppendLine("  TransientsCreated=" + VfxHub.TransientsCreated
                       + "  TransientsAlive(after 1.6s)=" + alive);
        log.AppendLine("  textSpawnedTotal=" + spawned + "  textReusedTotal=" + reused
                       + "  textCapacity=" + textCapacity
                       + "  textsBefore=" + beforeTexts);
        log.AppendLine("  sceneObjects before=" + beforeObjects + " after=" + afterObjects
                       + " delta=" + (afterObjects - beforeObjects));
        log.AppendLine("  maxParticlesDuringBurst=" + s.MaxParticles + "  maxTexts=" + s.MaxTexts
                       + "  maxRings=" + s.MaxRings);

        Verdict("特效会回收（一次性物体 1.6s 后回落到 0）",
            alive <= 1, "TransientsAlive=" + alive);
        Verdict("粒子/飘字有上限（30 连击不扩容）",
            spawned > 0 && textCapacity > 0 && s.MaxTexts <= textCapacity,
            "maxTexts=" + s.MaxTexts + " capacity=" + textCapacity);
        Verdict("飘字池真的在复用（第二次起复用旧物体）",
            reused > 0, "reusedTotal=" + reused);
        Verdict("30 连击不产生场景物体净增长（阈值 ≤ 8）",
            afterObjects - beforeObjects <= 8, "delta=" + (afterObjects - beforeObjects));
    }

    // ==================== 真实路径 / 兜底 ====================

    /// <summary>
    /// 用反射把玩家主手剑塞进 `PlayerCombat`，走**真实的起手 + 命中帧**两个回调。
    /// 返回 false = 手上没有剑（调用方走兜底复制路径）。
    /// </summary>
    bool TryRealMeleeSwing()
    {
        if (combat == null) return false;

        var f = typeof(PlayerCombat).GetField("loadout", BindingFlags.NonPublic | BindingFlags.Instance);
        if (f == null) return false;
        var loadout = f.GetValue(combat) as WeaponLoadout;
        if (loadout == null || loadout.MainHand == null) return false;
        if (loadout.MainHand.kind != WeaponKind.Sword) return false;

        // 冷却清零：一次挥砍会把 cooldown 设为武器冷却，三档连着打就要手动清
        var cd = typeof(PlayerCombat).GetField("cooldown", BindingFlags.NonPublic | BindingFlags.Instance);
        if (cd != null) cd.SetValue(combat, 0f);

        combat.Use(loadout.MainHand);
        combat.OnSlashImpact();
        return true;
    }

    /// <summary>复刻 `PlayerCombat.OnSlashImpact` 的查询，但返回**真实碰撞点**。</summary>
    Vector3 ProbeClosestPoint(Vector3 center, float range, out Vector3 normal)
    {
        normal = -Flat(forward);
        var cols = Physics.OverlapSphere(center, range, ~0, QueryTriggerInteraction.Ignore);
        for (int i = 0; i < cols.Length; i++)
        {
            var col = cols[i];
            if (col == null) continue;
            // 只要是个可伤害目标就行 —— 有真敌人时它就是敌人，没有时就是探针造的标靶。
            // ⚠️ 不要写死 `GetComponentInParent<Enemy>()`，那会让"场景里没有敌人"时兜底路径也失效。
            if (col.GetComponentInParent<IDamageable>() == null) continue;
            Vector3 p = col.ClosestPoint(center);
            Vector3 n = center - p;
            n.y = 0f;
            if (n.sqrMagnitude > 0.0001f) normal = n.normalized;
            return p;
        }
        return hitTarget.position + Vector3.up * 0.9f;
    }

    static float DamageFor(int gradeIndex)
    {
        if (gradeIndex <= 0) return VfxFeel.HeavyDamage * 0.5f;
        if (gradeIndex == 1) return (VfxFeel.HeavyDamage + VfxFeel.CritDamage) * 0.5f;
        return VfxFeel.CritDamage + 6f;
    }

    void FillGeometry(Sample s)
    {
        VfxCombat.ImpactRecord r = VfxCombat.LastImpact;
        s.Grade = r.Grade;
        s.Damage = r.Damage;
        Vector3 toAttacker = Flat(pt.position - hitTarget.position);
        if (toAttacker.sqrMagnitude < 1e-4f) toAttacker = Flat(forward);
        toAttacker.Normalize();

        s.HitPointDistanceToCenter = Vector3.Distance(Flat(r.Point), Flat(hitTarget.position));
        Vector3 off = Flat(r.Point - hitTarget.position);
        s.HitPointSideDot = off.sqrMagnitude > 1e-6f ? Vector3.Dot(off.normalized, toAttacker) : -2f;

        // 期望方向按"这一次特效到底该朝哪儿飞"来定，不是一律朝攻击者：
        //   * Melee       —— 火花沿**攻击方向**喷（攻击者 → 目标），即 `-toAttacker`。
        //                    早期版本这里误用了 `toAttacker`，导致点积恒为 -1 的假 FAIL ——
        //                    被这条断言抓出来的是"期望值写反了"，不是特效方向错。
        //   * Block       —— 格挡火花沿**来向**飞回攻击者，方向就是 `toAttacker`。
        //   * Spell/Arrow —— 沿弹道方向，探针里就是 `forward`。
        Vector3 expect;
        if (s.Kind == VfxCombat.ImpactKind.Melee) expect = -toAttacker;
        else if (s.Kind == VfxCombat.ImpactKind.Block) expect = toAttacker;
        else expect = Flat(forward);
        s.DirectionDot = Vector3.Dot(Flat(r.Direction).normalized, expect);
    }

    // ==================== 采集 ====================

    Sample NewSample(string name)
    {
        var s = new Sample { Name = name, Started = Time.realtimeSinceStartup };
        samples.Add(s);
        var shake = VfxHub.Instance != null ? VfxHub.Instance.EnsureShake() : null;
        if (shake != null) shake.ResetPeak();
        return s;
    }

    IEnumerator Collect(Sample s, float realSeconds)
    {
        float start = Time.realtimeSinceStartup;
        while (Time.realtimeSinceStartup - start < realSeconds)
        {
            SampleTick(s);
            yield return null;
        }
    }

    void SampleTick(Sample s)
    {
        if (Time.timeScale < s.MinTimeScale) s.MinTimeScale = Time.timeScale;
        if (VfxHub.Instance == null) return;

        var shake = VfxHub.Instance.EnsureShake();
        if (shake != null && shake.PeakAmplitude > s.MaxShake) s.MaxShake = shake.PeakAmplitude;

        int p = VfxHub.Instance.ActiveParticles;
        if (p > s.MaxParticles) s.MaxParticles = p;
        if (VfxHub.Instance.Rings != null && VfxHub.Instance.Rings.ActiveCount > s.MaxRings)
            s.MaxRings = VfxHub.Instance.Rings.ActiveCount;
        if (VfxHub.Instance.Text != null && VfxHub.Instance.Text.ActiveCount > s.MaxTexts)
            s.MaxTexts = VfxHub.Instance.Text.ActiveCount;
        if (VfxHub.TransientsAlive > s.TransientsPeak) s.TransientsPeak = VfxHub.TransientsAlive;
        // 相对时长（不是 realtimeSinceStartup 的绝对值）—— 绝对值会让报告里的 duration 变成天文数字
        s.Duration = Time.realtimeSinceStartup - s.Started;
    }

    static Vector3 Flat(Vector3 v) { v.y = 0f; return v; }

    static int CountObjects()
    {
        return Object.FindObjectsByType<Transform>(FindObjectsSortMode.None).Length;
    }

    static Enemy FirstAliveEnemy(Transform near, float maxDistance)
    {
        Enemy[] all = Object.FindObjectsByType<Enemy>(FindObjectsSortMode.None);
        Enemy best = null;
        float bestDist = maxDistance;
        for (int i = 0; i < all.Length; i++)
        {
            if (all[i] == null || !all[i].IsAlive) continue;
            float d = Vector3.Distance(all[i].transform.position, near.position);
            if (d < bestDist) { bestDist = d; best = all[i]; }
        }
        return best;
    }

    // ==================== 报告 ====================

    void Verdict(string claim, bool pass, string detail)
    {
        verdicts.Add((pass ? "PASS  " : "FAIL  ") + claim + "   [" + detail + "]");
    }

    Sample Find(string prefix)
    {
        for (int i = 0; i < samples.Count; i++)
            if (samples[i].Name != null && samples[i].Name.StartsWith(prefix)) return samples[i];
        return null;
    }

    void WriteReport(PlayerHealth player)
    {
        Sample light = Find("melee_light");
        Sample heavy = Find("melee_heavy");
        Sample crit = Find("melee_crit");
        Sample spell = Find("spell_crit");
        Sample arrow = Find("arrow_crit");
        Sample block = Find("block");
        Sample hurt = Find("player_hurt");

        log.Length = 0;
        log.AppendLine("VFX QA report (Play mode, Time.timeScale=0.25 during captures)");
        log.AppendLine("unity=" + Application.unityVersion
                       + "  scene=" + UnityEngine.SceneManagement.SceneManager.GetActiveScene().name);
        log.AppendLine("clipCount=" + SfxLibrary.ClipCount
                       + "  playerHealth=" + player.Health + "/" + player.MaxHealth);
        log.AppendLine("textPoolCapacity=" + textCapacity
                       + "  transientsAliveNow=" + VfxHub.TransientsAlive
                       + "  transientsCreatedTotal=" + VfxHub.TransientsCreated);
        // 目标类型必须写清楚：用临时标靶采样时，**敌人自己的**闪色/僵直/血花没有被测到。
        // 宁可报告里写明，也不要让读报告的人以为"敌人那条路也验过了"。
        log.AppendLine("target=" + (usingDummy
            ? "TEMP DUMMY [VfxQaTarget] —— 场景里没有活着的敌人；命中点/方向仍走真实路径，"
              + "但 Enemy 自身的闪色/僵直/血花未被覆盖"
            : "real Enemy '" + (enemy != null ? enemy.name : "?") + "'"));
        log.AppendLine();

        log.AppendLine("sample,kind,grade,damage,minTimeScale,peakShake(m),maxParticles,maxRings,maxTexts,transientsPeak,hpDistToCenter,hpSideDot,dirDot");
        for (int i = 0; i < samples.Count; i++)
        {
            Sample s = samples[i];
            log.AppendLine(s.Name + "," + s.Kind + "," + s.Grade + "," + s.Damage.ToString("F1") + ","
                + s.MinTimeScale.ToString("F3") + "," + s.MaxShake.ToString("F3") + ","
                + s.MaxParticles + "," + s.MaxRings + "," + s.MaxTexts + "," + s.TransientsPeak + ","
                + s.HitPointDistanceToCenter.ToString("F3") + "," + s.HitPointSideDot.ToString("F3")
                + "," + s.DirectionDot.ToString("F3"));
        }
        log.AppendLine();

        // ---------- 验收标准逐条判定 ----------
        Verdict("① 四类命中各有特效记录（近战/法术/箭矢/格挡）",
            light != null && light.HasImpact && spell != null && spell.HasImpact
            && arrow != null && arrow.HasImpact && block != null && block.HasImpact,
            "melee=" + (light != null && light.HasImpact) + " spell=" + (spell != null && spell.HasImpact)
            + " arrow=" + (arrow != null && arrow.HasImpact) + " block=" + (block != null && block.HasImpact));

        bool hpOk = light != null && light.HitPointSideDot > 0.2f && light.HitPointDistanceToCenter > 0.05f;
        Verdict("② 位置用真实碰撞点（在朝攻击者那一侧，不是身体中轴）",
            hpOk, "hpSideDot=" + F(light, x => x.HitPointSideDot) + " hpDistToCenter=" + F(light, x => x.HitPointDistanceToCenter));
        log.AppendLine("     （旧的假命中点是 `敌人.position + up*0.85`，它的 hpSideDot 恒为 0、hpDistToCenter 只有高度分量）");

        bool dirOk = light != null && light.DirectionDot > 0.99f
                     && spell != null && spell.DirectionDot > 0.99f
                     && arrow != null && arrow.DirectionDot > 0.99f;
        Verdict("③ 方向沿攻击方向 / 弹道方向（点积 > 0.99；近战=攻击方向、格挡=来向、法术/箭矢=弹道）", dirOk,
            "melee=" + F(light, x => x.DirectionDot) + " spell=" + F(spell, x => x.DirectionDot)
            + " arrow=" + F(arrow, x => x.DirectionDot));

        bool stopOrder = light != null && heavy != null && crit != null
                         && light.MinTimeScale > heavy.MinTimeScale
                         && heavy.MinTimeScale > crit.MinTimeScale
                         && crit.MinTimeScale <= 0.07f;
        Verdict("④ 顿帧随伤害分级（轻 > 重 > 暴 的 timeScale，且最重一档压到 ≤0.07）",
            stopOrder, "light=" + F(light, x => x.MinTimeScale) + " heavy=" + F(heavy, x => x.MinTimeScale)
            + " crit=" + F(crit, x => x.MinTimeScale));

        bool shakeOrder = light != null && heavy != null && crit != null
                          && light.MaxShake < heavy.MaxShake && heavy.MaxShake < crit.MaxShake;
        Verdict("⑤ 震屏随伤害分级（轻 < 重 < 暴 的峰值幅度）", shakeOrder,
            "light=" + F(light, x => x.MaxShake) + " heavy=" + F(heavy, x => x.MaxShake)
            + " crit=" + F(crit, x => x.MaxShake));

        bool textOk = light != null && light.MaxTexts > 0 && spell != null && spell.MaxTexts > 0
                      && block != null && block.MaxTexts > 0 && hurt != null && hurt.MaxTexts > 0;
        Verdict("⑥ 伤害飘字（近战/法术/格挡 BLOCK/玩家受击 都有）", textOk,
            "melee=" + I(light, x => x.MaxTexts) + " spell=" + I(spell, x => x.MaxTexts)
            + " block=" + I(block, x => x.MaxTexts) + " hurt=" + I(hurt, x => x.MaxTexts));

        bool particlesOk = light != null && heavy != null && crit != null
                           && light.MaxParticles < heavy.MaxParticles && heavy.MaxParticles < crit.MaxParticles;
        Verdict("⑦ 粒子量随伤害分级（轻 < 重 < 暴）", particlesOk,
            "light=" + I(light, x => x.MaxParticles) + " heavy=" + I(heavy, x => x.MaxParticles)
            + " crit=" + I(crit, x => x.MaxParticles));

        Verdict("⑧ 有音效（程序化音效库已加载）", SfxLibrary.ClipCount > 0,
            "clipCount=" + SfxLibrary.ClipCount);

        // 截图体检：证明这些图不是"全灰/空白" —— 后台窗口下 ScreenCapture 的经典翻车方式。
        log.AppendLine();
        log.AppendLine("截图体检（mean=平均亮度 std=对比度；全灰图的 std ≈ 0）");
        for (int i = 0; i < shotStats.Count; i++) log.AppendLine("  " + shotStats[i]);
        Verdict("⑨ 截图非空白（每张都有对比度；RenderTexture 直渲，不依赖 Game View 焦点）",
            shotCount > 0 && flatShots == 0,
            "shots=" + shotCount + " flat=" + flatShots + " recorded=" + shotStats.Count);

        log.AppendLine();
        log.AppendLine("=== VERDICT ===");
        int fails = 0;
        for (int i = 0; i < verdicts.Count; i++)
        {
            log.AppendLine(verdicts[i]);
            if (verdicts[i].StartsWith("FAIL")) fails++;
        }
        log.AppendLine(fails == 0
            ? "OVERALL: PASS (0 fail)"
            : "OVERALL: FAIL (" + fails + " fail)");

        // 顺序是刻意的：① 先落一份到 Temp/（不触发资源导入，绝对安全）；
        // ② 再写进 Assets/Screenshots/；③ 最后才发布 PNG。
        // 这样即使发布图片触发了域重载把 Play 掐断，报告也已经完整落盘。
        try
        {
            Directory.CreateDirectory(StageDir);
            File.WriteAllText(Path.Combine(StageDir, "vfx_qa_report.txt"), log.ToString());
        }
        catch (System.Exception e)
        {
            Debug.LogWarning("[VfxQaProbe] 暂存报告失败: " + e.Message);
        }

        VfxQaProbe.Write("vfx_qa_report.txt", log.ToString());
        PublishShots();
        if (fails == 0) Debug.Log("[VfxQaProbe] " + log);
        else Debug.LogError("[VfxQaProbe] " + log);
    }

    /// <summary>
    /// 采样全部结束后，把 <see cref="StageDir"/> 里暂存的 PNG 一次性发布到 `Assets/Screenshots/`。
    ///
    /// 放在最后一步是刻意的：发布图片会触发资源导入，在 Play 模式下可能带出强制域重载
    /// 而**掐断 Play 会话**。报告已经先落盘，所以即便会话就此结束，客观数据也不会丢
    /// （上一次探针就是栽在这里：图出来了，报告没了）。
    /// </summary>
    void PublishShots()
    {
        try
        {
            if (!Directory.Exists(StageDir))
            {
                Debug.LogWarning("[VfxQaProbe] 暂存目录不存在，没有可发布的截图: " + StageDir);
                return;
            }

            string dest = Path.Combine(Application.dataPath, "Screenshots");
            Directory.CreateDirectory(dest);

            string[] files = Directory.GetFiles(StageDir, "*.png");
            for (int i = 0; i < files.Length; i++)
            {
                File.Copy(files[i], Path.Combine(dest, Path.GetFileName(files[i])), true);
            }

            Debug.Log("[VfxQaProbe] 已把 " + files.Length + " 张截图从 " + StageDir + " 发布到 " + ShotDir + "/");
        }
        catch (System.Exception e)
        {
            Debug.LogWarning("[VfxQaProbe] 发布截图失败: " + e.Message
                             + "（原图仍在 " + StageDir + "，可手工拷出）");
        }
    }

    static string F(Sample s, System.Func<Sample, float> f)
    {
        return s == null ? "n/a" : f(s).ToString("F3");
    }

    static string I(Sample s, System.Func<Sample, int> f)
    {
        return s == null ? "n/a" : f(s).ToString();
    }
}

/// <summary>
/// 探针专用的**最小可命中标靶**：一个胶囊碰撞体 + 最小的 <see cref="MyWorld.IDamageable"/> 实现。
///
/// 存在的理由：`Tools/VFX QA/Capture Showcase` 需要"一个能被打中的东西"才能测出真实碰撞点。
/// 如果当前场景恰好没有活着的敌人，整套采样就没法跑 —— 而 Play 模式是**全队共享**的稀缺资源，
/// 白白浪费一个窗口的代价（十几分钟 + 一轮沟通）远高于这 20 行代码。town-dev 的城市场景
/// 就是这种"没有敌人"的情况。
///
/// ⚠️ 它**不是** <see cref="MyWorld.Enemy"/> 的替身：不参与 AI、没有血条、不闪色，
///    也**不会**触发 `Enemy.AnyDamaged`（所以血花那一路不会被它覆盖）。
///    但它走的是完全相同的判定链路 —— `PlayerCombat.OnSlashImpact` 的判定球照样查到它，
///    `Collider.ClosestPoint(判定中心)` 给出的仍然是**真实碰撞点** —— 于是
///    "位置用真实碰撞点、方向沿攻击方向"这两条验收标准测的还是真路径。
///    报告开头会写明这一次的目标是标靶。
/// </summary>
[DisallowMultipleComponent]
public sealed class VfxQaTarget : MonoBehaviour, MyWorld.IDamageable
{
    public int HitCount { get; private set; }
    public float LastDamage { get; private set; }
    public Vector3 LastPoint { get; private set; }

    // 永远活着：探针要连着打轻/重/暴三档 + 30 连击，不能被"打死了"打断
    public bool IsAlive => true;
    public Transform Transform => transform;

    public void TakeDamage(float amount, Vector3 hitPoint, Vector3 hitNormal)
    {
        HitCount++;
        LastDamage = amount;
        LastPoint = hitPoint;
    }
}

/// <summary>
/// 剑影（挥砍弧光）自审：连着打两段，各在刀锋扫过的 4 个时刻定格出图，
/// 用来逐张判断"弧光有没有贴着刀走 / alpha 衰减自不自然 / 有没有硬边和断头 / 上挑与下劈能不能一眼分开"。
///
/// 输出到 `WorkQC/slash/` —— **不在 `Assets/` 下**，所以写图不会触发资源导入、
/// 也就不会像之前那样把 Play 会话用强制域重载掐断。
/// </summary>
[DisallowMultipleComponent]
public sealed class SlashReviewRunner : MonoBehaviour
{
    /// <summary>
    /// 定格时刻，单位是**特效自己的年龄**（= 累加 `Time.deltaTime`，即缩放后的时间）。
    ///
    /// ⚠️ 早期版本用真实时间（`realtimeSinceStartup`）等这几个时刻，结果 8 张图几乎逐字节相同：
    /// 只要有一次卡顿让第一帧超过 0.05s，后面每个 `while` 都立刻满足条件，
    /// 四张照片就全挤在特效**已经消失之后**拍。用缩放时间累加则与帧率、顿帧都无关。
    /// </summary>
    static readonly float[] Ages = { 0.04f, 0.10f, 0.16f, 0.22f };

    /// <summary>
    /// 对照帧的时刻：同一个瞬间，但把弧光条带隐藏、只留月牙。
    /// 没有这条对照，评审只能说"两张图都模糊地看起来有东西"，判断不了条带到底有没有贡献。
    /// </summary>
    const float ControlAge = 0.10f;

    /// <summary>月牙的生命期（`SkillVfx.CrescentSlash.MaxLife`），用来把年龄换算成进度。</summary>
    const float CrescentLife = 0.3f;

    const int W = 1280, H = 720;

    string outDir;
    Transform target;
    GameObject dummyGo;

    IEnumerator Start()
    {
        outDir = Path.Combine(Directory.GetCurrentDirectory(), "WorkQC", "slash");
        Directory.CreateDirectory(outDir);

        var ph = Object.FindFirstObjectByType<MyWorld.PlayerHealth>();
        if (ph == null)
        {
            Debug.LogError("[SlashReview] 找不到 PlayerHealth，没法定位玩家");
            yield break;
        }
        Transform player = ph.transform;

        // 标靶摆在玩家正前方：让"刀光扫过的位置"和"命中点"的相对关系一眼可读
        dummyGo = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        dummyGo.name = "[SlashReviewTarget]";
        Vector3 p = player.position + player.forward * 2.2f;
        dummyGo.transform.position = new Vector3(p.x, player.position.y + 1.0f, p.z);
        dummyGo.transform.localScale = new Vector3(0.8f, 1f, 0.8f);
        target = dummyGo.transform;

        float savedScale = Time.timeScale;
        bool savedHitStop = MyWorld.VfxFeel.HitStopEnabled;

        // 冻结时间再拍。`Shot()` 一次约 0.2 秒（RenderTexture + ReadPixels + EncodeToPNG），
        // 早先"等到 age≥0.04 再拍"实际拍到的是 0.2 秒之后 —— 实测量到 seg1 四张全在
        // age=0.333s 拍的，那时月牙(寿命0.30)和条带(寿命0.36)都已经走完，于是四张图一模一样。
        // 冻结之后特效的 Update 不再推进，改用 Debug 接口把状态**显式**摆到指定年龄，
        // 出图就与帧率、抓图耗时、顿帧全部无关。
        Time.timeScale = 0f;
        MyWorld.VfxFeel.HitStopEnabled = false;   // 否则顿帧协程会把这 0 改回 0.06，冻结失效
        try
        {
            yield return null;
            // 1 = 横劈（平坦的横扫）  2 = 下劈（应当有一段明显的下坠弧）
            for (int seg = 1; seg <= 2; seg++)
            {
                for (int i = 0; i < Ages.Length; i++)
                    yield return CaptureAt(player, seg, Ages[i], "seg" + seg + "_f" + (i + 1), HideWhat.None);

                // 对照帧：同一瞬间，分别只藏条带 / 只藏贴地弧。
                // 没有对照就只能说"两张图都模糊地看起来有东西"，判断不了谁贡献了像素。
                yield return CaptureAt(player, seg, ControlAge, "seg" + seg + "_ctrl_noribbon", HideWhat.Ribbon);
                yield return CaptureAt(player, seg, ControlAge, "seg" + seg + "_ctrl_nogroundarc", HideWhat.GroundArc);
            }
        }
        finally
        {
            Time.timeScale = savedScale;
            MyWorld.VfxFeel.HitStopEnabled = savedHitStop;
            if (dummyGo != null) Destroy(dummyGo);
        }

        Debug.Log("[SlashReview] 出图完成 → " + outDir + "（共 " + ((Ages.Length + 2) * 2) + " 张）");
    }

    /// <summary>对照组要藏掉哪一层。</summary>
    enum HideWhat { None, Ribbon, GroundArc }

    /// <summary>
    /// 在**冻结时间**下摆好状态再拍一帧。
    /// 三层特效各自用 Debug 接口定格到指定年龄，于是同一组图之间只有年龄这一个变量。
    /// </summary>
    IEnumerator CaptureAt(Transform player, int seg, float age, string name, HideWhat hide)
    {
        Vector3 center = player.position + Vector3.up * 1.0f;
        Vector3 forward = player.forward;
        Vector3 hitPoint = target.position + Vector3.up * 0.1f;

        Vector3 attackDir = target.position - player.position;
        attackDir.y = 0f;
        if (attackDir.sqrMagnitude < 1e-4f) attackDir = forward;
        attackDir.Normalize();

        // 一律走"重击"档：满配效果才看得出上限，轻击只是它的子集
        MyWorld.VfxFeel.ForceGradeIndex = 1;
        MyWorld.SkillVfx.SwordSlash(center, forward, 2.4f, 65f, seg,
            hitPoint, attackDir, MyWorld.VfxFeel.HeavyDamage,
            (center - hitPoint).normalized);
        MyWorld.VfxFeel.ForceGradeIndex = -1;

        GameObject cres = GameObject.Find("Vfx_SwordSlash");
        GameObject rib = GameObject.Find("Vfx_SlashRibbon");
        GameObject arc = GameObject.Find("Vfx_GroundArc");

        var cv = cres != null ? cres.GetComponent<MyWorld.CrescentSlash>() : null;
        if (cv != null) cv.DebugSetProgress(Mathf.Clamp01(age / CrescentLife));

        var rv = rib != null ? rib.GetComponent<MyWorld.VfxSlashRibbon>() : null;
        if (rv != null) rv.DebugSetAge(age);

        var av = arc != null ? arc.GetComponent<MyWorld.VfxGroundArc>() : null;
        if (av != null) av.DebugSetProgress(Mathf.Clamp01(age / Mathf.Max(0.05f, av.DebugLife)));

        if (hide == HideWhat.Ribbon && rib != null) rib.SetActive(false);
        if (hide == HideWhat.GroundArc && arc != null) arc.SetActive(false);

        Shot(Path.Combine(outDir, name + ".png"));

        Debug.Log("[SlashReview] " + name + " age=" + age.ToString("F3") + "s"
                  + " crescent=" + (cres != null ? "1" : "-")
                  + " ribbon=" + (rv != null ? rv.DebugMaxAlpha.ToString() : "-")
                  + " groundArc=" + (av != null ? av.DebugMaxAlpha.ToString() : "-")
                  + (hide == HideWhat.None ? "" : "  [HIDDEN=" + hide + "]"));

        if (cres != null) Destroy(cres);
        if (rib != null) Destroy(rib);
        if (arc != null) Destroy(arc);
        yield return null;
        yield return null;
    }

    // 旧的按真实时间步进的实现已删除：它会在 Shot() 的 0.2 秒开销里跳过整个特效寿命。

    /// <summary>离屏渲一帧写盘。用 RenderTexture 直渲，不依赖 Game View 是否在前台/被最小化。</summary>
    void Shot(string path)
    {
        Camera cam = Camera.main;
        if (cam == null)
        {
            Debug.LogWarning("[SlashReview] 场景里没有 Camera.main，跳过 " + path);
            return;
        }

        RenderTexture rt = RenderTexture.GetTemporary(W, H, 24, RenderTextureFormat.ARGB32,
            RenderTextureReadWrite.sRGB);   // 项目是 Linear 色彩空间，不显式 sRGB 会读回发灰的图
        RenderTexture prevActive = RenderTexture.active;
        RenderTexture prevTarget = cam.targetTexture;

        try
        {
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;

            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply(false, false);

            byte[] png = tex.EncodeToPNG();
            Object.Destroy(tex);

            if (png != null && png.Length > 0) File.WriteAllBytes(path, png);
            else Debug.LogWarning("[SlashReview] EncodeToPNG 返回空: " + path);
        }
        catch (System.Exception e)
        {
            Debug.LogWarning("[SlashReview] 截图失败 " + path + " : " + e.Message);
        }
        finally
        {
            cam.targetTexture = prevTarget;
            RenderTexture.active = prevActive;
            RenderTexture.ReleaseTemporary(rt);
        }
    }

    void OnDestroy()
    {
        // Play 模式是全队共享资源：被强行停掉也不能把编辑器留在慢动作里
        Time.timeScale = 1f;
        MyWorld.VfxFeel.ForceGradeIndex = -1;
        if (dummyGo != null) Destroy(dummyGo);
    }
}
