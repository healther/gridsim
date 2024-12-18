import bisect
import datetime
import json
import requests
from data import energy_charts


import logging
log = logging.getLogger(__name__)

# ['Hydro pumped storage consumption',
# 'Cross border electricity trading',
# 'Hydro Run-of-River',
# 'Biomass',
# 'Fossil brown coal / lignite',
# 'Fossil hard coal',
# 'Fossil oil',
# 'Fossil gas',
# 'Geothermal',
# 'Hydro water reservoir',
# 'Hydro pumped storage',
# 'Others',
# 'Waste',
# 'Wind offshore',
# 'Wind onshore',
# 'Solar',
# 'Load (incl. self-consumption)',
# 'Residual load',
# 'Renewable share of generation',
# 'Renewable share of load']
DEFAULT_KEYS = [
	('hydro', 'Hydro Run-of-River', 'Hydro water reservoir', 'Hydro'),
	('solar', 'Solar'),
	('wind_on', 'Wind onshore'),
	('wind_of', 'Wind offshore'),
	('load', 'Load (incl. self-consumption)'),
]


class HistoricData:
	# We take the API form of energy-charts from the end of 2024
	# for internal storage. If a better one comes along, replace
	# the description below and adapt the query functionality

	# Hold capacity data as a dictionary with keys 'time' and
	# 'production_types', where time is a list of strings of
	# month identifiers of the form MM.YYYY and production_types
	# is a dictionary of <power type> -> <list of value in GW>
	# pairs where the list correspond to the times from time
	production_capacity = {}
	# Hold the historic power data as a dictionary with keys
	# 'unix_seconds' and 'production_types', where unix_seconds
	# is a list of quarter hour unix-timestamps and production_types
	# is a dictionary of <power type> -> <list of value in GWh>
	# pairs where the list correspond to the times from unix_seconds
	power = {}

	def __init__(self, cache_file="data/historic_data.json", start=datetime.datetime(year=2020, month=1, day=1), end=datetime.datetime.now(), initalize=True):
		self.cache_file = cache_file
		self._missing = True
		self._target_start = start.timestamp()
		self._target_end = end.timestamp()
		if initalize:
			self.initalize()

	def initalize(self, query_api=False):
		self.load_cache()
		if self.power:
			self._current_start = self.power['unix_seconds'][0]
			self._current_end = self.power['unix_seconds'][-1]
			if self._current_start <= self._target_start and self._current_end >= self._target_end:
				self._missing = False
			else:
				self._missing = True
		else:
			self._missing = True

		if query_api:
			if not self.power:
				self.update_data_from_api(self._target_start, self._target_end)
			elif self._missing:
				if self._target_start < self._current_start:
					self.update_data_from_api(self._target_start, self._current_start)
					self._current_start = self._target_start
				if self._target_end > self._current_end:
					self.update_data_from_api(self._current_end, self._target_end)
					self._current_end = self._target_end
				self._missing = False
			self.update_cache()

	def update_data_from_api(self, missing_start=None, missing_end=None):
		production_capacity = energy_charts.query_capacity_api()
		power = energy_charts.query_power_api(missing_start, missing_end)
		self.update_data(production_capacity=production_capacity, power=power)

	def update_data(self, production_capacity={}, power={}):
		if production_capacity:
			# The merging won't work as is, the time values are
			# not in lexigraphical order -> we would need to either
			# introduce our own storage format or manually fixup the
			# comparison operator used in merge().. For now just ignore
			# that part an just take everything every time
			# self.production_capacity = merge(self.production_capacity, production_capacity, timekey='time')
			self.production_capacity = production_capacity
		if power:
			self.power = merge(self.power, power, timekey='unix_seconds')

		self.update_cache()

	def update_cache(self):
		with open(self.cache_file, 'w') as f:
			f.write(json.dumps({"production_capacity": self.production_capacity, "power": self.power}))

	def load_cache(self):
		try:
			with open(self.cache_file) as f:
				d = json.load(f)
		except FileNotFoundError:
			log.info(f"Cache ({self.cache_file}) does not exist yet. Will be created on update_cache()")
			return

		self.production_capacity = d['production_capacity']
		self.power = d['power']

	def prepare(self, keys):
		# TODO: Rework this to directly provide the iterator output and make the api_calls correctly invalidate the preparation
		# keys is a list of (new_key, list of old keys) tuples which defines
		# the collection and later iteration of the data

		self._keys = [k[0] for k in keys]
		self._prepared_data = {
			'production': {'start_times': [], 'types': {}},
			'power': {'time': [], 'types': {}},
		}

		production_times = []
		for t in self.production_capacity['time']:
			try:
				month, year = t.split('.')
				production_times.append(datetime.datetime(int(year), int(month), 1).timestamp())
			except ValueError:
				production_times.append(datetime.datetime(int(t), 1, 1).timestamp())
		self._prepared_data['production']['start_times'] = production_times
		self._prepared_data['production']['types'] = {
			k: [0. for _ in range(len(production_times))]
			for k in self._keys
		}
		for k, v in self.production_capacity['production_types'].items():
			for klist in keys:
				new_key = klist[0]
				old_values = self._prepared_data['production']['types'][new_key]
				if k in klist:
					new_values = [ov + nv if nv is not None else 0. for ov, nv in zip(old_values, v)]
					self._prepared_data['production']['types'][new_key] = new_values

		self._prepared_data['power']['time'] = self.power['unix_seconds']
		self._prepared_data['power']['types'] = {
			k: [0. for _ in range(len(self._prepared_data['power']['time']))]
			for k in self._keys
		}
		for k, v in self.power['production_types'].items():
			for klist in keys:
				new_key = klist[0]
				old_values = self._prepared_data['power']['types'][new_key]
				if k in klist:
					new_values = [ov + nv if nv is not None else 0. for ov, nv in zip(old_values, v)]
					self._prepared_data['power']['types'][new_key][:] = new_values


	def __iter__(self):
		try:
			self._prepared_data
		except AttributeError:
			raise UsageError("Need to call self.prepare() first")

		first_power_time = self._prepared_data['power']['time'][0]
		production_idx = bisect.bisect(self._prepared_data['production']['start_times'], first_power_time) - 1
		if production_idx == len(self._prepared_data['production']['start_times']):
			log.info("Simulation time starts after the last production capacity time. Will not change factors over time!")
			production_idx = -1
			# some date in the far future # TODO: Check wrt to 2034? Python treats it as float, so probably doesn't matter
			next_production_time = datetime.datetime.now().timestamp() + 84600*365*10
		else:
			next_production_time = self._prepared_data['production']['start_times'][production_idx+1]
		out_capacity = []
		for k in self._keys:
			out_capacity += [self._prepared_data['production']['types'][k][production_idx]]

		for i, t in enumerate(self._prepared_data['power']['time']):
			if t > next_production_time:
				production_idx += 1
				next_production_time = self._prepared_data['production']['start_times'][production_idx+1]
				out_capacity = []
				for k in self._keys:
					out_capacity += [self._prepared_data['production']['types'][k][production_idx]]
			out_power = []
			for k in self._keys:
				out_power += [self._prepared_data['power']['types'][k][i]]
			yield t, out_power, out_capacity

	def keys(self):
		out_power = []
		out_capacity = []
		for k in self._keys:
			out_power += [k]
			out_capacity += [k]
		return 'timestamp', out_power, out_capacity


def merge(old, new, timekey='time'):
	# If there is no old data, we can just take the new set
	if not old:
		return new

	new_keys = set(new['production_types'].keys())
	old_keys = set(old['production_types'].keys())
	if new_keys - old_keys:
		raise KeyError(f"Got extra keys: {new_keys - old_keys} in the new data")

	for i, t in enumerate(new[timekey]):
		insert_idx = bisect.bisect(old[timekey], t)
		if t in old[timekey]:
			if old[timekey][insert_idx] != new['production_types'][k][i]:
				log.debug(f"Got different values for {t}. Old: {old[timekey][insert_idx]} New: {new['production_types'][k][i]}. Ignoring new one")
				continue
		old[timekey].insert(insert_idx, t)
		for k in new_keys:
			old['production_types'][k].insert(insert_idx, new['production_types'][k][i])

	return old


def verify_power_data(power_data):
	pass

