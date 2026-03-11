import re
from datetime import datetime
from typing import Any, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

SOURCE_URL = "https://www.gudoball.club/"
THAI_MONTHS = {
    "มกราคม": 1,
    "กุมภาพันธ์": 2,
    "มีนาคม": 3,
    "เมษายน": 4,
    "พฤษภาคม": 5,
    "มิถุนายน": 6,
    "กรกฎาคม": 7,
    "สิงหาคม": 8,
    "กันยายน": 9,
    "ตุลาคม": 10,
    "พฤศจิกายน": 11,
    "ธันวาคม": 12,
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_date_from_heading(text: str) -> Optional[datetime]:
    # Example: "ทรรศนะบอล วันพุธที่ 11 มีนาคม 2569"
    match = re.search(r"(\d{1,2})\s+([ก-๙]+)\s+(\d{4})", text)
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2)
    thai_year = int(match.group(3))
    month = THAI_MONTHS.get(month_name)
    if not month:
        return None
    gregorian_year = thai_year - 543
    try:
        return datetime(gregorian_year, month, day)
    except ValueError:
        return None


def _parse_table(table: Tag) -> list[dict[str, Any]]:
    rows = table.find_all("tr")
    if not rows:
        return []

    headers = [_clean_text(c.get_text(" ", strip=True)) for c in rows[0].find_all(["th", "td"])]
    data: list[dict[str, Any]] = []
    current_group = ""

    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        values = [_clean_text(c.get_text(" ", strip=True)) for c in cells]
        values = [v for v in values if v != ""]

        if not values:
            continue

        if len(values) == 1:
            current_group = values[0]
            continue

        item: dict[str, Any] = {}
        if current_group:
            item["group"] = current_group

        for idx, value in enumerate(values):
            key = headers[idx] if idx < len(headers) and headers[idx] else f"col_{idx + 1}"
            item[key] = value
        data.append(item)

    return data


def _find_heading(soup: BeautifulSoup, keyword: str) -> Optional[Tag]:
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        if keyword in _clean_text(tag.get_text(" ", strip=True)):
            return tag
    return None


def _next_heading(tag: Tag) -> Optional[Tag]:
    for sib in tag.find_all_next():
        if isinstance(sib, Tag) and re.match(r"^h[1-6]$", sib.name or ""):
            return sib
    return None


def _collect_between(start: Tag, stop: Optional[Tag]) -> list[Tag]:
    blocks: list[Tag] = []
    for node in start.find_all_next():
        if stop is not None and node == stop:
            break
        if isinstance(node, Tag):
            blocks.append(node)
    return blocks


def _parse_analysis_articles(soup: BeautifulSoup) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    for link in soup.find_all("a", href=True):
        title = _clean_text(link.get_text(" ", strip=True))
        if not title.startswith("วิเคราะห์บอล"):
            continue
        # Keep only real match analysis titles, skip menu links like "วิเคราะห์บอล".
        if " vs " not in title or len(title) < 25:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)
        records.append(
            {
                "title": title,
                "url": requests.compat.urljoin(SOURCE_URL, link["href"]),
            }
        )
    return records


def _parse_tips_section(soup: BeautifulSoup) -> list[dict[str, Any]]:
    tips_heading = _find_heading(soup, "ทีเด็ดบอลเต็ง บอลชุด")
    if not tips_heading:
        return []
    stop = _next_heading(tips_heading)
    blocks = _collect_between(tips_heading, stop)

    date_pattern = re.compile(r"ทีเด็ดบอล วันที่\s*\d{2}-\d{2}-\d{4}")
    date_labels: list[str] = []
    tables: list[Tag] = []

    for block in blocks:
        text = _clean_text(block.get_text(" ", strip=True))
        if date_pattern.search(text):
            date_labels.append(date_pattern.search(text).group(0))
        if block.name == "table":
            tables.append(block)

    result: list[dict[str, Any]] = []
    for idx, table in enumerate(tables):
        result.append(
            {
                "label": date_labels[idx] if idx < len(date_labels) else f"tips_table_{idx + 1}",
                "rows": _parse_table(table),
            }
        )
    return result


def _parse_opinion_sections(soup: BeautifulSoup) -> Tuple[dict[str, Any], dict[str, Any]]:
    opinion_headings: list[Tuple[Optional[datetime], Tag]] = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        text = _clean_text(tag.get_text(" ", strip=True))
        if "ทรรศนะบอล วัน" in text:
            opinion_headings.append((_extract_date_from_heading(text), tag))

    if not opinion_headings:
        return ({"title": "", "rows": []}, {"title": "", "rows": []})

    opinion_headings.sort(
        key=lambda x: x[0] if x[0] is not None else datetime.min,
        reverse=True,
    )

    parsed_sections: list[dict[str, Any]] = []
    for _, heading in opinion_headings[:2]:
        stop = _next_heading(heading)
        blocks = _collect_between(heading, stop)
        first_table = next((b for b in blocks if b.name == "table"), None)
        parsed_sections.append(
            {
                "title": _clean_text(heading.get_text(" ", strip=True)),
                "rows": _parse_table(first_table) if first_table else [],
            }
        )

    while len(parsed_sections) < 2:
        parsed_sections.append({"title": "", "rows": []})

    return parsed_sections[0], parsed_sections[1]


def fetch_gudoball_data() -> dict[str, Any]:
    response = requests.get(SOURCE_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    opinion_today, opinion_previous = _parse_opinion_sections(soup)
    payload = {
        "source": SOURCE_URL,
        "scraped_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
        "sections": {
            "section_1_analysis_today": _parse_analysis_articles(soup),
            "section_2_tips_combo": _parse_tips_section(soup),
            "section_3_opinion_today": opinion_today,
            "section_4_opinion_previous": opinion_previous,
        },
    }
    return payload
