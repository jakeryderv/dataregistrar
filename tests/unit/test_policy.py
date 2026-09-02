import pytest
from pydantic import HttpUrl

from dataregistrar.model import Confidence, Kind, License, Record, Rights
from dataregistrar.policy import DatasetPolicyError, check, derive_rights, load_table, preset


def _record(**kwargs: object) -> Record:
    base: dict[str, object] = {"id": "x:1", "kind": Kind.DATASET, "source": "x", "name": "n"}
    return Record.model_validate({**base, **kwargs})


def test_table_loads_and_every_entry_covers_every_right() -> None:
    table = load_table()
    for spdx, rights in table.licenses.items():
        assert set(rights) == set(Rights.model_fields) - {"confidence"}, spdx


def test_known_license_derives_imported_rights() -> None:
    rights = derive_rights(License(spdx="CC-BY-NC-4.0"))
    assert rights.commercial_use is False
    assert rights.redistribution is True
    assert rights.confidence is Confidence.IMPORTED


def test_unknown_license_derives_all_unknown() -> None:
    assert derive_rights(License(spdx="Proprietary-Weird")) == Rights()
    assert derive_rights(License()) == Rights()


def test_unknown_right_never_satisfies() -> None:
    with pytest.raises(DatasetPolicyError, match="commercial_use is unknown"):
        check(_record(), preset("commercial"))


def test_declared_false_fails_with_evidence_in_message() -> None:
    record = _record(
        license=License(spdx="CC-BY-NC-4.0", evidence_url=HttpUrl("https://example.org/lic")),
        rights=derive_rights(License(spdx="CC-BY-NC-4.0")),
    )
    with pytest.raises(DatasetPolicyError) as info:
        check(record, {"commercial_use": True})
    message = str(info.value)
    assert "CC-BY-NC-4.0" in message
    assert "https://example.org/lic" in message
    assert "commercial_use=False is declared, True was required" in message


def test_declared_true_passes() -> None:
    record = _record(rights=derive_rights(License(spdx="CC-BY-4.0")))
    check(record, preset("permissive"))


def test_unknown_preset_and_unknown_right_are_errors() -> None:
    with pytest.raises(ValueError, match="unknown policy preset"):
        preset("nope")
    with pytest.raises(ValueError, match="unknown right"):
        check(_record(), {"teleportation": True})
