# Effect Family Adapter Schemas

本目录保存特效族专用 adapter 契约。`vfxspec.schema.json` 只保留跨类型通用字段；具体形体、拓扑、专用评分和候选搜索边界放到这里。

当前第一批 adapter：

- `slash_adapter.schema.json`：刀光/斩击主体弧、残流和攻击方向。
- `fire_adapter.schema.json`：火焰舌、翻腾、根部亮度、火星和余烟。
- `lightning_adapter.schema.json`：雷电路径、分叉、瞬时峰值和接触电弧。
- `shield_adapter.schema.json`：护盾体积、表面图案、命中涟漪和包裹感。
- `magic_circle_adapter.schema.json`：法阵环层、符文密度、径向分段、显隐和贴地锚定。

约定：

- adapter 的 `name` 使用 `<family>.adapter`，例如 `slash.adapter`。
- adapter 只表达该特效族的形体和专用控制，不重复 `prompt`、`seed`、`render_plan` 等通用字段。
- 第一版字段优先服务候选生成和评价，不追求覆盖所有制作细节。
