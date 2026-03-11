import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException

from app.scraper import fetch_gudoball_data
from app.storage import load_payload, save_payload

app = FastAPI(title="Gudoball Scraper API", version="1.0.0")


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
