# -*- coding: utf-8 -*-
"""--diff 报告"对比区间"渲染回归测试。

要求（A/琦江）：从两个 BOM 的 metadata.timestamp 读取时间戳，格式化为
「对比区间：{t0} → {t1}」「间隔天数：N 天」；缺时间戳输出「未知」且不报错。
"""

import main as m


def test_timestamp_read_from_metadata_string():
    """metadata.timestamp 为 ISO 字符串时取日期部分。"""
    bom = {"metadata": {"timestamp": "2026-10-12T08:30:00+08:00"}}
    assert m._bom_snapshot_timestamp(bom) == "2026-10-12T08:30:00+08:00"
    assert m._format_snapshot_date(m._bom_snapshot_timestamp(bom)) == "2026-10-12"


def test_timestamp_accepts_cyclonedx_object_form():
    """CycloneDX 允许 timestamp 为对象，也要能解析。"""
    bom = {"metadata": {"timestamp": {"timestamp": "2026-10-11T10:00:00+08:00"}}}
    assert m._format_snapshot_date(m._bom_snapshot_timestamp(bom)) == "2026-10-11"


def test_timestamp_zulu_and_plain_date():
    """Z 结尾与纯日期形态都能解析。"""
    assert m._format_snapshot_date("2026-10-12T00:30:00Z") == "2026-10-12"
    assert m._format_snapshot_date("2026-10-09") == "2026-10-09"


def test_missing_or_broken_timestamp_is_unknown_without_error():
    """缺失 / 空串 / 乱码一律「未知」，不抛异常。"""
    for raw in (None, "", "not-a-date", "garbage"):
        assert m._format_snapshot_date(raw) == "未知"
    assert m._bom_snapshot_timestamp({}) is None
    assert m._bom_snapshot_timestamp({"metadata": None}) is None


def test_interval_lines_happy_path():
    """两侧都有时间戳：输出区间与间隔天数。"""
    lines = m._diff_interval_lines(
        {"metadata": {"timestamp": "2026-10-09T00:00:00+08:00"}},
        {"metadata": {"timestamp": "2026-10-12T00:00:00+08:00"}},
    )
    assert lines[0] == "> 对比区间：2026-10-09 → 2026-10-12"
    assert lines[1] == "> 间隔天数：3 天"
    assert not any("提示" in line for line in lines)


def test_interval_lines_missing_timestamp_reports_which_side():
    """缺时间戳：区间显示「未知」，并指明是哪一侧缺。"""
    lines = m._diff_interval_lines(
        {"metadata": {"timestamp": "2026-10-09T00:00:00+08:00"}},
        {},
    )
    assert lines[0] == "> 对比区间：2026-10-09 → 未知"
    assert not any("间隔天数" in line for line in lines)
    assert any("t1" in line and "缺少 metadata.timestamp" in line for line in lines)


def test_interval_lines_both_missing():
    """两侧都缺：区间「未知 → 未知」并提示 t0/t1。"""
    lines = m._diff_interval_lines({}, {})
    assert lines[0] == "> 对比区间：未知 → 未知"
    assert any("t0/t1" in line for line in lines)


def test_interval_lines_unparsable_timestamp_hint():
    """时间戳存在但无法解析：区间「未知」，提示无法解析。"""
    lines = m._diff_interval_lines(
        {"metadata": {"timestamp": "garbage"}},
        {"metadata": {"timestamp": "2026-10-12"}},
    )
    assert lines[0] == "> 对比区间：未知 → 2026-10-12"
    assert any("无法解析" in line for line in lines)


def test_render_report_includes_interval_lines():
    """interval_lines 必须出现在报告开头（生成时间之后）。"""
    import report_enhanced

    report = report_enhanced.render_report(
        [], [], "t0.json", "t1.json",
        interval_lines=["> 对比区间：2026-10-09 → 2026-10-12", "> 间隔天数：3 天"],
    )
    assert "> 对比区间：2026-10-09 → 2026-10-12" in report
    assert "> 间隔天数：3 天" in report
    lines = report.splitlines()
    assert lines.index("> 对比区间：2026-10-09 → 2026-10-12") > 2


def test_render_report_without_interval_lines_unchanged():
    """不传 interval_lines 时保持原样（向后兼容）。"""
    import report_enhanced

    report = report_enhanced.render_report([], [], "t0.json", "t1.json")
    assert "对比区间" not in report
