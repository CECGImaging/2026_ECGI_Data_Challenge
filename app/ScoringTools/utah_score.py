import numpy as np
import numpy.typing as npt
import scipy.io as scio
import glob, os

class UtahDataError(Exception):
    """Raised when Utah Data Scoring fails."""
    pass

from .config import TRUE_DATA_DIR, TRUE_DATA_FILES
#TRUE_DATA_DIR="/uufs/sci.utah.edu/projects/comp-cardio/ECGI_Challenge/UtahDataset/Train/Beats/"
#TRUE_DATA_FILES="*-cs.mat"
VERBOSE=True

def log(message):
	"""
	TODO:Document
	"""
	if VERBOSE:
		print(message)

def calculate_correlation(signal1: npt.NDArray[np.floating],
						  signal2: npt.NDArray[np.floating]) -> npt.NDArray[np.floating]:
	'''
	Calculates correlation between two signals.
	Takes:
		signal1: (n) numpy array of length n
		signal2: (m) numpy array of length m (can be equal to n)
	'''
	signal1 = np.squeeze(signal1)
	signal2 = np.squeeze(signal2)

	if len(signal1.shape)>1 or len(signal2.shape)>1:
		raise UtahDataError('Correlation calculation requires both signals to be 1D')

	if signal1.shape[0] != signal2.shape[0]:
		len_1 = signal1.shape[0]
		len_2 = signal2.shape[0]
		len_diff = len_1-len_2
		if len_diff > 0:#signal 1 longer, pad signal 2
			signal2 = np.concatenate((signal2,np.zeros(len_diff)))
		else:#signal 2 longer, pad signal 1
			signal1 = np.concatenate((signal1,np.zeros(-len_diff)))

	sig1_norm = np.linalg.norm(signal1)
	sig2_norm = np.linalg.norm(signal2)
	if sig1_norm == 0 and sig2_norm == 0:
		corrVal = 1
	elif sig1_norm == 0 or sig2_norm == 0:
		corrVal = 0
	else:
		corrVal = signal1@signal2/(sig1_norm*sig2_norm)
	return corrVal

def calc_spatial_correlation(sig1,sig2):
	"""
	TODO:Document
	"""
	log("\tCalculating Spatial Correlation")
	correlations = np.empty(sig1.shape[1],dtype=np.float64)
	for time_index in range(sig1.shape[1]):
		correlations[time_index] = calculate_correlation(sig1[:,time_index],
														 sig2[:,time_index])
	final_corr = np.mean(correlations)
	return final_corr, correlations

def calc_temporal_correlation(sig1,sig2):
	"""
	TODO:Document
	"""
	log("\tCalculating Temporal Correlation")
	correlations = np.empty(sig1.shape[0],dtype=np.float64)
	for node_index in range(sig1.shape[0]):
		correlations[node_index] = calculate_correlation(sig1[node_index,:],
														 sig2[node_index,:])
	final_corr = np.mean(correlations)
	return final_corr, correlations

def calc_RMSE(sig1,sig2):
	"""
	TODO:Document
	"""
	log("\tCalculating RMSE")
	return np.sqrt(np.sum(np.power(sig1-sig2,2))/sig1.size)

def validate_inputs(true_data,given_data):
  """
  TODO:Document
  """
  log("Validating inputs")
  #check for empty inputs
#  print(true_data.keys())
#  print(true_data["potvals"])
#  print(given_data["potvals"])
  if len(true_data) == 0 or len(given_data) == 0:
    raise UtahDataError("Missing data"
              f"\n\tNum True Data: {len(true_data)}"
              f"\n\tNum Test Data: {len(given_data)}")
  #check for equal number of beats
  if len(true_data) != len(given_data):
    raise UtahDataError("Data lengths do not match"
              f"\n\tExpected: {len(true_data)}"
              f"\n\tGot     : {len(given_data)}")
  #check all beats have the same dimensions
  for sigIndex,(true_signal,given_signal) in enumerate(zip(true_data,given_data)):
    if true_signal['potvals'].shape != given_signal['potvals'].shape:
      raise UtahDataError(f"Signals at index {sigIndex} size did not match."
                f"\n\tExpected:{true_signal['potvals'].shape}"
                f"\n\tGot     :{given_signal['potvals'].shape}")

def load_truth():
	"""
	TODO:Document
	"""
	log("Loading true data")
	true_data = []
	pattern = f"{TRUE_DATA_DIR}{TRUE_DATA_FILES}"
	dataFiles = [os.path.abspath(name) for name in glob.glob(pattern)]
	log(f"\tFound {len(dataFiles)} files")
	for file in dataFiles:
		raw_mat = scio.loadmat(file,squeeze_me=True,struct_as_record=False)
		true_data.append({'potvals':raw_mat['ts'].potvals,
						  'file':raw_mat['ts'].filename,
						  'leadinfo':raw_mat['ts'].leadinfo})
	return true_data
	
def normalize_RMSE(RMSES):
	"""
	TODO:Document
	"""
	log('\tNormalizing RMSE')
	RMSES = np.mean(RMSES)
	#TODO implement norm
	maxValue = 1.0
	RMSE_norm = 1.0-(RMSES / maxValue)
	return RMSE_norm

def combine_scores(all_scores):
	"""
	TODO:Document
	"""
	log("Combining scores")
	total_score = 0
	for score in all_scores.keys():
		value = all_scores[score]['value']
		if all_scores[score]['norm'] is not None:
			value = all_scores[score]['norm'](value)
		total_score = total_score + value*all_scores[score]['weight']
	return total_score


def run_score(given_answer):
	"""
	TODO:Document
	"""

	#Load the true data
	true_data = load_truth()
	#ensure given and true data look correct (structurally)
	validate_inputs(true_data,given_answer)

	#initilize score arrays
	number_of_beats = len(true_data)
	spatial_correlations = np.empty(number_of_beats,dtype=np.float64)
	temporal_correlations = np.empty(number_of_beats,dtype=np.float64)
	RMSEs = np.empty(number_of_beats,dtype=np.float64)

	#For each signal, calculate the scores
	for sigIndex,(true_signal,given_signal) in enumerate(zip(true_data,given_answer)):
		log(f"Working on signal {sigIndex+1} of {number_of_beats}")
		#Spatial Correlation
		spatial_correlations[sigIndex], _ = calc_spatial_correlation(true_signal['potvals'],
																	 given_signal['potvals'])
		#Temporal Correlation
		temporal_correlations[sigIndex], _ = calc_temporal_correlation(true_signal['potvals'],
																	   given_signal['potvals'])
		#RMSE
		RMSEs[sigIndex] = calc_RMSE(true_signal['potvals'],
									given_signal['potvals'])

	#Create the all_scores dictionary expected by the combining function
	all_scores = {"SC":{"value":spatial_correlations,
						"weight":1/3,
						"norm":np.mean},
				  "TC":{"value":temporal_correlations,
						"weight":1/3,
						"norm":np.mean},
				  "RMSE":{"value":RMSEs,
						"weight":1/3,
						"norm":normalize_RMSE}}
	#Combine all of the scores
	final_score = combine_scores(all_scores)
	return final_score, all_scores

if __name__=="__main__":
	"""
	TODO:Document
	"""
	#Just run on the true data if called directly. Should give a perfect score
	log("Running on true data")
	data = load_truth()
	final_score,all_scores = run_score(data)
	log(f"Final score {final_score}")

