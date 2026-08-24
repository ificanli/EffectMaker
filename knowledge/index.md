# 资料知识库索引

## 用途

本目录负责管理外部资料从"收到"到"可复用能力"的转化过程。它不替代 Unity 工程，也不存放未经授权的大型源文件；知识库记录来源、证据、提炼结论、实验结果和与特效资产的关系。

## 双管道架构

所有资料必须先判断类型，进入对应的处理管道：

- **审美类（Aesthetic）**：点评、赏析、参考视频 → 提炼判断规则
- **制作类（Craft）**：教程、复刻、实战录屏 → 提炼可执行步骤

详见 [双管道学习架构](../docs/30-操作指南/双管道学习架构.md)。

## 生命周期

```text
inbox → screened → extracted → experimental → verified → absorbed
                                      ├→ archived
                                      └→ deprecated
```

- `inbox`：刚收到或刚发现，尚未检查。
- `screened`：已完成来源、授权、完整性和版本初筛。
- `extracted`：已提取事实、步骤、参数和限制。
- `experimental`：已设计 Unity/MCP 验证实验。
- `verified`：实验结果支持资料中的关键结论。
- `absorbed`：结论已进入规范、教程、效果或可复用资产。
- `archived`：资料保留用于追溯，但当前不再使用。
- `deprecated`：已知过期、不可复现或被更可靠资料替代。

## 目录说明

- `inbox/`：待处理资料登记、临时链接和投喂任务。
- `sources/`：按资料 ID 保存来源信息、视频时间戳、文章切片或源文件结构说明。
- `cards/`：经过提炼的知识卡片。审美类以 `AESTHETIC-*` 开头，制作类以 `CRAFT-*` 开头。
- `experiments/`：与 Unity、MCP 或离线工具对应的最小验证记录。
- `index.md`：资料、卡片、实验和效果之间的追踪关系。

## 追踪表

