import numpy as np
import numpy.typing as npt
import scipy.io as scio
import glob, os
import zipfile
import io
import fnmatch

class ECGIDataException(Exception):
    """Raised when Utah Data Scoring fails."""
    pass

DATA_FILE_PATTERN="*-cs.mat"
VERBOSE=True

def log(message,ending="\n"):
	"""
	Log messages if the VERBOSE flag is set.
	Takes:
		message : anything to be printed
	"""
	if VERBOSE:
		print(message, end=ending, flush=True)

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

	#Ensure both are 1D signals.
	if len(signal1.shape)>1 or len(signal2.shape)>1:
		raise UtahDataError('Correlation calculation requires both signals to be 1D')
	#pad a signal that is shorter if needed
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

def calc_spatial_correlation(data1,data2):
	"""
	TODO:Document
	"""
	sig1 = data1['potvals']
	sig2 = data2['potvals']
	log("\tCalculating Spatial Correlation")
	correlations = np.empty(sig1.shape[1],dtype=np.float64)
	for time_index in range(sig1.shape[1]):
		correlations[time_index] = calculate_correlation(sig1[:,time_index],
														 sig2[:,time_index])
	final_corr = np.mean(correlations)
	return final_corr

def calc_temporal_correlation(data1,data2):
	"""
	TODO:Document
	"""
	sig1 = data1['potvals']
	sig2 = data2['potvals']
	log("\tCalculating Temporal Correlation")
	correlations = np.empty(sig1.shape[0],dtype=np.float64)
	for node_index in range(sig1.shape[0]):
		correlations[node_index] = calculate_correlation(sig1[node_index,:],
														 sig2[node_index,:])
	final_corr = np.mean(correlations)
	return final_corr

def calc_RMSE(data1,data2):
	"""
	TODO:Document
	"""
	sig1 = data1['potvals']
	sig2 = data2['potvals']
	log("\tCalculating RMSE")
	return np.sqrt(np.sum(np.power(sig1-sig2,2))/sig1.size)

def calc_LocErr(data1,data2):
	"""
	TODO:Document
	"""
	true_loc = data1['pacingLoc']
	given_loc = data2['pacingLoc']
	log("\tCalculating Localization Error")
	return np.linalg.norm(true_loc - given_loc)

def validate_inputs(true_data,given_data):
	"""
	TODO:Document
	"""
	log("Validating inputs")
	#check for empty inputs
	if len(true_data) == 0 or len(given_data) == 0:
		raise ECGIDataException("Validation Check:\n"
							    "\tMissing data"
							f"\n\tNum True Data: {len(true_data)}"
							f"\n\tNum Test Data: {len(given_data)}")
	
	#check for equal number of beats
	if len(true_data) != len(given_data):
		raise ECGIDataException("Validation Check:\n"
							    "\tData lengths do not match"
							f"\n\tExpected: {len(true_data)}"
							f"\n\tGot     : {len(given_data)}")
	
	#check all beats have the same dimensions
	for sigIndex,(true_signal,given_signal) in enumerate(zip(true_data,given_data)):
		if given_signal['potvals'] is None:#only check if given signals have potvals
			log(f"One or more given signals does not have defined potential reconstruction {sigIndex}")
			break
		if true_signal['potvals'].shape != given_signal['potvals'].shape:
			raise ECGIDataException("Validation Check:\n"
							    f"\tSignals at index {sigIndex} size did not match."
								f"\n\tExpected:{true_signal['potvals'].shape}"
								f"\n\tGot     :{given_signal['potvals'].shape}")
	
	#check all beats have a defined pacing loc for true data
	for signalIndex,thisSignal in enumerate(true_data):
		if thisSignal['pacingLoc'] is None:
			raise ECGIDataException("Validation Check:\n"
							       f"\tTrue data missing pacing location for beat {signalIndex}: {thisSignal['file']}")
		if thisSignal['pacingLoc'].shape != (3,):
			raise ECGIDataException("Validation Check:\n"
							       f"\tTrue data incorrect pacing/pvc site shape {signalIndex}: {thisSignal['file']} : {thisSignal['pacingLoc'].shape }")
	#check all beats have a defined pacing loc for given data
	for signalIndex,thisSignal in enumerate(given_data):
		if thisSignal['pacingLoc'] is None:
			raise ECGIDataException("Validation Check:\n"
							       f"\tGiven data missing pacing location for beat {signalIndex}: {thisSignal['file']}")
		if thisSignal['pacingLoc'].shape != (3,):
			raise ECGIDataException("Validation Check:\n"
							       f"\tGiven data incorrect pacing/pvc site shape signal: {signalIndex} file : {thisSignal['file']} shape : {thisSignal['pacingLoc'].shape }")


def load_data(dataDir,dataPattern=DATA_FILE_PATTERN):
	"""
	TODO:Document
	"""
	log("Loading data")
	loaded_data = []
	fullFilePattern = f"{dataDir}{dataPattern}"
	log(f"\tLooking with pattern {fullFilePattern}")
	dataFiles = [os.path.abspath(name) for name in glob.glob(fullFilePattern)]
	log(f"\tFound {len(dataFiles)} files")
	for file in dataFiles:
		log(f"\r\033[K\tLoading file: {file}", ending="")
		raw_mat = scio.loadmat(file,squeeze_me=True,struct_as_record=False)
		loaded_data.append({'potvals':np.squeeze(raw_mat['ts'].potvals),
						  'file':os.path.basename(file),
						  'pacingLoc':np.squeeze(raw_mat['ts'].pacingLoc)})
	log("\n\tDone loading")
	return loaded_data

def normalize_LocErr(LocErrors):
	LocErrors_norm = np.mean(LocErrors)
	return LocErrors_norm

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


def run_score(true_data,given_data,metrics={}):
	"""
	TODO:Document
	"""
	log("=======Running Score Calculation=======")
#	log(f"Ground truth data source: {true_data_dir}")
#	log(f"Solution data source: {given_data_dir}")
	log("Calculating the following metrics:")
	[log(f"\t{metric}") for metric in metrics.keys()]
	log("Begin\n")

	#Load the true data
#	true_data = load_data(true_data_dir)
#	given_data = load_data(given_data_dir)

	#ensure given and true data look correct (structurally)
	validate_inputs(true_data,given_data)

	#initilize score arrays
	number_of_beats = len(true_data)
	all_scores = {}
	for metricName in metrics.keys():
		metricScore = { "value":np.empty(number_of_beats,dtype=np.float64),
						"weight":metrics[metricName]["weight"],
						"norm":metrics[metricName]["norm"]}
		all_scores[metricName] = metricScore
	


	#For each signal, calculate the scores
	for sigIndex,(true_signal,given_signal) in enumerate(zip(true_data,given_data)):
		log(f"Working on signal {sigIndex+1} of {number_of_beats}")
		assert true_signal['file'] == given_signal['file'] , f"File names do not match True: {true_signal['file']} given: {given_signal['file']}"
		for metricName in metrics.keys():
			all_scores[metricName]['value'][sigIndex] = metrics[metricName]["run"](true_signal,given_signal)

	#Combine all of the scores
	combined_score = combine_scores(all_scores)
	return combined_score, all_scores

if __name__=="__main__":
	"""
	TODO:Document
	"""
	print("This is a helper module with functions to help run scoring of the ECGI data")
