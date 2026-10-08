# 开源及第三方资源使用清单

- 生成时间：2026-10-02T17:31:34Z
- 输入 BOM：`data\sample_bom.json`
- 快照 ID：`basic-20261003`
- 本报告由 `main.py` 调用 BOM 解析、实体对齐、证据补全和 HF 血缘提取模块生成；通用 depends_on 边已移除。

## 摘要

- BOM 解析资产数：72
- 实体对齐后资产数：71
- 候选配对日志数：2
- HF 血缘边数：0
- 支持远程证据的 purl 数：71
- 成功补全远程证据数：0
- 网络失败降级数：71
- 处理前无证据资产：2
- 处理后无证据资产：0

## 许可证风险分布

| 风险等级 | 资产数 |
| --- | --- |
| 1 | 68 |
| 2 | 1 |

### 类别分布

| 许可证类别 | 资产数 |
| --- | --- |
| 宽松许可 | 69 |
| 未知 / 待人工确认 | 2 |

## 重点资产

_无数据_

## 资产清单

| canonical_id | 类型 | 名称 | 版本 | 许可证 | 风险 | 类别 | 最佳证据 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model:huggingface/bert-base-uncased@main | model | bert-base-uncased | main | Apache-2.0 | 2 | 宽松许可 | B | [1](https://huggingface.co/api/models/bert-base-uncased) |
| package:npm/accepts@1.3.8 | package | accepts | 1.3.8 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/accepts/-/accepts-1.3.8.tgz)<br>[2](https://registry.npmjs.org/accepts) |
| package:npm/array-flatten@1.1.1 | package | array-flatten | 1.1.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/array-flatten/-/array-flatten-1.1.1.tgz)<br>[2](https://registry.npmjs.org/array-flatten) |
| package:npm/body-parser@1.20.8 | package | body-parser | 1.20.8 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/body-parser/-/body-parser-1.20.8.tgz)<br>[2](https://registry.npmjs.org/body-parser) |
| package:npm/bytes@3.1.2 | package | bytes | 3.1.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/bytes/-/bytes-3.1.2.tgz)<br>[2](https://registry.npmjs.org/bytes) |
| package:npm/call-bind-apply-helpers@1.0.2 | package | call-bind-apply-helpers | 1.0.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/call-bind-apply-helpers/-/call-bind-apply-helpers-1.0.2.tgz)<br>[2](https://registry.npmjs.org/call-bind-apply-helpers) |
| package:npm/call-bound@1.0.4 | package | call-bound | 1.0.4 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/call-bound/-/call-bound-1.0.4.tgz)<br>[2](https://registry.npmjs.org/call-bound) |
| package:npm/content-disposition@0.5.4 | package | content-disposition | 0.5.4 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/content-disposition/-/content-disposition-0.5.4.tgz)<br>[2](https://registry.npmjs.org/content-disposition) |
| package:npm/content-type@1.0.5 | package | content-type | 1.0.5 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/content-type/-/content-type-1.0.5.tgz)<br>[2](https://registry.npmjs.org/content-type) |
| package:npm/cookie-signature@1.0.7 | package | cookie-signature | 1.0.7 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/cookie-signature/-/cookie-signature-1.0.7.tgz)<br>[2](https://registry.npmjs.org/cookie-signature) |
| package:npm/cookie@0.7.2 | package | cookie | 0.7.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/cookie/-/cookie-0.7.2.tgz)<br>[2](https://registry.npmjs.org/cookie) |
| package:npm/debug@2.6.9 | package | debug | 2.6.9 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/debug/-/debug-2.6.9.tgz)<br>[2](https://registry.npmjs.org/debug) |
| package:npm/depd@2.0.0 | package | depd | 2.0.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/depd/-/depd-2.0.0.tgz)<br>[2](https://registry.npmjs.org/depd) |
| package:npm/destroy@1.2.0 | package | destroy | 1.2.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/destroy/-/destroy-1.2.0.tgz)<br>[2](https://registry.npmjs.org/destroy) |
| package:npm/dunder-proto@1.0.1 | package | dunder-proto | 1.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/dunder-proto/-/dunder-proto-1.0.1.tgz)<br>[2](https://registry.npmjs.org/dunder-proto) |
| package:npm/ee-first@1.1.1 | package | ee-first | 1.1.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/ee-first/-/ee-first-1.1.1.tgz)<br>[2](https://registry.npmjs.org/ee-first) |
| package:npm/encodeurl@2.0.0 | package | encodeurl | 2.0.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/encodeurl/-/encodeurl-2.0.0.tgz)<br>[2](https://registry.npmjs.org/encodeurl) |
| package:npm/es-define-property@1.0.1 | package | es-define-property | 1.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/es-define-property/-/es-define-property-1.0.1.tgz)<br>[2](https://registry.npmjs.org/es-define-property) |
| package:npm/es-errors@1.3.0 | package | es-errors | 1.3.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/es-errors/-/es-errors-1.3.0.tgz)<br>[2](https://registry.npmjs.org/es-errors) |
| package:npm/es-object-atoms@1.1.2 | package | es-object-atoms | 1.1.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/es-object-atoms/-/es-object-atoms-1.1.2.tgz)<br>[2](https://registry.npmjs.org/es-object-atoms) |
| package:npm/escape-html@1.0.3 | package | escape-html | 1.0.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/escape-html/-/escape-html-1.0.3.tgz)<br>[2](https://registry.npmjs.org/escape-html) |
| package:npm/etag@1.8.1 | package | etag | 1.8.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/etag/-/etag-1.8.1.tgz)<br>[2](https://registry.npmjs.org/etag) |
| package:npm/express@4.22.3 | package | express | 4.22.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/express/-/express-4.22.3.tgz)<br>[2](https://registry.npmjs.org/express) |
| package:npm/finalhandler@1.3.2 | package | finalhandler | 1.3.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/finalhandler/-/finalhandler-1.3.2.tgz)<br>[2](https://registry.npmjs.org/finalhandler) |
| package:npm/forwarded@0.2.0 | package | forwarded | 0.2.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/forwarded/-/forwarded-0.2.0.tgz)<br>[2](https://registry.npmjs.org/forwarded) |
| package:npm/fresh@0.5.2 | package | fresh | 0.5.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/fresh/-/fresh-0.5.2.tgz)<br>[2](https://registry.npmjs.org/fresh) |
| package:npm/function-bind@1.1.2 | package | function-bind | 1.1.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/function-bind/-/function-bind-1.1.2.tgz)<br>[2](https://registry.npmjs.org/function-bind) |
| package:npm/get-intrinsic@1.3.0 | package | get-intrinsic | 1.3.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/get-intrinsic/-/get-intrinsic-1.3.0.tgz)<br>[2](https://registry.npmjs.org/get-intrinsic) |
| package:npm/get-proto@1.0.1 | package | get-proto | 1.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/get-proto/-/get-proto-1.0.1.tgz)<br>[2](https://registry.npmjs.org/get-proto) |
| package:npm/gopd@1.2.0 | package | gopd | 1.2.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/gopd/-/gopd-1.2.0.tgz)<br>[2](https://registry.npmjs.org/gopd) |
| package:npm/has-symbols@1.1.0 | package | has-symbols | 1.1.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/has-symbols/-/has-symbols-1.1.0.tgz)<br>[2](https://registry.npmjs.org/has-symbols) |
| package:npm/hasown@2.0.4 | package | hasown | 2.0.4 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/hasown/-/hasown-2.0.4.tgz)<br>[2](https://registry.npmjs.org/hasown) |
| package:npm/http-errors@2.0.1 | package | http-errors | 2.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/http-errors/-/http-errors-2.0.1.tgz)<br>[2](https://registry.npmjs.org/http-errors) |
| package:npm/iconv-lite@0.4.24 | package | iconv-lite | 0.4.24 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/iconv-lite/-/iconv-lite-0.4.24.tgz)<br>[2](https://registry.npmjs.org/iconv-lite) |
| package:npm/inherits@2.0.4 | package | inherits | 2.0.4 | ISC | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/inherits/-/inherits-2.0.4.tgz)<br>[2](https://registry.npmjs.org/inherits) |
| package:npm/ipaddr.js@1.9.1 | package | ipaddr.js | 1.9.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/ipaddr.js/-/ipaddr.js-1.9.1.tgz)<br>[2](https://registry.npmjs.org/ipaddr.js) |
| package:npm/math-intrinsics@1.1.0 | package | math-intrinsics | 1.1.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/math-intrinsics/-/math-intrinsics-1.1.0.tgz)<br>[2](https://registry.npmjs.org/math-intrinsics) |
| package:npm/media-typer@0.3.0 | package | media-typer | 0.3.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/media-typer/-/media-typer-0.3.0.tgz)<br>[2](https://registry.npmjs.org/media-typer) |
| package:npm/merge-descriptors@1.0.3 | package | merge-descriptors | 1.0.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/merge-descriptors/-/merge-descriptors-1.0.3.tgz)<br>[2](https://registry.npmjs.org/merge-descriptors) |
| package:npm/methods@1.1.2 | package | methods | 1.1.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/methods/-/methods-1.1.2.tgz)<br>[2](https://registry.npmjs.org/methods) |
| package:npm/mime-db@1.52.0 | package | mime-db | 1.52.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/mime-db/-/mime-db-1.52.0.tgz)<br>[2](https://registry.npmjs.org/mime-db) |
| package:npm/mime-types@2.1.35 | package | mime-types | 2.1.35 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/mime-types/-/mime-types-2.1.35.tgz)<br>[2](https://registry.npmjs.org/mime-types) |
| package:npm/mime@1.6.0 | package | mime | 1.6.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/mime/-/mime-1.6.0.tgz)<br>[2](https://registry.npmjs.org/mime) |
| package:npm/ms@2.0.0 | package | ms | 2.0.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/ms/-/ms-2.0.0.tgz)<br>[2](https://registry.npmjs.org/ms) |
| package:npm/ms@2.1.3 | package | ms | 2.1.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/ms/-/ms-2.1.3.tgz)<br>[2](https://registry.npmjs.org/ms) |
| package:npm/negotiator@0.6.3 | package | negotiator | 0.6.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/negotiator/-/negotiator-0.6.3.tgz)<br>[2](https://registry.npmjs.org/negotiator) |
| package:npm/object-inspect@1.13.4 | package | object-inspect | 1.13.4 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/object-inspect/-/object-inspect-1.13.4.tgz)<br>[2](https://registry.npmjs.org/object-inspect) |
| package:npm/on-finished@2.4.1 | package | on-finished | 2.4.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/on-finished/-/on-finished-2.4.1.tgz)<br>[2](https://registry.npmjs.org/on-finished) |
| package:npm/parseurl@1.3.3 | package | parseurl | 1.3.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/parseurl/-/parseurl-1.3.3.tgz)<br>[2](https://registry.npmjs.org/parseurl) |
| package:npm/path-to-regexp@0.1.13 | package | path-to-regexp | 0.1.13 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/path-to-regexp/-/path-to-regexp-0.1.13.tgz)<br>[2](https://registry.npmjs.org/path-to-regexp) |
| package:npm/proxy-addr@2.0.8 | package | proxy-addr | 2.0.8 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/proxy-addr/-/proxy-addr-2.0.8.tgz)<br>[2](https://registry.npmjs.org/proxy-addr) |
| package:npm/qs@6.16.0 | package | qs | 6.16.0 | BSD-3-Clause | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/qs/-/qs-6.16.0.tgz)<br>[2](https://registry.npmjs.org/qs) |
| package:npm/range-parser@1.2.1 | package | range-parser | 1.2.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/range-parser/-/range-parser-1.2.1.tgz)<br>[2](https://registry.npmjs.org/range-parser) |
| package:npm/raw-body@2.5.3 | package | raw-body | 2.5.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/raw-body/-/raw-body-2.5.3.tgz)<br>[2](https://registry.npmjs.org/raw-body) |
| package:npm/safe-buffer@5.2.1 | package | safe-buffer | 5.2.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/safe-buffer/-/safe-buffer-5.2.1.tgz)<br>[2](https://registry.npmjs.org/safe-buffer) |
| package:npm/safer-buffer@2.1.2 | package | safer-buffer | 2.1.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/safer-buffer/-/safer-buffer-2.1.2.tgz)<br>[2](https://registry.npmjs.org/safer-buffer) |
| package:npm/send@0.19.2 | package | send | 0.19.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/send/-/send-0.19.2.tgz)<br>[2](https://registry.npmjs.org/send) |
| package:npm/serve-static@1.16.3 | package | serve-static | 1.16.3 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/serve-static/-/serve-static-1.16.3.tgz)<br>[2](https://registry.npmjs.org/serve-static) |
| package:npm/setprototypeof@1.2.0 | package | setprototypeof | 1.2.0 | ISC | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/setprototypeof/-/setprototypeof-1.2.0.tgz)<br>[2](https://registry.npmjs.org/setprototypeof) |
| package:npm/side-channel-list@1.0.1 | package | side-channel-list | 1.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/side-channel-list/-/side-channel-list-1.0.1.tgz)<br>[2](https://registry.npmjs.org/side-channel-list) |
| package:npm/side-channel-map@1.0.1 | package | side-channel-map | 1.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/side-channel-map/-/side-channel-map-1.0.1.tgz)<br>[2](https://registry.npmjs.org/side-channel-map) |
| package:npm/side-channel-weakmap@1.0.2 | package | side-channel-weakmap | 1.0.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/side-channel-weakmap/-/side-channel-weakmap-1.0.2.tgz)<br>[2](https://registry.npmjs.org/side-channel-weakmap) |
| package:npm/side-channel@1.1.1 | package | side-channel | 1.1.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/side-channel/-/side-channel-1.1.1.tgz)<br>[2](https://registry.npmjs.org/side-channel) |
| package:npm/statuses@2.0.2 | package | statuses | 2.0.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/statuses/-/statuses-2.0.2.tgz)<br>[2](https://registry.npmjs.org/statuses) |
| package:npm/toidentifier@1.0.1 | package | toidentifier | 1.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/toidentifier/-/toidentifier-1.0.1.tgz)<br>[2](https://registry.npmjs.org/toidentifier) |
| package:npm/type-is@1.6.18 | package | type-is | 1.6.18 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/type-is/-/type-is-1.6.18.tgz)<br>[2](https://registry.npmjs.org/type-is) |
| package:npm/unpipe@1.0.0 | package | unpipe | 1.0.0 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/unpipe/-/unpipe-1.0.0.tgz)<br>[2](https://registry.npmjs.org/unpipe) |
| package:npm/utils-merge@1.0.1 | package | utils-merge | 1.0.1 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/utils-merge/-/utils-merge-1.0.1.tgz)<br>[2](https://registry.npmjs.org/utils-merge) |
| package:npm/vary@1.1.2 | package | vary | 1.1.2 | MIT | 1 | 宽松许可 | B | [1](https://registry.npmjs.org/vary/-/vary-1.1.2.tgz)<br>[2](https://registry.npmjs.org/vary) |
| package:pypi/flask@3.0.0 | package | flask | 3.0.0 | - | 待人工确认 | 未知 / 待人工确认 | C | [1](https://pypi.org/pypi/flask/json) |
| package:pypi/requests@2.31.0 | package | requests | 2.31.0 | - | 待人工确认 | 未知 / 待人工确认 | C | [1](https://pypi.org/pypi/requests/json) |

## 待人工确认

未发现无法识别的许可证片段。

## 血缘边统计

_无数据_

- 通用依赖关系边（depends_on）：已移除。

## 免责声明

本报告是基于结构化证据的辅助审计结果，不构成法律意见。
