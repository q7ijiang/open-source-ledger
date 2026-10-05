# 开源账本（open-source-ledger）

开源账本用于对开源软件、AI 模型和数据集进行中文合规清单生成，并进一步分析时间化血缘风险传播。

项目周期：2026-09-18 至 2026-10-15
项目定位：
1. 基础部分（面向学生/小团队）：一键扫描项目，生成中文《开源及第三方资源使用清单》，标注高风险项，附证据链接。
2. 深度部分（面向合规研究者）：输入两个 CycloneDX BOM，做时间化血缘传播，输出三级判定（RISK_CONFIRMED / RISK_POTENTIAL / UNDETERMINED）和路径证书。

## 团队分工

| 成员 | 负责模块 |
|---|---|
| A（数据管道） | BOM解析、跨生态实体对齐、证据链补全、GitHub Action集成、全流程集成 |
| B（算法核心） | AI许可证规则库、血缘图构建、Delta检测、风险传播 |
| C（交付与验证） | 中文清单生成、测试数据准备、增强层报告、深度测试数据、技术报告、演示视频 |

## 协作工具与文档

- [接口约定](docs/接口约定.md)：所有 JSON 数据结构必须严格遵循此文档。
- [进度追踪](docs/进度追踪.md)：查看各模块负责人、截止日期和当前状态。
- [每日站会模板](docs/每日站会模板.md)：每人每天按固定格式同步进度。
- [每周验收清单](docs/每周验收清单.md)：按周检查交付物和验收标准。
- [分支与代码协作规范](docs/分支与代码协作规范.md)：分支策略、合并规则与代码规范。

## 安装

### 1. 安装 Node.js

cdxgen 依赖 Node.js，请先安装 Node.js（建议 18 及以上，可通过官方安装包或 nvm 安装）。

### 2. 安装 cdxgen

```bash
npm install -g @cyclonedx/cdxgen
```

安装后确认可用：

```bash
cdxgen --version
```

### 3. 安装 Python 依赖

Python 最低版本：3.10+

```bash
pip install -r requirements.txt
```

### 4.（可选）设置 CDXGEN_PATH 环境变量

如果 `cdxgen` 不在 PATH 中，可设置环境变量 `CDXGEN_PATH` 指向 cdxgen 可执行文件，脚本会优先使用它：

- Windows（PowerShell）：

  ```powershell
  $env:CDXGEN_PATH = "C:\path\to\cdxgen.cmd"
  ```

- Linux / macOS：

  ```bash
  export CDXGEN_PATH=/path/to/cdxgen
  ```

## 快速开始

运行 cdxgen
在 Windows 上请使用 `tools/cdxgen/cdxgen.cmd`，不要用 `cdxgen.ps1`，否则会因 PowerShell 执行策略被拒绝。
命令示例：
tools\cdxgen\cdxgen.cmd -t python -t npm -t ai --evidence --no-install-deps --json-pretty -o sample_bom.json .

> 基础模式（生成中文合规清单）：
> `python main.py --mode basic --input sample_bom.json --output reports/basic_report.md`

> 深度模式（时间化血缘风险传播）：
> `python main.py --mode deep --before t0_bom.json --after t1_bom.json --output reports/deep_report.md`

### 模块化命令（深度部分，B 交付）

深度链路为「图构建 → Delta 检测 → 风险传播」，可直接逐模块运行：

```
python build_graph.py        --assets t1_assets.json --edges t1_edges.json --output out/graph_t1.json
python delta_engine.py       --before-assets t0_assets.json --before-edges t0_edges.json \
                             --after-assets t1_assets.json  --after-edges t1_edges.json  --output out/events.json
python propagation_engine.py --events out/events.json --graph-before out/graph_t0.json \
                             --graph-after out/graph_t1.json --output out/propagated.json
```

许可证规则库可独立查询：

```
python license_db.py --list                  # 列出 24 种许可证规则
python license_db.py --compare MIT GPL-3.0   # 判断宽松→严格方向
```

## 免责声明

本工具输出为基于证据的辅助审计，不构成法律意见。

## 迁移说明

本目录中的 `tools/node/node_modules` 是 Windows junction，指向 `tools/cdxgen/node_modules`。这是为了避免重复复制约 409 MiB 依赖。

如果需要把本目录迁移到其他机器或其他操作系统：
1. 不要直接复制 `tools/` 目录。
2. 在新机器上重新执行 `npm install -g @cyclonedx/cdxgen`，或按 `tools/cdxgen/README` 说明重装。
3. 本目录仅作为本地工作目录，不提交到 GitHub 仓库。
