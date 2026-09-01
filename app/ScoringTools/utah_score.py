import scoring_tools as st
import numpy as np
import fire

from .config import TRUE_DATA_DIR, TRUE_DATA_FILES
#TRUE_DATA_DIR="/uufs/sci.utah.edu/projects/comp-cardio/ECGI_Challenge/UtahDataset/Train/Beats/"
#TRUE_DATA_FILES="*-cs.mat"
VERBOSE=True

class UtahDataError(Exception):
    """Raised when Utah Data Scoring fails."""
    pass


def run_utah_score(truth,solutions):
	metrics = {	"SC":{"weight":1/6,
					 "norm":np.mean,
					 "run":st.calc_spatial_correlation},
				"TC":{"weight":1/6,
					 "norm":np.mean,
					 "run":st.calc_temporal_correlation},
				"RMSE":{"weight":1/6,
					 "norm":st.normalize_RMSE,
					 "run":st.calc_RMSE},
				"LocErr":{"weight":1/2,
					 "norm":st.normalize_LocErr,
					 "run":st.calc_LocErr}}
	combined_score, all_scores = st.run_score(truth,solutions,metrics=metrics)
	st.log(f"Combined score {combined_score}")
	for metric in all_scores.keys():
		st.log(f"{metric}:{np.mean(all_scores[metric]['value'])}")
	return combined_score, all_scores


if __name__=="__main__":
	"""
	TODO:Document
	"""
	#Just run on the true data if called directly. Should give a perfect score
	fire.Fire({"run":run_utah_score})

