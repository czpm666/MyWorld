var sb = new System.Text.StringBuilder();
var lights = UnityEngine.Object.FindObjectsByType<UnityEngine.Light>(UnityEngine.FindObjectsSortMode.None);
foreach (var l in lights)
{
    if (l == null) continue;
    if (l.type != UnityEngine.LightType.Directional) continue;
    sb.AppendLine("SUN " + l.name + " int=" + l.intensity.ToString("0.00") + " col=" + l.color.ToString() + " rot=" + l.transform.eulerAngles.ToString() + " shadows=" + l.shadows + " str=" + l.shadowStrength.ToString("0.00"));
}
sb.AppendLine("ambientMode=" + UnityEngine.RenderSettings.ambientMode + " sky=" + UnityEngine.RenderSettings.ambientSkyColor.ToString() + " eq=" + UnityEngine.RenderSettings.ambientEquatorColor.ToString() + " gnd=" + UnityEngine.RenderSettings.ambientGroundColor.ToString() + " int=" + UnityEngine.RenderSettings.ambientIntensity.ToString("0.00"));
sb.AppendLine("fog=" + UnityEngine.RenderSettings.fog + " mode=" + UnityEngine.RenderSettings.fogMode + " col=" + UnityEngine.RenderSettings.fogColor.ToString() + " start=" + UnityEngine.RenderSettings.fogStartDistance.ToString("0.0") + " end=" + UnityEngine.RenderSettings.fogEndDistance.ToString("0.0") + " dens=" + UnityEngine.RenderSettings.fogDensity.ToString("0.0000"));
sb.AppendLine("skybox=" + (UnityEngine.RenderSettings.skybox == null ? "null" : UnityEngine.RenderSettings.skybox.name));
var cam = UnityEngine.Camera.main;
if (cam != null) sb.AppendLine("cam=" + cam.name + " pos=" + cam.transform.position.ToString() + " far=" + cam.farClipPlane.ToString("0") + " exp=" + cam.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>() + " shadows=" + UnityEngine.QualitySettings.shadowDistance.ToString("0"));
var vols = UnityEngine.Object.FindObjectsByType<UnityEngine.Rendering.Volume>(UnityEngine.FindObjectsSortMode.None);
sb.AppendLine("volumes=" + vols.Length);
foreach (var v in vols)
{
    sb.AppendLine("VOL " + v.name + " weight=" + v.weight.ToString("0.00") + " profile=" + (v.sharedProfile == null ? "null" : v.sharedProfile.name));
    if (v.sharedProfile != null)
    {
        foreach (var c in v.sharedProfile.components)
        {
            if (c == null) continue;
            sb.AppendLine("   comp " + c.GetType().Name + " active=" + c.active);
        }
    }
}
return sb.ToString();