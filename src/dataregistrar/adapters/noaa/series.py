"""Release listings from plain file directories, the way most government data ships."""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import httpx
from pydantic import HttpUrl

from dataregistrar.model import Release

# Directory listings put the modification time shortly after the link, either inline
# (`<pre>` style) or in the next table cell. The size column never looks like a date.
_DATE_AFTER_LINK = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T]\d{2}:\d{2}")


def _published(revision: str | None) -> date | None:
    if revision and re.fullmatch(r"\d{8}", revision):
        return datetime.strptime(revision, "%Y%m%d").date()
    return None


def list_releases(
    client: httpx.Client,
    listing_url: str,
    pattern: re.Pattern[str],
    *,
    listing_dates: bool = False,
) -> list[Release]:
    """Parse a directory listing for filenames matching `pattern`.

    The pattern must define a `period` group and may define a `revision` group. When it does
    not, and `listing_dates` is set, the listing's modification date serves as the revision.
    Planned filenames are `<period>/<name>`, or `<period>/<revision>/<name>` when the name does
    not itself carry the revision, so a re-issued period never overwrites an earlier file.
    """
    response = client.get(listing_url)
    response.raise_for_status()
    text = response.text
    seen: dict[str, Release] = {}
    for match in pattern.finditer(text):
        name = match.group(0)
        if name in seen:
            continue
        period = match.group("period")
        revision = match.groupdict().get("revision")
        if revision is None and listing_dates:
            dated = _DATE_AFTER_LINK.search(text, match.end(), match.end() + 300)
            if dated:
                revision = "".join(dated.groups())
        filename = (
            f"{period}/{name}"
            if revision is None or revision in name
            else f"{period}/{revision}/{name}"
        )
        seen[name] = Release(
            id=period,
            revision=revision,
            published=_published(revision),
            url=HttpUrl(urljoin(listing_url, name)),
            filename=filename,
        )
    return sorted(seen.values(), key=lambda r: (r.id, r.revision or ""))
