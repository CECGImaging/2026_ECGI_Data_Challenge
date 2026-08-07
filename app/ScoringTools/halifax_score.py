import scoring_tools as st
import numpy as np
import fire

class UtahDataError(Exception):
    """Raised when Utah Data Scoring fails."""
    pass


def run_halifax_score(truth,solutions):
	metrics = {"LocErr":{"weight":1.0,
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
	
	fire.Fire({"run":run_halifax_score})

