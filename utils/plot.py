import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from scipy.signal import correlate, correlation_lags


from line_profiler import profile


# class ShortFall:
    # def __init__(self, t, s):
    #     self.start = t
    #     self.end = None
    #     self.deficits = [s]
def plot_shortfalls(shortfalls, name=None):
	hours = []
	deficits = []
	for s in shortfalls:
		hours.append(s.get_duration_in_hours())
		# deficits.append(s.get_average_deficit_in_GW())
		deficits.append(s.get_deficit_in_GWh())

	fig = plt.figure()
	ax = fig.add_subplot(111)
	ax.plot(hours, deficits, 'x')
	ax.set_xlabel('Shortfall duration [hour]')
	ax.set_ylabel('Shortfall size [GWh]')
	if name:
		plt.savefig(name)
	else:
		plt.savefig('plots/bla.pdf')
	plt.close()


def get_cumdev(shortfalls, times, production, loads):
	cumdef = []
	sind = 0
	is_shortfall = False
	for i, t in enumerate(times):
		if sind >= len(shortfalls):
			cumdef.append(0.)
			continue
		if t >= shortfalls[sind].start:
			sind += 1
			is_shortfall = True
		if is_shortfall:
			if t >= shortfalls[sind-1].end:
				is_shortfall = False
			cumdef.append(cumdef[-1] + production[i] - loads[i])
		else:
			cumdef.append(0.)

	return -np.array(cumdef)


@profile
def plot_shortfalls_timecourse(shortfalls, times, storages, loads, production, battery, others, maxstorage, dt=24.):
	fig = plt.figure()
	ax = fig.add_subplot(111)
	ax.plot(times, np.array(loads) / 1000., label='load')
	ax.plot(times, np.array(production) / 1000., label='production')
	ax.plot(times, np.array(battery) / 1000., label='battery')
	ax.set_ylabel('Power [GW]')
	ax.set_xlabel('Time')
	ax2 = ax.twinx()
	ax2.plot(times, np.array(storages) / 1000. / 4., '--', color='C4', label='storage')
	cumdef = get_cumdev(shortfalls, times, production, loads) / 1000. / 4.
	ax2.plot(times, cumdef, '--', color='C5')
	ax2.set_ylabel('Storage [GWh]')
	ax2.axhline(maxstorage)
	ax.legend()
	ax.tick_params(axis='x', labelrotation=45)
	plt.tight_layout()

	with PdfPages('plots/shortfalls.pdf') as pdf:
		for s in shortfalls:
			start = s.start - datetime.timedelta(hours=dt)
			end = s.end + datetime.timedelta(hours=dt)
			ax.axvline(s.start, color='C8')
			ax.axvline(s.end, color='C9')
			ax.set_xlim(start, end)
			pdf.savefig()

	    # # We can also set the file's metadata via the PdfPages object:
	    # d = pdf.infodict()
	    # d['Title'] = 'Multipage PDF Example'
	    # d['Author'] = 'Jouni K. Sepp\xe4nen'
	    # d['Subject'] = 'How to create a multipage pdf file and set its metadata'
	    # d['Keywords'] = 'PdfPages multipage keywords author title subject'
	    # d['CreationDate'] = datetime.datetime(2009, 11, 13)
	    # d['ModDate'] = datetime.datetime.today()

	plt.close()

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
