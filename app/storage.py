import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "latest.json"


def save_payload(payload: dict[str, Any]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_payload() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"message": "No data yet. Run scraper first."}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))
