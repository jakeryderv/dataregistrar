from dataregistrar.adapters.huggingface import HuggingFaceAdapter
from dataregistrar.model import Confidence, Status

BASE = {"id": "org/name", "author": "org", "gated": False, "description": "  a\n\n b  "}


def test_single_known_license_tag_derives_imported_rights() -> None:
    r = HuggingFaceAdapter().to_record({**BASE, "tags": ["license:cc-by-nc-4.0"]})
    assert r.id == "hf:org/name"
    assert r.license.spdx == "CC-BY-NC-4.0"
    assert str(r.license.evidence_url) == "https://huggingface.co/datasets/org/name"
    assert r.rights.commercial_use is False
    assert r.rights.confidence is Confidence.IMPORTED
    assert r.description == "a b"


def test_unknown_or_ambiguous_license_tags_stay_unknown() -> None:
    adapter = HuggingFaceAdapter()
    none = adapter.to_record({**BASE, "tags": []})
    other = adapter.to_record({**BASE, "tags": ["license:other"]})
    two = adapter.to_record({**BASE, "tags": ["license:mit", "license:cc-by-4.0"]})
    for r in (none, other, two):
        assert r.license.spdx is None
        assert r.rights.commercial_use == "unknown"


def test_gated_datasets_are_restricted() -> None:
    r = HuggingFaceAdapter().to_record({**BASE, "gated": "manual", "tags": ["license:mit"]})
    assert r.status is Status.RESTRICTED
    assert r.access.gated and r.access.authentication


def test_task_and_modality_tags_are_extracted() -> None:
    r = HuggingFaceAdapter().to_record(
        {**BASE, "tags": ["task_categories:image-classification", "modality:image"]}
    )
    assert r.tasks == ["image-classification"]
    assert r.modality == "image"
