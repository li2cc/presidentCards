"""Harvest US president cards from Wikipedia (list page + MediaWiki API)."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from . import textutils as tx

LIST_URL = "https://en.wikipedia.org/wiki/List_of_presidents_of_the_United_States"
API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = (
    "WikiCardLearningSystem/1.0 (educational Streamlit app; "
    "https://github.com/li2cc/presidentCards) python-requests"
)
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_us_presidents.json"
CATEGORY = "US Presidents"
BATCH = 20


@dataclass
class Presidency:
    number: int
    name: str
    image_url: str
    party: str
    years: tuple[int, int | None]
    title: str  # Wikipedia article title
    url: str


@dataclass
class HarvestResult:
    cards: list[dict]
    source: str  # "wikipedia" or "snapshot"
    list_requests: int = 0
    lead_requests: int = 0
    warnings: list[str] = field(default_factory=list)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    return session


def http_get(session, url, *, params=None, retries=4, timeout=20, sleep=time.sleep):
    """GET with exponential backoff on HTTP 429 (honours Retry-After)."""
    delay = 2.0
    for attempt in range(retries + 1):
        response = session.get(url, params=params, timeout=timeout)
        if response.status_code != 429:
            response.raise_for_status()
            return response
        if attempt == retries:
            response.raise_for_status()
        retry_after = response.headers.get("Retry-After", "")
        wait = float(retry_after) if retry_after.isdigit() else delay
        sleep(min(wait, 30))
        delay *= 2
    raise RuntimeError("unreachable")


def _clean_cell(cell) -> str:
    for sup in cell.find_all("sup"):
        sup.decompose()
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).replace("- ", "-")


def _absolute(url: str) -> str:
    return "https:" + url if url.startswith("//") else url


def parse_presidency_table(html: str) -> list[Presidency]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.wikitable")
    if table is None:
        raise ValueError("Presidents table not found")
    rows: list[Presidency] = []
    for tr in table.find_all("tr"):
        th = tr.find("th", scope="row")
        cells = tr.find_all("td")
        if th is None or len(cells) < 5:
            continue
        number = int(re.sub(r"\D", "", th.get_text()))
        link = cells[1].find("a", href=re.compile(r"/wiki/"))
        if link is None:
            continue
        img = cells[0].find("img")
        image = ""
        if img is not None:
            srcset = img.get("srcset", "")
            larger = srcset.split(",")[0].strip().split(" ")[0] if srcset else ""
            image = _absolute(larger or img.get("src", ""))
        href = link["href"]
        title = unquote(href.split("/wiki/", 1)[1].split("#")[0]).replace("_", " ")
        rows.append(Presidency(
            number=number,
            name=link.get_text(strip=True),
            image_url=image,
            party=_clean_cell(cells[4]),
            years=tx.parse_term_years(_clean_cell(cells[2])),
            title=title,
            url=f"https://en.wikipedia.org/wiki/{href.split('/wiki/', 1)[1]}",
        ))
    return rows


def fetch_leads(session, titles: list[str], sleep=time.sleep) -> tuple[dict[str, dict], int]:
    """Return {requested title: {extract, thumbnail}} and the request count."""
    out: dict[str, dict] = {}
    requests_made = 0
    for i in range(0, len(titles), BATCH):
        batch = titles[i:i + BATCH]
        params = {
            "action": "query", "format": "json", "formatversion": 2,
            "prop": "extracts|pageimages", "exintro": 1, "explaintext": 1,
            "exlimit": BATCH, "piprop": "thumbnail", "pithumbsize": 400,
            "redirects": 1, "titles": "|".join(batch),
        }
        response = http_get(session, API_URL, params=params, sleep=sleep)
        requests_made += 1
        query = response.json().get("query", {})
        alias = {}
        for m in query.get("normalized", []) + query.get("redirects", []):
            alias[m["from"]] = m["to"]
        pages = {p["title"]: p for p in query.get("pages", []) if "missing" not in p}
        for title in batch:
            target = title
            for _ in range(3):
                target = alias.get(target, target)
            page = pages.get(target)
            if page:
                out[title] = {
                    "extract": page.get("extract", ""),
                    "thumbnail": (page.get("thumbnail") or {}).get("source", ""),
                }
    return out, requests_made


def merge_presidencies(rows: list[Presidency]) -> list[list[Presidency]]:
    """Group presidencies by article title (Cleveland, Trump), in first-term order."""
    groups: dict[str, list[Presidency]] = {}
    for row in rows:
        groups.setdefault(row.title, []).append(row)
    return list(groups.values())


def build_cards(groups: list[list[Presidency]], leads: dict[str, dict]) -> list[dict]:
    cards = []
    for order, group in enumerate(groups, start=1):
        first = group[0]
        lead = leads.get(first.title, {})
        paragraphs = tx.split_paragraphs(lead.get("extract", ""))
        numbers = [g.number for g in group]
        details = paragraphs[0] if paragraphs else ""
        cards.append({
            "name": first.name,
            "image_url": first.image_url or lead.get("thumbnail", ""),
            "category": CATEGORY,
            "hint": tx.build_hint(first.name, numbers, paragraphs),
            "answer": first.name,
            "details": details,
            "highlights": tx.build_highlights(first.name, paragraphs),
            "party": first.party,
            "years_in_office": tx.format_term_years([g.years for g in group]),
            "sort_order": order,
            "source_url": first.url,
        })
    return cards


def load_seed(path: Path = SEED_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_seed(cards: list[dict], path: Path = SEED_PATH) -> None:
    Path(path).write_text(json.dumps(cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def harvest(session=None, sleep=time.sleep, allow_snapshot: bool = True) -> HarvestResult:
    """Collect cards from Wikipedia; fall back to the bundled snapshot on failure."""
    session = session or make_session()
    try:
        html = http_get(session, LIST_URL, sleep=sleep).text
        groups = merge_presidencies(parse_presidency_table(html))
        if not groups:
            raise ValueError("No presidents parsed from the list page")
        leads, lead_requests = fetch_leads(session, [g[0].title for g in groups], sleep=sleep)
        cards = build_cards(groups, leads)
        return HarvestResult(cards, "wikipedia", 1, lead_requests)
    except (requests.RequestException, ValueError, KeyError) as exc:
        if not allow_snapshot:
            raise
        cards = load_seed()
        return HarvestResult(
            cards, "snapshot", warnings=[f"Wikipedia unreachable ({exc}); used bundled snapshot."]
        )
