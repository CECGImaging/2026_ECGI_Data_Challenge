"""
Command-line scoring, for running a dataset's metrics outside the web app.

Run from the repo root:

    python -m app.ScoringTools.scoring_main run --dataset utah \
        --submission /path/to/unpacked/submission

The ground truth defaults to whatever that dataset's ECGI_GT_<NAME>_DIR
variable points at (see example.env); pass --ground_truth to override it.
"""

import fire

from app.ScoringTools import config
from app.ScoringTools import scoring_tools as st


def run(dataset, submission, ground_truth=None):
	"""
	Score a directory of submitted beat files against a dataset's ground truth.
	Takes:
		dataset      : which challenge dataset, e.g. utah
		submission   : directory of the submitted *-cs.mat beat files
		ground_truth : directory of the ground-truth beats, if not from the env
	"""
	if not config.is_known(dataset):
		raise SystemExit(f"Unknown dataset '{dataset}'. "
						 f"Choose one of: {', '.join(config.DATASETS)}")

	ground_truth = ground_truth or config.ground_truth_dir(dataset)
	if not ground_truth:
		raise SystemExit(f"No ground truth for '{dataset}'. Pass --ground_truth, "
						 f"or set {config.DATASETS[dataset]['env']}.")

	truth = st.load_data(ground_truth, config.DATA_FILE_PATTERN)
	solutions = st.load_data(submission, config.DATA_FILE_PATTERN)
	combined_score, _ = config.scorer(dataset)(truth, solutions)
	print(f"{config.label(dataset)} score: {combined_score}")
	return combined_score


def datasets():
	"""List the challenge datasets and whether each one is configured here."""
	for info in config.describe_all():
		state = "available" if info["available"] else "not configured"
		print(f"{info['key']:<12} {info['label']:<12} {state}")


if __name__ == "__main__":
	fire.Fire({"run": run, "datasets": datasets})
