# EXP-2026-037：特效Orange刀光方向溶解与迭代控制验证

## 对照组

- `BladeIter_A`：单层、全体同时溶解。
- `BladeIter_B`：复制分层 + 外层/暗层/内层。
- `BladeIter_C`：B + UV/贴图边界修正。
- `BladeIter_D`：C + 尾部向前方向溶解与软边。
- `BladeIter_E`：D + 存根保留和播放状态迭代。
- `BladeIter_F`：过强形变、UV 越界、全体同速溶解的反例。

## 观察指标

主体完整度、攻击方向、溶解连续性、边缘穿出、迭代可回退性、透明过绘和帧时间。

## 当前状态

`planned`。无可运行 Unity 工程，尚未执行；结论保持 `experimental`。
