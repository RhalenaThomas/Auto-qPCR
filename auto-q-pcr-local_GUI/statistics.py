import pandas
import pingouin as pg
from pingouin import pairwise_ttests, multicomp, ttest
from scipy.stats import mannwhitneyu, wilcoxon
import re


def stats(model, quantity, data, targets, rm, nd):
	if model == 'absolute':
		data = data.drop(['NormQuant'], axis=1)
		mean = 'NormMean'
	else:
		data = data.drop(['rq'], axis=1)
		mean = 'rqMean'

	# prepare data from intermediate dataframe
	data = data[data['Outliers'].eq(False)]
	data = data.drop_duplicates(keep='first')

	# t-test and anova for normally distributed data
	if nd == 'True':
		if quantity == 2:
			# T-Test between 2 groups
			stats_dfs = pandas.DataFrame()
			posthoc_dfs = pandas.DataFrame()
			group = data['Group']
			group = group.drop_duplicates(keep='first').values.tolist()
			for item in targets:
				df = data[data['Target Name'].eq(item)]
				group1 = df[df['Group'].eq(group[0])][mean]
				group2 = df[df['Group'].eq(group[1])][mean]
				t_test = ttest(group1, group2, paired=bool(rm))
				if rm == 'True':
					t_test['paired'] = 'TRUE'
				else:
					t_test['paired'] = 'FALSE'
				t_test['Target Name'] = item
				if stats_dfs is None:
					stats_dfs = t_test
				else:
					stats_dfs = stats_dfs.append(t_test, ignore_index=True)
			# reformat output table
			stats_dfs = stats_dfs.rename(columns={'cohen-d': 'effect size', 'BF10': 'Bayes factor', 'dof': 'DF'})
			stats_dfs = stats_dfs.drop(['T'], axis=1)
			cols = ['Target Name', 'DF', 'tail', 'paired', 'p-val', 'effect size', 'power', 'Bayes factor']
			stats_dfs = stats_dfs.reindex(columns=cols)
		elif quantity >= 3:
			# ANOVA test
			stats_dfs = pandas.DataFrame()
			posthoc_dfs = pandas.DataFrame()
			pvals = []
			for item in targets:
				if rm == 'True':
					# repeated measure anova
					aov = pg.rm_anova(dv=mean, data=data[data['Target Name'].eq(item)], within='Group', subject='Sample Name', detailed=True)
					aov = aov.drop([1])
					aov.drop(['eps'], axis=1)
					pvals.append(aov['p-unc'][0])
					aov['measures'] = ['dependent']
					ph = pairwise_ttests(data=data[data['Target Name'].eq(item)], dv=mean, within='Group',
										 subject='Sample Name', padjust='fdr_bh')
					ph['Target Name'] = item
				else:
					aov = pg.anova(dv=mean, between='Group', data=data[data['Target Name'].eq(item)], detailed=True)
					aov = aov.drop([1])
					pvals.append(aov['p-unc'][0])
					aov['measures'] = ['independent']
					ph = pairwise_ttests(data=data[data['Target Name'].eq(item)], dv=mean, between='Group', padjust='fdr_bh')
					ph['Target Name'] = item
				if stats_dfs is None:
					stats_dfs = aov
				else:
					stats_dfs = stats_dfs.append(aov, ignore_index=True)
				if posthoc_dfs is None:
					posthoc_dfs = ph
				else:
					posthoc_dfs = posthoc_dfs.append(ph, ignore_index=True)
			reject, pvals_corr = pg.multicomp(pvals, alpha=0.05, method='bonf')
			# reformat output tables
			stats_dfs = stats_dfs.drop(['F', 'Source'], axis=1)
			stats_dfs = stats_dfs.rename(columns={'p-unc': 'p-value', 'np2': 'effect size'})
			stats_dfs['Target Name'] = targets
			stats_dfs['p-value corrected'] = pvals_corr
			stats_dfs['distribution'] = ['parametric'] * len(targets)
			stats_dfs['test'] = ['ANOVA'] * len(targets)
			stats_dfs['statistic'] = ['NA'] * len(targets)
			cols = ['Target Name', 'DF', 'MS', 'SS', 'p-value', 'p-value corrected', 'measures', 'distribution', 'test',
					'statistic', 'effect size']
			stats_dfs = stats_dfs.reindex(columns=cols)

			posthoc_dfs = posthoc_dfs.drop(['Contrast', 'T'], axis=1)
			posthoc_dfs = posthoc_dfs.rename(columns={'hedges': 'effect size', 'p-corr': 'p-value corrected', 'p-unc': 'p-value',
													  'p-adjust': 'correction method', 'BF10': 'Bayes factor', 'dof': 'DF'})
			cols2 = ['Target Name', 'A', 'B', 'DF', 'p-value corrected', 'p-value', 'correction method', 'Paired', 'Parametric', 'effect size', 'Bayes factor']
			posthoc_dfs = posthoc_dfs.reindex(columns=cols2)

	# nonparametric tests for not normally distributed data
	else:
		if quantity == 2:
			stats_dfs = pandas.DataFrame()
			posthoc_dfs = pandas.DataFrame()
			group = data['Group']
			group = group.drop_duplicates(keep='first').values.tolist()
			for item in targets:
				df = data[data['Target Name'].eq(item)]
				group1 = df[df['Group'].eq(group[0])][mean]
				group2 = df[df['Group'].eq(group[1])][mean]
				if rm == 'True':
					# Mann-Whitney U test
					test = mannwhitneyu(group1, group2)
					test = pandas.DataFrame({'Target Name': item, 'pvalue': test.pvalue, 'statistic': test.statistic}, index=[0])
				else:
					test = wilcoxon(group1, group2)
					test = pandas.DataFrame({'Target Name': item, 'pvalue': test.pvalue, 'statistic': test.statistic}, index=[0])
				if stats_dfs is None:
					stats_dfs = test
				else:
					stats_dfs = stats_dfs.append(test, ignore_index=True)

		elif quantity >= 3:
			stats_dfs = pandas.DataFrame()
			posthoc_dfs = pandas.DataFrame()

			pvals = []
			for item in targets:
				if rm == 'True':
					# friedman test for repeated measurements
					df = pg.friedman(dv=mean, within='Group', subject='Sample Name', data=data[data['Target Name'].eq(item)])
					pvals.append(df['p-unc'][0])
					df['test'] = ['Friedman Q']
					df['measures'] = ['dependent']
					df = df.rename(columns={'Q': 'statistic'})
					df['Target Name'] = item
					df['DF'] = 'NA'
					ph = pairwise_ttests(data=data[data['Target Name'].eq(item)], dv=mean, within='Group',
										 subject='Sample Name', padjust='fdr_bh', parametric=False)
					ph['Target Name'] = item
					ph['DF'] = 'NA'
					ph['Bayes factor'] = 'NA'
				else:
					# Kruskal-Wallis H test
					df = pg.kruskal(dv=mean, between='Group', data=data[data['Target Name'].eq(item)])
					pvals.append(df['p-unc'][0])
					df['test'] = ['Kruskal-Wallis H']
					df['measures'] = ['independent']
					df = df.rename(columns={'H': 'statistic'})
					df['Target Name'] = item
					df['DF'] = 'NA'
					ph = pairwise_ttests(data=data[data['Target Name'].eq(item)], dv=mean, between='Group',
										 padjust='fdr_bh', parametric=False)
					ph['Target Name'] = item
					ph['DF'] = 'NA'
					ph['Bayes factor'] = 'NA'
				if stats_dfs is None:
					stats_dfs = df
				else:
					stats_dfs = stats_dfs.append(df, ignore_index=True)
				if posthoc_dfs is None:
					posthoc_dfs = ph
				else:
					posthoc_dfs = posthoc_dfs.append(ph, ignore_index=True)

			reject, pvals_corr = pg.multicomp(pvals, alpha=0.05, method='bonf')
			# reformat output tables
			stats_dfs = stats_dfs.rename(columns={'dof': 'DF', 'p-unc': 'p-value'})
			stats_dfs['p-value corrected'] = pvals_corr
			stats_dfs['distribution'] = ['non-parametric'] * len(targets)
			stats_dfs['MS'] = ['NA'] * len(targets)
			stats_dfs['SS'] = ['NA'] * len(targets)
			stats_dfs['effect size'] = ['NA'] * len(targets)
			cols = ['Target Name', 'DF', 'MS', 'SS', 'p-value', 'p-value corrected', 'measures', 'distribution',
					'test', 'statistic', 'effect size']
			stats_dfs = stats_dfs.reindex(columns=cols)

			posthoc_dfs = posthoc_dfs.drop(['Contrast'], axis=1)
			posthoc_dfs = posthoc_dfs.rename(columns={'hedges': 'effect size', 'p-corr': 'p-value corrected', 'p-unc': 'p-value',
								'p-adjust': 'correction method', 'BF10': 'Bayes factor'})
			cols2 = ['Target Name', 'A', 'B', 'DF', 'p-value corrected', 'p-value', 'correction method', 'Paired', 'Parametric',
					 'effect size', 'Bayes factor']
			posthoc_dfs = posthoc_dfs.reindex(columns=cols2)

	return stats_dfs, posthoc_dfs


# Extract groups from sample name
def add_groups(df, groups):
	df['Group'] = df['Sample Name'].str.extract(re.compile('(' + '|'.join(groups) + ')', re.IGNORECASE),
												expand=False).fillna('')
	df['Sample Name'] = df['Sample Name'].str.replace(re.compile('(' + '|'.join(groups) + ')', re.IGNORECASE), '')

	return df
