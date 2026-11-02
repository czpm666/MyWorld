// UexportAxisProbe -- temporary verification harness for the UEXPORT (Unity export
// pipeline) subagent.  Imports the axis-probe FBX set, reports the numbers, and
// renders a top-down orthographic shot so orientation can be judged by eye.
//
//   Tuanjie.exe -batchmode -projectPath "E:\My World" \
//       -executeMethod UexportAxisProbe.Run -logFile "...\ux_axis_unity.log" -quit
//
// Delete together with Assets/Generated/UexportAxis/ when verification is done.
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

public static class UexportAxisProbe
{
    const string SRC = @"E:\My World\WorkQC\uexport\axis";
    const string DST = "Assets/Generated/UexportAxis";
    const string REPORT = @"E:\My World\WorkQC\uexport\axis\unity_report.json";

    static StringBuilder LOG = new StringBuilder();
    static void L(string s) { LOG.AppendLine(s); Debug.Log("[UAXIS] " + s); }

    public static void Run()
    {
        try { RunInner(); }
        catch (Exception e) { L("EXCEPTION " + e); }
        finally
        {
            try { File.WriteAllText(@"E:\My World\WorkQC\uexport\axis\unity_probe.log", LOG.ToString()); } catch { }
        }
    }

    static void RunInner()
    {
        L("unity_version " + Application.unityVersion);
        L("pipeline " + (UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline != null
            ? UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline.GetType().Name : "BuiltIn"));

        // ---- calibration reference: a built-in cube whose winding Unity authored
        var refCube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        var refMesh = refCube.GetComponent<MeshFilter>().sharedMesh;
        L("builtin_cube readable=" + refMesh.isReadable + " verts=" + refMesh.vertexCount
          + " winding_dot=" + WindingDot(refMesh).ToString("F3"));
        UnityEngine.Object.DestroyImmediate(refCube);

        // ---- copy FBX in
        Directory.CreateDirectory(DST);
        var files = Directory.GetFiles(SRC, "*.fbx").OrderBy(f => f).ToArray();
        foreach (var f in files)
        {
            string target = Path.Combine(Directory.GetCurrentDirectory(), DST + "/" + Path.GetFileName(f));
            File.Copy(f, target, true);
        }
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);

        // ---- force the import settings the real pipeline will use
        var paths = files.Select(f => DST + "/" + Path.GetFileName(f)).ToArray();
        foreach (var p in paths)
        {
            var mi = AssetImporter.GetAtPath(p) as ModelImporter;
            if (mi == null) { L("NO_IMPORTER " + p); continue; }
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
            mi.isReadable = true;                 // probe only: needs vertex access
            mi.SaveAndReimport();
        }

