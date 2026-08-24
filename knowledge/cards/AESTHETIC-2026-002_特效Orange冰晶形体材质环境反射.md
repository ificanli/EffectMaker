# AESTHETIC-2026-002：特效Orange冰晶的形体、明暗与环境反射

## 来源

- 来源资料：[SRC-2026-UP389578709](../sources/SRC-2026-UP389578709_source.md)
- 视频：`BV1yzftBiEvW_冰的制作技巧.mp4`、`BV1CzcbzGEod_冰特效小雪面制作技巧超简单.mp4`
- 原始来源：https://www.bilibili.com/video/BV1yzftBiEvW/、https://www.bilibili.com/video/BV1CzcbzGEod/
- 作者：特效Orange
- 证据：`visual_review_BV1CzcbzGEod_00-03.md`、`visual_review_BV1yzftBiEvW_00-10.md`、`10-20.md`、`20-25.md`
- 管道：审美类（Aesthetic）
- 验证状态：`experimental`

## 核心结论

1. 冰晶的风格先由基础几何面数、比例和尖厚关系决定，再由贴图和材质补充质感。
2. 整体造型与局部起伏分开：FFD 做大形，软选择做局部和边缘；冰面要保留与地面的自然空间关系。
3. 主贴图用明确的暗色、蓝色过渡和高明度亮色建立结构，亮边只做补充。
4. Fresnel、自定义光照和环境反射分别承担边缘提亮、光照响应和环境细节，任何一层过强都会削弱主体结构。
5. 普通软选择用于边缘弱化，反向软选择用于边界强调和颜色变化；边缘处理直接影响冰体是否自然。

## 限制

具体 3D 软件、Shader、渲染管线、Cubemap 导入设置和参数尚未通过 Unity/MCP 验证；当前不能升级为项目稳定规范。

## 关联实验

`EXP-2026-011_特效Orange冰晶形体材质环境反射验证.md`
