"""
Registry of the ground-truth datasets the app can score against.

Host-side ground-truth locations are never hard-coded here or anywhere else in
the repo, so nothing about a deployment's data layout ends up in version
control. The container-side paths are a fixed internal convention.

To bring a dataset online, mount its ground-truth beats at
/data/ground-truth/<key> inside the container (see docker-compose.yml and
example.env). That container path is fixed, not deployment configuration; the
ECGI_GT_<NAME>_DIR variable overrides it if a deployment needs a different
layout. A dataset whose directory holds no matching beat files is simply
reported as unavailable to the UI.
"""

import os

from app.ScoringTools import scoring_tools as st
from app.ScoringTools import (
    auckland_score,
    bratislava_score,
    halifax_score,
    utah_score,
)

# Beat files, in the ground truth and in a submission, are named *-cs.mat for
# every dataset. This is a naming convention, not deployment configuration.
DATA_FILE_PATTERN = st.DATA_FILE_PATTERN

# key -> how to present it, where to look for it, and how to score it.
DATASETS = {
    "utah": {
        "label": "Utah",
        "env": "ECGI_GT_UTAH_DIR",
        "run": utah_score.run_utah_score,
    },
    "auckland": {
        "label": "Auckland",
        "env": "ECGI_GT_AUCKLAND_DIR",
        "run": auckland_score.run_auckland_score,
    },
    "halifax": {
        "label": "Halifax",
        "env": "ECGI_GT_HALIFAX_DIR",
        "run": halifax_score.run_halifax_score,
    },
    "bratislava": {
        "label": "Bratislava",
        "env": "ECGI_GT_BRATISLAVA_DIR",
        "run": bratislava_score.run_bratislava_score,
    },
}


def is_known(key: str) -> bool:
    """True if key names one of the challenge datasets."""
    return key in DATASETS


def label(key: str) -> str:
    """Human-readable name, e.g. 'utah' -> 'Utah'."""
    return DATASETS[key]["label"]


def scorer(key: str):
    """The run_<dataset>_score function for this dataset."""
    return DATASETS[key]["run"]


# Where docker-compose.yml mounts each dataset. Internal to the container.
GT_ROOT = "/data/ground-truth"


def ground_truth_dir(key: str) -> str:
    """
    Where this dataset's ground truth lives inside the container. Defaults to
    the path docker-compose.yml mounts it at; the dataset's ECGI_GT_<NAME>_DIR
    variable overrides that. Read fresh each call so the value never has to be
    baked in at import time.
    """
    return os.environ.get(DATASETS[key]["env"]) or os.path.join(GT_ROOT, key)


def is_available(key: str) -> bool:
    """
    True if this dataset can actually be scored right now: its directory holds
    at least one beat file. Says nothing about where that directory is.
    """
    directory = ground_truth_dir(key)
    return bool(directory) and bool(st.find_data_files(directory, DATA_FILE_PATTERN))


def describe_all() -> list:
    """
    The dataset list for the UI. Deliberately carries no paths -- the browser
    only ever learns a dataset's key, its name, and whether it is scorable.
    """
    return [{"key": key,
             "label": info["label"],
             "available": is_available(key)}
            for key, info in DATASETS.items()]
