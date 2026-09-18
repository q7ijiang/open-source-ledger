import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BOM_PATH = BASE_DIR / "sample_bom.json"
ASSETS_PATH = BASE_DIR / "assets.json"
SNAPSHOT_ID = "basic-20260918"


def asset_type_for(component):
    component_type = component.get("type", "")
    if component_type in {"machine-learning-model", "model"}:
        return "model"
    if component_type in {"data", "dataset"}:
        return "dataset"
    if component_type == "repository":
        return "repository"
    return "package"


def license_name(license_entry):
    if not isinstance(license_entry, dict):
        return None
    license_value = license_entry.get("license")
    if isinstance(license_value, dict):
        return license_value.get("id") or license_value.get("name")
    if isinstance(license_value, str):
        return license_value
    return license_entry.get("expression")


def extract_licenses(component):
    names = []
    for entry in component.get("licenses", []):
        name = license_name(entry)
        if name and name not in names:
            names.append(name)
    return names


def evidence_entry(source_field, raw_value, retrieved_at):
    return {
        "evidence_level": "A",
        "source_api": "cyclonedx",
        "source_url": None,
        "source_field": source_field,
        "retrieved_at": retrieved_at,
        "status": "ok",
        "raw_value": raw_value,
    }


def convert_component(component, retrieved_at):
    asset_type = asset_type_for(component)
    name = component.get("name", "")
    purl = component.get("purl")
    licenses = extract_licenses(component)
    evidence_chain = []

    for entry in component.get("licenses", []):
        evidence_chain.append(
            evidence_entry(
                "components[].licenses",
                json.dumps(entry, ensure_ascii=False),
                retrieved_at,
            )
        )

    occurrences = component.get("evidence", {}).get("occurrences", [])
    for occurrence in occurrences:
        location = occurrence.get("location")
        if location:
            evidence_chain.append(
                evidence_entry(
                    "components[].evidence.occurrences[].location",
                    location,
                    retrieved_at,
                )
            )

    return {
        "canonical_id": f"{asset_type}:{name}",
        "asset_type": asset_type,
        "name": name,
        "version": component.get("version", ""),
        "purls": [purl] if purl else [],
        "license": "; ".join(licenses),
        "evidence_chain": evidence_chain,
        "snapshot_id": SNAPSHOT_ID,
    }


def main():
    with BOM_PATH.open("r", encoding="utf-8") as bom_file:
        bom = json.load(bom_file)

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assets = [
        convert_component(component, retrieved_at)
        for component in bom.get("components", [])
    ]

    with ASSETS_PATH.open("w", encoding="utf-8") as assets_file:
        json.dump(assets, assets_file, ensure_ascii=False, indent=2)
        assets_file.write("\n")

    print(f"Read {BOM_PATH}")
    print(f"Wrote {len(assets)} assets to {ASSETS_PATH}")
    print(f"Retrieved at {retrieved_at}")


if __name__ == "__main__":
    main()
