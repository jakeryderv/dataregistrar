import pytest
from pydantic import HttpUrl, ValidationError

from dataregistrar import Kind, Record, Status


def test_record_defaults_to_imported() -> None:
    record = Record(id="uci:186", kind=Kind.DATASET, source="uci", name="Wine Quality")
    assert record.status is Status.IMPORTED


def test_record_round_trips_through_json() -> None:
    record = Record(
        id="hf:org/name",
        kind=Kind.DATASET,
        source="huggingface",
        name="Name",
        url=HttpUrl("https://huggingface.co/datasets/org/name"),
    )
    assert Record.model_validate_json(record.model_dump_json()) == record


def test_every_kind_is_accepted() -> None:
    for kind in Kind:
        Record(id=f"x:{kind}", kind=kind, source="x", name="n")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Record.model_validate(
            {"id": "x:1", "kind": "dataset", "source": "x", "name": "n", "bogus": 1}
        )
