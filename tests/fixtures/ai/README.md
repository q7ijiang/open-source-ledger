# AI 证据夹具

本目录只保存离线回归和验收使用的人工构造数据，不代表真实模型的法律结论。

- `source_bundles/`：固定 ModelScope 详情、LICENSE/README 原文和 SHA256；
- `model_profiles/`：Mock Provider 返回的模型条款 JSON；
- `project_contexts/`：Mock Provider 返回的项目使用方式 JSON；
- `semantic_diffs/`：同一非标准许可证在 t0/t1 的语义收紧样例。

所有引文都必须能在对应 `source_bundle.documents[].content` 或项目文件原文中逐字找到。`tests/acceptance/generate_ai_acceptance.py` 使用这些夹具生成完整验收包，全程不访问网络。
