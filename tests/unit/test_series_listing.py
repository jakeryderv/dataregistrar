import re

import httpx

from dataregistrar.adapters.noaa.series import list_releases


def _row(name: str, when: str, size: str) -> str:
    link = f'<a href="{name}">{name}</a>'
    return f'<tr><td>{link}</td><td align="right">{when}  </td><td>{size}</td></tr>'


TABLE = (
    "<table>"
    + "".join(
        [
            _row("1763.csv.gz", "2026-09-04 23:37", "3.3K"),
            _row("2026.csv.gz", "2026-09-04 23:36", "89M"),
            _row("readme.txt", "2025-01-01 00:00", "1K"),
        ]
    )
    + "</table>"
)
PRE = '<pre><a href="d2024_c20260728.csv.gz">d2024_c20260728.csv.gz</a>  2026-07-28 10:00  1M</pre>'


def _client(text: str) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=text)))


def test_listing_dates_become_revisions_and_nest_the_filename() -> None:
    pattern = re.compile(r'(?<=["/>])(?P<period>\d{4})\.csv\.gz')
    releases = list_releases(_client(TABLE), "https://x.test/by_year/", pattern, listing_dates=True)
    assert [r.id for r in releases] == ["1763", "2026"]
    assert releases[1].revision == "20260904"
    assert str(releases[1].published) == "2026-09-04"
    assert releases[1].filename == "2026/20260904/2026.csv.gz"
    assert str(releases[1].url) == "https://x.test/by_year/2026.csv.gz"


NCEI_TABLE = (
    '<tr>\n<td><a href="2026.csv.gz">2026.csv.gz</a></td>\n'
    '<td align="right">2026-09-03 19:29</td>\n<td align="right">93127070</td>\n'
    "<td>\xa0</td>\n</tr>\n"
    '<tr>\n<td><a href="readme-by_year.txt">readme-by_year.txt</a></td>\n'
    '<td align="right">2021-03-08 10:06</td>\n</tr>'
)


def test_ncei_multi_cell_layout_yields_the_right_date() -> None:
    pattern = re.compile(r'(?<=["/>])(?P<period>\d{4})\.csv\.gz')
    releases = list_releases(_client(NCEI_TABLE), "https://x.test/", pattern, listing_dates=True)
    assert [(r.id, r.revision) for r in releases] == [("2026", "20260903")]


def test_without_listing_dates_no_revision_and_plain_filename() -> None:
    pattern = re.compile(r'(?<=["/>])(?P<period>\d{4})\.csv\.gz')
    releases = list_releases(_client(TABLE), "https://x.test/by_year/", pattern)
    assert releases[0].revision is None and releases[0].published is None
    assert releases[0].filename == "1763/1763.csv.gz"


def test_revision_in_name_is_not_nested_again() -> None:
    pattern = re.compile(r"d(?P<period>\d{4})_c(?P<revision>\d{8})\.csv\.gz")
    releases = list_releases(_client(PRE), "https://x.test/", pattern, listing_dates=True)
    assert releases[0].revision == "20260728"
    assert releases[0].filename == "2024/d2024_c20260728.csv.gz"
