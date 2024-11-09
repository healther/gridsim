import datetime
from pprint import pprint


from data.energy_charts import acquire_data
from grid.grid import run_simulation, Compensate
from grid.report import analyse, find_shortfalls, find_compensate_time
from utils.plot import plot_shortfalls, plot_shortfalls_timecourse


from line_profiler import profile


@profile
def main():
	use_sources = {
	    'solar': ['Solar'],
	    'wind_on': ['Wind onshore'],
	    'wind_off': ['Wind offshore'],
	    'hydro': ['Hydro Run-of-River', 'Hydro water reservoir'],
	    'load': ['Load'],
	    'price': ['Day Ahead Auction'],
	}


	data, capacity = acquire_data(use_sources, '..')

	st_pow = 100.
	m_cap = 0.
	solarpower = 200.
	wind_on_power = 130.
	wind_of_power = 60.
	times, storages, loads, production, battery, others = run_simulation(
	                        data,
	                        capacity,
	                       {'sources': ['solar', 'wind_on', 'wind_off', 'hydro'],
	                        'storage': {'max_power': st_pow, 'max_capacity': m_cap, 'efficiency': 0.9},
	                        'capacity': {'solar': solarpower, 'wind_on': wind_on_power, 'wind_off': wind_of_power},
	                       },
	                        nsteps=1000000,
	                        simstart=datetime.datetime(year=2022, month=1, day=1))
	shortfalls = find_shortfalls(times, others)
	for s in shortfalls:
		print(find_compensate_time(s, 2000., 20.))
	# pprint(
	# 	shortfalls
	# )
	print(len(shortfalls))
	# plot_shortfalls(shortfalls)

	# plot_shortfalls_timecourse(shortfalls, times, storages, loads, production, battery, others, maxstorage=m_cap)

	res = analyse(storages, loads, production, battery, others)
	res['solar'] = solarpower
	res['wind_on'] = wind_on_power
	res['wind_of'] = wind_of_power
	res['storage_power'] = st_pow
	res['storage_capacity'] = m_cap
	print(res)
	return shortfalls

	print(find_minimal_compensate(shortfalls, m_cap))

	return
	compensates = [Compensate(s, 3) for s in find_shortfalls(times, others)]
	pprint(compensates)
	times, storages, loads, production, battery, others = run_simulation(
	                        data,
	                        capacity,
	                       {'sources': ['solar', 'wind_on', 'wind_off', 'hydro'],
	                        'storage': {'max_power': st_pow, 'max_capacity': m_cap, 'efficiency': 0.9},
	                        'capacity': {'solar': solarpower, 'wind_on': wind_on_power, 'wind_off': wind_of_power},
	                       },
	                        nsteps=1000000,
	                        simstart=datetime.datetime(year=2022, month=1, day=1),
	                        compensates=compensates)

	shortfalls = find_shortfalls(times, others)
	pprint(
		shortfalls
	)
	print(len(shortfalls))
	# plot_shortfalls(shortfalls)

	plot_shortfalls_timecourse(shortfalls, times, storages, loads, production, battery, others, maxstorage=m_cap, dt=72)
	res = analyse(storages, loads, production, battery, others)
	res['solar'] = solarpower
	res['wind_on'] = wind_on_power
	res['wind_of'] = wind_of_power
	res['storage_power'] = st_pow
	res['storage_capacity'] = m_cap
	print(res)


if __name__ == '__main__':
	main()