        var report = new Dictionary<string, object>();
        foreach (var p in paths)
        {
            var mi = AssetImporter.GetAtPath(p) as ModelImporter;
            string key = Path.GetFileNameWithoutExtension(p);
            var d = new Dictionary<string, object>
            {
                ["path"] = p,
                ["materialImportMode"] = mi.materialImportMode.ToString(),
                ["materialLocation"] = mi.materialLocation.ToString(),
                ["globalScale"] = mi.globalScale,
                ["useFileScale"] = mi.useFileScale,
                ["importNormals"] = mi.importNormals.ToString(),
                ["bakeAxisConversion"] = mi.bakeAxisConversion,
                ["meshes"] = new List<object>(),
                ["renderers"] = new List<object>(),
            };
            L("---- " + key + "  mode=" + mi.materialImportMode + " loc=" + mi.materialLocation
              + " globalScale=" + mi.globalScale + " useFileScale=" + mi.useFileScale
              + " bakeAxis=" + mi.bakeAxisConversion + " normals=" + mi.importNormals);

            foreach (var a in AssetDatabase.LoadAllAssetsAtPath(p))
            {
                var mesh = a as Mesh;
                if (mesh == null) continue;
                var md = new Dictionary<string, object>
                {
                    ["name"] = mesh.name,
                    ["verts"] = mesh.vertexCount,
                    ["submeshes"] = mesh.subMeshCount,
                    ["bounds_min"] = V3(mesh.bounds.min),
                    ["bounds_max"] = V3(mesh.bounds.max),
                    ["outwardness"] = Math.Round(Outwardness(mesh), 4),
                    ["winding_dot"] = Math.Round(WindingDot(mesh), 4),
                };
                ((List<object>)d["meshes"]).Add(md);
                L(string.Format("  mesh {0} verts={1} sub={2} bmin=({3:F2},{4:F2},{5:F2}) bmax=({6:F2},{7:F2},{8:F2}) outward={9:F3} winding={10:F3}",
                    mesh.name, mesh.vertexCount, mesh.subMeshCount,
                    mesh.bounds.min.x, mesh.bounds.min.y, mesh.bounds.min.z,
                    mesh.bounds.max.x, mesh.bounds.max.y, mesh.bounds.max.z,
                    md["outwardness"], md["winding_dot"]));
            }

            var root = AssetDatabase.LoadAssetAtPath<GameObject>(p);
            if (root != null)
            {
                foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true))
                {
                    var mats = r.sharedMaterials.Select(m => m == null ? "<null>" : m.name).ToArray();
                    L("  renderer " + r.name + " mats=[" + string.Join(", ", mats) + "]");
                    ((List<object>)d["renderers"]).Add(new Dictionary<string, object>
                    {
                        ["name"] = r.name, ["materials"] = mats,
                    });
                }
            }
            report[key] = d;
        }
        File.WriteAllText(REPORT, UexportMiniJson.Serialize(report));
        L("report -> " + REPORT);

        // ---- render each variant from straight above (orthographic map view)
        foreach (var p in paths)
        {
            string key = Path.GetFileNameWithoutExtension(p);
            RenderVariant(p, key);
        }
        L("DONE");
    }

    // image right = world +X, image up = world +Z
    static void RenderVariant(string assetPath, string key)
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
        var go = (GameObject)PrefabUtility.InstantiatePrefab(root);
        if (go == null) { L("instantiate failed " + assetPath); return; }
        L("instantiated " + key + " root_pos=" + go.transform.position);

        // flat URP/Lit grey so shading reveals inverted normals
        var sh = Shader.Find("Universal Render Pipeline/Lit");
        var mat = new Material(sh != null ? sh : Shader.Find("Standard"));
        mat.color = new Color(0.72f, 0.70f, 0.66f);
        foreach (var r in go.GetComponentsInChildren<MeshRenderer>(true))
            r.sharedMaterial = mat;

        var camGo = new GameObject("shot_cam");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = 24f;
        cam.nearClipPlane = 0.1f;
        cam.farClipPlane = 200f;
        camGo.transform.position = new Vector3(0f, 60f, 0f);
        camGo.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.13f, 0.14f, 0.17f);

        var sun = new GameObject("sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.transform.rotation = Quaternion.Euler(48f, -35f, 0f);
        sun.intensity = 1.6f;

        Shot(cam, "axis_top_" + key + ".png");
    }

    static void Shot(Camera cam, string file)
    {
        const int W = 1000, H = 1000;
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
        byte[] png = tex.EncodeToPNG();
        string outPath = Path.Combine(@"E:\My World\WorkQC\uexport\axis", file);
        File.WriteAllBytes(outPath, png);
        UnityEngine.Object.DestroyImmediate(tex);
        rt.Release();
        L("shot -> " + outPath + " (" + png.Length + " bytes)");
    }

    // ------------------------------------------------------------------ metrics
    static Dictionary<string, float> V3(Vector3 v) { return new Dictionary<string, float> { ["x"] = v.x, ["y"] = v.y, ["z"] = v.z }; }

    // mean(dot(normalize(v - center), normal)) : +1 outward, -1 inverted
    static float Outwardness(Mesh m)
    {
        var v = m.vertices; var n = m.normals;
        if (n.Length != v.Length || v.Length == 0) return 0f;
        Vector3 c = m.bounds.center;
        double acc = 0; int cnt = 0;
        for (int i = 0; i < v.Length; i++)
        {
            var d = v[i] - c;
            if (d.sqrMagnitude < 1e-8f) continue;
            acc += Vector3.Dot(d.normalized, n[i]); cnt++;
        }
        return cnt == 0 ? 0f : (float)(acc / cnt);
    }

    // mean(dot(normalize(cross(b-a, c-a)), normal)) : sign tells whether Unity's
    // index winding matches the stored normals (calibrated against a built-in cube)
    static float WindingDot(Mesh m)
    {
        var v = m.vertices; var n = m.normals;
        if (n.Length != v.Length || v.Length == 0) return 0f;
        double acc = 0; int cnt = 0;
        for (int s = 0; s < m.subMeshCount; s++)
        {
            var idx = m.GetTriangles(s);
            for (int i = 0; i + 2 < idx.Length; i += 3)
            {
                Vector3 a = v[idx[i]], b = v[idx[i + 1]], c = v[idx[i + 2]];
                var g = Vector3.Cross(b - a, c - a);
                if (g.sqrMagnitude < 1e-12f) continue;
                g.Normalize();
                Vector3 nn = (n[idx[i]] + n[idx[i + 1]] + n[idx[i + 2]]).normalized;
                acc += Vector3.Dot(g, nn); cnt++;
            }
        }
        return cnt == 0 ? 0f : (float)(acc / cnt);
    }
}

// minimal JSON writer (no dependencies, deterministic key order not required)
public static class UexportMiniJson
{
    public static string Serialize(object o) { var sb = new StringBuilder(); W(sb, o); return sb.ToString(); }
    static void W(StringBuilder sb, object o)
    {
        if (o == null) { sb.Append("null"); return; }
        if (o is string s) { sb.Append('"').Append(s.Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"'); return; }
        if (o is bool b) { sb.Append(b ? "true" : "false"); return; }
        if (o is float f) { sb.Append(f.ToString("R", System.Globalization.CultureInfo.InvariantCulture)); return; }
        if (o is double d) { sb.Append(d.ToString("R", System.Globalization.CultureInfo.InvariantCulture)); return; }
        if (o is int i) { sb.Append(i.ToString(System.Globalization.CultureInfo.InvariantCulture)); return; }
        if (o is System.Collections.IDictionary dict)
        {
            sb.Append('{'); bool first = true;
            foreach (System.Collections.DictionaryEntry e in dict)
            {
                if (!first) sb.Append(','); first = false;
                W(sb, e.Key as string ?? e.Key.ToString()); sb.Append(':'); W(sb, e.Value);
            }
            sb.Append('}'); return;
        }
        if (o is System.Collections.IEnumerable en)
        {
            sb.Append('['); bool first = true;
            foreach (var e in en) { if (!first) sb.Append(','); first = false; W(sb, e); }
            sb.Append(']'); return;
        }
        W(sb, o.ToString());
    }
}
