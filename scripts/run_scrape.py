import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.scraper import fetch_gudoball_data
from app.storage import save_payload


def main() -> None:
    payload = fetch_gudoball_data()
    save_payload(payload)
    print("Scrape completed.")


if __name__ == "__main__":
    main()
