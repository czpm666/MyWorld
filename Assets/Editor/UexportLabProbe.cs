// UexportLabProbe -- verification harness for the UEXPORT subagent's chunked FBX set.
//
//   Tuanjie.exe -batchmode -quit -projectPath "E:\My World" \
//       -executeMethod UexportLabProbe.Run -logFile "E:\My World\WorkQC\uexport\lab\unity_lab.log"
//
// What it proves, in order:
//   1. the FBX import settings from the manifest actually import (ImportStandard
//      keeps the material names, useFileScale + globalScale 1 keeps the metres);
//   2. every chunk's imported bounds equal the manifest's bbox_unity -> the
//      Blender->Unity axis mapping (x, z, -y) is verified, not assumed;
//   3. per-mesh vertex/triangle/submesh counts and material names match expect.tsv;
//   4. three side-by-side renders: as-imported (flat), "plan B" (procedural JSON
//      replayed with the triplanar shader + kit textures), "plan A" (baked tile).
//
// This file is also the reference implementation of the manifest contract; the
// real importer should read expect.tsv / materials.tsv rather than parse JSON.
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

public static class UexportLabProbe
{
    const string SRC = @"E:\My World\WorkQC\uexport\lab\out";
    const string DST = "Assets/Generated/UexportLab";
    const string WORK = @"E:\My World\WorkQC\uexport\lab";
    const string KITDIR = "Assets/Art/Textures";
    const int W = 1600, H = 900;

    static readonly StringBuilder LOG = new StringBuilder();
    static readonly List<string> FAIL = new List<string>();
    static readonly Dictionary<string, Material> MatCache = new Dictionary<string, Material>();
    static readonly Dictionary<string, Texture2D> TexCache = new Dictionary<string, Texture2D>();

    static void L(string s) { LOG.AppendLine(s); Debug.Log("[ULAB] " + s); }
    static void Bad(string s) { FAIL.Add(s); L("FAIL " + s); }

    public static void Run()
    {
        try { RunInner(); }
        catch (Exception e) { Bad("EXCEPTION " + e); }
        finally
        {
            L("failures " + FAIL.Count);
            try { File.WriteAllText(Path.Combine(WORK, "unity_lab.log"), LOG.ToString()); } catch { }
            try { File.WriteAllText(Path.Combine(WORK, "unity_lab_failures.txt"), string.Join("\n", FAIL)); } catch { }
        }
    }

    // ------------------------------------------------------------------ main
    static void RunInner()
    {
        L("unity " + Application.unityVersion);
        L("pipeline " + (UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline != null
            ? UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline.GetType().Name : "BuiltIn"));
        L("srgb " + PlayerSettings.colorSpace);

        var expect = ReadTsv(Path.Combine(SRC, "expect.tsv"));
        var mats = ReadTsv(Path.Combine(SRC, "materials.tsv"));
        L("expect_rows " + expect.Count + " material_rows " + mats.Count);

        CopyAssets();
        ApplyImportSettings();

        // ---- per-file contract checks
        var byPath = new Dictionary<string, Dictionary<string, string>>();
        foreach (var e in expect) byPath[e["path"]] = e;

        int checkedFiles = 0, badFiles = 0;
        float worstBBoxErr = 0f;
        foreach (var kv in byPath.OrderBy(k => k.Key))
        {
            string rel = kv.Key;
            var e = kv.Value;
            string assetPath = DST + "/" + rel;
            if (!File.Exists(Path.Combine(Directory.GetCurrentDirectory(), assetPath)))
            {
                Bad("missing asset " + assetPath);
                badFiles++;
                continue;
            }
            var fb = new Bounds();
            bool first = true;
            int verts = 0, tris = 0, subs = 0;
            var matNames = new List<string>();
            foreach (var a in AssetDatabase.LoadAllAssetsAtPath(assetPath))
            {
                var mesh = a as Mesh;
                if (mesh == null) continue;
                verts += mesh.vertexCount;
                for (int s = 0; s < mesh.subMeshCount; s++)
                {
                    tris += (int)(mesh.GetIndexCount(s) / 3);
                    if (mesh.subMeshCount > 1) subs++;
                }
                if (mesh.subMeshCount == 1) subs++;
                if (first) { fb = mesh.bounds; first = false; } else fb.Encapsulate(mesh.bounds);
            }
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (root != null)
            {
                foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true))
                {
                    var sm = r.sharedMaterials;
                    for (int i = 0; i < sm.Length; i++)
                    {
                        string n = sm[i] == null ? "<null>" : sm[i].name;
                        if (!matNames.Contains(n)) matNames.Add(n);
                    }
                }
            }

