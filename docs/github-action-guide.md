# ModelScope License Risk Watch 使用指南

本指南面向希望在自己的 GitHub 仓库中定时检查 ModelScope 模型许可证风险的团队。该自动化流程不会把 BOM 快照提交到用户仓库，BOM 通过 GitHub Actions Cache 保存，报告通过 Artifact 上传。

## 一、配置 MODELSCOPE_API_KEY（可选，推荐）

扫描公开 ModelScope 模型时不需要配置 Key，工具会使用匿名请求。私有模型、受限模型或遇到 API 频率限制时，建议配置自己的 `MODELSCOPE_API_KEY`。本地运行可以把 Key 放进未提交的 `.env`；GitHub Actions 则应使用仓库 Secret，而不是提交 `.env` 文件。

1. 打开用户仓库的 GitHub 页面。
2. 进入 `Settings` -> `Secrets and variables` -> `Actions`。
3. 点击 `New repository secret`。
4. 名称填写 `MODELSCOPE_API_KEY`。
5. 值填写有效的 ModelScope API Key，然后保存。

工作流只在需要访问 ModelScope API 的步骤中注入该 Secret，不会写入仓库文件或 Artifact。

## 二、复制工作流文件

把工具仓库中的：

```text
.github/workflows/license-watch.yml
```

复制到用户仓库的同名路径：

```text
.github/workflows/license-watch.yml
```

工作流会：

1. 拉取用户仓库代码。
2. 单独拉取 `q7ijiang/open-source-ledger` 到 `.license-watch-tool`。
3. 安装 Python 3.10 和工具依赖。
4. 从 Actions Cache 恢复上一次 BOM 快照。
5. 扫描当前项目并生成新的 BOM。
6. 如果存在历史快照，运行 `--diff` 并检查 `RISK_CONFIRMED`。
7. 上传 `outputs/diff_report.md` 和 `outputs/watch_report.md` 到 `license-report` Artifact。
8. 只有在风险检查通过时才推进 BOM 基线缓存。

BOM 查找使用 `find ... | head -n 1`，不依赖 GNU `find -printf`，因此除 GitHub Actions 的 Ubuntu 环境外，也兼容 macOS 类 Unix 环境。
Fork PR 无法读取仓库 Secret。为避免泄露 `MODELSCOPE_API_KEY`，来自外部 Fork 的 PR 会显示警告并跳过扫描；仓库内部分支的 PR 会正常执行风险阻断。

## 三、使用 composite Action

如果不想复制完整工作流，也可以在用户仓库的工作流中调用：

```yaml
name: License Watch

on:
  workflow_dispatch:
  pull_request:
  schedule:
    - cron: '0 2 * * 1'

permissions:
  contents: read

jobs:
  license-watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: q7ijiang/open-source-ledger@main
        with:
          project_path: .
          api_key: ${{ secrets.MODELSCOPE_API_KEY }}
```

如果只扫描公开模型，可以省略 `api_key` 参数；需要访问私有模型或受限模型时，再通过 GitHub Secrets 传入。

如果希望保存 Action 生成的上传报告，可以在调用后追加 `actions/upload-artifact@v4`，上传 `outputs/diff_report.md` 和 `outputs/watch_report.md`。

## 四、修改 cron 扫描频率

GitHub Actions 的 `cron` 使用 UTC，不是本地时区。默认配置是：

```yaml
- cron: '0 2 * * 1'
```

它表示每周一 02:00 UTC，即北京时间每周一 10:00。常见调整方式：

```yaml
# 每天 02:00 UTC
- cron: '0 2 * * *'

# 每月 1 日 02:00 UTC
- cron: '0 2 1 * *'

# 每周五 18:00 UTC
- cron: '0 18 * * 5'
```

用户可以直接编辑复制到仓库中的 `.github/workflows/license-watch.yml`，修改后提交即可生效。

## 五、首次运行说明

第一次运行时，Actions Cache 中没有历史 BOM。工作流会：

1. 正常扫描当前项目并生成 `latest_bom.json`。
2. 跳过 `--diff`。
3. 在 `outputs/diff_report.md` 中写入“首次运行只建立基线”的说明。
4. 在风险检查通过后，把本次 BOM 保存为后续运行的 t0 基线。

因此第一次运行不会因为缺少历史快照而失败。第二次及之后运行才会进行时间对比。

## 六、阻断机制

`--diff` 生成的报告包含一行：

```text
> 对比区间：{t0日期} → {t1日期}
```

用户可以从报告第一屏直接看到两次快照的时间范围。

如果 `outputs/diff_report.md` 中出现实际的 `RISK_CONFIRMED` 风险记录，工作流会执行 `exit 1`，当前 Job 失败。配置为必需检查后，PR 将被阻止合并。

检测逻辑会排除报告末尾固定说明表中用于解释判定等级的 `RISK_CONFIRMED`，避免“说明文字本身”触发误报。检测到风险时：

- 报告仍会作为 `license-report` Artifact 上传。
- 新的 BOM 不会写回 Cache，基线不会推进。
- 用户需要先修复许可证风险，下一次运行才会在检查通过后更新基线。

## 七、常见问题排查

### 1. 未配置 API Key

现象：日志提示未配置 `MODELSCOPE_API_KEY`，但 Job 仍会继续执行。

处理：公开模型可以继续匿名扫描；如果模型是私有模型，或 API 返回鉴权/频率限制错误，请进入仓库 `Settings` -> `Secrets and variables` -> `Actions`，添加名为 `MODELSCOPE_API_KEY` 的 Repository Secret。

### 2. Fork PR 被跳过

现象：外部 Fork 发来的 PR 只出现安全警告，没有执行扫描。

原因：GitHub 默认不会向 Fork PR 暴露仓库 Secrets。不要为此改用 `pull_request_target` 执行不可信代码。需要完整检查时，可以让贡献者从仓库内部分支提交 PR，或由维护者在可信分支中运行。

### 3. ModelScope API 网络异常

现象：扫描步骤超时，或 ModelScope API 请求失败。

处理：先等待后重试；确认 `https://www.modelscope.cn/api/v1` 可访问；如果是临时网络波动，可在 Actions 页面重新运行失败 Job。

### 4. 项目扫描未生成 bom.json

现象：日志出现警告“项目扫描未生成 bom.json”。Job 不会失败，但会跳过 diff 和风险检测。

可能原因：

- `project_path` 指向的目录不存在。
- 项目中没有可识别的 ModelScope 模型标识。
- 候选模型没有通过 ModelScope 详情 API 验证。
- `MODELSCOPE_API_KEY` 无效或没有访问权限。

处理：先查看 `license-report` Artifact 中的 `watch_report.md`，确认工具识别到了哪些模型和来源文件；也可以在本地运行：

```bash
python main.py --project . --output outputs/watch_report.md
```

### 5. diff_report.md 缺少对比区间

现象：日志提示 diff 报告缺少「对比区间」说明行。

原因：BOM 快照缺少可解析的 `metadata.timestamp`，或报告生成流程被意外替换。

处理：确认使用当前版本的 `main.py` 和 `report_enhanced.py`；如果历史 Cache 来自旧版本，可以先删除对应 Actions Cache，让流程重新建立基线。

### 6. 缓存没有命中

现象：日志显示“缓存中没有历史 BOM，本次仅建立基线”。

原因：首次运行、Cache 已过期、缓存被手动删除，或当前分支没有可复用的 Cache。

处理：等待本次成功运行完成后再次触发。GitHub Actions Cache 有容量和过期策略，首次建基线属于正常行为。
