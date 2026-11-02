// UexportMenu -- one-click wrappers around the UEXPORT verification probes.
//
// Why this exists: the probes are normally run with
//     Unity.exe -batchmode -quit -projectPath "E:\My World" -executeMethod ...
// which cannot run while an interactive editor has the project open (Unity refuses
// with "another Unity instance is running with this project open").  A menu item
// calls exactly the same entry point inside the live editor, so the verification
// can be done without closing anybody's editor.
//
// The probes write their own detail files under WorkQC\uexport\<tag>\; this wrapper
// additionally appends a header + their logs to E:\My World\Logs\uexport_probe.log
// so one click leaves one file for the agent/human to read.
using System;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class UexportMenu
{
    const string LOGDIR = @"E:\My World\Logs";
    const string LOGFILE = LOGDIR + @"\uexport_probe.log";
    const string LABWORK = @"E:\My World\WorkQC\uexport\lab";
    const string AXISWORK = @"E:\My World\WorkQC\uexport\axis";

    [MenuItem("Tools/UEXPORT/Run Lab Probe (chunks + materials)", false, 100)]
    public static void RunLabProbe()
    {
        Run("lab", UexportLabProbe.Run, LABWORK,
            new[] { "unity_lab.log", "unity_lab_failures.txt" });
    }

    [MenuItem("Tools/UEXPORT/Run Axis Probe (orientation + scale)", false, 101)]
    public static void RunAxisProbe()
    {
        Run("axis", UexportAxisProbe.Run, AXISWORK,
            new[] { "unity_probe.log", "unity_report.json" });
    }

    [MenuItem("Tools/UEXPORT/Open UEXPORT logs folder", false, 120)]
    public static void OpenLogs()
    {
        EditorUtility.RevealInFinder(LOGDIR + @"\uexport_probe.log");
    }

    [MenuItem("Tools/UEXPORT/Open exported lab FBX folder", false, 121)]
    public static void OpenLabOut()
    {
        EditorUtility.RevealInFinder(LABWORK + @"\out\manifest.json");
    }

    // ------------------------------------------------------------------ plumbing
    static void Run(string tag, Action entry, string workDir, string[] artefacts)
    {
        var sb = new StringBuilder();
        var sw = System.Diagnostics.Stopwatch.StartNew();
        sb.AppendLine("================================================================");
        sb.AppendLine("== uexport probe '" + tag + "'  " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
        sb.AppendLine("== unity " + Application.unityVersion + "  project " + Directory.GetCurrentDirectory());
        bool threw = false;
        try
        {
            entry();
        }
        catch (Exception e)
        {
            threw = true;
            sb.AppendLine("EXCEPTION " + e);
        }
        sw.Stop();
        sb.AppendLine("== finished in " + sw.Elapsed.TotalSeconds.ToString("F1") + " s"
                      + (threw ? "  (THREW)" : ""));
        foreach (var a in artefacts)
        {
            string p = Path.Combine(workDir, a);
            sb.AppendLine("---- " + p);
            try
            {
                if (File.Exists(p)) sb.AppendLine(File.ReadAllText(p));
                else sb.AppendLine("(missing)");
            }
            catch (Exception e) { sb.AppendLine("(unreadable: " + e.Message + ")"); }
        }
        try
        {
            Directory.CreateDirectory(LOGDIR);
            File.AppendAllText(LOGFILE, sb.ToString());
            Debug.Log("[UEXPORT] probe '" + tag + "' done in " + sw.Elapsed.TotalSeconds.ToString("F1")
                      + " s -> " + LOGFILE);
        }
        catch (Exception e) { Debug.LogError("[UEXPORT] could not write " + LOGFILE + ": " + e.Message); }
        AssetDatabase.Refresh();
    }
}