| 资料 ID | 类型 | 管道 | 标题 | 状态 | 知识卡片 | 实验 | 最后复核 |
|---|---|---|---|---|---|---|---|
| [SRC-2026-SERIES-001](sources/SRC-2026-SERIES-001_source.md) | video-series | 审美 | 作业点评（82集） | screened | [CARD-2026-001](cards/CARD-2026-001_游戏特效基本功点评规则.md) | [EXP-2026-001](experiments/EXP-2026-001_特效基本功对照验证.md) | 2026-08-23 |
| [SRC-2026-TEACHING-001](sources/SRC-2026-TEACHING-001_source.md) | video-series | 制作 | 零碎知识点（9集） | screened | 待建立 | 待设计 | 2026-08-23 |
| [SRC-2026-GAMEVFX-001](sources/SRC-2026-GAMEVFX-001_source.md) | video-series | 制作 | 游戏特效制作（18集） | extracted | [CRAFT-2026-001](cards/CRAFT-2026-001_场景搭建基线.md), [CRAFT-2026-002](cards/CRAFT-2026-002_后处理配置证据缺口.md), [CRAFT-2026-003](cards/CRAFT-2026-003_烟花分层制作基线.md), [CRAFT-2026-004](cards/CRAFT-2026-004_刀光模型贴图序列图流程.md), [CRAFT-2026-005](cards/CRAFT-2026-005_受击接触反馈结构.md), [CRAFT-2026-006](cards/CRAFT-2026-006_护盾碰撞触发流程.md), [CRAFT-2026-007](cards/CRAFT-2026-007_水系前摇爆发流程.md), [CRAFT-2026-008](cards/CRAFT-2026-008_其余课程集盘点.md) | [EXP-2026-002](experiments/EXP-2026-002_场景搭建基线验证.md), [EXP-2026-003](experiments/EXP-2026-003_后处理开关强度验证.md), [EXP-2026-004](experiments/EXP-2026-004_烟花生命周期分层验证.md), [EXP-2026-005](experiments/EXP-2026-005_刀光模型贴图序列图验证.md), [EXP-2026-006](experiments/EXP-2026-006_受击接触反馈验证.md), [EXP-2026-007](experiments/EXP-2026-007_护盾碰撞触发验证.md), [EXP-2026-008](experiments/EXP-2026-008_水系前摇爆发验证.md), [EXP-2026-009](experiments/EXP-2026-009_剩余课程统一验证模板.md) | 2026-08-23 |
| [SRC-2026-UP389578709](sources/SRC-2026-UP389578709_source.md) | creator-video-library | 混合 | 特效Orange公开投稿（54集） | experimental | [AESTHETIC-2026-001](cards/AESTHETIC-2026-001_特效Orange刀光节奏明暗配色.md), [CRAFT-2026-009](cards/CRAFT-2026-009_特效Orange刀光模型贴图亮层.md), [AESTHETIC-2026-002](cards/AESTHETIC-2026-002_特效Orange冰晶形体材质环境反射.md), [CRAFT-2026-010](cards/CRAFT-2026-010_特效Orange冰晶模型材质环境反射流程.md), [AESTHETIC-2026-003](cards/AESTHETIC-2026-003_特效Orange法阵高级感对比体量.md), [CRAFT-2026-011](cards/CRAFT-2026-011_特效Orange法阵元素气浪局部流动.md), [AESTHETIC-2026-004](cards/AESTHETIC-2026-004_特效Orange对比节奏主题一致性.md), [AESTHETIC-2026-005](cards/AESTHETIC-2026-005_特效Orange主题元素视觉反差.md), [AESTHETIC-2026-006](cards/AESTHETIC-2026-006_特效Orange多维度修评镜头空间表达.md), [CRAFT-2026-012](cards/CRAFT-2026-012_特效Orange顶点偏移法线噪声UV流程.md), [AESTHETIC-2026-007](cards/AESTHETIC-2026-007_特效Orange水墨风主题层级原创转化.md), [CRAFT-2026-013](cards/CRAFT-2026-013_特效Orange水墨素材分层Mask流动.md), [AESTHETIC-2026-008](cards/AESTHETIC-2026-008_特效Orange龙卷风实体感随机性空间层.md), [CRAFT-2026-014](cards/CRAFT-2026-014_特效Orange龙卷风UV网格软边多层流程.md), [AESTHETIC-2026-009](cards/AESTHETIC-2026-009_特效Orange火焰攻击因果链与收尾冲击.md), [CRAFT-2026-015](cards/CRAFT-2026-015_特效Orange火焰纹理法阵分层顶点偏移流程.md), [AESTHETIC-2026-010](cards/AESTHETIC-2026-010_特效Orange女娲一技能四向节奏与边缘层级.md), [CRAFT-2026-016](cards/CRAFT-2026-016_特效Orange女娲一技能对称贴图UV与多层爆发流程.md), [AESTHETIC-2026-011](cards/AESTHETIC-2026-011_特效Orange女娲二技能中心合体与对流空间.md), [CRAFT-2026-017](cards/CRAFT-2026-017_特效Orange女娲二技能镜像UV合体与样条IK路径流程.md), [AESTHETIC-2026-012](cards/AESTHETIC-2026-012_特效Orange女娲三技能龙头分层与路径节奏.md), [CRAFT-2026-018](cards/CRAFT-2026-018_特效Orange女娲三技能对称龙头与双龙地面路径流程.md), [AESTHETIC-2026-013](cards/AESTHETIC-2026-013_特效Orange女娲四技能节奏与空间显隐.md), [CRAFT-2026-019](cards/CRAFT-2026-019_特效Orange女娲四技能Mask与Stencil空间显隐流程.md), [AESTHETIC-2026-014](cards/AESTHETIC-2026-014_特效Orange修评期待兑现与攻击递进.md), [CRAFT-2026-020](cards/CRAFT-2026-020_特效Orange修评残留蓄力与视觉弹道流程.md), [AESTHETIC-2026-015](cards/AESTHETIC-2026-015_特效Orange主题贯穿对比升级与状态标记.md), [CRAFT-2026-021](cards/CRAFT-2026-021_特效Orange主题元素连击状态与终结形体流程.md), [AESTHETIC-2026-016](cards/AESTHETIC-2026-016_特效Orange参考拆解冲击层次与合成判断.md), [CRAFT-2026-022](cards/CRAFT-2026-022_特效Orange参考拆解分层方向与模糊流程.md), [AESTHETIC-2026-017](cards/AESTHETIC-2026-017_特效Orange质感五组对比诊断法.md), [CRAFT-2026-023](cards/CRAFT-2026-023_特效Orange对比诊断到参数排查流程.md), [AESTHETIC-2026-018](cards/AESTHETIC-2026-018_特效Orange节奏曲线快进快收与材质逻辑.md), [CRAFT-2026-024](cards/CRAFT-2026-024_特效Orange粒子大小颜色透明度与旋转曲线流程.md), [AESTHETIC-2026-019](cards/AESTHETIC-2026-019_特效Orange冰雪面大形起伏与边缘过渡.md), [CRAFT-2026-025](cards/CRAFT-2026-025_特效Orange冰雪面网格FFD软选择与边缘渐隐流程.md), [AESTHETIC-2026-020](cards/AESTHETIC-2026-020_特效Orange简易龙卷风低证据参考.md), [AESTHETIC-2026-021](cards/AESTHETIC-2026-021_特效Orange修评镜头克制主体结构与空间分层.md), [CRAFT-2026-026](cards/CRAFT-2026-026_特效Orange镜头主体残留与地面空间反馈流程.md), [AESTHETIC-2026-022](cards/AESTHETIC-2026-022_特效Orange修评主次对比冲击收束与场景展示.md), [CRAFT-2026-027](cards/CRAFT-2026-027_特效Orange主次层尾巴过渡与展示场景排查流程.md), [AESTHETIC-2026-023](cards/AESTHETIC-2026-023_特效Orange初级班作品展示低证据参考.md), [AESTHETIC-2026-024](cards/AESTHETIC-2026-024_特效Orange近期优秀作品合集低证据参考.md), [AESTHETIC-2026-025](cards/AESTHETIC-2026-025_特效Orange优秀作品第二弹低证据参考.md), [AESTHETIC-2026-026](cards/AESTHETIC-2026-026_特效Orange刀光作品展示低证据参考.md), [AESTHETIC-2026-029](cards/AESTHETIC-2026-029_特效Orange刀光支撑层与冲击层时序.md), [CRAFT-2026-030](cards/CRAFT-2026-030_特效Orange刀光多层材质与时序调节流程.md), [AESTHETIC-2026-030](cards/AESTHETIC-2026-030_特效Orange刀光冲击层与地面反馈权重.md), [CRAFT-2026-031](cards/CRAFT-2026-031_特效Orange刀光受击与地面滑痕反馈流程.md), [AESTHETIC-2026-031](cards/AESTHETIC-2026-031_特效Orange从主题到形式的设计创新.md), [CRAFT-2026-032](cards/CRAFT-2026-032_特效Orange主题拆解到可落地表现流程.md), [AESTHETIC-2026-032](cards/AESTHETIC-2026-032_特效Orange雷电作品展示低证据参考.md), [AESTHETIC-2026-033](cards/AESTHETIC-2026-033_特效Orange修评节奏与视觉元素层级.md), [CRAFT-2026-033](cards/CRAFT-2026-033_特效Orange修评节奏与视觉元素调整流程.md), [AESTHETIC-2026-034](cards/AESTHETIC-2026-034_特效Orange基础入门短视频低证据参考.md), [AESTHETIC-2026-035](cards/AESTHETIC-2026-035_特效Orange天空盒环境选择与主体衬托.md), [CRAFT-2026-034](cards/CRAFT-2026-034_特效Orange天空盒导入与场景主体衬托流程.md), [AESTHETIC-2026-036](cards/AESTHETIC-2026-036_特效Orange参考研究与主题形式融合.md), [CRAFT-2026-035](cards/CRAFT-2026-035_特效Orange参考研究到主题形式落地流程.md), [AESTHETIC-2026-037](cards/AESTHETIC-2026-037_特效Orange草薙京短展示低证据参考.md), [AESTHETIC-2026-038](cards/AESTHETIC-2026-038_特效Orange冰属性重置短展示低证据参考.md), [AESTHETIC-2026-039](cards/AESTHETIC-2026-039_特效Orange简易弓箭短展示低证据参考.md), [AESTHETIC-2026-040](cards/AESTHETIC-2026-040_特效Orange武器练习短展示低证据参考.md), [AESTHETIC-2026-041](cards/AESTHETIC-2026-041_特效Orange飞行刀光短展示低证据参考.md), [AESTHETIC-2026-042](cards/AESTHETIC-2026-042_特效Orange修评镜头受击与范围控制.md), [CRAFT-2026-036](cards/CRAFT-2026-036_特效Orange修评镜头与受击层调整流程.md), [AESTHETIC-2026-043](cards/AESTHETIC-2026-043_特效Orange皮肤技能氛围色彩与细节层级.md), [CRAFT-2026-037](cards/CRAFT-2026-037_特效Orange皮肤技能预警爆发与贴图分层流程.md), [AESTHETIC-2026-044](cards/AESTHETIC-2026-044_特效Orange个人CG短片低证据参考.md), [AESTHETIC-2026-045](cards/AESTHETIC-2026-045_特效Orange职业展示低证据参考.md), [AESTHETIC-2026-046](cards/AESTHETIC-2026-046_特效Orange进阶课宣传片低证据参考.md), [AESTHETIC-2026-047](cards/AESTHETIC-2026-047_特效Orange小小节奏趣玩科技低证据参考.md), [AESTHETIC-2026-048](cards/AESTHETIC-2026-048_特效Orange森林系低证据参考.md), [AESTHETIC-2026-049](cards/AESTHETIC-2026-049_特效Orange蝴蝶忍效果设计低证据参考.md), [AESTHETIC-2026-050](cards/AESTHETIC-2026-050_特效Orange猴子珍品无双练习低证据参考.md), [AESTHETIC-2026-051](cards/AESTHETIC-2026-051_特效Orange轻舟已过万重山低证据参考.md), [AESTHETIC-2026-052](cards/AESTHETIC-2026-052_特效Orange学员入职职业展示低证据参考.md), [AESTHETIC-2026-053](cards/AESTHETIC-2026-053_特效Orange案例展示低证据参考.md), [AESTHETIC-2026-054](cards/AESTHETIC-2026-054_特效Orange圣诞祝福低证据参考.md), [AESTHETIC-2026-055](cards/AESTHETIC-2026-055_特效Orange大鱼吃小鱼低证据参考.md), [AESTHETIC-2026-056](cards/AESTHETIC-2026-056_特效Orange特效练习低证据参考.md) | [EXP-2026-010](experiments/EXP-2026-010_特效Orange刀光节奏分层验证.md), [EXP-2026-011](experiments/EXP-2026-011_特效Orange冰晶形体材质环境反射验证.md), [EXP-2026-012](experiments/EXP-2026-012_特效Orange法阵对比体量与单元素流动验证.md), [EXP-2026-013](experiments/EXP-2026-013_特效Orange对比节奏与主题材质验证.md), [EXP-2026-014](experiments/EXP-2026-014_特效Orange主题贯穿与视觉反差验证.md), [EXP-2026-015](experiments/EXP-2026-015_特效Orange顶点偏移方向与UV验证.md), [EXP-2026-016](experiments/EXP-2026-016_特效Orange水墨层级与原创转化验证.md), [EXP-2026-017](experiments/EXP-2026-017_特效Orange龙卷风形态层级与空间感验证.md), [EXP-2026-018](experiments/EXP-2026-018_特效Orange火焰因果转换与分层冲击验证.md), [EXP-2026-019](experiments/EXP-2026-019_特效Orange女娲一技能四向节奏与贴图分层验证.md), [EXP-2026-020](experiments/EXP-2026-020_特效Orange女娲二技能对流合体与路径生物验证.md), [EXP-2026-021](experiments/EXP-2026-021_特效Orange女娲三技能龙头与双龙路径验证.md), [EXP-2026-022](experiments/EXP-2026-022_特效Orange女娲四技能节奏与Stencil显隐验证.md), [EXP-2026-023](experiments/EXP-2026-023_特效Orange修评期待递进与视觉弹道验证.md), [EXP-2026-024](experiments/EXP-2026-024_特效Orange主题贯穿与连击状态对比验证.md), [EXP-2026-025](experiments/EXP-2026-025_特效Orange参考拆解分层与合成判断验证.md), [EXP-2026-026](experiments/EXP-2026-026_特效Orange质感五组对比诊断验证.md), [EXP-2026-027](experiments/EXP-2026-027_特效Orange节奏曲线与材质分层验证.md), [EXP-2026-028](experiments/EXP-2026-028_特效Orange冰雪面大形起伏与边缘过渡验证.md), [EXP-2026-029](experiments/EXP-2026-029_特效Orange简易龙卷风证据缺口登记.md), [EXP-2026-030](experiments/EXP-2026-030_特效Orange镜头克制与主体空间分层验证.md), [EXP-2026-031](experiments/EXP-2026-031_特效Orange修评主次对比与冲击收束验证.md), [EXP-2026-032](experiments/EXP-2026-032_特效Orange作品展示证据等级与复核登记.md), [EXP-2026-033](experiments/EXP-2026-033_特效Orange作品合集逐片复核入口验证.md), [EXP-2026-034](experiments/EXP-2026-034_特效Orange音乐混剪作品逐片复核登记.md), [EXP-2026-035](experiments/EXP-2026-035_特效Orange刀光展示证据缺口登记.md), [EXP-2026-038](experiments/EXP-2026-038_特效Orange刀光支撑层与冲击层时序验证.md), [EXP-2026-039](experiments/EXP-2026-039_特效Orange刀光受击与地面反馈时序验证.md), [EXP-2026-040](experiments/EXP-2026-040_特效Orange主题形式创新与落地成本验证.md), [EXP-2026-041](experiments/EXP-2026-041_特效Orange雷电短展示证据缺口登记.md), [EXP-2026-042](experiments/EXP-2026-042_特效Orange修评节奏与视觉元素层级验证.md), [EXP-2026-043](experiments/EXP-2026-043_特效Orange基础入门短视频证据缺口登记.md), [EXP-2026-044](experiments/EXP-2026-044_特效Orange天空盒导入与场景主体衬托验证.md), [EXP-2026-045](experiments/EXP-2026-045_特效Orange参考研究与主题形式落地验证.md), [EXP-2026-046](experiments/EXP-2026-046_特效Orange草薙京短展示证据缺口登记.md), [EXP-2026-047](experiments/EXP-2026-047_特效Orange冰属性重置短展示证据缺口登记.md), [EXP-2026-048](experiments/EXP-2026-048_特效Orange简易弓箭短展示证据缺口登记.md), [EXP-2026-049](experiments/EXP-2026-049_特效Orange武器练习短展示证据缺口登记.md), [EXP-2026-050](experiments/EXP-2026-050_特效Orange飞行刀光短展示证据缺口登记.md), [EXP-2026-051](experiments/EXP-2026-051_特效Orange修评镜头受击与范围控制验证.md), [EXP-2026-052](experiments/EXP-2026-052_特效Orange皮肤技能预警爆发与贴图分层验证.md), [EXP-2026-053](experiments/EXP-2026-053_特效Orange个人CG短片证据缺口登记.md), [EXP-2026-054](experiments/EXP-2026-054_特效Orange职业展示证据缺口登记.md), [EXP-2026-055](experiments/EXP-2026-055_特效Orange进阶课宣传片证据等级登记.md), [EXP-2026-056](experiments/EXP-2026-056_特效Orange小小节奏趣玩科技证据缺口登记.md), [EXP-2026-057](experiments/EXP-2026-057_特效Orange森林系证据缺口登记.md), [EXP-2026-058](experiments/EXP-2026-058_特效Orange蝴蝶忍效果设计证据缺口登记.md), [EXP-2026-059](experiments/EXP-2026-059_特效Orange猴子珍品无双练习证据缺口登记.md), [EXP-2026-060](experiments/EXP-2026-060_特效Orange轻舟已过万重山证据缺口登记.md), [EXP-2026-061](experiments/EXP-2026-061_特效Orange学员入职职业展示证据缺口登记.md), [EXP-2026-062](experiments/EXP-2026-062_特效Orange案例展示证据缺口登记.md), [EXP-2026-063](experiments/EXP-2026-063_特效Orange圣诞祝福证据等级登记.md), [EXP-2026-064](experiments/EXP-2026-064_特效Orange大鱼吃小鱼证据缺口登记.md), [EXP-2026-065](experiments/EXP-2026-065_特效Orange特效练习证据缺口登记.md) | 2026-08-23 |

