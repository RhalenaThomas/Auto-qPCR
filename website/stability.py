import pandas
import numpy as np


def process(data , csample):
	outlier_data = data[data['Outliers'].eq(True)]
	data = data[data['Outliers'].eq(False)]

	# Calculate CT Mean (Endogenous Control Mean) and SSD for all Controls

	control_filter = (data['Control'].eq(True))
	data_controls_grouped = data[control_filter].groupby(['Target Name' , 'Sample Name'], sort=False).agg(
		{'CT': [np.size , 'mean' , 'std']})

	# print("Endogenous Control CT Means and SSD")
	# print(data_controls_grouped)

	data_controls_ct = data[control_filter].groupby(['Sample Name'], sort=False).agg({'CT': 'mean'})

	# print("Combined Endogenous Control CT Means and SSD")
	# print(data_controls_ct)

	# Create deltaCT column
	for i , row in enumerate(data_controls_ct.itertuples(name=None) , 1):
		name_filter =  (data['Sample Name'] == row[0])
		for j in data[name_filter].index:
			data.loc[j , 'deltaCT'] = data.loc[j , 'CT'] - row[1]

	# Mark the Control Samples
	data['ControlSample'] = data['Sample Name'].apply(lambda x: True if x.lower() in csample.lower() else False)
	filter_sample = (data['ControlSample'].eq(True))
	data_sampled = data[filter_sample].groupby(['Target Name']).agg({('deltaCT'): 'mean'})

	# print("Mean Control Sample Delta CT")
	# print(data_sampled)

	for i , row in enumerate(data_sampled.itertuples(name=None) , 1):
		target_filter = (data['Target Name'] == row[0])
		for j in data[target_filter].index:
			data.loc[j , 'rq'] = np.power(2 , -(data.loc[j , 'deltaCT'] - row[1]))

	# Calculate the SEM for technical replicate groups
	targets = data['Target Name'].drop_duplicates(keep='first').values
	mean_sem_result = {}
	for target in targets:
		mean_sem_result[target] = {}
		samples = data[data['Target Name'] == target]['Sample Name'].drop_duplicates(keep='first').values
		for sample in samples:
			target_sample_data = data[(data['Target Name'] == target) & (data['Sample Name'] == sample)]
			mean = target_sample_data['rq'].mean()
			sdt_dev = target_sample_data['rq'].std()
			std_err = target_sample_data['rq'].sem()
			mean_sem_result[target][sample] = (mean , sdt_dev , std_err)
	for i_row , row in data.iterrows():
		if data.at[i_row , 'Sample Name'] in samples and data.at[i_row , 'Sample Name'] in samples and data.at[
			i_row , 'Target Name'] in mean_sem_result and data.at[i_row , 'Sample Name'] in mean_sem_result[
			data.at[i_row , 'Target Name']]:
			data.at[i_row , 'rqMean'] = mean_sem_result[data.at[i_row , 'Target Name']][data.at[i_row , 'Sample Name']][0]
			data.at[i_row , 'rqSD'] = mean_sem_result[data.at[i_row , 'Target Name']][data.at[i_row , 'Sample Name']][1]
			data.at[i_row , 'rqSEM'] = mean_sem_result[data.at[i_row , 'Target Name']][data.at[i_row , 'Sample Name']][
				2]
	# indel column: threshold=0.3
	data['Indel'] = data['rq'].apply(lambda x: 'Insertion' if x > 1.3 else ('Deletion' if x < 0.7 else 'Normal'))

	# Making the intermediate dataframe
	data = data.append(outlier_data)
	cols = ['Target Name', 'Sample Name', 'rq', 'rqMean', 'rqSD', 'rqSEM', 'Outliers', 'Indel']
	df = pandas.DataFrame(columns=cols)
	for item in cols:
		df[item] = data[item]
	df.reset_index(drop=True , inplace=True)

	data_output_summary = data.groupby(['Target Name' , 'Sample Name'], sort=False).agg(
		{'rq': [np.size , 'mean'] , 'rqSD': 'mean' , 'rqSEM': 'mean'})

	return df, data_output_summary, targets, samples