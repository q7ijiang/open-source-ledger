# 真实项目夹具与快照场景测试

## 测试目的

验证构建出的项目扫描夹具、冻结血缘、模拟 Diff 和可移植快照满足验收约束。覆盖项目直接模型、上游模型分支、BOM 来源信息、AI 验收证据以及快照中不得出现机器专属路径。

## 文件与覆盖范围

| 文件 | 覆盖内容 |
| --- | --- |
| `test_real_modelscope_project_fixtures.py` | 完整项目快照的模型覆盖、上游分支、模拟标记、BOM 来源和 Diff 布局 |
| `test_snapshot_portability.py` | 已提交快照不包含本机用户目录或机器专属绝对路径 |

## 测试数据

- `tests/fixtures/projects/real_modelscope/full_project/`：受控的多服务项目源码。
- `tests/fixtures/projects/real_modelscope/snapshots/full/`：项目扫描、AI 证据和变更场景快照。
- `tests/fixtures/projects/real_modelscope/snapshots/full/scenarios/`：直接模型变更和上游模型变更的 `t0/t1` 数据。

## 运行方式

```powershell
python -m pytest tests/scenarios/project_fixtures -q
```

## 真实性边界

- `full_project` 是为验收构造的受控项目，不代表真实企业的生产仓库。
- ModelScope 血缘的 `t0` 已冻结为观测快照；测试运行时不重新访问平台。
- 场景中的 `t1` 许可证变化是人为模拟，文件必须保留 `simulation=true`。
- AI 验收数据是预录响应，不代表 Qwen 或其他模型当前的真实许可证文本。
- 当前范围只审查项目直接使用的模型及其上游，不要求保存全量下游模型名。
