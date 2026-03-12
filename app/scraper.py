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


def _table_to_matrix(table: Tag) -> list[list[str]]:
    rows = table.find_all("tr")
    if not rows:
        return []

    header_cells = rows[0].find_all(["th", "td"])
    expected_cols = max(len(header_cells), 1)
    matrix: list[list[str]] = []
    rowspans: dict[int, dict[str, Any]] = {}

    for row in rows:
        row_values: list[str] = []
        cells = row.find_all(["th", "td"])
        cell_idx = 0
        col_idx = 0

        while col_idx < expected_cols:
            span = rowspans.get(col_idx)
            if span:
                row_values.append(span["text"])
                span["remaining"] -= 1
                if span["remaining"] <= 0:
                    rowspans.pop(col_idx, None)
                col_idx += 1
                continue

            if cell_idx >= len(cells):
                row_values.append("")
                col_idx += 1
                continue

            cell = cells[cell_idx]
            cell_idx += 1
            value = _clean_text(cell.get_text(" ", strip=True))
            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            for _ in range(colspan):
                if col_idx >= expected_cols:
                    break
                row_values.append(value)
                if rowspan > 1:
                    rowspans[col_idx] = {"text": value, "remaining": rowspan - 1}
                col_idx += 1

        matrix.append(row_values)

    return matrix


def _extract_analysis_detail(article_url: str) -> dict[str, Any]:
    response = requests.get(article_url, timeout=30)
    response.raise_for_status()
    page = BeautifulSoup(response.text, "html.parser")
    article = page.find("article")
    if article is None:
        article = page.body
    if article is None:
        return {"content": "", "team_icons": []}

    content_lines: list[str] = []
    for node in article.find_all(["h2", "h3", "h4", "p", "li"]):
        text = _clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        content_lines.append(text)

    # Remove repeated lines while preserving order.
    deduped_lines: list[str] = []
    seen: set[str] = set()
    for line in content_lines:
        if line in seen:
            continue
        seen.add(line)
        deduped_lines.append(line)

    # Team names in these articles are commonly standalone short lines.
    team_candidates: list[str] = []
    for line in deduped_lines:
        if "วิเคราะห์บอล" in line:
            continue
        if len(line) > 40:
            continue
        if re.search(r"[0-9]", line):
            continue
        if any(mark in line for mark in [":", "(", ")", ",", "http", "www."]):
            continue
        team_candidates.append(line)

    teams: list[str] = []
    for name in team_candidates:
        if name not in teams:
            teams.append(name)
        if len(teams) >= 2:
            break

    all_images: list[str] = []
    for img in article.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        all_images.append(requests.compat.urljoin(article_url, src))

    team_icons = [
        img
        for img in all_images
        if "uefa" not in img.lower()
        and "champions_league" not in img.lower()
        and "premier-league" not in img.lower()
    ]
    if len(team_icons) < 2:
        team_icons = all_images

    return {
        "content": "\n".join(deduped_lines),
        "team_icons": team_icons[:2],
        "teams": teams,
    }


def _parse_analysis_articles(soup: BeautifulSoup) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
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
        article_url = requests.compat.urljoin(SOURCE_URL, link["href"])
        detail = _extract_analysis_detail(article_url)
        records.append(
            {
                "title": title,
                "content": detail["content"],
                "team_icons": detail["team_icons"],
                "teams": detail["teams"],
            }
        )
    return records


def _parse_tips_rows(table: Tag) -> list[dict[str, str]]:
    matrix = _table_to_matrix(table)
    if not matrix:
        return []

    headers = matrix[0]
    if len(headers) < 2:
        return []

    row_label_key = "ประเภท"
    expert_headers = headers[1:]
    parsed_rows: list[dict[str, str]] = []

    for row in matrix[1:]:
        if not any(row):
            continue
        item: dict[str, str] = {row_label_key: row[0]}
        for idx, expert in enumerate(expert_headers, start=1):
            if idx < len(row) and row[idx]:
                item[expert] = row[idx]
        parsed_rows.append(item)

    return parsed_rows


def _parse_date_ddmmyyyy(label: str) -> datetime:
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", label)
    if not m:
        return datetime.min
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(year, month, day)
    except ValueError:
        return datetime.min


def _parse_tips_section(soup: BeautifulSoup) -> dict[str, Any]:
    tips_heading = _find_heading(soup, "ทีเด็ดบอลเต็ง บอลชุด")
    if not tips_heading:
        return {"current": {"label": "", "rows": []}, "previous": {"label": "", "rows": []}}

    date_pattern = re.compile(r"ทีเด็ดบอล วันที่\s*\d{2}-\d{2}-\d{4}")
    entries: list[dict[str, Any]] = []

    for sib in tips_heading.next_siblings:
        if not isinstance(sib, Tag):
            continue
        if re.match(r"^h[1-6]$", sib.name or ""):
            break

        text = _clean_text(sib.get_text(" ", strip=True))
        date_match = date_pattern.search(text)
        table = sib.find("table")
        if not date_match or table is None:
            continue

        entries.append(
            {
                "label": date_match.group(0),
                "rows": _parse_tips_rows(table),
            }
        )

    entries.sort(key=lambda item: _parse_date_ddmmyyyy(item["label"]), reverse=True)
    current = entries[0] if len(entries) > 0 else {"label": "", "rows": []}
    previous = entries[1] if len(entries) > 1 else {"label": "", "rows": []}
    return {"current": current, "previous": previous}


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
