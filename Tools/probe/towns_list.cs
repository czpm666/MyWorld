var sb = new System.Text.StringBuilder();
var root = GameObject.Find("Towns");
if (root == null) return "no Towns root";
int n = root.transform.childCount;
for (int i = 0; i < n; i++)
{
    var c = root.transform.GetChild(i);
    sb.AppendLine(c.name + " pos=" + c.position.ToString() + " scale=" + c.localScale.x.ToString("0.00"));
}
return "count=" + n + "\n" + sb.ToString();