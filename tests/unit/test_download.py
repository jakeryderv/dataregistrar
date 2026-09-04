import hashlib
from pathlib import Path

import httpx
import pytest
from pydantic import HttpUrl

from dataregistrar.download import ChecksumMismatch, download, sha256_of
from dataregistrar.model import PlannedFile

BODY = b"a,b\n1,2\n"
GOOD = hashlib.sha256(BODY).hexdigest()


def _client(calls: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=BODY)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_download_writes_file_and_verifies_checksum(tmp_path: Path) -> None:
    calls: list[str] = []
    planned = PlannedFile(url=HttpUrl("https://x.test/d.csv"), filename="d.csv", sha256=GOOD)
    path = download(_client(calls), planned, tmp_path)
    assert path.read_bytes() == BODY
    assert sha256_of(path) == GOOD
    assert not list(tmp_path.glob("*.part"))
    assert calls == ["https://x.test/d.csv"]


def test_mismatch_raises_and_leaves_nothing_behind(tmp_path: Path) -> None:
    planned = PlannedFile(url=HttpUrl("https://x.test/d.csv"), filename="d.csv", sha256="0" * 64)
    with pytest.raises(ChecksumMismatch) as info:
        download(_client([]), planned, tmp_path)
    assert info.value.actual == GOOD
    assert list(tmp_path.iterdir()) == []


def test_existing_verified_file_is_not_downloaded_again(tmp_path: Path) -> None:
    calls: list[str] = []
    planned = PlannedFile(url=HttpUrl("https://x.test/d.csv"), filename="d.csv", sha256=GOOD)
    client = _client(calls)
    download(client, planned, tmp_path)
    download(client, planned, tmp_path)
    assert len(calls) == 1


def test_existing_stale_file_is_replaced_when_checksum_known(tmp_path: Path) -> None:
    calls: list[str] = []
    (tmp_path / "d.csv").write_bytes(b"old")
    planned = PlannedFile(url=HttpUrl("https://x.test/d.csv"), filename="d.csv", sha256=GOOD)
    path = download(_client(calls), planned, tmp_path)
    assert path.read_bytes() == BODY
    assert len(calls) == 1
