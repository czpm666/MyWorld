UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/KingdomWorld.unity", UnityEditor.SceneManagement.OpenSceneMode.Single);
var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
return "active=" + scene.path + " roots=" + scene.rootCount;