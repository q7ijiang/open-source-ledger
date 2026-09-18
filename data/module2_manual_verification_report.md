# 模块 2 合并结果独立第三方核验报告

## 1. 核验范围与方法

- 全量合并对：3,971 对。
- 抽样数量：50 对。
- 抽样方式：固定随机种子 20260918，从全部合并对中无放回随机抽取。
- 抽样结果全部为 `npm::npm`，没有跨生态配对。
- 50 对涉及 15 个唯一规范 `pkg:npm/<name>@<version>`。
- 每一对的两个规范 purl 主体完全相同，区别仅为 Syft 生成的 `package-id` 查询限定。
- 第三方来源为 npm 官方 registry 的版本级 JSON API，并保留官方返回的 repository、homepage、author、maintainers、tarball 和 dist integrity。
- 每项网络查询最多重试 3 次。首轮 `minipass-fetch@3.0.5` 出现过 TLS 握手超时，按同一官方 API 重试成功后纳入核验；最终 15/15 查询成功。

核验判断使用以下独立事实：

1. 官方 registry 存在该 `name@version` 唯一版本记录。
2. 两个规范 purl 去除非身份限定后指向同一个 `name@version`。
3. 对 URL 依据，官方 homepage/repository 与日志 URL 一致。
4. 对 author 依据，官方 author/maintainer 与日志作者一致。
5. npm 包名在 registry 中唯一，`package-id` 是 Syft 内部限定，不构成另一个 npm 包身份。

## 2. 逐对核验结果

表中 purl 优先列出带 `package-id` 的差异记录；其共同的无参数基础 purl 完全相同。

