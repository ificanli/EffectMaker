# EXP-2026-142 雷电主电流/分支层级 Teacher R001

## 专业证据

来源为 `SRC-2026-SERIES-001 / EP004`，时间码 `00:17:10-00:24:34`。专业点评明确指出：雷电中心主电流应更粗，外围线条更细且数量克制；持续、细碎、同亮的线条会削弱主体和小屏可见性。

画面证据位于 `knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/04_28_lightning/`。

## 受控实验

关闭 ImpactFlash 和 ResidualSpark，保留 MainBolt 与 BranchSupport。两版只改变 BranchSupport 的尺寸与 Alpha：

- `equal_weight`：分支与主电流同尺寸、同 Alpha；
- `main_dominant`：主电流更粗更亮，分支缩小并压暗。

材质、两张 Lightning 贴图、粒子数量、时序、相机和随机种子保持一致。

## 结果

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- 主体轮廓宽度保留：`0.9303`；
- 全长高亮跨度减少：`0.009375`；
- Teacher 状态：`verified`。

联系表：`workspace/data/vfx_generation/generated/professional_teacher_lightning_hierarchy_r001/lightning_hierarchy_pair_contact_sheet.png`。

该规则只监督 `lightning/main_branch_hierarchy`。当前贴图仍有图标化倾向，Teacher 通过不等于雷电整体质量已经完成。
