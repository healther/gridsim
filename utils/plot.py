import datetime
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import correlate, correlation_lags



def plot_acf(valuedict, name=None, window_in_days=30.):
	times = sorted(list(valuedict.keys()))
	dt = (times[1]-times[0]).total_seconds()
	values = np.array([valuedict[t] for t in times])
	values -= values.mean()

	lags = correlation_lags(len(values), len(values)) * dt / (24 * 60 * 60)
	corr = correlate(values, values)
	corr /= corr.max()

	fig = plt.figure()
	ax = fig.add_subplot(111)
	ax.plot(lags, corr)
	ax.set_xlim(0., window_in_days)

	if name:
		plt.savefig(name)
	else:
		plt.savefig('bla.pdf')
	plt.close()


def plot_2d_time_per_day(valuedict, name=None):
	times = valuedict.keys()
	dates = set()
	daytimes = set()
	for t in times:
		dates.add(t.date())
		daytimes.add(t.time())

	dates = sorted(list(dates))
	daytimes = sorted(list(daytimes))

	plotdata = np.zeros((len(dates), len(daytimes)))
	pdates = []
	ptimes = []
	pvalues = []
	for t, v in valuedict.items():
		d = t.date()
		dt = t.time()
		plotdata[dates.index(d), daytimes.index(dt)] = v
		pdates.append(d)
		ptimes.append(t)
		pvalues.append(v)

	fig = plt.figure()
	ax = fig.add_subplot(111)
	tc = ax.tricontourf([p.toordinal() for p in pdates],
				   [(t.hour * 60 + t.minute) * 60 + t.second for t in ptimes],
				   pvalues)
	# TODO: This generates a warning.. Just use better labels..
	ax.set_xticklabels([datetime.date.fromordinal(int(o)) for o in ax.get_xticks()])
	ax.set_yticklabels([datetime.time(hour=int((o%86400)//3600),
									  minute=int((o%3600)//60),
									  second=int(o%60)) for o in ax.get_yticks()])
	plt.colorbar(tc)
	if name:
		plt.savefig(name)
	else:
		plt.savefig('bla.pdf')
	plt.close()