| # | SBOM | name | version | purl A | purl B | 合并依据 | 结论 | 第三方证据 |
|---:|---|---|---:|---|---|---|---|---|
| 3607 | `sbom_syft_node_jod-bookworm_cdx.json` | `@npmcli/agent` | `2.2.2` | `pkg:npm/%40npmcli/agent@2.2.2?package-id=e5aaa014cd0a6a68` | `pkg:npm/%40npmcli/agent@2.2.2?package-id=e4a422721254b40e` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/%40npmcli%2Fagent/2.2.2) / [npm 页面](https://www.npmjs.com/package/@npmcli%2Fagent/v/2.2.2) |
| 1262 | `sbom_syft_node_22.11.0-bookworm_cdx.json` | `unique-slug` | `4.0.0` | `pkg:npm/unique-slug@4.0.0?package-id=583ace7227f54fd3` | `pkg:npm/unique-slug@4.0.0?package-id=8b1c47717a6a0bd9` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-slug/4.0.0) / [npm 页面](https://www.npmjs.com/package/unique-slug/v/4.0.0) |
| 3557 | `sbom_syft_node_iron-bookworm_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=b1793c299d41ea2e` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 632 | `sbom_syft_node_22.10.0-bookworm_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=b1793c299d41ea2e` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 2531 | `sbom_syft_node_23.1-bullseye-slim_cdx.json` | `minipass-fetch` | `3.0.5` | `pkg:npm/minipass-fetch@3.0.5?package-id=b507dad53434e3ba` | `pkg:npm/minipass-fetch@3.0.5?package-id=601e929d9e757519` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass-fetch/3.0.5) / [npm 页面](https://www.npmjs.com/package/minipass-fetch/v/3.0.5) |
| 207 | `sbom_syft_node_20.16.0-alpine3.19_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=a40aeaca74a18cab` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 2485 | `sbom_syft_node_23.1-bookworm_cdx.json` | `mkdirp` | `3.0.1` | `pkg:npm/mkdirp@3.0.1?package-id=3cb751ffc0192fe9` | `pkg:npm/mkdirp@3.0.1?package-id=8164dfc68c384e39` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/mkdirp/3.0.1) / [npm 页面](https://www.npmjs.com/package/mkdirp/v/3.0.1) |
| 3752 | `sbom_syft_node_jod_cdx.json` | `unique-slug` | `4.0.0` | `pkg:npm/unique-slug@4.0.0?package-id=583ace7227f54fd3` | `pkg:npm/unique-slug@4.0.0?package-id=8b1c47717a6a0bd9` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-slug/4.0.0) / [npm 页面](https://www.npmjs.com/package/unique-slug/v/4.0.0) |
| 1767 | `sbom_syft_node_23-bookworm-slim_cdx.json` | `make-fetch-happen` | `13.0.1` | `pkg:npm/make-fetch-happen@13.0.1?package-id=86cfee54d14120b5` | `pkg:npm/make-fetch-happen@13.0.1?package-id=1b5b8486c1293566` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/make-fetch-happen/13.0.1) / [npm 页面](https://www.npmjs.com/package/make-fetch-happen/v/13.0.1) |
| 1443 | `sbom_syft_node_22.5-slim_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | `pkg:npm/minipass@3.3.6?package-id=e1062d9881f71e7d` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 3363 | `sbom_syft_node_current-bookworm_cdx.json` | `cacache` | `18.0.4` | `pkg:npm/cacache@18.0.4?package-id=1be64550a9520714` | `pkg:npm/cacache@18.0.4?package-id=6b58e86e4f846657` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/cacache/18.0.4) / [npm 页面](https://www.npmjs.com/package/cacache/v/18.0.4) |
| 3292 | `sbom_syft_node_bullseye-slim_cdx.json` | `ssri` | `10.0.6` | `pkg:npm/ssri@10.0.6?package-id=994720b72122cff2` | `pkg:npm/ssri@10.0.6?package-id=0da7f42d8c015056` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/ssri/10.0.6) / [npm 页面](https://www.npmjs.com/package/ssri/v/10.0.6) |
| 2574 | `sbom_syft_node_23.1-slim_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=c85b7861124a8745` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 1333 | `sbom_syft_node_22.11.0-slim_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=b1793c299d41ea2e` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 2701 | `sbom_syft_node_23.1.0-alpine3.20_cdx.json` | `unique-slug` | `4.0.0` | `pkg:npm/unique-slug@4.0.0?package-id=583ace7227f54fd3` | `pkg:npm/unique-slug@4.0.0?package-id=32286e06f5fb427b` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-slug/4.0.0) / [npm 页面](https://www.npmjs.com/package/unique-slug/v/4.0.0) |
| 642 | `sbom_syft_node_22.10.0-bookworm_cdx.json` | `minipass-fetch` | `3.0.5` | `pkg:npm/minipass-fetch@3.0.5?package-id=500541b29e499c07` | `pkg:npm/minipass-fetch@3.0.5?package-id=601e929d9e757519` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass-fetch/3.0.5) / [npm 页面](https://www.npmjs.com/package/minipass-fetch/v/3.0.5) |
| 1467 | `sbom_syft_node_22.5.1-bookworm_cdx.json` | `ansi-regex` | `6.0.1` | `pkg:npm/ansi-regex@6.0.1?package-id=644574c30c4e79b8` | `pkg:npm/ansi-regex@6.0.1?package-id=8f452df775a099de` | 同名+同版本+同author或maintainer | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/ansi-regex/6.0.1) / [npm 页面](https://www.npmjs.com/package/ansi-regex/v/6.0.1) |
| 3390 | `sbom_syft_node_current-bookworm_cdx.json` | `ssri` | `10.0.6` | `pkg:npm/ssri@10.0.6?package-id=238df8fcf320b3bb` | `pkg:npm/ssri@10.0.6?package-id=994720b72122cff2` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/ssri/10.0.6) / [npm 页面](https://www.npmjs.com/package/ssri/v/10.0.6) |
| 3025 | `sbom_syft_node_23.1_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=c85b7861124a8745` | `pkg:npm/minipass@3.3.6?package-id=e1062d9881f71e7d` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 449 | `sbom_syft_node_22-bookworm-slim_cdx.json` | `proc-log` | `4.2.0` | `pkg:npm/proc-log@4.2.0?package-id=06618a7349088991` | `pkg:npm/proc-log@4.2.0?package-id=5e534737a203961a` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/proc-log/4.2.0) / [npm 页面](https://www.npmjs.com/package/proc-log/v/4.2.0) |
| 2249 | `sbom_syft_node_23.0_cdx.json` | `unique-filename` | `3.0.0` | `pkg:npm/unique-filename@3.0.0?package-id=775ebc366c52f5ba` | `pkg:npm/unique-filename@3.0.0?package-id=0b288c5165455d25` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-filename/3.0.0) / [npm 页面](https://www.npmjs.com/package/unique-filename/v/3.0.0) |
| 2416 | `sbom_syft_node_23.1-bookworm-slim_cdx.json` | `make-fetch-happen` | `13.0.1` | `pkg:npm/make-fetch-happen@13.0.1?package-id=86cfee54d14120b5` | `pkg:npm/make-fetch-happen@13.0.1?package-id=92f00d935c39d61e` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/make-fetch-happen/13.0.1) / [npm 页面](https://www.npmjs.com/package/make-fetch-happen/v/13.0.1) |
| 1514 | `sbom_syft_node_22.5.1-bullseye_cdx.json` | `string-width` | `4.2.3` | `pkg:npm/string-width@4.2.3?package-id=54dbf56ee3c24fdc` | `pkg:npm/string-width@4.2.3?package-id=a07df3ff794d86cd` | 同名+同版本+同author或maintainer | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/string-width/4.2.3) / [npm 页面](https://www.npmjs.com/package/string-width/v/4.2.3) |
| 512 | `sbom_syft_node_22-slim_cdx.json` | `unique-slug` | `4.0.0` | `pkg:npm/unique-slug@4.0.0?package-id=583ace7227f54fd3` | `pkg:npm/unique-slug@4.0.0?package-id=8b1c47717a6a0bd9` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-slug/4.0.0) / [npm 页面](https://www.npmjs.com/package/unique-slug/v/4.0.0) |
| 401 | `sbom_syft_node_22-alpine_cdx.json` | `spdx-expression-parse` | `3.0.1` | `pkg:npm/spdx-expression-parse@3.0.1?package-id=d9e53414cd58088c` | `pkg:npm/spdx-expression-parse@3.0.1?package-id=946f96a7e1e91737` | 同名+同版本+同author或maintainer | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/spdx-expression-parse/3.0.1) / [npm 页面](https://www.npmjs.com/package/spdx-expression-parse/v/3.0.1) |
| 892 | `sbom_syft_node_22.11-alpine_cdx.json` | `minipass-fetch` | `3.0.5` | `pkg:npm/minipass-fetch@3.0.5?package-id=500541b29e499c07` | `pkg:npm/minipass-fetch@3.0.5?package-id=601e929d9e757519` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass-fetch/3.0.5) / [npm 页面](https://www.npmjs.com/package/minipass-fetch/v/3.0.5) |
| 780 | `sbom_syft_node_22.11-alpine3.19_cdx.json` | `make-fetch-happen` | `13.0.1` | `pkg:npm/make-fetch-happen@13.0.1?package-id=92f00d935c39d61e` | `pkg:npm/make-fetch-happen@13.0.1?package-id=1b5b8486c1293566` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/make-fetch-happen/13.0.1) / [npm 页面](https://www.npmjs.com/package/make-fetch-happen/v/13.0.1) |
| 3526 | `sbom_syft_node_hydrogen-bullseye_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=c85b7861124a8745` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 191 | `sbom_syft_node_20.16-alpine_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 1378 | `sbom_syft_node_22.5-bookworm-slim_cdx.json` | `string-width` | `4.2.3` | `pkg:npm/string-width@4.2.3?package-id=54dbf56ee3c24fdc` | `pkg:npm/string-width@4.2.3?package-id=a07df3ff794d86cd` | 同名+同版本+同author或maintainer | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/string-width/4.2.3) / [npm 页面](https://www.npmjs.com/package/string-width/v/4.2.3) |
| 3447 | `sbom_syft_node_current-bullseye-slim_cdx.json` | `unique-filename` | `3.0.0` | `pkg:npm/unique-filename@3.0.0?package-id=d72e796bcca2815e` | `pkg:npm/unique-filename@3.0.0?package-id=775ebc366c52f5ba` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-filename/3.0.0) / [npm 页面](https://www.npmjs.com/package/unique-filename/v/3.0.0) |
| 747 | `sbom_syft_node_22.10.0_cdx.json` | `mkdirp` | `3.0.1` | `pkg:npm/mkdirp@3.0.1?package-id=3cb751ffc0192fe9` | `pkg:npm/mkdirp@3.0.1?package-id=8164dfc68c384e39` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/mkdirp/3.0.1) / [npm 页面](https://www.npmjs.com/package/mkdirp/v/3.0.1) |
| 2732 | `sbom_syft_node_23.1.0-alpine_cdx.json` | `minizlib` | `3.0.1` | `pkg:npm/minizlib@3.0.1?package-id=d14c0f09d0234816` | `pkg:npm/minizlib@3.0.1?package-id=10d6685f2e0017d4` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minizlib/3.0.1) / [npm 页面](https://www.npmjs.com/package/minizlib/v/3.0.1) |
| 3498 | `sbom_syft_node_current_cdx.json` | `unique-filename` | `3.0.0` | `pkg:npm/unique-filename@3.0.0?package-id=d72e796bcca2815e` | `pkg:npm/unique-filename@3.0.0?package-id=0b288c5165455d25` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-filename/3.0.0) / [npm 页面](https://www.npmjs.com/package/unique-filename/v/3.0.0) |
| 2471 | `sbom_syft_node_23.1-bookworm_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=b1793c299d41ea2e` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 1186 | `sbom_syft_node_22.11.0-bookworm-slim_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=c85b7861124a8745` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 3960 | `sbom_syft_node_lts_cdx.json` | `ssri` | `10.0.6` | `pkg:npm/ssri@10.0.6?package-id=238df8fcf320b3bb` | `pkg:npm/ssri@10.0.6?package-id=0da7f42d8c015056` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/ssri/10.0.6) / [npm 页面](https://www.npmjs.com/package/ssri/v/10.0.6) |
| 964 | `sbom_syft_node_22.11-bookworm-slim_cdx.json` | `unique-slug` | `4.0.0` | `pkg:npm/unique-slug@4.0.0?package-id=8b1c47717a6a0bd9` | `pkg:npm/unique-slug@4.0.0?package-id=32286e06f5fb427b` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/unique-slug/4.0.0) / [npm 页面](https://www.npmjs.com/package/unique-slug/v/4.0.0) |
| 2483 | `sbom_syft_node_23.1-bookworm_cdx.json` | `minizlib` | `3.0.1` | `pkg:npm/minizlib@3.0.1?package-id=d14c0f09d0234816` | `pkg:npm/minizlib@3.0.1?package-id=0c71080d1888fc0f` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minizlib/3.0.1) / [npm 页面](https://www.npmjs.com/package/minizlib/v/3.0.1) |
| 2573 | `sbom_syft_node_23.1-slim_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=c85b7861124a8745` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 3111 | `sbom_syft_node_alpine3.19_cdx.json` | `cacache` | `18.0.4` | `pkg:npm/cacache@18.0.4?package-id=b0072b4f966cc5f7` | `pkg:npm/cacache@18.0.4?package-id=1be64550a9520714` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/cacache/18.0.4) / [npm 页面](https://www.npmjs.com/package/cacache/v/18.0.4) |
| 2038 | `sbom_syft_node_23.0-bullseye_cdx.json` | `proc-log` | `4.2.0` | `pkg:npm/proc-log@4.2.0?package-id=e18db8595c402719` | `pkg:npm/proc-log@4.2.0?package-id=5e534737a203961a` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/proc-log/4.2.0) / [npm 页面](https://www.npmjs.com/package/proc-log/v/4.2.0) |
| 2808 | `sbom_syft_node_23.1.0-bookworm_cdx.json` | `@npmcli/fs` | `3.1.1` | `pkg:npm/%40npmcli/fs@3.1.1?package-id=3924c352e7aa35d1` | `pkg:npm/%40npmcli/fs@3.1.1?package-id=03da1fb11c11af1b` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/%40npmcli%2Ffs/3.1.1) / [npm 页面](https://www.npmjs.com/package/@npmcli%2Ffs/v/3.1.1) |
| 1140 | `sbom_syft_node_22.11.0-alpine_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | `pkg:npm/minipass@3.3.6?package-id=e1062d9881f71e7d` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 2278 | `sbom_syft_node_23.1-alpine3.19_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | `pkg:npm/minipass@3.3.6?package-id=e1062d9881f71e7d` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 920 | `sbom_syft_node_22.11-bookworm-slim_cdx.json` | `@npmcli/fs` | `3.1.1` | `pkg:npm/%40npmcli/fs@3.1.1?package-id=3924c352e7aa35d1` | `pkg:npm/%40npmcli/fs@3.1.1?package-id=03da1fb11c11af1b` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/%40npmcli%2Ffs/3.1.1) / [npm 页面](https://www.npmjs.com/package/@npmcli%2Ffs/v/3.1.1) |
| 2735 | `sbom_syft_node_23.1.0-alpine_cdx.json` | `mkdirp` | `3.0.1` | `pkg:npm/mkdirp@3.0.1?package-id=3cb751ffc0192fe9` | `pkg:npm/mkdirp@3.0.1?package-id=8164dfc68c384e39` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/mkdirp/3.0.1) / [npm 页面](https://www.npmjs.com/package/mkdirp/v/3.0.1) |
| 2238 | `sbom_syft_node_23.0_cdx.json` | `proc-log` | `4.2.0` | `pkg:npm/proc-log@4.2.0?package-id=e18db8595c402719` | `pkg:npm/proc-log@4.2.0?package-id=5e534737a203961a` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/proc-log/4.2.0) / [npm 页面](https://www.npmjs.com/package/proc-log/v/4.2.0) |
| 2026 | `sbom_syft_node_23.0-bullseye_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | `pkg:npm/minipass@3.3.6?package-id=042160c7b66b24f8` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |
| 2075 | `sbom_syft_node_23.0.0-bookworm_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=c85b7861124a8745` | `pkg:npm/minipass@3.3.6?package-id=e1062d9881f71e7d` | homepage或repository URL相同 | **CONFIRMED** | [registry JSON](https://registry.npmjs.org/minipass/3.3.6) / [npm 页面](https://www.npmjs.com/package/minipass/v/3.3.6) |

## 3. 结论分布

| 结论 | 对数 | 比例 |
|---|---:|---:|
| CONFIRMED | 50 | 100.0% |
| SUSPECT | 0 | 0.0% |
| WRONG | 0 | 0.0% |

- URL 类合并：官方 homepage/repository 支持 46 对，冲突 0 对，其余为 author 类，不适用 URL 核验。
- author 类合并：官方 author/maintainer 支持 47 对，冲突 0 对，其余为 URL 类，不适用作者核验。
- 官方查询失败数：0。

## 4. WRONG 案例

本次 50 对随机样本中没有发现 WRONG。

因此按题设规则，不需要将抽样扩大到 200 对。需要注意，这表示 50 对样本中无误合并，不表示已经穷举验证全部 3,971 对。

## 5. 唯一包官方证据

| npm 包 | 版本 | 官方 repository | 官方 author | maintainers | registry 链接 |
|---|---:|---|---|---:|---|
| `@npmcli/agent` | `2.2.2` | git+https://github.com/npm/agent.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/%40npmcli%2Fagent/2.2.2) |
| `@npmcli/fs` | `3.1.1` | git+https://github.com/npm/fs.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/%40npmcli%2Ffs/3.1.1) |
| `ansi-regex` | `6.0.1` | git+https://github.com/chalk/ansi-regex.git | Sindre Sorhus | 2 | [JSON](https://registry.npmjs.org/ansi-regex/6.0.1) |
| `cacache` | `18.0.4` | git+https://github.com/npm/cacache.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/cacache/18.0.4) |
| `make-fetch-happen` | `13.0.1` | git+https://github.com/npm/make-fetch-happen.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/make-fetch-happen/13.0.1) |
| `minipass-fetch` | `3.0.5` | git+https://github.com/npm/minipass-fetch.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/minipass-fetch/3.0.5) |
| `minipass` | `3.3.6` | git+https://github.com/isaacs/minipass.git | Isaac Z. Schlueter | 6 | [JSON](https://registry.npmjs.org/minipass/3.3.6) |
| `minizlib` | `3.0.1` | git+https://github.com/isaacs/minizlib.git | Isaac Z. Schlueter | 6 | [JSON](https://registry.npmjs.org/minizlib/3.0.1) |
| `mkdirp` | `3.0.1` | git+https://github.com/isaacs/node-mkdirp.git | (未提供) | 1 | [JSON](https://registry.npmjs.org/mkdirp/3.0.1) |
| `proc-log` | `4.2.0` | git+https://github.com/npm/proc-log.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/proc-log/4.2.0) |
| `spdx-expression-parse` | `3.0.1` | git+https://github.com/jslicense/spdx-expression-parse.js.git | Kyle E. Mitchell | 2 | [JSON](https://registry.npmjs.org/spdx-expression-parse/3.0.1) |
| `ssri` | `10.0.6` | git+https://github.com/npm/ssri.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/ssri/10.0.6) |
| `string-width` | `4.2.3` | git+https://github.com/sindresorhus/string-width.git | Sindre Sorhus | 1 | [JSON](https://registry.npmjs.org/string-width/4.2.3) |
| `unique-filename` | `3.0.0` | git+https://github.com/npm/unique-filename.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/unique-filename/3.0.0) |
| `unique-slug` | `4.0.0` | git+https://github.com/npm/unique-slug.git | GitHub Inc. | 5 | [JSON](https://registry.npmjs.org/unique-slug/4.0.0) |

## 6. 整体准确率估计

- 样本点估计：50/50 = 100.0%。
- 若把 50 次独立核验近似看作二项抽样，0 个错误时，Clopper-Pearson 双侧 95% 置信区间下界约为 92.89%，上界为 100%。
- 抽样覆盖全部合并规则：URL 规则 46 对，author 规则 4 对。
- 全量 3,971 对均为 `npm::npm`，且规范 purl 主体相同；结合本次独立核验，可以把“仅 package-id 不同的同 name@version 记录应合并”作为高可信结论。

不能把 100% 样本准确率外推为对其他生态或跨生态规则的 100% 准确率，因为本次抽样没有出现 PyPI、Debian、Docker OS 包或跨生态合并。

## 7. 建议

1. 保留当前规则：对 npm 合并先比较去掉查询限定后的规范 purl；如果 `name@version` 完全相同，可以直接视为同一包版本实体。
2. `package-id` 不应参与 npm 包实体身份判断，它只是 Syft 的内部安装记录标识。
3. 如果后续把同一规则用于 PyPI、Debian 或跨生态合并，应分别抽样并查询对应官方源，不能直接沿用 npm 的验证结论。
4. 对 URL 规则继续保留同版本护栏；不同版本共用 repository 只能说明同一项目，不能说明同一版本实体。
5. 若技术报告需要更强的总体统计，可对全部 3,971 对中的唯一 `name@version` 做全量 registry 查询；当前 50 对随机核验已足以支持本批 npm 合并结论。

## 8. 审计文件

- `outputs/module2_manual_verification_evidence.json`
- `outputs/module2_manual_verification_pairs.json`

本报告中的结论只来自 npm 官方 registry 的独立查询结果；原始合并日志只用于提取待核验的 name、version、purl、依据和 SBOM 路径。
