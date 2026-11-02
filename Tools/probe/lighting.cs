var sb = new System.Text.StringBuilder();
var lights = UnityEngine.Object.FindObjectsByType<UnityEngine.Light>(UnityEngine.FindObjectsSortMode.None);
foreach (var l in lights)
{
    sb.AppendLine("LIGHT " + l.name + " type=" + l.type + " int=" + l.intensity.ToString("F2") +
        " col=" + l.color.ToString("F2") + " rot=" + l.transform.eulerAngles.ToString("F1") +
        " shadows=" + l.shadows + " strength=" + l.shadowStrength.ToString("F2") +
        " cull=" + l.cullingMask + " enabled=" + l.enabled);
}
sb.AppendLine("ambientMode=" + UnityEngine.RenderSettings.ambientMode + " ambientLight=" + UnityEngine.RenderSettings.ambientLight.ToString("F2") +
    " ambientIntensity=" + UnityEngine.RenderSettings.ambientIntensity.ToString("F2") +
    " skybox=" + (UnityEngine.RenderSettings.skybox == null ? "none" : UnityEngine.RenderSettings.skybox.name) +
    " fog=" + UnityEngine.RenderSettings.fog + " fogCol=" + UnityEngine.RenderSettings.fogColor.ToString("F2"));
sb.AppendLine("Quality shadowDistance=" + UnityEngine.QualitySettings.shadowDistance + " shadowCascades=" + UnityEngine.QualitySettings.shadowCascades);
var roots = UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene().GetRootGameObjects();
foreach (var r in roots) sb.AppendLine("ROOT " + r.name + " active=" + r.activeSelf);
return sb.ToString();

