# -*- coding: utf-8 -*-
"""比赛版合并规则测试：覆盖 bug 修复、降级策略和受限传递。"""

from __future__ import annotations

import unittest
from typing import Any, Callable

import bom_adapter
import entity_resolver


def make_asset(
    *,
    name: str = "demo",
    asset_type: str = "package",
    version: str = "",
    purls: list[str] | None = None,
    hashes: list[dict[str, str]] | None = None,
    evidence_chain: list[dict[str, Any]] | None = None,
    marker: str = "",
) -> dict[str, Any]:
    """构造最小资产记录，避免测试依赖真实 BOM。"""

    return {
        "name": name,
        "asset_type": asset_type,
        "version": version,
        "purls": purls or [],
        "hashes": hashes or [],
        "evidence_chain": evidence_chain or [],
        "marker": marker,
    }


def url_evidence(url: str = "https://example.test/project") -> list[dict[str, Any]]:
    """构造 homepage 证据。"""

    return [
        {
            "source_field": "components[].externalReferences[]",
            "raw_value": {"type": "website", "url": url},
        }
    ]


def author_evidence(author: str = "Alice") -> list[dict[str, Any]]:
    """构造 author 证据。"""

    return [
        {
            "source_field": "components[].author",
            "raw_value": author,
        }
    ]


