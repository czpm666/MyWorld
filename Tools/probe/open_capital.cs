var esc = UnityEditor.SceneManagement.EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo();
UnityEditor.SceneManagement.EditorSceneManager.OpenScene(
    "Assets/Scenes/AsuraCapital.unity", UnityEditor.SceneManagement.OpenSceneMode.Single);
var scene = UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene();
return "active=" + scene.path + " roots=" + scene.GetRootGameObjects().Length;
