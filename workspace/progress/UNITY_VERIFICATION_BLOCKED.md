# Unity 验证阻塞记录

日期：2026-08-23

## 现象

使用 Unity `2021.3.29f1` 对 `workspace/unity-verification` 执行 batchmode 场景构建时，进程退出码为 0，但没有执行项目脚本，也没有生成场景文件。

## 证据

日志：`workspace/unity-verification/build.log`

关键错误：

- `Unity license information is invalid.`
- `Current license is invalid and cannot be activated.`
- `You must delete the license file and then activate a new license on current machine.`

## 影响

- 最小验证工程尚未真正运行。
- 没有生成 `VerificationBaseline.unity`。
- 没有生成 `verification-results.json`。
- `EXP-2026-002` 至 `EXP-2026-009` 必须保持 `planned`，不能标记为 `verified`。
- `vfx-2zo.9` 已记录为阻塞。

## 解阻步骤

在本机完成 Unity Hub/Editor 的有效 license 激活后，重新运行：

```text
"C:/Program Files/Unity 2021.3.29f1/Editor/Unity.exe" -batchmode -nographics -quit -projectPath "E:/Unity特效人工智能学习/workspace/unity-verification" -executeMethod VerificationSceneBuilder.Build -logFile "E:/Unity特效人工智能学习/workspace/unity-verification/build.log"
```

然后运行：

```text
"C:/Program Files/Unity 2021.3.29f1/Editor/Unity.exe" -batchmode -nographics -quit -projectPath "E:/Unity特效人工智能学习/workspace/unity-verification" -executeMethod VerificationRunner.Run -logFile "E:/Unity特效人工智能学习/workspace/unity-verification/verify.log"
```

只有当场景文件、验证 JSON 和 Unity 日志都真实生成，并且结果为 `verified`，才能更新实验记录和关闭对应 Beads 任务。
