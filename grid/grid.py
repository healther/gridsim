import datetime
import functools
from scipy.interpolate import interp1d

from grid.capacity import PowerCapacity


@functools.lru_cache(maxsize=1000, typed=False)
def battery_interaction(
    current_load,
    current_production,
    current_storage,
    max_power=0.0,  # GW
    max_capacity=0.0,  # GWh
    efficiency=0.9,  # fraction, applied at storage time
):
    max_power *= 1000
    max_capacity *= 4 * 1000
    residual = current_production - current_load
    if residual < 0:
        # we could deal with the complete demand from batteries
        if -residual < max_power:
            # but we need to recoup more than we have, so take everything from storage and fill up the rest with other
            if current_storage < -residual:
                battery = current_storage
                other = -residual - current_storage
                current_storage = 0.0
            else:
                battery = -residual
                other = 0.0
                current_storage += residual
        # we cannot deal with this demand solely from batteries
        else:
            # we need to recoup more than we have, so take everything
            if current_storage < max_power:
                battery = current_storage
                other = -residual - current_storage
                current_storage = 0.0
            else:
                battery = max_power
                other = -residual - max_power
                current_storage -= max_power
    # we can store energy
    else:
        other = 0.0
        if residual > max_power:
            current_storage += max_power * efficiency
            battery = -max_power
        else:
            current_storage += residual * efficiency
            battery = -residual
        if current_storage > max_capacity:
            battery -= current_storage - max_capacity
            current_storage = max_capacity
    return current_storage, battery, other


def get_production(t, observed_data, sources, capacity):
    production = 0.0

    for s in sources:
        scale_factor = capacity.get_scale_factor(s, t)
        production += observed_data[s][t] * scale_factor

    return production
    # sum(observed_data[s][t] for s in sources)


def get_obs_capacity_fcts(observed_capacity):
    obs_caps = {}
    for k, v in observed_capacity.items():
        days = sorted(v.keys())
        values = [v[d] for d in days]
        days = [d.timestamp() for d in days]
        obs_caps[k] = interp1d(days, values, fill_value="extrapolate")
    return obs_caps


def run_simulation(
    historic_data, historic_capacity, grid_configuration, nsteps=100, simstart=None
):
    """Simulate power generation for some grid_configuration

    Takes historical production and load data, scales it up (or down) to a given grid
    configuration and returns the resulting load state of the power grid
    """

    sources = grid_configuration["sources"]
    print(grid_configuration.get("capacity", {}))
    print(grid_configuration.get("storage", {}))

    capacity = PowerCapacity(historic_capacity, grid_configuration['capacity'])

    times = sorted(historic_data["solar"].keys())
    if simstart:
        times = [t for t in times if t > simstart.replace(tzinfo=t.tzinfo)]

    current_storage = 0.0
    storages = []
    loads = []
    production = []
    battery = []
    others = []
    oldt = None
    for t in times[:nsteps]:
        current_load = historic_data["load"][t]

        current_production = (
            get_production(
                t,
                historic_data,
                sources,
                capacity,
            )
        )

        loads.append(current_load)
        production.append(current_production)

        current_storage, bat, other = battery_interaction(
            current_load,
            current_production,
            current_storage,
            **grid_configuration.get("storage", {})
        )
        battery.append(bat)
        others.append(other)
        storages.append(current_storage)

        oldt = t

    return times, storages, loads, production, battery, others


def add_reserve_times(others, start_extra=-4 * 24 * 7):
    lack_of_capacity = []
    extra_needed = False
    cur_start = None
    for i, o in enumerate(others):
        if extra_needed:
            if o == 0:
                extra_needed = False
                duration = i - cur_start

                next_start = cur_start + start_extra
                if next_start < 0:
                    next_start = 0
                try:
                    last_end = lack_of_capacity[-1][1]
                except IndexError:
                    last_end = None
                if last_end and next_start < last_end:
                    lack_of_capacity[-1] = (lack_of_capacity[-1][0], i)
                else:
                    lack_of_capacity.append((next_start, i))
        else:
            if o > 0:
                cur_start = i
                extra_needed = True

    return lack_of_capacity
