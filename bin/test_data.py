from data.energy_charts import acquire_data
from utils.plot import plot_2d_time_per_day, plot_acf


use_sources = {
    'solar': ['Solar'],
    'wind_on': ['Wind onshore'],
    'wind_off': ['Wind offshore'],
    'hydro': ['Hydro Run-of-River', 'Hydro water reservoir'],
    'load': ['Load'],
    'price': ['Day Ahead Auction'],
}

data, capacity = acquire_data(use_sources, '..')
print(data.keys())
plot_2d_time_per_day(data['solar'], 'plots/solar.pdf')
plot_2d_time_per_day(data['wind_on'], 'plots/wind.pdf')
plot_2d_time_per_day(data['load'], 'plots/wind.pdf')


plot_acf(data['solar'], 'plots/acf_solar.pdf')
plot_acf(data['wind_on'], 'plots/acf_wind.pdf')
plot_acf(data['wind_off'], 'plots/acf_wind_of.pdf')

