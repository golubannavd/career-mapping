import json
import os
from datetime import datetime
from pathlib import Path

DIGESTS_DIR = Path(__file__).parent / "digests"
DIGESTS_DIR.mkdir(exist_ok=True)


def save_digest(digest: dict) -> str:
    digest_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    digest["id"] = digest_id
    path = DIGESTS_DIR / f"{digest_id}.json"
    with open(path, "w") as f:
        json.dump(digest, f, indent=2)
    return digest_id


def list_digests() -> list[dict]:
    digests = []
    for path in sorted(DIGESTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(path) as f:
                data = json.load(f)
            digests.append({
                "id": data.get("id", path.stem),
                "date": data.get("date", path.stem),
                "competitors": data.get("competitors", []),
            })
        except Exception:
            pass
    return digests


def load_digest(digest_id: str) -> dict | None:
    path = DIGESTS_DIR / f"{digest_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def delete_digest(digest_id: str) -> bool:
    path = DIGESTS_DIR / f"{digest_id}.json"
    if not path.exists():
        return False
    os.remove(path)
    return True