class MergeRuleTests(unittest.TestCase):
    """覆盖用户指定的 13 项合并规则验收用例。"""

    def test_exact_purl_coordinate_ignores_package_id_qualifier(self) -> None:
        """purl 坐标相同，package-id qualifier 不同仍应自动合并。"""

        left = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:pypi/demo@1.0?package-id=left"],
        )
        right = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:pypi/demo@1.0?package-id=right"],
        )

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "AUTO_MERGE")
        self.assertEqual(decision["reason_code"], "PURL_COORDINATE_EXACT")

    def test_pypi_names_share_normalized_coordinate(self) -> None:
        """PEP 503 下 foo_bar 与 foo-bar 应生成相同身份。"""

        entity_key_a, canonical_id_a, _ = bom_adapter.build_asset_identifiers(
            "package", "foo_bar", "1.0", ["pkg:pypi/foo_bar@1.0"]
        )
        entity_key_b, canonical_id_b, _ = bom_adapter.build_asset_identifiers(
            "package", "foo-bar", "1.0", ["pkg:pypi/foo-bar@1.0"]
        )

        self.assertEqual(entity_key_a, "package:pypi/foo-bar")
        self.assertEqual(entity_key_b, "package:pypi/foo-bar")
        self.assertEqual(canonical_id_a, "package:pypi/foo-bar@1.0")
        self.assertEqual(canonical_id_b, "package:pypi/foo-bar@1.0")

    def test_same_hash_same_version_same_coordinate_auto_merges(self) -> None:
        """同哈希、同版本、同坐标应自动合并。"""

        digest = [{"algorithm": "sha256", "value": "abc"}]
        left = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:pypi/demo@1.0"],
            hashes=digest,
        )
        right = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:pypi/demo@1.0"],
            hashes=digest,
        )

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "AUTO_MERGE")
        self.assertEqual(decision["reason_code"], "HASH_MATCH_SAME_VERSION")

    def test_same_hash_different_nonempty_version_requires_review(self) -> None:
        """同哈希但版本不同必须人工复核。"""

        digest = [{"algorithm": "sha256", "value": "abc"}]
        left = make_asset(name="demo", version="1.0", hashes=digest)
        right = make_asset(name="demo", version="2.0", hashes=digest)

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "REVIEW")
        self.assertEqual(
            decision["reason_code"], "HASH_MATCH_VERSION_MISMATCH"
        )

    def test_shared_and_conflicting_hash_requires_review(self) -> None:
        """同算法既有共享摘要又有独有摘要时，共享不能覆盖冲突。"""

        left = make_asset(
            name="demo",
            version="1.0",
            hashes=[
                {"algorithm": "sha256", "value": "shared"},
                {"algorithm": "sha256", "value": "left-only"},
            ],
        )
        right = make_asset(
            name="demo",
            version="1.0",
            hashes=[
                {"algorithm": "sha256", "value": "shared"},
                {"algorithm": "sha256", "value": "right-only"},
            ],
        )

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "REVIEW")
        self.assertEqual(decision["reason_code"], "HASH_CONFLICT")
        self.assertTrue(decision["conflicting_evidence"])

    def test_same_url_same_version_different_namespace_requires_review(self) -> None:
        """同 URL、同版本但 namespace 不同，只能人工复核。"""

        left = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:npm/@left/demo@1.0"],
            evidence_chain=url_evidence(),
        )
        right = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:npm/@right/demo@1.0"],
            evidence_chain=url_evidence(),
        )

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "REVIEW")
        self.assertEqual(decision["reason_code"], "URL_SHARED_REVIEW")

    def test_repository_reference_is_used_as_url_signal(self) -> None:
        """repository 类型外部引用必须进入 URL 信号。"""

        repository_evidence: list[dict[str, Any]] = [
            {
                "source_field": "components[].externalReferences[]",
                "raw_value": {
                    "type": "repository",
                    "url": "git+https://github.com/example/demo.git",
                },
            }
        ]
        left = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:pypi/demo@1.0"],
            evidence_chain=repository_evidence,
        )
        right = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:pypi/demo@1.0?package-id=other"],
            evidence_chain=repository_evidence,
        )

        self.assertIn(
            "https://github.com/example/demo",
            entity_resolver.extract_urls(left),
        )
        self.assertEqual(
            entity_resolver.evaluate_pair(left, right)["reason_code"],
            "PURL_COORDINATE_EXACT",
        )

    def test_empty_versions_with_same_url_require_review(self) -> None:
        """双侧版本为空时，URL 不能自动合并。"""

        left = make_asset(name="demo", evidence_chain=url_evidence())
        right = make_asset(name="demo", evidence_chain=url_evidence())

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "REVIEW")
        self.assertEqual(decision["reason_code"], "URL_SHARED_REVIEW")

    def test_author_only_different_coordinates_requires_review(self) -> None:
        """包坐标不同且只有 author 命中时，只能人工复核。"""

        left = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:npm/@left/demo@1.0"],
            evidence_chain=author_evidence(),
        )
        right = make_asset(
            name="demo",
            version="1.0",
            purls=["pkg:npm/@right/demo@1.0"],
            evidence_chain=author_evidence(),
        )

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "REVIEW")
        self.assertEqual(decision["reason_code"], "AUTHOR_SHARED_REVIEW")

    def test_no_purl_same_hash_auto_merges(self) -> None:
        """无 purl 时相同哈希仍可自动合并。"""

        digest = [{"algorithm": "sha256", "value": "abc"}]
        left = make_asset(name="demo", hashes=digest)
        right = make_asset(name="demo", hashes=digest)

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "AUTO_MERGE")
        self.assertEqual(decision["reason_code"], "HASH_MATCH_WITHOUT_PURL")

    def test_no_purl_name_version_only_is_undetermined(self) -> None:
        """无 purl 且只有 name+version 时证据不足。"""

        left = make_asset(name="demo", version="1.0")
        right = make_asset(name="demo", version="1.0")

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "UNDETERMINED")
        self.assertEqual(
            decision["reason_code"], "NO_PURL_NAME_VERSION_ONLY"
        )
        self.assertTrue(decision["note"])

    def test_no_purl_name_only_is_undetermined(self) -> None:
        """无 purl、无版本且只有 name 时证据不足。"""

        left = make_asset(name="demo")
        right = make_asset(name="demo")

        decision = entity_resolver.evaluate_pair(left, right)

        self.assertEqual(decision["status"], "UNDETERMINED")
        self.assertEqual(
            decision["reason_code"], "NAME_ONLY_OR_VERSION_MISSING"
        )
        self.assertTrue(decision["note"])

    def test_transitive_conflict_blocks_component_folding(self) -> None:
        """A-B、B-C 自动边与 A-C 冲突边共存时，不折叠整个分量。"""

        assets = [
            make_asset(name="demo", version="1.0", marker="a"),
            make_asset(name="demo", version="1.0", marker="b"),
            make_asset(name="demo", version="1.0", marker="c"),
        ]

        def fake_evaluate(
            left: dict[str, Any], right: dict[str, Any]
        ) -> dict[str, Any]:
            pair = {left["marker"], right["marker"]}
            if pair in ({"a", "b"}, {"b", "c"}):
                return entity_resolver.make_decision(
                    "AUTO_MERGE", "PURL_COORDINATE_EXACT", "测试自动边"
                )
            return entity_resolver.make_decision(
                "REVIEW",
                "HASH_CONFLICT",
                "测试冲突否决",
                conflicting_evidence=[{"signal": "hash_conflict"}],
            )

        original_evaluate: Callable[..., dict[str, Any]] = (
            entity_resolver.evaluate_pair
        )
        entity_resolver.evaluate_pair = fake_evaluate
        try:
            deduplicated, merge_log = entity_resolver.deduplicate_assets(assets)
        finally:
            entity_resolver.evaluate_pair = original_evaluate

        self.assertEqual(len(deduplicated), 3)
        self.assertEqual(
            {asset["merge_status"] for asset in deduplicated}, {"REVIEW"}
        )
        self.assertTrue(
            all(
                entry["component_auto_folded"] is False
                for entry in merge_log
            )
        )
        self.assertTrue(
            all(entry["component_conflicting_edges"] for entry in merge_log)
        )

    def test_canonical_id_is_versioned_and_entity_key_is_stable(self) -> None:
        """canonical_id 带版本，entity_key 跨版本保持稳定。"""

        entity_key_v1, canonical_id_v1, _ = (
            bom_adapter.build_asset_identifiers(
                "package", "demo", "1.0", ["pkg:pypi/demo@1.0"]
            )
        )
        entity_key_v2, canonical_id_v2, _ = (
            bom_adapter.build_asset_identifiers(
                "package", "demo", "2.0", ["pkg:pypi/demo@2.0"]
            )
        )

        self.assertEqual(entity_key_v1, "package:pypi/demo")
        self.assertEqual(entity_key_v2, "package:pypi/demo")
        self.assertEqual(canonical_id_v1, "package:pypi/demo@1.0")
        self.assertEqual(canonical_id_v2, "package:pypi/demo@2.0")
        self.assertNotEqual(canonical_id_v1, canonical_id_v2)


    def test_purl_version_is_authoritative_for_identity(self) -> None:
        """purl 版本应同时驱动 canonical_id 和配对版本判断。"""

        left = make_asset(
            name="demo",
            version="9.9",
            purls=["pkg:pypi/demo@1.0"],
        )
        right = make_asset(
            name="demo",
            version="9.9",
            purls=["pkg:pypi/demo@2.0"],
        )

        self.assertEqual(entity_resolver.effective_version(left), "1.0")
        self.assertEqual(entity_resolver.effective_version(right), "2.0")
        decision = entity_resolver.evaluate_pair(left, right)
        self.assertEqual(decision["status"], "KEEP_SEPARATE")
        self.assertEqual(decision["reason_code"], "VERSION_MISMATCH")


if __name__ == "__main__":
    unittest.main(verbosity=2)
