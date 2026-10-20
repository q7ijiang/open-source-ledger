"""证据补全只允许受支持平台的回归测试。"""

import evidence_enricher


def test_huggingface_purl_is_unsupported():
    assert evidence_enricher.parse_purl("pkg:huggingface/acme/model@main") is None


def test_huggingface_purl_never_triggers_network_request(monkeypatch):
    def unexpected_request(*args, **kwargs):
        raise AssertionError("HF purl must not trigger a remote request")

    monkeypatch.setattr(evidence_enricher, "fetch_remote_evidence", unexpected_request)
    enriched, stats = evidence_enricher.enrich_asset(
        {"purls": ["pkg:huggingface/acme/model@main"], "evidence_chain": []},
        timeout=3,
    )

    assert stats["requests"] == 0
    assert enriched["evidence_chain"][0]["source_api"] == "cyclonedx"


def test_modelscope_purl_targets_modelscope_api():
    target = evidence_enricher.parse_purl("pkg:modelscope/Qwen/Qwen2.5-0.5B-Instruct@master")

    assert target == {
        "source_api": "modelscope",
        "package_name": "Qwen/Qwen2.5-0.5B-Instruct",
        "version": "master",
        "source_url": (
            "https://www.modelscope.cn/api/v1/models/"
            "Qwen/Qwen2.5-0.5B-Instruct"
        ),
    }