## 单集索引

### SRC-2026-SERIES-001（作业点评系列）

| 集数 | BV 号 | 标题 | 状态 | 卡片 |
|---|---|---|---|---|
| 01 | BV1xmQnBaE6b | 20260415点评-一定要练基本功 | extracted | CARD-2026-001 |
| 02 | BV1PrXaBFE5d | 20260330点评 | extracted | [CARD-2026-002](cards/CARD-2026-002_刀光与蓄力特效点评规则.md) |
| 03 | BV1e2w4zXEPM | 20260314点评-年后第一讲 | extracted | [CARD-2026-003](cards/CARD-2026-003_空间承接与相对运动规则.md) |
| 04 | BV1E66iBAE7h | 20260130点评-蛇年再见 | extracted | [CARD-2026-004](cards/CARD-2026-004_空间层级与相对运动点评规则.md) |
| 05 | BV1h6rsB4Ef1 | 20260114点评 | extracted | [CARD-2026-005](cards/CARD-2026-005_接触尺度纹理复用与火焰表达规则.md) |
| 06 | BV12nvvBbEuk | 20251230点评-今年最后一讲 | extracted | [CARD-2026-006](cards/CARD-2026-006_画质层级尺度参照与时光节奏规则.md) |
| 07 | BV1MVqsB3Erz | 20251215点评-大家做的真可以 | extracted | [CARD-2026-007](cards/CARD-2026-007_颜色预算形体生成与功能兑现规则.md) |
| 08 | BV1wtSqBYEk1 | 20251130点评-快成某同学专场了 | extracted | [CARD-2026-008](cards/CARD-2026-008_颜色连续残流承接与分片动态规则.md) |
| 09 | BV1T1C2BnE3E | 20251115点评-怎么增加细节 | extracted | [CARD-2026-009](cards/CARD-2026-009_资源减化材质残留与功能节奏规则.md) |
| 10–82 | — | 待处理 | — | — |

