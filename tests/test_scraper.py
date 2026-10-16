import json

import pytest
import requests

from wikicard import scraper

TABLE = """
<table class="wikitable"><tr><th>No.</th></tr>
{rows}
</table>"""
ROW = """
<tr><th scope="row"><a href="/wiki/Presidency_of_{u}">{n}</a></th>
<td><img src="//upload.example/{u}.jpg" srcset="//upload.example/{u}-2x.jpg 1.5x"></td>
<td><b><a href="/wiki/{u}">{name}</a></b><br>(1700–1780)<sup>[ 1 ]</sup></td>
<td>{term}<sup>[ e ]</sup></td><td></td><td>{party}</td></tr>"""


def make_html():
    rows = [
        ROW.format(u="A_One", n=1, name="A One", term="March 4, 1789 – March 4, 1797", party="Whig"),
        ROW.format(u="B_Two", n=2, name="B Two", term="March 4, 1841 – April 4, 1841", party="Democratic- Republican"),
        ROW.format(u="A_One", n=3, name="A One", term="January 20, 2025 – Incumbent", party="Whig"),
    ]
    return TABLE.format(rows="".join(rows))


class Resp:
    def __init__(self, status=200, text="", data=None, headers=None):
        self.status_code, self.text, self._data, self.headers = status, text, data, headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, fail_first_429=False):
        self.calls = []
        self.pending_429 = fail_first_429

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if self.pending_429:
            self.pending_429 = False
            return Resp(429, headers={"Retry-After": "1"})
        if params is None:
            return Resp(text=make_html())
        titles = params["titles"].split("|")
        pages = [{"title": t, "extract": f"{t} (born 1700) was a person.\nSecond paragraph of text here that is long enough to be a hint."} for t in titles]
        return Resp(data={"query": {"pages": pages}})


def test_parse_table():
    rows = scraper.parse_presidency_table(make_html())
    assert [r.name for r in rows] == ["A One", "B Two", "A One"]
    assert rows[1].party == "Democratic-Republican"
    assert rows[0].image_url == "https://upload.example/A_One-2x.jpg"
    assert rows[1].years == (1841, 1841)
    assert rows[2].years == (2025, None)


def test_harvest_merges_terms_and_limits_requests():
    session = FakeSession()
    result = scraper.harvest(session, sleep=lambda s: None)
    assert result.source == "wikipedia"
    assert [c["name"] for c in result.cards] == ["A One", "B Two"]
    first = result.cards[0]
    assert first["years_in_office"] == "1789–1797, 2025–present"
    assert first["hint"].startswith("The 1st and 3rd president of the United States.")
    assert result.cards[1]["years_in_office"] == "1841"
    assert result.lead_requests == 1 and result.list_requests == 1
    assert "WikiCard" in scraper.USER_AGENT


def test_retry_on_429():
    sleeps = []
    session = FakeSession(fail_first_429=True)
    result = scraper.harvest(session, sleep=sleeps.append)
    assert result.source == "wikipedia" and sleeps == [1.0]


def test_falls_back_to_snapshot():
    class Down:
        def get(self, *a, **k):
            raise requests.ConnectionError("offline")

    result = scraper.harvest(Down())
    assert result.source == "snapshot" and len(result.cards) == 45 and result.warnings


def test_batches_of_twenty():
    session = FakeSession()
    titles = [f"T{i}" for i in range(45)]
    leads, n = scraper.fetch_leads(session, titles)
    assert n == 3 and len(leads) == 45


# ---- bundled snapshot acceptance checks
CARDS = json.loads(scraper.SEED_PATH.read_text(encoding="utf-8"))
BY_NAME = {c["name"]: c for c in CARDS}


def test_snapshot_shape():
    assert len(CARDS) == 45
    first = CARDS[0]
    assert (first["name"], first["years_in_office"], first["party"]) == (
        "George Washington", "1789–1797", "Unaffiliated")
    assert BY_NAME["Grover Cleveland"]["years_in_office"] == "1885–1889, 1893–1897"
    assert BY_NAME["Grover Cleveland"]["hint"].startswith("The 22nd and 24th president")
    assert BY_NAME["Donald Trump"]["years_in_office"] == "2017–2021, 2025–present"
    assert BY_NAME["William Henry Harrison"]["years_in_office"] == "1841"
    assert [c["sort_order"] for c in CARDS] == list(range(1, 46))


@pytest.mark.parametrize("card", CARDS, ids=lambda c: c["name"])
def test_snapshot_card_quality(card):
    from wikicard.textutils import name_parts
    assert card["image_url"].startswith("https://") and card["details"]
    assert 1 <= len(card["highlights"]) <= 5
    for part in name_parts(card["name"]):
        assert part.lower() not in card["hint"].lower()
    assert not any(h.rstrip("…") in card["details"] for h in card["highlights"])
