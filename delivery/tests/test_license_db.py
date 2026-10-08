# -*- coding: utf-8 -*-
"""模块 4：AI 许可证规则库回归测试。"""

import license_db as db


def test_rule_count_within_spec():
    """验收标准：覆盖 10–15 种许可证（扩展真实数据覆盖后不少于 15）。"""
    assert len(db.LICENSE_DB) >= 15


def test_every_rule_has_pdp_triplets():
    """每种许可证都含 P/D/P 三元组且风险等级在 1–5。"""
    for rule in db.LICENSE_DB.values():
        assert isinstance(rule.permissions, tuple) and len(rule.permissions) >= 1
        assert isinstance(rule.duties, tuple)
        assert isinstance(rule.prohibitions, tuple)
        assert 1 <= rule.risk_level <= 5
        assert rule.category in db.CATEGORY_ZH


def test_ai_licenses_recognized():
    """AI 专用许可证必须可识别（Llama-2 / OpenRAIL-M / Gemma）。"""
    for name in ("llama2", "Llama-2-Community-License", "openrail-m", "gemma"):
        assert db.is_ai_license(name), name
        rule = db.get_rule(name)
        assert rule is not None and rule.is_ai_license


def test_normalize_aliases():
    """常见别名与变体归一化。"""
    assert db.normalize_license("MIT/X11") == "MIT"
    assert db.normalize_license("Expat") == "MIT"
    assert db.normalize_license("Apache License 2.0") == "Apache-2.0"
    assert db.normalize_license("GPL v3 or later") == "GPL-3.0-only"
    assert db.normalize_license("LGPLv3+") == "LGPL-3.0-only"
    assert db.normalize_license("llama 2 community license") == "Llama-2-Community-License"
    # 规范化 ID 必须能解析回自身
    for canonical in db.LICENSE_DB:
        assert db.normalize_license(canonical) == canonical


def test_unknown_license_returns_none():
    """未知许可证返回 None，可标为待人工确认。"""
    assert db.normalize_license("TOTALLY-MADE-UP-LICENSE") is None
    assert db.get_rule("TOTALLY-MADE-UP-LICENSE") is None
    assert db.classify("TOTALLY-MADE-UP-LICENSE") == "unknown"
    assert db.risk_level("TOTALLY-MADE-UP-LICENSE") is None


def test_compare_direction_permissive_to_strict():
    """宽松 -> 严格方向判断。"""
    result = db.compare_direction("MIT", "GPL-3.0")
    assert result["direction"] == "宽松→严格"
    assert result["risk_increased"] is True


def test_compare_direction_strict_to_permissive():
    result = db.compare_direction("GPL-3.0", "MIT")
    assert result["direction"] == "严格→宽松"
    assert result["risk_increased"] is False


def test_compare_direction_same_level():
    result = db.compare_direction("MIT", "BSD-3-Clause")
    assert result["direction"] == "同级不变"
    assert result["risk_increased"] is False


def test_compare_direction_ai_involved():
    """AI 专用许可证参与比较时标记 ai_involved。"""
    result = db.compare_direction("llama2", "Apache-2.0")
    assert result["ai_involved"] is True
    assert result["direction"] == "严格→宽松"


def test_multi_license_expression():
    """多许可证表达式取最严格项。"""
    evaluation = db.evaluate_expression("MIT; GPL-3.0-only")
    assert evaluation["max_risk_level"] == 4
    assert evaluation["worst_category"] == "strong_copyleft"
    assert evaluation["unknown_items"] == []


def test_export_db_structure():
    """导出 JSON 结构完整。"""
    exported = db.export_db()
    assert exported["count"] == len(db.LICENSE_DB)
    assert len(exported["rules"]) == len(db.LICENSE_DB)
    rule = exported["rules"]["Llama-2-Community-License"]
    assert rule["is_ai_license"] is True
    assert set(rule.keys()) >= {"permissions", "duties", "prohibitions", "risk_level"}


def test_composite_expression_single_value_interfaces():
    """';' 分隔的复合表达式（Debian 格式）在单值接口上取最严格项。"""
    expr = "GPL-2.0; LGPL-2.0; public-domain"
    assert db.risk_level(expr) == 4
    assert db.classify(expr) == "strong_copyleft"
    rule = db.get_rule(expr)
    assert rule is not None and rule.canonical_id == "GPL-2.0-only"
    assert db.get_rule("MIT; Apache-2.0").canonical_id == "Apache-2.0"


def test_composite_expression_ai_detection():
    """复合表达式中任一项为 AI 许可证时 is_ai_license 返回 True。"""
    assert db.is_ai_license("MIT; OpenRAIL-M") is True
    assert db.is_ai_license("Apache-2.0; MIT") is False


def test_compare_direction_composite():
    """复合表达式参与变更方向判断。"""
    result = db.compare_direction("MIT; BSD-3-Clause", "GPL-2.0; GPL-3.0")
    assert result["direction"] == "宽松→严格"
    assert result["risk_increased"] is True


def test_debian_labels_and_gpl_exceptions():
    """Debian 公有领域 / 宽松标注与 GPL 例外条款可识别。"""
    assert db.get_rule("public-domain").canonical_id == "Public-Domain"
    assert db.risk_level("probably-PD") == 1
    assert db.risk_level("permissive") == 2
    assert db.risk_level("__AUTO_PERMISSIVE__") == 2
    assert db.get_rule("GPL-2.0-with-bison-exception").canonical_id == "GPL-2.0-only"
    assert db.get_rule("GPL-2 with Linux-syscall-note exception").canonical_id == "GPL-2.0-only"
    assert db.get_rule("GFDL-1.2").canonical_id == "GFDL-1.3-only"
    assert db.get_rule("BSD-2-Clause").canonical_id == "BSD-2-Clause"


def test_real_data_license_coverage():
    """A 提供的真实资产数据（data/assets_real_final.json）覆盖率 >= 90%。

    空 license 字段视为"无许可证"，不参与识别率统计。
    """
    import json
    from pathlib import Path

    assets = json.loads(Path("data/assets_real_final.json").read_text(encoding="utf-8"))
    evaluated = [a for a in assets if (a.get("license") or "").strip()]
    assert len(evaluated) > 50
    covered = [a for a in evaluated if db.get_rule(a["license"]) is not None]
    assert len(covered) / len(evaluated) >= 0.9
