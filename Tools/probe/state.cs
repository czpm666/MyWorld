var sb = new System.Text.StringBuilder();
sb.AppendLine("isPlaying=" + UnityEditor.EditorApplication.isPlaying + " isPlayingOrWillChange=" + UnityEditor.EditorApplication.isPlayingOrWillChangePlaymode);
var scene = UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene();
sb.AppendLine("scene=" + scene.path + " roots=" + scene.GetRootGameObjects().Length + " frame=" + UnityEngine.Time.frameCount);
var cam = UnityEngine.Camera.main;
sb.AppendLine("cam=" + (cam == null ? "none" : cam.name + " pos=" + cam.transform.position.ToString("F1") + " fov=" + cam.fieldOfView));
return sb.ToString();