### SRC-2026-TEACHING-001（零碎知识点）

| 集数 | BV 号 | 标题 | 管道 | 状态 |
|---|---|---|---|---|
| 01 | BV1D5411a7Gd | 场景搭建 | 制作 | 待处理 |
| 02 | BV1Qi4y137yb | 后处理效果配置 | 制作 | 待处理 |
| 03 | BV1eT4y1j7Mh | 模型UV讲解 | 制作 | 待处理 |
| 04 | BV1gU4y1J7Ak | Shader Graph 云朵 | 制作 | 待处理 |
| 05 | BV1MR4y1J7Ta | Water Bending | 制作 | 待处理 |
| 06 | BV1ht421E7KU | 虚拟力场粒子特效 | 制作 | 待处理 |
| 07 | BV1a54y1n7Kt | 灯光烘焙知识 | 制作 | 待处理 |
| 08 | BV1PU4y1J7Ta | 一键去黑抠图神器 | 制作 | 待处理 |
| 09 | BV1zQ4y1X7ET | Unity官方薅羊毛指引 | 制作 | 待处理 |

### SRC-2026-GAMEVFX-001（游戏特效制作）

按优先级排列，详见 `sources/SRC-2026-GAMEVFX-001_source.md`。

## 使用规则

1. 每份资料先登记再吸收，禁止只保存一个无上下文的链接或文件。
2. 必须先判断管道类型（审美/制作/混合），再进入处理流程。
3. 资料结论必须能定位到原文、时间戳、文件路径、Inspector 参数或实验记录。
4. 未验证的内容只能作为假设，不能直接写入稳定规范。
5. 审美规则和制作步骤分别以 `AESTHETIC-*` 和 `CRAFT-*` 编号。
6. 外部资源必须记录来源、作者、获取日期和授权状态。
7. 版本、渲染管线和目标平台不明确时，结论必须标记适用范围未知。

## 关联关系

```text
资料 SRC-* → 知识卡片 AESTHETIC-*/CRAFT-* → 验证实验 EXP-* → 效果 FX-* / 资产 AST-*
```

一个资料可以产生多张知识卡片；一张卡片可以由多个来源共同支持；一个实验可以验证多张卡片；一个效果可以引用多个实验和卡片。
