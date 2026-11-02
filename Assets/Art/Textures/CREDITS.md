# 地图贴图来源与授权（Assets/Art/Textures）

本目录的 `kit_*.jpg` 全部来自 **CC0 1.0（公有领域）** 材质库，可商用、可修改、无需署名；
下面仍按要求登记原始资产与链接。**不要**往这里放来源不明或许可非 CC0 的图片。

| 文件 | 原始资产 | 来源 | 许可 | 用途 |
|---|---|---|---|---|
| `kit_cobble.jpg` | `PavingStones150_1K-JPG_Color` | [ambientCG PavingStones150](https://ambientcg.com/view?id=PavingStones150) | CC0 1.0 | 街道/广场铺地（扇铺小石） |
| `kit_stone_wall.jpg` | `rock_wall_17_diff_1k` | [Poly Haven rock_wall_17](https://polyhaven.com/a/rock_wall_17) | CC0 | 粗石砌墙 |
| `kit_blocks.jpg` | `medieval_blocks_03_diff_1k` | [Poly Haven medieval_blocks_03](https://polyhaven.com/a/medieval_blocks_03) | CC0 | 规整方石（台基、柱础、广场石板） |
| `kit_roof_tile.jpg` | `RoofingTiles014B_1K-JPG_Color` | [ambientCG RoofingTiles014B](https://ambientcg.com/view?id=RoofingTiles014B) | CC0 1.0 | 赤陶/石板/青绿等瓦屋顶（靠 `_BaseColor` 调色） |
| `kit_plaster.jpg` | `Plaster007_1K-JPG_Color` | [ambientCG Plaster007](https://ambientcg.com/view?id=Plaster007) | CC0 1.0 | 抹灰墙面 |
| `kit_planks.jpg` | `Planks039_1K-JPG_Color` | [ambientCG Planks039](https://ambientcg.com/view?id=Planks039) | CC0 1.0 | 木板/木构件 |
| `kit_thatch.jpg` | `thatch_roof_angled_diff_1k` | [Poly Haven thatch_roof_angled](https://polyhaven.com/a/thatch_roof_angled) | CC0 | 茅草屋顶 |
| `kit_barrel.jpg` | `wooden_barrel_diff_1k` | [Poly Haven wooden_barrel](https://polyhaven.com/a/wooden_barrel) | CC0 | 木桶/桶板 |
| `kit_grass.jpg` | `Grass001_1K-JPG_Color` | [ambientCG Grass001](https://ambientcg.com/view?id=Grass001) | CC0 1.0 | 草地（大地块 + 草丘） |
| `kit_dirt.jpg` | `Ground110_1K-JPG_Color` | [ambientCG Ground110](https://ambientcg.com/view?id=Ground110) | CC0 1.0 | 土路/泥地 |
| `kit_sand.jpg` | `Ground111_1K-JPG_Color` | [ambientCG Ground111](https://ambientcg.com/view?id=Ground111) | CC0 1.0 | 沙地/碎石地面 |
| `kit_brick.jpg` | `castle_brick_07_diff_1k` | [Poly Haven castle_brick_07](https://polyhaven.com/a/castle_brick_07) | CC0 | 红砖建筑 |
| `kit_wood_dark.jpg` | `medieval_wood_diff_1k` | [Poly Haven medieval_wood](https://polyhaven.com/a/medieval_wood) | CC0 | 深色木门/木框/梁 |

以上 13 张全部登记在 `AssetCandidates/_MANIFEST_TEXTURES.md`（ambientCG / Poly Haven 的 1K JPG 包，
ambientCG 全站 CC0；Poly Haven 材质站全站 CC0）。原始包里的 `_NormalGL` / `_NormalDX` /
`_Roughness` / `_AmbientOcclusion` / `_arm` / `_disp` 也都在 `AssetCandidates/` 里，**本轮没有导入**
（先把颜色做对）；以后接法线贴图时请继续登记到本表。

导入设置（所有 `kit_*.jpg.meta` 一致，由 Unity TextureImporter v13 生成）：

- Texture Type: `Default`，sRGB: 开，Mip Maps: 开，Max Size: 2048，Filter: Bilinear
- Wrap Mode U/V: `Repeat`（ambientCG/Poly Haven 的贴图本身可平铺）
- `isReadable: 0`（运行时不要 `GetPixels`，需要采样请在编辑器侧预处理）

> 修改贴图文件名/路径时，`Assets/Scripts/MyWorld/World/MapMaterials.cs` 里的 `Textures` 表要同步改，
> 否则材质会静默退回纯色（编辑器 Console 有 warning）。
