// TEMPORARY (lead, 2026-10-19): forces one script recompile so Unity's own
// [InitializeOnLoad] handlers (including the MCP-for-Unity bridge) re-run and
// re-register with the HTTP server that is already listening on 8080.
// Delete this file once the bridge is confirmed connected.
using UnityEditor;
using UnityEngine;

internal static class ZzBridgeKick
{
    [InitializeOnLoadMethod]
    private static void OnLoad()
    {
        Debug.Log("[ZzBridgeKick] domain reload @ " + System.DateTime.Now.ToString("HH:mm:ss")
                  + " -- MCP bridge handlers re-run; server expected on http://127.0.0.1:8080");
    }
}
