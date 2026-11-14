# Qwen-Image 受控演示项目

这是“开源账本”的半决赛受控演示项目，不是生产仓库，也不是真实用户项目。

项目直接使用两个 ModelScope 模型：

- `unsloth/Qwen-Image-2.1-Turbo-FP8`：本地图像生成；
- `OpenGVLab/InternVL3-8B-Instruct`：文档理解。

这两个模型 ID 都是真实存在的。演示时，Action 扫描本项目得到真实现状 t1；
受控 t0 使用冻结的历史许可证快照，二者做 Diff，用于展示许可证变化如何沿
`Qwen-Image-2.1-Turbo-FP8 → Qwen-Image-2.1-Turbo → Qwen-Image-2.1`
传播到项目资产。

边界：

- 本项目不包含模型权重。
- 本项目不声称 Qwen-Image-2.1 的许可证在现实中刚刚发生变化。
- 受控 t0 会显式标记 `simulation=true` / `historical_reconstruction=true`。
- 扫描结果只用于工程审计演示，不构成法律意见。
