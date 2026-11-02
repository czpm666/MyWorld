# 阿斯拉王国 —— 地图交付说明（草稿）

> 这条线是回应你的要求：「地图可以用几十个你这样的小城组成，然后主城再做一个这几个小城 10 倍大的地图」。

## 一、做了什么（三层）

| 层 | 名字 | 尺度 | 在哪个场景 |
|---|---|---|---|
| 王国大地图 | 阿斯拉王国 | 3000 m × 3000 m | `Assets/Scenes/KingdomWorld.unity` |
| 小镇 ×30 | 农场村 / 矿镇 / 河港镇 各 3 个变体 | 每座约 120 m 见方 | 预制体，运行时摆进大地图 |
| 王都「阿尔斯」 | Asura Capital | 约 700 m 直径（含郊区） | `Assets/Scenes/AsuraCapital.unity` |

为什么王都是 700 m 而不是字面上的 1200 m（小镇的 10 倍）：1200 m 摊在同样多的房子上会变成一大片空地，
看起来**比小镇还空**。所以按「镇心到镇心」约 5.8 倍直径、地面覆盖率约 10 倍来做，密度不掉。

## 二、王都的内容

- 外城墙 r=300 m，8 m 高石墙 + 城垛 + 72 个扶壁 + 16 座塔（每座半径/高度都抖动，不是等距项链）
- 内城 r=150 m：第二道墙、8 座内塔
- 岩石城堡：r=82 m、高 18 m 的抖动岩体 + 城堡本体 + 双旗
- 大教堂（西北）、冒险者公会（东北）、中央集市（大集市棚 + 摊位）
- 港口：河（y=-352）、码头、栈桥、货船
- 下城区：6 圈环路 + 8 条放射大道，沿街的连排联排屋（背靠背、共用山墙），带后院
- 郊区：墙外一圈农舍与田地

## 三、怎么打开看

Unity 菜单（每天只用这几条）：

```
Tools/My World/王国①导入城镇 FBX       ← Blender 导出后重新导入（会重建材质）
Tools/My World/王国②城镇清单           ← 只打印，不改文件
Tools/My World/王国③生成王国大地图场景  ← 重建 KingdomWorld.unity
Tools/My World/王国④生成王都场景        ← 重建 AsuraCapital.unity
Tools/My World/王国⑤检查王国场景        ← 检查两个场景和预制体清单
```

然后打开 `Assets/Scenes/KingdomWorld.unity` 按 Play：出生点在王都城门外的土路上，
往北走是王都占位广场（带传送门），四周三圈环带上是 30 座小镇。

## 四、Blender 侧

```
E:\My World\Blender\kingdom\capital.py     ← 王都生成脚本
E:\My World\Blender\kingdom\run_capital.ps1 ← 一键重建 + 渲染 + 导出
E:\My World\Blender\kingdom\kcommon.py      ← 渲染/导出的公共函数
```

重建命令（PowerShell）：

```powershell
& "E:\My World\Blender\kingdom\run_capital.ps1" -Stage full -Houses 420 -Save
```

渲染图在 `E:\My World\Blender\renders\kingdom\`，FBX 在 `E:\My World\Blender\export\capital\`，
材质色板 JSON 在 `E:\My World\Blender\export\kingdom\palettes\`。

## 五、已知问题（诚实清单）

1. 小镇**没有碰撞体**：能走进房子里。大地图的地面有碰撞，房子没有。
2. 大地图的小镇是「整体一块」预制体，没有远处低模 LOD；靠雾（90–1500 m）遮住远处。
3. 王都场景与大地图是两个场景，靠传送门连接；还没做无缝加载。
4. 王都的窗户在近景仍然偏平，岩体材质与城墙材质偏接近。
