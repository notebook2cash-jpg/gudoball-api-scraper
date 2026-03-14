import os
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from app.scraper import fetch_gudoball_data
from app.storage import load_payload, save_payload

app = FastAPI(title="Gudoball Scraper API", version="1.0.0")
ALLOWED_ICON_HOSTS = {
    "polball.club",
    "www.polball.club",
    "gudoball.club",
    "www.gudoball.club",
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/gudoball/latest")
def get_latest() -> dict[str, Any]:
    return load_payload()


@app.get("/api/v1/gudoball/sections/{section_id}")
def get_section(section_id: int) -> Any:
    if section_id < 1 or section_id > 4:
        raise HTTPException(status_code=400, detail="section_id must be 1..4")
    data = load_payload()
    sections = data.get("sections", {})
    key = f"section_{section_id}"
    candidates = [k for k in sections.keys() if k.startswith(key)]
    if not candidates:
        raise HTTPException(status_code=404, detail="Section not found")
    return sections[candidates[0]]


@app.post("/api/v1/gudoball/refresh")
def refresh(token: Optional[str] = None) -> dict[str, Any]:
    expected_token = os.getenv("REFRESH_TOKEN")
    if expected_token and token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    payload = fetch_gudoball_data()
    save_payload(payload)
    return payload


@app.get("/api/v1/gudoball/icon")
def get_icon(url: str) -> Response:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_ICON_HOSTS:
        raise HTTPException(status_code=400, detail="Invalid icon URL")

    referer = "https://www.polball.club/" if "polball" in parsed.hostname else "https://www.gudoball.club/"
    headers = {
        "Referer": referer,
        "User-Agent": "Mozilla/5.0",
    }
    try:
        upstream = requests.get(url, headers=headers, timeout=20)
        upstream.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Icon fetch failed: {exc}") from exc

    content_type = (upstream.headers.get("Content-Type") or "").split(";")[0].strip()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Upstream did not return an image")

    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
