# 开源台账交付包

面向 Hugging Face 模型血缘的许可证变更风险传播工具。通过对模型依赖关系（血缘）的构建与增量比对，将许可证变更沿依赖链传播，输出可审计的风险报告与血缘图。

## 目录结构

- `main.py`：主入口，支持血缘图构建、diff 风险传播与基础报告三种模式
- `work/`：辅助脚本（如 `extract_hf_lineage.py`，用于抽取 Hugging Face 模型血缘）
- `data/`：样例数据（`sample_bom.json`、`hf_models_bom/`、`test_scenarios/`）
- `docs/`：文档（`接口约定.md`）
- `tests/`：测试用例与 fixtures
- `outputs/`：示例产出（血缘图、报告）

## 运行环境

- Python 3.10+

## 安装

```bash
pip install -r requirements.txt
```

## 用法

### 用法一：模型血缘图 + 报告

输入模型名，生成血缘图与报告：

```bash
python main.py --model <模型名> --output <报告路径>
```

### 用法二：时间化风险传播

比较两个 BOM，输出随时间变化的许可证风险传播结果：

```bash
python main.py --diff --before <t0_bom> --after <t1_bom> --output <报告路径>
```

### 用法三：基础模式

输出中文合规清单：

```bash
python main.py --mode basic --input <bom> --output <报告路径>
```

## 示例产出

- `outputs/example_lineage_graph.png`：血缘图
- `outputs/example_report.md`：报告

## 已知缺口

`report_basic.py` 尚未接入 `main.py`，主入口使用内联渲染。
