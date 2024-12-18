import datetime
import functools
from scipy.interpolate import interp1d

from grid.capacity import PowerCapacity


from line_profiler import profile


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


class Compensate:
    def __init__(self, shortfall, stretch_factor=4):
        self.end = shortfall.end - datetime.timedelta(hours=4)
        self.start = self.end - datetime.timedelta(hours=24 + shortfall.get_duration_in_hours()*stretch_factor)
        # self.value = shortfall.get_average_deficit_in_GW() / stretch_factor * 1.15
        self.value = shortfall.get_peak_deficit_in_GW() / stretch_factor

    @functools.lru_cache(maxsize=1000)
    def get_value(self, t):
        if t < self.start or t > self.end:
            return 0.
        return self.value * 1000.

    def __repr__(self):
        return f"Start: {self.start}\n  End: {self.end}\n  Value: {self.value:.1f} GW"


# @profile
def get_production(t, observed_data, sources, capacity, compensates, MAX_COMP=10000.):
    production = 0.0

    for s in sources:
        scale_factor = capacity.get_scale_factor(s, t)
        production += observed_data[s][t] * scale_factor

    comp_prod = 0.
    for c in compensates:
        comp_prod += c.get_value(t)
    comp_prod = min(comp_prod, MAX_COMP)

    production += comp_prod

    return production


def get_scaled_production(historic_production, historic_capacity, simulated_capacity):
    total_prod = 0.
    for hp, hc, sc in zip(historic_production, historic_capacity, simulated_capacity):
        total_prod += hp * sc / hc
    return total_prod


@profile
def simulate(historic_data, renewable_capacity):
    pd = PowerData()

    for t, h_prod, h_cap in historic_data:
        load = h_prod[-1]
        s_prod = simulated_production = get_scaled_production(
            h_prod[:-1], h_cap[:-1], renewable_capacity
        )
        pd.add(t, load, s_prod)

    return pd


class PowerData:
    def __init__(self):
        self.times = []
        self.loads = []
        self.productions = []
        self._deficits = None

    def add(self, t, l, p):
        self.times.append(t)
        self.loads.append(l)
        self.productions.append(p)
        self._deficits = None

    def prepare_deficits(self):
        # Move this to add?
        self._deficits = []
        for t, l, p in zip(self.times, self.loads, self.productions):
            if l - p > 0:
                self._deficits.append((t, l - p))

    def return_deficits(self):
        if self._deficits:
            return self._deficits

        self.prepare_deficits()
        return self._deficits


@profile
def run_simulation(
    historic_data, historic_capacity, grid_configuration, nsteps=100, simstart=None, compensates=[]
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
                compensates,
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


def get_compensate(times, storages, loads, production, battery, others):
    compensates = [Compensate(s) for s in find_shortfalls(times, others)]
    return compensates


