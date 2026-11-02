using System.IO;
using UnityEngine;

namespace MyWorldProbes
{
    /// <summary>
    /// 临时探针：在 Play 模式下用一台临时相机把画面渲进 RenderTexture 再写成 PNG。
    /// 为什么不用 ScreenCapture：它返回的是上一帧，而且 Game 视图失焦时是灰的。
    /// 交付前必须删除本文件。
    /// </summary>
    public static class ZzKingdomShots
    {
        public const string OutDir = @"E:\My World\WorkQC\kingdom";

        public static string Shoot(string file, float px, float py, float pz,
                                   float lx, float ly, float lz, float fov = 45f, bool ortho = false)
        {
            Directory.CreateDirectory(OutDir);
            int w = 1600, h = 900;
            var go = new GameObject("ZzShotCam");
            var cam = go.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.Skybox;
            cam.fieldOfView = fov;
            cam.nearClipPlane = 0.3f;
            cam.farClipPlane = 3000f;
            if (ortho) { cam.orthographic = true; cam.orthographicSize = fov; }
            cam.transform.position = new Vector3(px, py, pz);
            cam.transform.LookAt(new Vector3(lx, ly, lz));

            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
            rt.antiAliasing = 4;
            var prev = RenderTexture.active;
            cam.targetTexture = rt;

            // 两帧：冷启动第一帧偶尔是空的
            cam.Render();
            cam.Render();

            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;

            string path = Path.Combine(OutDir, file + ".png");
            File.WriteAllBytes(path, tex.EncodeToPNG());

            // 出图自检：评审两次拿到「相机埋进墙里」的废图，这一条比任何美术修正都省时间。
            // 亮度 < 80/255 的像素占比 > 8% → 多半是相机穿进几何体或被近裁剪面挡住。
            int dark = 0;
            var px32 = tex.GetPixels32();
            for (int i = 0; i < px32.Length; i += 3)
            {
                if (px32[i].r * 0.299f + px32[i].g * 0.587f + px32[i].b * 0.114f < 80f) dark++;
            }
            float darkPct = 100f * dark / Mathf.Max(1, px32.Length / 3f);

            var camPos = new Vector3(px, py, pz);
            bool inside = false;
            var cols = Physics.OverlapSphere(camPos, 0.75f);
            for (int i = 0; i < cols.Length; i++)
            {
                if (cols[i] != null && !cols[i].isTrigger) { inside = true; break; }
            }

            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(tex);
            Object.DestroyImmediate(go);

            string flags = (darkPct > 8f ? " WARN_DARK" : "") + (inside ? " CAMERA_INSIDE_GEOMETRY" : "");
            return path + " bytes=" + new FileInfo(path).Length + " dark=" + darkPct.ToString("0.0") + "%" + flags;
        }
    }
}
