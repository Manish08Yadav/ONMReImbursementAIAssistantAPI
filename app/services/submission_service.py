
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[2]
SUBMISSIONS_FILE = BASE_DIR / "submitted_claims.json"


def load_submissions() -> list:
    if not SUBMISSIONS_FILE.exists():
        return []

    with SUBMISSIONS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def submit_claim(bill_details: dict, claim_result: dict) -> dict:
    submissions = load_submissions()

    submission = {
        "submission_id": str(uuid4()),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "Submitted",
        "bill_details": bill_details,
        "claim_result": claim_result,
    }

    submissions.append(submission)

    with SUBMISSIONS_FILE.open("w", encoding="utf-8") as file:
        json.dump(submissions, file, indent=2, ensure_ascii=False)

    return submission
