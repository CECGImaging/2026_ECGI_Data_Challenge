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
            "dataset": rec.get("dataset"),
            "dataset_label": rec.get("dataset_label"),
            "final_score": rec.get("final_score"),
            "num_beats": rec.get("num_beats"),
            # per-metric breakdown, shown on hover in the history table
            "components": rec.get("components"),
        })
    return out



# Rank every participant's best submission on one dataset
# ---
def _public_name(user: dict) -> str:
    """What other participants see. Usernames are email addresses on the NDP
    realm, so never show one in full: prefer the display name, else mask it"""
    if user.get("name"):
        return user["name"]
    email = user.get("email") or user.get("username") or ""
    if "@" in email:
        local, domain = email.split("@", 1)
        return f"{local[:2]}***@{domain}"
    return email or "Participant"

def leaderboard(dataset: str, viewer: dict, hide_subs=()) -> list:
    """One row per participant: their best score on this dataset, best first.
    Equal scores go to whoever got there first. Submissions by users whose
    "sub" is in hide_subs are left out. Carries no user identifiers, only a
    display name and whether the row is the viewer's own

    Nothing is cached: the board is rebuilt from the result.json files on disk
    on every call, so a new submission shows up on the next request.

    Disk layout being read (written by save_submission):
        SUBMISSIONS_DIR/<user key>/<timestamp>/result.json
    """
    if not SUBMISSIONS_DIR.is_dir():
        return []

    # Used at the end to flag the viewer's own row as "(you)"
    viewer_key = _user_key(viewer)

    # Step 1: find each participant's best submission on this dataset.
    # best = { user key: (best result record, how many results they have on this dataset) }
    best = {}
    for user_dir in SUBMISSIONS_DIR.iterdir():   # one folder per user
        if not user_dir.is_dir():
            continue

        top, count = None, 0   # this user's best record so far, and their result count
        for record_path in user_dir.glob("*/result.json"):   # one per submission
            try:
                rec = json.loads(record_path.read_text())
            except (ValueError, OSError):
                continue   # corrupt or unreadable record: skip it rather than fail the board

            # Only results scored against THIS dataset count. Datasets use
            # different metrics, so their scores can't be mixed on one board
            if rec.get("dataset") != dataset or not isinstance(rec.get("final_score"), (int, float)):
                continue
            # e.g. the dev stand-in user's test runs, once real logins are on (see main.py)
            if (rec.get("user") or {}).get("sub") in hide_subs:
                continue

            count += 1

            # Keep this record if it beats the current best. On an equal score keep
            # the EARLIER one: the timestamp (YYYY-MM-DDTHH-MM-SS-ffffff) compares
            # correctly as plain text, so a smaller string means an earlier submission
            score, ts = rec["final_score"], rec.get("timestamp", "")
            if (top is None
                    or score > top["final_score"]
                    or (score == top["final_score"] and ts < top.get("timestamp", ""))):
                top = rec

        if top is not None:   # users with nothing scored on this dataset aren't listed
            best[user_dir.name] = (top, count)

    # Step 2: order participants by their best score, highest first. Negating the
    # score makes Python's ascending sort go high -> low. On a tie, the earlier
    # timestamp sorts first, so whoever reached that score first ranks higher
    def rank_order(item):
        _user, (rec, _count) = item
        return (-rec["final_score"], rec.get("timestamp", ""))

    ranked = sorted(best.items(), key=rank_order)

    # Step 3: build the rows the browser receives. Rank is simply the position
    # (1, 2, 3, ...), so tied participants still get different ranks. Only a
    # display name goes out, never the username/email/sub (see _public_name)
    rows = []
    for position, (user, (rec, count)) in enumerate(ranked, start=1):
        rows.append({
            "rank": position,
            "participant": _public_name(rec.get("user") or {}),
            "is_you": user == viewer_key,
            "final_score": rec["final_score"],
            "components": rec.get("components"),    # per-metric breakdown for the hover card
            "num_beats": rec.get("num_beats"),
            "submissions": count,                   # all their results on this dataset, not just the best
            "created_at": rec.get("created_at"),    # when the best one was submitted
        })
    return rows
