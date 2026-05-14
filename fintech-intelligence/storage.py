import json
import os
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def save_report(report: dict) -> str:
    report_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report["id"] = report_id
    path = REPORTS_DIR / f"{report_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report_id


def list_reports() -> list[dict]:
    reports = []
    for path in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            reports.append({
                "id": data.get("id", path.stem),
                "date": data.get("date", path.stem),
                "competitors": data.get("competitors", []),
            })
        except Exception:
            pass
    return reports


def load_report(report_id: str) -> dict | None:
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def delete_report(report_id: str) -> bool:
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return False
    os.remove(path)
    return True
