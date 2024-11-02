import datetime


from data.energy_charts import acquire_data
from grid.grid import run_simulation
from grid.report import analyse



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
m_cap = 20000.
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
res = analyse(storages, loads, production, battery, others)
res['solar'] = solarpower
res['wind_on'] = wind_on_power
res['wind_of'] = wind_of_power
res['storage_power'] = st_pow
res['storage_capacity'] = m_cap
print(res)