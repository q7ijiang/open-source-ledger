# -*- coding: utf-8 -*-
"""模块 4：AI 许可证规则库（license_db.py）。

负责人：B（算法核心）
对应任务：基础部分 · 模块 4（截止 2026-09-23）

功能：
1. 内置 24 种常见开源 / AI 专用许可证的 P/D/P 三元组
   （Permission 许可 / Duty 义务 / Prohibition 禁止）；
2. 支持 Llama-2-Community、OpenRAIL-M、Gemma 等非 SPDX 的 AI 专用许可证；
3. 对任意许可证名称做归一化（别名 / 大小写 / 常见变体），
   并兼容 Debian copyright 的 ';' 分隔复合表达式（取最严格项）；
4. 判断许可证变更方向（宽松 -> 严格 / 严格 -> 宽松 / 同级不变）；
5. 通过命令行可列出、查询、比较、导出规则库。

用法：
    python license_db.py --list                 # 列出全部规则
    python license_db.py --show MIT             # 查看单个许可证
    python license_db.py --compare MIT GPL-3.0  # 比较两个许可证的风险方向
    python license_db.py --export licenses.json # 导出规则库 JSON

所有字段与 docs/接口约定.md 保持一致；本模块不涉及网络请求。
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------- 数据结构

@dataclass(frozen=True)
class LicenseRule:
    """一条许可证规则：P/D/P 三元组 + 风险等级。

    risk_level 为 1（最宽松）到 5（最严格）的等级：
      1 = 公有领域 / 宽松许可；2 = 宽松 + 额外义务（署名、专利授权）；
      3 = 弱 copyleft / 带使用限制的 AI 许可；4 = 强 copyleft / AI 商用受限；
      5 = 网络 copyleft（AGPL）。
    """

    canonical_id: str            # 规范化许可证标识（尽量贴近 SPDX 或官方名称）
    name_zh: str                 # 中文名称
    category: str                # permissive / weak_copyleft / strong_copyleft /
                                 # network_copyleft / public_domain / ai_restricted
    permissions: tuple = field(default_factory=tuple)   # 许可（允许做的事）
    duties: tuple = field(default_factory=tuple)        # 义务（必须做的事）
    prohibitions: tuple = field(default_factory=tuple)  # 禁止（不能做的事）
    risk_level: int = 3
    is_ai_license: bool = False  # 是否为 AI 专用许可证（非 SPDX）
    spdx_like: bool = True       # 是否近似 SPDX 标识
    note: str = ""               # 补充说明（如 Hugging Face 卡片上的别名）


# ---------------------------------------------------------------- 规则库（24 种）

# 每种规则按官方许可文本提炼 P/D/P 三元组；AI 许可证条款以官方公开文本为准。
LICENSE_DB: dict[str, LicenseRule] = {
    # ---- 宽松许可（Permissive）----
    "MIT": LicenseRule(
        canonical_id="MIT",
        name_zh="MIT 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用", "再许可"),
        duties=("保留版权声明", "附带许可证全文"),
        prohibitions=(),
        risk_level=1,
    ),
    "Apache-2.0": LicenseRule(
        canonical_id="Apache-2.0",
        name_zh="Apache 2.0 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用", "再许可", "专利授权"),
        duties=("附带许可证全文", "保留 NOTICE 文件", "修改文件需显著声明变更"),
        prohibitions=("不得使用贡献者商标", "专利诉讼反制条款", "不得附加额外限制"),
        risk_level=2,
    ),
    "BSD-3-Clause": LicenseRule(
        canonical_id="BSD-3-Clause",
        name_zh="BSD 3-Clause 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留版权声明", "保留免责声明"),
        prohibitions=("未经书面许可不得用作者名义背书衍生品",),
        risk_level=1,
    ),
    "BSD-2-Clause": LicenseRule(
        canonical_id="BSD-2-Clause",
        name_zh="BSD 2-Clause 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留版权声明", "保留免责声明"),
        prohibitions=(),
        risk_level=1,
    ),
    "BSD-4-Clause": LicenseRule(
        canonical_id="BSD-4-Clause",
        name_zh="BSD 4-Clause 许可证（含广告条款）",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留版权声明", "保留免责声明", "广告材料须致谢"),
        prohibitions=("未经书面许可不得用作者名义背书衍生品",),
        risk_level=2,
        note="含原版 BSD 广告条款，Debian 常写作 BSD-4-Clause",
    ),
    "ISC": LicenseRule(
        canonical_id="ISC",
        name_zh="ISC 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留版权声明", "附带许可证全文"),
        prohibitions=(),
        risk_level=1,
    ),
    "Artistic-2.0": LicenseRule(
        canonical_id="Artistic-2.0",
        name_zh="Artistic 2.0 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用", "再许可"),
        duties=("保留版权声明", "分发修改版需提供标准版或补丁", "附带许可证全文"),
        prohibitions=(),
        risk_level=2,
        note="Perl 社区常用；Debian 的 artistic/artistic-dist 标注近似归入此类",
    ),
    "Unicode-3.0": LicenseRule(
        canonical_id="Unicode-3.0",
        name_zh="Unicode 3.0 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留版权声明", "保留许可条款"),
        prohibitions=("不得宣称作品为 Unicode 标准组织出品",),
        risk_level=2,
    ),
    "Zlib": LicenseRule(
        canonical_id="Zlib",
        name_zh="zlib 许可证",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留版权声明", "保留原始通知"),
        prohibitions=("不得谎称修改版为原始版本",),
        risk_level=1,
    ),
    # ---- 公有领域 ----
    "CC0-1.0": LicenseRule(
        canonical_id="CC0-1.0",
        name_zh="CC0 1.0 公有领域贡献",
        category="public_domain",
        permissions=("商用", "修改", "分发", "私人使用", "无需署名"),
        duties=(),
        prohibitions=(),
        risk_level=1,
    ),
    "Public-Domain": LicenseRule(
        canonical_id="Public-Domain",
        name_zh="公有领域标注（Debian）",
        category="public_domain",
        permissions=("商用", "修改", "分发", "私人使用", "无需署名"),
        duties=(),
        prohibitions=(),
        risk_level=1,
        spdx_like=False,
        note="Debian copyright 中的公有领域标注（public-domain / PD / probably-PD 等），非正式许可证文本",
    ),
    "Permissive": LicenseRule(
        canonical_id="Permissive",
        name_zh="宽松许可标注（Debian）",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("具体条款以源文件为准",),
        prohibitions=(),
        risk_level=2,
        spdx_like=False,
        note="Debian 中的宽松类标注（permissive / __AUTO_PERMISSIVE__ / FSFUL 等），无统一许可证文本",
    ),
    # ---- 数据集许可（Creative Commons）----
    "CC-BY-4.0": LicenseRule(
        canonical_id="CC-BY-4.0",
        name_zh="知识共享署名 4.0（数据集常用）",
        category="dataset",
        permissions=("商用", "修改", "分发", "私人使用", "再许可"),
        duties=("保留署名", "附带许可证链接", "标明修改"),
        prohibitions=(),
        risk_level=2,
        note="署名（Attribution）许可，训练数据集常见；Hugging Face 数据集卡片常写作 cc-by-4.0",
    ),
    "CC-BY-NC-4.0": LicenseRule(
        canonical_id="CC-BY-NC-4.0",
        name_zh="知识共享署名-非商业 4.0（数据集常用）",
        category="dataset",
        permissions=("修改", "分发", "私人使用"),
        duties=("保留署名", "附带许可证链接", "标明修改"),
        prohibitions=("不得用于商业用途",),
        risk_level=3,
        note="署名-非商业许可，禁止商用；Hugging Face 数据集卡片常写作 cc-by-nc-4.0",
    ),
    # ---- 弱 copyleft ----
    "MPL-2.0": LicenseRule(
        canonical_id="MPL-2.0",
        name_zh="Mozilla Public License 2.0",
        category="weak_copyleft",
        permissions=("商用", "修改", "分发", "私人使用", "再许可", "专利授权"),
        duties=("MPL 文件源码需可获取", "保留许可证文本", "修改文件需记录变更"),
        prohibitions=("不得使用贡献者商标",),
        risk_level=3,
    ),
    "LGPL-2.0-only": LicenseRule(
        canonical_id="LGPL-2.0-only",
        name_zh="GNU LGPL 2.0 仅本版本",
        category="weak_copyleft",
        permissions=("商用", "修改", "分发", "私人使用", "动态链接"),
        duties=("保留许可证文本", "修改库需提供源码", "提供可重链接的目标文件"),
        prohibitions=(),
        risk_level=3,
        note="已被 LGPL-2.1 取代，条款基本相同",
    ),
    "LGPL-2.1-only": LicenseRule(
        canonical_id="LGPL-2.1-only",
        name_zh="GNU LGPL 2.1 仅本版本",
        category="weak_copyleft",
        permissions=("商用", "修改", "分发", "私人使用", "动态链接"),
        duties=("保留许可证文本", "修改库需提供源码", "提供可重链接的目标文件"),
        prohibitions=(),
        risk_level=3,
    ),
    "LGPL-3.0-only": LicenseRule(
        canonical_id="LGPL-3.0-only",
        name_zh="GNU LGPL 3.0 仅本版本",
        category="weak_copyleft",
        permissions=("商用", "修改", "分发", "私人使用", "动态链接", "专利授权"),
        duties=("保留许可证文本", "修改库需提供源码", "提供可重链接的目标文件"),
        prohibitions=(),
        risk_level=3,
    ),
    # ---- 强 copyleft ----
    "GPL-1.0-only": LicenseRule(
        canonical_id="GPL-1.0-only",
        name_zh="GNU GPL 1.0 仅本版本",
        category="strong_copyleft",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("衍生作品必须以 GPL 开源", "提供完整源码", "保留许可证文本"),
        prohibitions=(),
        risk_level=4,
        note="Debian 版权文件中的 GPL-1.0 标注",
    ),
    "GPL-2.0-only": LicenseRule(
        canonical_id="GPL-2.0-only",
        name_zh="GNU GPL 2.0 仅本版本",
        category="strong_copyleft",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("衍生作品必须以 GPL 开源", "提供完整源码", "保留许可证文本", "记录变更"),
        prohibitions=("不得附加额外限制",),
        risk_level=4,
    ),
    "GPL-3.0-only": LicenseRule(
        canonical_id="GPL-3.0-only",
        name_zh="GNU GPL 3.0 仅本版本",
        category="strong_copyleft",
        permissions=("商用", "修改", "分发", "私人使用", "专利授权"),
        duties=("衍生作品必须以 GPL 开源", "提供完整源码", "保留许可证文本", "记录变更"),
        prohibitions=("不得附加额外限制", "禁止 tivoization（硬件锁定）"),
        risk_level=4,
    ),
    "AGPL-3.0-only": LicenseRule(
        canonical_id="AGPL-3.0-only",
        name_zh="GNU AGPL 3.0 仅本版本",
        category="network_copyleft",
        permissions=("商用", "修改", "分发", "私人使用", "专利授权"),
        duties=("衍生作品必须以 AGPL 开源", "提供完整源码", "网络提供服务需披露源码"),
        prohibitions=("不得附加额外限制",),
        risk_level=5,
    ),
    # ---- 文档 copyleft（GFDL）----
    "GFDL-1.3-only": LicenseRule(
        canonical_id="GFDL-1.3-only",
        name_zh="GNU 自由文档许可证 1.3",
        category="weak_copyleft",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("衍生文档必须以 GFDL 分发", "保留不可变章节与封面文本", "附带许可证全文"),
        prohibitions=("不得使用 DRM 限制副本",),
        risk_level=3,
        note="文档类 copyleft；Debian 的 GFDL-1.2/1.3 与 no-invariant 变体近似归入此类",
    ),
    # ---- AI 专用许可证（非 SPDX）----
    "Llama-2-Community-License": LicenseRule(
        canonical_id="Llama-2-Community-License",
        name_zh="Llama 2 社区许可证",
        category="ai_restricted",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留许可证文本", "附带归属声明", "遵守可接受使用政策", "衍生作品保留相同许可证"),
        prohibitions=(
            "禁止使用模型输出训练其他大语言模型",
            "月活用户超过 7 亿需 Meta 书面许可",
            "不得谎称作品为 Meta 出品",
        ),
        risk_level=4,
        is_ai_license=True,
        spdx_like=False,
        note="Hugging Face 模型卡片上常写作 llama2",
    ),
    "OpenRAIL-M": LicenseRule(
        canonical_id="OpenRAIL-M",
        name_zh="OpenRAIL-M 许可证（BigScience）",
        category="ai_restricted",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留许可证文本", "保留归属声明", "衍生分发需附带相同使用限制"),
        prohibitions=("禁止用于违法或有害用途", "不得错误陈述模型能力或来源"),
        risk_level=3,
        is_ai_license=True,
        spdx_like=False,
        note="Open Responsible AI License，面向模型/权重",
    ),
    "Gemma-Terms-of-Use": LicenseRule(
        canonical_id="Gemma-Terms-of-Use",
        name_zh="Gemma 使用条款（Google）",
        category="ai_restricted",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("遵守使用政策（禁止生成/分发有害内容）", "保留相关通知"),
        prohibitions=(
            "禁止使用模型输出训练其他模型",
            "禁止用于受限高风险场景（如未经评估的医疗/金融决策）",
            "不得使用 Google 商标",
        ),
        risk_level=4,
        is_ai_license=True,
        spdx_like=False,
        note="非许可证文本，属使用条款；Hugging Face 卡片写作 gemma",
    ),
    # ---- Creative Commons（数据集 / 文档场景）----
    "CC-BY-4.0": LicenseRule(
        canonical_id="CC-BY-4.0",
        name_zh="知识共享 署名 4.0",
        category="permissive",
        permissions=("商用", "修改", "分发", "私人使用"),
        duties=("保留署名", "附许可证链接", "标注修改"),
        prohibitions=(),
        risk_level=1,
    ),
    "CC-BY-NC-4.0": LicenseRule(
        canonical_id="CC-BY-NC-4.0",
        name_zh="知识共享 署名-非商业 4.0",
        category="ai_restricted",
        permissions=("修改", "分发", "私人使用"),
        duties=("保留署名", "附许可证链接", "标注修改"),
        prohibitions=("禁止商业使用",),
        risk_level=3,
        note="数据集场景常见；非商业限制使基于其训练/衍生产品的商业化受限",
    ),
}

# 别名 / 常见变体 -> 规范化标识。大小写、空白已在 normalize_license 中预处理。
LICENSE_ALIASES: dict[str, str] = {
    # MIT 家族
    "mit": "MIT",
    "expat": "MIT",
    "mit/x11": "MIT",
    "x11": "MIT",
    # Apache 家族
    "apache-2.0": "Apache-2.0",
    "apache-2": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache2": "Apache-2.0",
    # BSD 家族
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "bsd3": "BSD-3-Clause",
    "new bsd": "BSD-3-Clause",
    "bsd-3-clause-generic": "BSD-3-Clause",
    "bsd-3-clause-with-weird-numbering": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "bsd2": "BSD-2-Clause",
    "bsd-4-clause": "BSD-4-Clause",
    "bsd 4-clause": "BSD-4-Clause",
    "bsd4": "BSD-4-Clause",
    "bsd-4-clause-powerdog": "BSD-4-Clause",
    "bsd-variant": "Permissive",
    # 其他宽松
    "isc": "ISC",
    "isc+ibm": "ISC",
    "zlib": "Zlib",
    "libpng": "Zlib",
    "artistic": "Artistic-2.0",
    "artistic-1.0": "Artistic-2.0",
    "artistic-2": "Artistic-2.0",
    "artistic-2.0": "Artistic-2.0",
    "artistic-dist": "Artistic-2.0",
    "unicode": "Unicode-3.0",
    "unicode-3.0": "Unicode-3.0",
    # 公有领域标记（非许可证文本，按低风险处理）
    "cc0": "CC0-1.0",
    "cc0-1.0": "CC0-1.0",
    # Creative Commons（别名合并：dev-B 与 main 取并集去重）
    "cc-by-4.0": "CC-BY-4.0",
    "cc by 4.0": "CC-BY-4.0",
    "cc-by": "CC-BY-4.0",
    "creative commons attribution 4.0": "CC-BY-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0",
    "cc by-nc 4.0": "CC-BY-NC-4.0",
    "cc-by-nc": "CC-BY-NC-4.0",
    "public-domain": "Public-Domain",
    "public domain": "Public-Domain",
    "pd": "Public-Domain",
    "probably-pd": "Public-Domain",
    "public-domain-s-s-d": "Public-Domain",
    "public-domain-md5": "Public-Domain",
    "pd-debian": "Public-Domain",
    "sdbm-public-domain": "Public-Domain",
    # Debian 宽松类标注（无统一许可证文本，按宽松低风险处理）
    "permissive": "Permissive",
    "permissive-fsf": "Permissive",
    "permissive-nowarranty": "Permissive",
    "permissive-makefile-in": "Permissive",
    "permissive-autoconf-m4-no-warranty": "Permissive",
    "permissive-autoconf-m4": "Permissive",
    "permissive-configure": "Permissive",
    "permissive-like-automake-output": "Permissive",
    "__auto_permissive__": "Permissive",
    "all-permissive": "Permissive",
    "free software": "Permissive",
    "freesoftware": "Permissive",
    "fsfullr": "Permissive",
    "fsful": "Permissive",
    "fsf-manpages": "Permissive",
    "regcomp": "Permissive",
    "g10-permissive": "Permissive",
    "tinyscheme": "Permissive",
    "bzip": "Permissive",
    # 弱 copyleft
    "mpl-2.0": "MPL-2.0",
    "mpl 2.0": "MPL-2.0",
    "lgpl-2.0": "LGPL-2.0-only",
    "lgpl-2.0-only": "LGPL-2.0-only",
    "lgpl2.0": "LGPL-2.0-only",
    "lgpl-2.1": "LGPL-2.1-only",
    "lgpl-2.1-only": "LGPL-2.1-only",
    "lgpl-2.1+": "LGPL-2.1-only",
    "lgplv2.1": "LGPL-2.1-only",
    "lgpl-3.0": "LGPL-3.0-only",
    "lgpl-3.0-only": "LGPL-3.0-only",
    "lgplv3": "LGPL-3.0-only",
    "lgplv3+": "LGPL-3.0-only",
    # 文档 copyleft（GFDL）
    "gfdl": "GFDL-1.3-only",
    "gfdl-1.2": "GFDL-1.3-only",
    "gfdl-1.2+": "GFDL-1.3-only",
    "gfdl-1.3": "GFDL-1.3-only",
    "gfdl-1.3+": "GFDL-1.3-only",
    "gfdl-1.3+-no-invariant": "GFDL-1.3-only",
    "gfdl-3": "GFDL-1.3-only",
    # 强 copyleft
    "gpl-1.0": "GPL-1.0-only",
    "gpl-1.0-only": "GPL-1.0-only",
    "gplv1": "GPL-1.0-only",
    "gpl 1.0": "GPL-1.0-only",
    "gpl-1": "GPL-1.0-only",
    "gpl-2.0": "GPL-2.0-only",
    "gpl-2.0-only": "GPL-2.0-only",
    "gpl v2": "GPL-2.0-only",
    "gplv2": "GPL-2.0-only",
    "gpl-2.0+": "GPL-2.0-only",
    "gpl v2 or later": "GPL-2.0-only",
    "gpl-2.0-or-later": "GPL-2.0-only",
    "gpl-2": "GPL-2.0-only",
    "gpl-2.0-with-autoconf-exception": "GPL-2.0-only",
    "gpl-2+-autoconf-exception": "GPL-2.0-only",
    "gpl-2+ with distribution exception": "GPL-2.0-only",
    "gpl-2.0-with-bison-exception": "GPL-2.0-only",
    "gpl-2+-libtool-exception": "GPL-2.0-only",
    "gpl-2-with-linux-syscall-note-exception": "GPL-2.0-only",
    "gpl-2-with-linux-syscall-note": "GPL-2.0-only",
    "gpl-3.0": "GPL-3.0-only",
    "gpl-3.0-only": "GPL-3.0-only",
    "gpl v3": "GPL-3.0-only",
    "gplv3": "GPL-3.0-only",
    "gpl-3": "GPL-3.0-only",
    "gpl-3.0+": "GPL-3.0-only",
    "gpl v3 or later": "GPL-3.0-only",
    "gpl-3.0-or-later": "GPL-3.0-only",
    "gpl-3.0-with-autoconf-exception": "GPL-3.0-only",
    "gpl-3+-autoconf-exception": "GPL-3.0-only",
    "agpl-3.0": "AGPL-3.0-only",
    "agpl-3.0-only": "AGPL-3.0-only",
    "agplv3": "AGPL-3.0-only",
    "agpl v3": "AGPL-3.0-only",
    # AI 专用
    "llama2": "Llama-2-Community-License",
    "llama-2": "Llama-2-Community-License",
    "llama 2 community license": "Llama-2-Community-License",
    "llama-2-community": "Llama-2-Community-License",
    "openrail-m": "OpenRAIL-M",
    "openrail": "OpenRAIL-M",
    "openrail m": "OpenRAIL-M",
    "openrail-m license": "OpenRAIL-M",
    "gemma": "Gemma-Terms-of-Use",
    "gemma license": "Gemma-Terms-of-Use",
    "gemma terms of use": "Gemma-Terms-of-Use",
}

# 自动注册：每个 canonical_id 本身必须能解析回自己（含连字符等写法），
# 避免 get_rule(canonical_id) 因模糊匹配失败而返回 None。
for _canonical_id in list(LICENSE_DB):
    LICENSE_ALIASES.setdefault(_canonical_id.lower(), _canonical_id)

CATEGORY_ZH = {
    "permissive": "宽松许可",
    "public_domain": "公有领域",
    "weak_copyleft": "弱 copyleft",
    "strong_copyleft": "强 copyleft",
    "network_copyleft": "网络 copyleft",
    "dataset": "数据集许可",
    "ai_restricted": "AI 专用（受限）",
    "unknown": "未知 / 待人工确认",
}

# ---------------------------------------------------------------- 归一化


def normalize_license(name) -> str | None:
    """把任意许可证写法归一化为规则库中的 canonical_id。

    返回 None 表示规则库中没有匹配项（应标为"待人工确认"）。
    """
    if name is None:
        return None
    if not isinstance(name, str):
        name = str(name)
    key = re.sub(r"\s+", " ", name.strip()).lower()
    if not key:
        return None
    if key in LICENSE_ALIASES:
        return LICENSE_ALIASES[key]
    # 兜底：去掉常见前缀/后缀后再次匹配（同时支持空格与连字符形式）
    stripped = re.sub(r"^(the |gnu )", "", key)
    stripped = re.sub(
        r"( license| licence| terms of use|-license|-licence|-v|-only|-or-later|-2\.0|-3\.0|-2\.1|-4\.0)$",
        "",
        stripped,
    )
    # GPL 例外条款结构：gpl-2 with xxx exception -> gpl-2
    stripped = re.sub(r"\s+with\s+.+?\s+exception$", "", stripped)
    stripped = stripped.strip()
    if stripped and stripped in LICENSE_ALIASES:
        return LICENSE_ALIASES[stripped]
    return None


def split_license_text(license_text: str | None) -> list[str]:
    """把可能由 ';' / ' AND ' / ' OR ' / ',' 连接的许可证表达式拆成单项。

    注意 "GPL v2 or later" 中的 "or later" 不会被拆开。
    """
    if not license_text:
        return []
    parts = re.split(
        r"[;,]\s*|\s+(?:AND|OR)\s+(?!later\b|earlier\b)|\s+and\s+|\s+or\s+(?!later\b|earlier\b)",
        license_text.strip(),
    )
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------- 查询接口


def get_rule(name) -> LicenseRule | None:
    """获取某许可证的规则；未知许可证返回 None。

    对 ';' / ' AND ' / ' OR ' 连接的复合表达式（Debian copyright 常见），
    返回其中最严格（risk_level 最高）的已识别项规则。
    """
    canonical = normalize_license(name)
    if canonical is not None:
        return LICENSE_DB.get(canonical)
    # 复合表达式：取最严的已识别项（每项不含分隔符，递归终止）
    parts = split_license_text(name)
    if len(parts) <= 1:
        return None
    best = None
    for part in parts:
        rule = get_rule(part)
        if rule is None:
            continue
        if best is None or rule.risk_level > best.risk_level:
            best = rule
    return best


def get_triplets(name) -> dict | None:
    """返回 P/D/P 三元组（含类别、风险等级）。"""
    rule = get_rule(name)
    if rule is None:
        return None
    return {
        "canonical_id": rule.canonical_id,
        "name_zh": rule.name_zh,
        "category": rule.category,
        "category_zh": CATEGORY_ZH[rule.category],
        "permissions": list(rule.permissions),
        "duties": list(rule.duties),
        "prohibitions": list(rule.prohibitions),
        "risk_level": rule.risk_level,
        "is_ai_license": rule.is_ai_license,
        "note": rule.note,
    }


def classify(name) -> str:
    """返回风险类别（permissive / weak_copyleft / ... / unknown）。"""
    rule = get_rule(name)
    return rule.category if rule else "unknown"


def risk_level(name) -> int | None:
    """返回风险等级 1–5；未知许可证返回 None。"""
    rule = get_rule(name)
    return rule.risk_level if rule else None


def is_ai_license(name) -> bool:
    """判断是否为 AI 专用许可证（复合表达式中任一项命中即 True）。"""
    rule = get_rule(name)
    if rule is not None and rule.is_ai_license:
        return True
    for part in split_license_text(name):
        item = get_rule(part)
        if item is not None and item.is_ai_license:
            return True
    return False


def evaluate_expression(license_text: str | None) -> dict:
    """评估一个可能包含多项许可证的字段。

    返回：{
        "items": [{canonical_id, risk_level, category, known}, ...],
        "max_risk_level": int|None,     # 取最严格项
        "worst_category": str,          # 取风险最高的类别
        "unknown_items": [...],         # 未识别项
    }
    """
    items = []
    max_level = None
    worst_category = "unknown"
    unknown_items = []
    for part in split_license_text(license_text):
        rule = get_rule(part)
        if rule is None:
            unknown_items.append(part)
            items.append({
                "canonical_id": None,
                "raw": part,
                "risk_level": None,
                "category": "unknown",
                "known": False,
            })
            continue
        items.append({
            "canonical_id": rule.canonical_id,
            "raw": part,
            "risk_level": rule.risk_level,
            "category": rule.category,
            "known": True,
        })
        if max_level is None or rule.risk_level > max_level:
            max_level = rule.risk_level
            worst_category = rule.category
    return {
        "items": items,
        "max_risk_level": max_level,
        "worst_category": worst_category,
        "unknown_items": unknown_items,
    }


# ---------------------------------------------------------------- 变更方向判断


def compare_direction(old_license: str | None, new_license: str | None) -> dict:
    """判断许可证变更方向（宽松 -> 严格 等）。

    返回：{
        "old": {"raw", "canonical", "risk_level", "category"},
        "new": {...},
        "direction": "宽松→严格" | "严格→宽松" | "同级不变" | "未知" | "新增许可证" | "许可证移除",
        "risk_increased": bool,   # 严格方向变严（含新增）
        "ai_involved": bool,      # 任一侧涉及 AI 专用许可证
    }
    """
    old_eval = evaluate_expression(old_license)
    new_eval = evaluate_expression(new_license)
    old_level = old_eval["max_risk_level"]
    new_level = new_eval["max_risk_level"]

    def _any_ai(items):
        for item in items:
            if not item["known"]:
                continue
            rule = get_rule(item["canonical_id"])
            if rule is not None and rule.is_ai_license:
                return True
        return False

    old_ai = _any_ai(old_eval["items"])
    new_ai = _any_ai(new_eval["items"])

    if old_level is None and new_level is None:
        direction = "未知"
        risk_increased = False
    elif old_level is None:
        direction = "新增许可证"
        risk_increased = True
    elif new_level is None:
        direction = "许可证移除"
        risk_increased = False
    elif new_level > old_level:
        direction = "宽松→严格"
        risk_increased = True
    elif new_level < old_level:
        direction = "严格→宽松"
        risk_increased = False
    else:
        direction = "同级不变"
        risk_increased = False

    return {
        "old": {
            "raw": old_license,
            "canonical_ids": [i["canonical_id"] for i in old_eval["items"]],
            "risk_level": old_level,
            "category": old_eval["worst_category"],
            "unknown_items": old_eval["unknown_items"],
        },
        "new": {
            "raw": new_license,
            "canonical_ids": [i["canonical_id"] for i in new_eval["items"]],
            "risk_level": new_level,
            "category": new_eval["worst_category"],
            "unknown_items": new_eval["unknown_items"],
        },
        "direction": direction,
        "risk_increased": risk_increased,
        "ai_involved": old_ai or new_ai,
    }


# ---------------------------------------------------------------- 导出 / CLI


def export_db() -> dict:
    """导出规则库为纯 JSON 结构（供中文清单 / 增强层报告引用）。"""
    return {
        "module": "license_db",
        "version": "0.2",
        "count": len(LICENSE_DB),
        "categories": CATEGORY_ZH,
        "rules": {
            cid: get_triplets(cid) for cid in sorted(LICENSE_DB)
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI 许可证规则库（模块 4）")
    parser.add_argument("--list", action="store_true", help="列出全部许可证规则")
    parser.add_argument("--show", metavar="LICENSE", help="查看单个许可证的 P/D/P")
    parser.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"),
                        help="比较两个许可证的风险方向")
    parser.add_argument("--export", metavar="OUT.json", help="导出规则库 JSON")
    args = parser.parse_args(argv)

    if args.list:
        print(f"{'canonical_id':<28}{'类别':<12}{'风险':<6}{'AI专用':<8}说明")
        for cid in sorted(LICENSE_DB):
            rule = LICENSE_DB[cid]
            print(f"{cid:<28}{CATEGORY_ZH[rule.category]:<12}{rule.risk_level:<6}"
                  f"{'是' if rule.is_ai_license else '否':<8}{rule.name_zh}")
        return

    if args.show:
        info = get_triplets(args.show)
        if info is None:
            print(f"未识别许可证：{args.show}（建议标为『待人工确认』）")
            return
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    if args.compare:
        result = compare_direction(args.compare[0], args.compare[1])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.export:
        target = Path(args.export)
        target.write_text(
            json.dumps(export_db(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"已导出 {len(LICENSE_DB)} 条规则到 {target}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
