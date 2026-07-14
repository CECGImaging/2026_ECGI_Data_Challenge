import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path


# Config
# ---
UTAH_TZ = ZoneInfo( "America/Denver" )
SUBMISSIONS_DIR = Path( "/data/submissions" ) # container volume
SAFE = re.compile( r"[^A-Za-z0-9_.@-]+" )



# Util functions for handling file paths and user data
# ---
def _safe(name: str) -> str:
    """Make a string safe to use as a single path segment"""
    return SAFE.sub("_", (name or "unknown")).strip("_.") or "unknown"

def _user_key(user: dict) -> str:
    return _safe(user.get("username") or user.get("sub") or "unknown")



# Save a user's submission to the file system
# ---
def save_submission(user: dict, filename: str, zip_bytes: bytes, result: dict) -> Path:
    """Write the uploaded zip and a result.json record. Returns the folder path"""
    now = datetime.now(UTAH_TZ)
    ts = now.strftime("%Y-%m-%dT%H-%M-%S-%f")

    folder = SUBMISSIONS_DIR / _user_key(user) / ts
    folder.mkdir(parents=True, exist_ok=True)
    (folder / _safe(filename)).write_bytes(zip_bytes)

    record = {
        "user": user,
        "filename": filename,
        "timestamp": ts,
        "created_at": now.isoformat(),
        **result,
    }
    (folder / "result.json").write_text(json.dumps(record, indent=2))
    return folder



# List a user's past submission
# ---
def list_submissions(user: dict) -> list:
    """Return this user's past submissions, newest first (summary fields only)"""
    base = SUBMISSIONS_DIR / _user_key(user)
    if not base.is_dir():
        return []

    out = []
    for folder in sorted(base.iterdir(), reverse=True):
        record_path = folder / "result.json"
        if not record_path.is_file():
            continue
        try:
            rec = json.loads(record_path.read_text())
        except (ValueError, OSError):
            continue
        out.append({
            "timestamp": rec.get("timestamp"),
            "created_at": rec.get("created_at"),
            "filename": rec.get("filename"),
            "final_score": rec.get("final_score"),
            "num_beats": rec.get("num_beats"),
        })
    return out
