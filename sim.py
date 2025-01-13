




# [simulation]

# grid = Grid(
# 	historic_production,
# 	historic_production_capacity,
# )


# grid.set_capacity(
# 	renewable_capacity, 
# 	battery_capacity, 
# 	extra_capacity
# )

# # simulates the timeframe covering historic_production
# power_data = grid.simulate(
#       # optional
# 	timeframe,
# )
# analysis(power_data)



# [grid.simulate]
# simulate(
# 	historic_data,       # historic_production_capacity,
# 	renewable_capacity,
# 	battery_config,
# 	extra_capacity
# ):
# 	power_data = PowerData(
# 		battery_config.power,
# 		battery_config.capacity,
# 	)

# 	for t, h_prod, h_prod_cap, h_load in historic_data:

# 		s_prod = get_production(
# 			t,
# 			h_prod,
# 			historic_production_capacity,
# 			renewable_capacity,
# 			battery_capacity,
# 		)

# 		power_data.add(
# 			t,
# 			load,
# 			s_prod,
# 		)

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.INFO)

from grid import history, grid
from line_profiler import profile

import datetime

@profile
def main():
	logging.debug("Bla")
	logging.warning("Blab")
	historic_data = history.HistoricData(start=history.datetime.datetime(2022, 1, 1))
	if historic_data._missing:
		historic_data.initalize(query_api=True)
	historic_data.prepare(history.DEFAULT_KEYS)
	# for i, (t, p, c) in enumerate(historic_data):
	# 	print(datetime.datetime.fromtimestamp(t), p, c)
	# 	if i>40:
	# 		break
	renewable_capacity = (
		6.5, # 6.439, # hydro
		220.0, # 160.0, # 96.095, # solar
		150.0, # 100.0, # 62.67, # wind_on
		40.0, # 20.0, # 9.215, # wind_of
		)
	if len(renewable_capacity) != len(historic_data.keys()[1])-1:
		# historic_data also provides the load
		raise ValueError(f"Wrong number of entries for renewable_capacity {len(renewable_capacity)} {len(historic_data.keys()[1])-1} {historic_data.keys()}")
	power_data = grid.simulate(historic_data, renewable_capacity)
	power_data.finalize()
	# print(power_data.return_deficits())
	# print(len(power_data))
	power_data.prepare_deficits()
	print(len(power_data._deficits))
	print(f"Fraction load covered by production: {power_data.load_coverage_factor():.3f}")
	print(power_data.average_deficit())

	power_data.add_battery(max_power=100000., max_capacity=1e7)

	print(grid.summarize_deficit(power_data))

	# deficits, excesses = grid.find_excesses(power_data, 0)
	deficits, excesses = grid.find_excesses_with_battery(power_data, 0, 1.e6)
	# deficits, excesses = grid.find_excesses_with_battery(power_data, 0, 0)
	grid.report_excesses([datetime.datetime.fromtimestamp(t) for t in power_data.times], deficits, excesses)



main()