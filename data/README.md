# 数据说明

## MSU SBOM Benchmark
- 来源：GitHub MSUSEL/msusel-pique-sbom-supplychain-sec
- Zenodo DOI: 10.5281/zenodo.15122007
- 内容：995 个 Docker CycloneDX SBOM
- 用途：验证模块 1（BOM解析）、模块 2（同生态实体对齐）

## Wild SBOMs
- 来源：Zenodo DOI: 10.5281/zenodo.17397281
- 内容：57,877 个 CycloneDX JSON
- 用途：验证模块 2（跨生态实体对齐的保守性）

## Hugging Face 真实模型 BOM
- 来源：用 cdxgen 扫描 9 个真实 HF 模型生成
- 用途：模块 8（血缘图构建）的输入数据

## 合成测试项目
- 位置：test-project/
- 用途：模块 1-3 的基础验证