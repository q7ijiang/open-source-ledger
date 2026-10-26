from __future__ import annotations

import hashlib

import modelscope_adapter


class FakeResponse:
    def __init__(self, *, payload: dict | None = None, content: bytes = b"") -> None:
        self._payload = payload
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


def test_source_bundle_uses_modelscope_http_responses(monkeypatch) -> None:
    license_text = "qwen-research 许可证\n\n该模型仅限研究用途，不得用于商业目的。\n"
    readme_text = "本模型用于研究实验。分发时请保留许可证和版权声明。\n"
    license_sha = hashlib.sha256(license_text.encode("utf-8")).hexdigest()
    calls: list[tuple[str, dict]] = []

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/models/acme/demo"):
            return FakeResponse(
                payload={
                    "Code": 200,
                    "Data": {
                        "Name": "demo",
                        "Path": "acme",
                        "Revision": "master",
                        "LicenseName": "qwen-research",
                        "ReadMeContent": readme_text,
                    },
                }
            )
        if url.endswith("/repo/files"):
            return FakeResponse(
                payload={
                    "Code": 200,
                    "Data": {
                        "Files": [
                            {
                                "Path": "LICENSE",
                                "Type": "blob",
                                "Sha256": license_sha,
                                "Size": len(license_text.encode("utf-8")),
                            }
                        ]
                    },
                }
            )
        if url.endswith("/repo"):
            file_path = kwargs["params"]["FilePath"]
            content = license_text.encode("utf-8") if file_path == "LICENSE" else b""
            return FakeResponse(content=content)
        if url.endswith("/lineage"):
            return FakeResponse(payload={"Code": 200, "Data": None})
        raise AssertionError(url)

    monkeypatch.setattr(modelscope_adapter.requests, "get", fake_get)
    bundle = modelscope_adapter.fetch_source_bundle("acme", "demo")

    assert bundle["model_id"] == "acme/demo"
    assert bundle["facts"]["license"]["value"] == "qwen-research"
    assert {document["path"] for document in bundle["documents"]} == {"LICENSE", "README.md"}
    license_doc = next(item for item in bundle["documents"] if item["path"] == "LICENSE")
    assert license_doc["sha256"] == license_sha
    assert license_doc["evidence_level"] == "A"
    assert bundle["facts"]["files"][0]["sha256_match"] is True
    assert not bundle["warnings"]
    assert len(calls) == 4


def test_source_bundle_ignores_unsafe_file_paths(monkeypatch) -> None:
    def fake_get(url: str, **kwargs):
        if url.endswith("/models/acme/demo"):
            return FakeResponse(payload={"Data": {"Name": "demo", "Path": "acme"}})
        if url.endswith("/repo/files"):
            return FakeResponse(
                payload={"Data": {"Files": [{"Path": "../LICENSE"}, {"Path": "README.md"}]}}
            )
        if url.endswith("/repo"):
            return FakeResponse(content=b"official readme")
        if url.endswith("/lineage"):
            return FakeResponse(payload={"Data": None})
        raise AssertionError(url)

    monkeypatch.setattr(modelscope_adapter.requests, "get", fake_get)
    bundle = modelscope_adapter.fetch_source_bundle("acme", "demo")

    assert all(".." not in document["path"] for document in bundle["documents"])


def test_source_document_priority_prefers_license_and_readme() -> None:
    paths = ["config/model.json", "docs/guide.md", "README.md", "LICENSE"]
    ordered = sorted(paths, key=modelscope_adapter._document_priority)

    assert ordered[:2] == ["LICENSE", "README.md"]
