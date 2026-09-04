"""Release listings from plain file directories, the way most government data ships."""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import httpx
from pydantic import HttpUrl

from dataregistrar.model import Release


def _published(revision: str | None) -> date | None:
    if revision and re.fullmatch(r"\d{8}", revision):
        return datetime.strptime(revision, "%Y%m%d").date()
    return None


def list_releases(
    client: httpx.Client, listing_url: str, pattern: re.Pattern[str]
) -> list[Release]:
    """Parse a directory listing for filenames matching `pattern`.

    The pattern must define a `period` group and may define a `revision` group. The planned
    filename is `<period>/<name>` so a re-issued period never overwrites an earlier file.
    """
    response = client.get(listing_url)
    response.raise_for_status()
    seen: dict[str, Release] = {}
    for match in pattern.finditer(response.text):
        name = match.group(0)
        if name in seen:
            continue
        period = match.group("period")
        revision = match.groupdict().get("revision")
        seen[name] = Release(
            id=period,
            revision=revision,
            published=_published(revision),
            url=HttpUrl(urljoin(listing_url, name)),
            filename=f"{period}/{name}",
        )
    return sorted(seen.values(), key=lambda r: (r.id, r.revision or ""))