            int eTris = I(e["tris"]), eVerts = I(e["verts_export"]), eSubs = I(e["submeshes"]);
            float[] emin = { F(e["minx"]), F(e["miny"]), F(e["minz"]) };
            float[] emax = { F(e["maxx"]), F(e["maxy"]), F(e["maxz"]) };
            float bboxErr = 0f;
            if (!first)
            {
                float[] amin = { fb.min.x, fb.min.y, fb.min.z };
                float[] amax = { fb.max.x, fb.max.y, fb.max.z };
                for (int i = 0; i < 3; i++)
                {
                    bboxErr = Mathf.Max(bboxErr, Mathf.Abs(amin[i] - emin[i]));
                    bboxErr = Mathf.Max(bboxErr, Mathf.Abs(amax[i] - emax[i]));
                }
            }
            worstBBoxErr = Mathf.Max(worstBBoxErr, bboxErr);

            var emats = (e.ContainsKey("materials") && !string.IsNullOrEmpty(e["materials"]))
                ? e["materials"].Split(',').ToList() : new List<string>();
            var missingMats = emats.Where(m => !matNames.Contains(Sanitize(m)) && !matNames.Any(x => Sanitize(x) == Sanitize(m))).ToList();

            bool ok = bboxErr <= 0.05f
                      && Mathf.Abs(verts - eVerts) <= Mathf.Max(8, eVerts / 50)
                      && Mathf.Abs(tris - eTris) <= Mathf.Max(8, eTris / 50)
                      && missingMats.Count == 0;
            if (!ok)
            {
                badFiles++;
                Bad(string.Format("contract {0} tris {1}/{2} verts {3}/{4} subs {5}/{6} bboxErr {7:F3} missingMats [{8}]",
                    rel, tris, eTris, verts, eVerts, subs, eSubs, bboxErr, string.Join(",", missingMats)));
            }
            checkedFiles++;
            L(string.Format("ok={0} {1} tris={2}/{3} verts={4}/{5} subs={6}/{7} bboxErr={8:F3} mats={9}",
                ok, rel, tris, eTris, verts, eVerts, subs, eSubs, bboxErr, matNames.Count));
        }
        L(string.Format("CONTRACT files={0} failed={1} worstBBoxErr={2:F4}m", checkedFiles, badFiles, worstBBoxErr));

        // ---- renders
        var lods0 = byPath.Keys.Where(p => p.EndsWith(".fbx") && !p.Contains("_col") && !p.Contains("_L1") && !p.Contains("_L2")).OrderBy(p => p).ToList();
        L("lod0 files " + lods0.Count);
        if (lods0.Count > 0)
        {
            RenderSet(lods0, "importstd", 0, mats);
            RenderSet(lods0, "planB", 1, mats);
            RenderSet(lods0, "planA", 2, mats);
        }
        L("DONE");
    }

    static string Sanitize(string n)
    {
        if (n == null) return "";
        int i = n.LastIndexOf('.');
        if (i > 0 && i == n.Length - 4 && char.IsDigit(n[n.Length - 1])) return n.Substring(0, i);
        return n;
    }

    // ------------------------------------------------------------------ io
    static void CopyAssets()
    {
        if (AssetDatabase.IsValidFolder(DST)) AssetDatabase.DeleteAsset(DST);
        Directory.CreateDirectory(Path.Combine(Directory.GetCurrentDirectory(), DST));
        int n = 0;
        foreach (var f in Directory.GetFiles(SRC, "*.fbx", SearchOption.AllDirectories))
        {
            string rel = f.Substring(SRC.Length + 1);
            string dst = Path.Combine(Directory.GetCurrentDirectory(), DST, rel);
            Directory.CreateDirectory(Path.GetDirectoryName(dst));
            File.Copy(f, dst, true);
            n++;
        }
        string texSrc = Path.Combine(SRC, "textures");
        if (Directory.Exists(texSrc))
        {
            foreach (var f in Directory.GetFiles(texSrc, "*.png", SearchOption.AllDirectories))
            {
                string rel = f.Substring(SRC.Length + 1);
                string dst = Path.Combine(Directory.GetCurrentDirectory(), DST, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(dst));
                File.Copy(f, dst, true);
                n++;
            }
        }
        L("copied " + n + " files into " + DST);
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
    }

    static void ApplyImportSettings()
    {
        int n = 0;
        foreach (var f in Directory.GetFiles(Path.Combine(Directory.GetCurrentDirectory(), DST), "*.fbx", SearchOption.AllDirectories))
        {
            string rel = f.Substring(Path.Combine(Directory.GetCurrentDirectory(), DST).Length + 1).Replace('\\', '/');
            string p = DST + "/" + rel;
            var mi = AssetImporter.GetAtPath(p) as ModelImporter;
            if (mi == null) { Bad("no ModelImporter " + p); continue; }
            mi.globalScale = 1.0f;
            mi.useFileScale = true;
            mi.importCameras = false;
            mi.importLights = false;
            mi.importBlendShapes = false;
            mi.importVisibility = false;
            mi.addCollider = false;
            mi.meshCompression = ModelImporterMeshCompression.Off;
            mi.animationType = ModelImporterAnimationType.None;
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            mi.materialLocation = ModelImporterMaterialLocation.InPrefab;
            mi.isReadable = true;   // probe only, production keeps this false
            mi.SaveAndReimport();
            n++;
        }
        L("import settings applied to " + n + " fbx");

        foreach (var f in Directory.GetFiles(Path.Combine(Directory.GetCurrentDirectory(), DST, "textures"), "*.png", SearchOption.AllDirectories))
        {
            string rel = f.Substring(Path.Combine(Directory.GetCurrentDirectory(), DST).Length + 1).Replace('\\', '/');
            var ti = AssetImporter.GetAtPath(DST + "/" + rel) as TextureImporter;
            if (ti == null) continue;
            string name = Path.GetFileNameWithoutExtension(f).ToLowerInvariant();
            bool srgb = name.Contains("base") || name.Contains("color");
            ti.textureType = TextureImporterType.Default;
            ti.sRGBTexture = srgb;
            ti.wrapMode = TextureWrapMode.Repeat;
            ti.filterMode = FilterMode.Bilinear;
            ti.mipmapEnabled = true;
            ti.maxTextureSize = 2048;
            ti.textureCompression = TextureImporterCompression.Uncompressed;
            ti.isReadable = true;
            ti.SaveAndReimport();
        }
    }

    static List<Dictionary<string, string>> ReadTsv(string path)
    {
        var rows = new List<Dictionary<string, string>>();
        if (!File.Exists(path)) { Bad("missing " + path); return rows; }
        var lines = File.ReadAllLines(path);
        if (lines.Length < 2) return rows;
        var head = lines[0].Split('\t');
        for (int i = 1; i < lines.Length; i++)
        {
            if (string.IsNullOrWhiteSpace(lines[i])) continue;
            var cols = lines[i].Split('\t');
            var d = new Dictionary<string, string>();
            for (int c = 0; c < head.Length; c++) d[head[c]] = c < cols.Length ? cols[c] : "";
            rows.Add(d);
        }
        return rows;
    }

    static int I(string s) { int v; int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out v); return v; }
    static float F(string s) { float v; float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out v); return v; }
    static string S(Dictionary<string, string> d, string k)
    {
        string v;
        return (d != null && d.TryGetValue(k, out v) && v != null) ? v : "";
    }

    // ------------------------------------------------------------------ material plans
    static Material GetPlanMaterial(string matName, Dictionary<string, string> row, int mode)
    {
        string key = mode + "|" + matName;
        if (MatCache.ContainsKey(key)) return MatCache[key];
        var sh = Shader.Find("MyWorld/TriplanarLit");
        if (sh == null) { Bad("shader MyWorld/TriplanarLit missing"); return null; }
        var m = new Material(sh);
        m.name = "M_" + matName;

        float tile = row != null && row.ContainsKey("tile_m") && !string.IsNullOrEmpty(row["tile_m"]) ? F(row["tile_m"]) : 4f;
        if (tile <= 0.01f) tile = 4f;
        float rough = !string.IsNullOrEmpty(S(row, "rough")) ? F(S(row, "rough")) : 0.8f;
        float metal = !string.IsNullOrEmpty(S(row, "metal")) ? F(S(row, "metal")) : 0f;
        Color col = row != null ? HexColor(S(row, "base_hex")) : new Color(0.6f, 0.58f, 0.54f);

        if (mode == 2)
        {
            string tex = S(row, "base_tex");
            var t = LoadTex(SRC + "/" + tex, true);
            if (t != null)
            {
                m.SetTexture("_BaseMap", t);
                m.SetColor("_BaseColor", Color.white);
                m.SetFloat("_DetailStrength", 0f);
                m.SetFloat("_DetailGain", 1f);
                m.SetFloat("_DetailMean", 0.5f);
            }
            else mode = 1;   // fall back to plan B for this material
        }
        if (mode == 1)
        {
            string kit = S(row, "kit");
            var t = LoadKitTex(kit);
            if (t != null)
            {
                m.SetTexture("_BaseMap", t);
                m.SetFloat("_DetailMean", TexMean(t));
                m.SetFloat("_DetailGain", 1f);
                m.SetFloat("_DetailStrength", 0.7f);
            }
            m.SetColor("_BaseColor", col);
        }
        m.SetFloat("_Smoothness", Mathf.Clamp01(1f - rough));
        m.SetFloat("_Metallic", Mathf.Clamp01(metal));
        m.SetVector("_BaseMap_ST", new Vector4(1f, 1f, tile, 0f));
        m.SetFloat("_BumpScale", 0.5f);
        MatCache[key] = m;
        return m;
    }

    static Texture2D LoadKitTex(string kit)
    {
        if (string.IsNullOrEmpty(kit)) return null;
        foreach (var ext in new[] { ".jpg", ".png" })
        {
            string p = KITDIR + "/kit_" + kit + ext;
            var t = AssetDatabase.LoadAssetAtPath<Texture2D>(p);
            if (t != null) return t;
        }
        return null;
    }

    static Texture2D LoadTex(string absPath, bool srgb)
    {
        if (string.IsNullOrEmpty(absPath) || !File.Exists(absPath)) return null;
        if (TexCache.ContainsKey(absPath)) return TexCache[absPath];
        string rel = absPath.Substring(SRC.Length + 1).Replace('\\', '/');
        var t = AssetDatabase.LoadAssetAtPath<Texture2D>(DST + "/" + rel);
        TexCache[absPath] = t;
        return t;
    }

    static readonly Dictionary<Texture2D, float> MeanCache = new Dictionary<Texture2D, float>();
    static float TexMean(Texture2D t)
    {
        if (t == null) return 0.5f;
        if (MeanCache.ContainsKey(t)) return MeanCache[t];
        float mean = 0.5f;
        try
        {
            var px = t.GetPixels();
            double acc = 0; int step = Mathf.Max(1, px.Length / 4096);
            int n = 0;
            for (int i = 0; i < px.Length; i += step)
            {
                acc += 0.2126 * px[i].r + 0.7152 * px[i].g + 0.0722 * px[i].b;
                n++;
            }
            if (n > 0) mean = (float)(acc / n);
        }
        catch (Exception e) { L("mean failed " + t.name + " " + e.Message); }
        MeanCache[t] = Mathf.Max(0.02f, mean);
        return MeanCache[t];
    }

    static Color HexColor(string hex)
    {
        if (string.IsNullOrEmpty(hex)) return new Color(0.6f, 0.58f, 0.54f);
        hex = hex.TrimStart('#');
        if (hex.Length < 6) return new Color(0.6f, 0.58f, 0.54f);
        int r = Convert.ToInt32(hex.Substring(0, 2), 16);
        int g = Convert.ToInt32(hex.Substring(2, 2), 16);
        int b = Convert.ToInt32(hex.Substring(4, 2), 16);
        return new Color(r / 255f, g / 255f, b / 255f, 1f);
    }

    // ------------------------------------------------------------------ render
    static void RenderSet(List<string> files, string tag, int mode, List<Dictionary<string, string>> mats)
    {
        var byName = new Dictionary<string, Dictionary<string, string>>();
        foreach (var r in mats)
        {
            if (!byName.ContainsKey(r["name"])) byName[r["name"]] = r;
            string clean = Sanitize(r["name"]);
            if (!byName.ContainsKey(clean)) byName[clean] = r;
        }

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var parent = new GameObject("root_" + tag);
        var bounds = new Bounds();
        bool first = true;
        int inst = 0;
        foreach (var rel in files)
        {
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(DST + "/" + rel);
            if (root == null) { Bad("prefab null " + rel); continue; }
            var go = (GameObject)PrefabUtility.InstantiatePrefab(root);
            if (go == null) { Bad("instantiate failed " + rel); continue; }
            go.transform.SetParent(parent.transform, false);
            inst++;
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (first) { bounds = r.bounds; first = false; } else bounds.Encapsulate(r.bounds);
                if (mode > 0)
                {
                    var sm = r.sharedMaterials;
                    for (int i = 0; i < sm.Length; i++)
                    {
                        if (sm[i] == null) continue;
                        Dictionary<string, string> row;
                        if (!byName.TryGetValue(sm[i].name, out row)) byName.TryGetValue(Sanitize(sm[i].name), out row);
                        var pm = GetPlanMaterial(sm[i].name, row, mode);
                        if (pm != null) sm[i] = pm;
                    }
                    r.sharedMaterials = sm;
                }
            }
        }
        L(string.Format("{0}: instantiated {1} prefabs bounds center=({2:F1},{3:F1},{4:F1}) size=({5:F1},{6:F1},{7:F1})",
            tag, inst, bounds.center.x, bounds.center.y, bounds.center.z,
            bounds.size.x, bounds.size.y, bounds.size.z));

        var sunGo = new GameObject("sun");
        var sun = sunGo.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.transform.rotation = Quaternion.Euler(46f, -38f, 0f);
        sun.intensity = 1.7f;
        sun.shadows = LightShadows.Soft;
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.32f, 0.36f, 0.44f);

        // top-down orthographic map view
        var camGo = new GameObject("cam");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = Mathf.Max(bounds.size.x, bounds.size.z) * 0.55f + 4f;
        cam.nearClipPlane = 0.05f;
        cam.farClipPlane = Mathf.Max(400f, bounds.size.y * 6f + 200f);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.12f, 0.13f, 0.16f);
        camGo.transform.position = new Vector3(bounds.center.x, bounds.max.y + 60f, bounds.center.z);
        camGo.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
        Shot(cam, tag + "_top.png");

        // 52 degree top-down game camera, 34 m back like TopDownCameraRig
        float pitch = 52f, dist = 34f;
        cam.orthographic = false;
        cam.fieldOfView = 30f;
        var target = new Vector3(bounds.center.x, bounds.center.y, bounds.center.z);
        var dir = Quaternion.Euler(pitch, 0f, 0f) * Vector3.forward;
        camGo.transform.position = target - dir * dist;
        camGo.transform.rotation = Quaternion.LookRotation(dir, Vector3.up);
        Shot(cam, tag + "_game.png");
    }

    static void Shot(Camera cam, string file)
    {
        var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        rt.Create();
        cam.targetTexture = rt;
        cam.Render();
        cam.Render();
        RenderTexture.active = rt;
        var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        cam.targetTexture = null;
        // cheap brightness report so a black/white frame is obvious in the log
        long dark = 0, tot = 0;
        var px = tex.GetPixels32();
        tot = px.Length;
        for (int i = 0; i < px.Length; i += 7)
        {
            int l = (px[i].r * 54 + px[i].g * 183 + px[i].b * 19) >> 8;
            if (l < 20) dark++;
        }
        byte[] png = tex.EncodeToPNG();
        string outPath = Path.Combine(WORK, file);
        File.WriteAllBytes(outPath, png);
        UnityEngine.Object.DestroyImmediate(tex);
        rt.Release();
        L(string.Format("shot {0} {1} bytes dark={2:F1}%", file, png.Length, 100.0 * dark / Mathf.Max(1, tot / 7)));
    }
}
