import bisect
import datetime
import functools
from scipy.interpolate import interp1d
import numpy as np

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

    def __len__(self):
        return(len(self.times))

    def load_coverage_factor(self):
        return sum(self.productions) / sum(self.loads)

    def finalize(self):
        self.loads = np.array(self.loads)
        self.productions = np.array(self.productions)

    def average_deficit(self):
        return np.mean(self.productions - self.loads)

    def add_battery(self, max_power, max_capacity):
        av_missing = self.average_deficit()
        av_missing = -10000.
        self.max_power = max_power
        self.max_capacity = max_capacity
        self.state_of_charge = []
        self.extra = []
        self.waste = []
        current_charge = 0.
        for l, p in zip(self.loads, self.productions):
            extra = 0.
            waste = 0.
            deficit = p - l - 1*av_missing
            # The power part can probably be dropped, any meaningful
            # battery storage will be hopelessly overpowered and still
            # capacity limited
            if deficit < -self.max_power:
                extra = deficit + self.max_power
                deficit = -self.max_power
            elif deficit > self.max_power:
                # extra = deficit + self.max_power
                deficit = self.max_power
            current_charge += deficit
            # check signs below
            if current_charge < 0:
                extra -= current_charge
                current_charge = 0.
            elif current_charge > self.max_capacity:
                # extra += (current_charge - self.max_capacity)
                waste +=  current_charge - self.max_capacity
                current_charge = self.max_capacity
            self.state_of_charge.append(current_charge)
            self.extra.append(extra)
            self.waste.append(waste)


def find_deficits(pd, new_deficit_delay=0):
    deficits = []
    current_deficit = []
    deficit_end = 100
    for t, l, p in zip(pd.times, pd.loads, pd.productions):
        d = p - l
        if d < 0:
            deficit_end = -1
            current_deficit.append((t, -d))
        else:
            deficit_end += 1
            if current_deficit:
                if deficit_end >= new_deficit_delay:
                    deficits.append({
                        'values': current_deficit,
                        'start': current_deficit[0][0],
                        'end': t,
                        'sum': sum(c[1] for c in current_deficit)/4.,
                        })
                    current_deficit = []
                else:
                    current_deficit.append((t, 0))
    return deficits


def find_excesses(pd, new_deficit_delay=0):
    deficits = find_deficits(pd, new_deficit_delay)
    d = pd.productions - pd.loads
    d[d<0] = 0
    excess = np.cumsum(d)

    for d in deficits:
        next_deficit_end_idx = bisect.bisect_left(pd.times, d['end'])
        if excess[next_deficit_end_idx] > d['sum']:
            excess[next_deficit_end_idx:] -= d['sum']
            d['covered'] = d['sum']
        else:
            excess[next_deficit_end_idx:] -= excess[next_deficit_end_idx]
            d['covered'] = excess[next_deficit_end_idx]

    # TODO: Handle excess that exceeds battery capacity
    return deficits, excess


def find_excesses_with_battery(pd, new_deficit_delay=0, battery_capacity=100e3):
    # battery_capacity in MWh
    deficits = find_deficits(pd, new_deficit_delay)
    d = pd.productions - pd.loads
    d[d<0] = 0
    excess = np.cumsum(d) / 4.

    next_deficit_idx = 0
    next_deficit_start = deficits[next_deficit_idx]['start']
    i_next_deficit_end = bisect.bisect_left(pd.times, deficits[next_deficit_idx]['end'])

    for i in range(len(excess)):
        t = pd.times[i]
        if t > next_deficit_start:
            d = deficits[next_deficit_idx]
            current_storage = excess[i]
            if current_storage > d['sum']:
                d['covered'] = d['sum']
                excess[i:] -= d['sum']
            else:
                d['covered'] = excess[i]
                excess[i:] -= excess[i]
            next_deficit_idx += 1
            if next_deficit_idx < len(deficits):
                next_deficit_start = deficits[next_deficit_idx]['start']
                i_next_deficit_start = bisect.bisect_left(pd.times, next_deficit_start)
                i_next_deficit_end = bisect.bisect_left(pd.times, deficits[next_deficit_idx]['end'])
            else:
                next_deficit_start = 1e99
                i_next_deficit_end = len(excess)
        if excess[i] > battery_capacity:
            overcharge_end_delta = 0
            while True:
                overcharge_end_delta += 1
                if i+overcharge_end_delta == i_next_deficit_end:
                    break
                if excess[i+overcharge_end_delta] < battery_capacity:
                    break
            excess[i:i+overcharge_end_delta] = battery_capacity

    # for d in deficits:
    #     next_deficit_end_idx = bisect.bisect_left(pd.times, d['end'])
    #     if excess[next_deficit_end_idx] > d['sum']:
    #         excess[next_deficit_end_idx:] -= d['sum']
    #         d['covered'] = d['sum']
    #     else:
    #         excess[next_deficit_end_idx:] -= excess[next_deficit_end_idx]
    #         d['covered'] = excess[next_deficit_end_idx]

    # TODO: Handle excess that exceeds battery capacity
    return deficits, excess


def report_excesses(times, deficits, excesses):
    print(len(deficits))
    missing_powers = []
    missing_energy = 0.
    completely_covered = 0
    for d in deficits:
        coverage_ratio = d['covered']/d['sum']
        if coverage_ratio < 1.:
            uncovered = (d['sum']-d['covered']) / 4.
            duration = (d['end']-d['start']) / 60. / 60. # seconds to hours
            missing_power = uncovered / duration
            missing_powers.append(missing_power)
            missing_energy += d['sum']
            print(f"Coverage ratio: {coverage_ratio:.3f} (of {d['sum']/1000.:.1f} GWh), duration: {duration} h, av. missing power: {missing_power:.1f} MW")
        else:
            completely_covered += 1
    print(f"{completely_covered} of {len(deficits)} deficits covered")
    print(f"Max missing power: {max(missing_powers):.2f} MW. Sum {missing_energy/1e6:.1f} TWh")

    import matplotlib.pyplot as plt
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(times, excesses)
    ax.set_xlabel('Time')
    ax.set_ylabel('Capacity MWh')
    plt.savefig("excesses.png")



def summarize_deficit(pd):
    max_deficit = 0
    sum_deficit = 0
    total_duration = 0

    deficits = []

    current_deficit_sum = 0

    for i, (t, l, p) in enumerate(zip(pd.times, pd.loads, pd.productions)):
        if i == 935:
            print(t, l, p)
        if l > p:
            deficit = l - p
            sum_deficit += deficit / 4. # quarter hours
            max_deficit = max(max_deficit, deficit)
            if max_deficit == deficit:
                maxtime = t
                max_ind = i
            total_duration += 0.25 # quarter hours

            current_deficit_sum += deficit
        elif current_deficit_sum:
            deficits.append(current_deficit_sum)
            current_deficit_sum = 0.

    # print(deficits)
    print(len(deficits))
    print("Deficit report:")
    print(f"Maximum: {max_deficit:.2f} MW")
    print(f" (at time {datetime.datetime.fromtimestamp(maxtime)} {max_ind})")
    print(f"Sum: {sum_deficit/1000000.:.2f} TWh")
    print(f"Total deficit time: {total_duration:.2f} h (of {len(pd.times)/4:.2f} h)")
    print(f"  (average: {sum_deficit/total_duration:.2f} MW)")

    print(f"Adding constant production of the average deficit {pd.average_deficit():.1f} MW")
    print(f"  and a battery of {pd.max_capacity/1000.:.1f} GWh")
    print(f"  leads to: {np.sum(pd.extra)/1000./4.:.1f} GWh gap with a maximum of {max(pd.extra):.1f} MW demand")

    import matplotlib.pyplot as plt

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot([datetime.datetime.fromtimestamp(t) for t in pd.times],
        np.cumsum(pd.productions-pd.loads-pd.average_deficit()),
        label='average')
    ax.plot([datetime.datetime.fromtimestamp(t) for t in pd.times],
        pd.state_of_charge,
        label='battery')
    ax.plot([datetime.datetime.fromtimestamp(t) for t in pd.times],
        np.cumsum(pd.extra),
        label='extra')
    # ax.plot([datetime.datetime.fromtimestamp(t) for t in pd.times],
    #     np.cumsum(pd.waste),
    #     label='waste')
    ax.axhline(0, ls='--', color='grey', alpha=0.3)
    ax.set_title("Cumulative load/production mismatch")
    ax.set_xlabel('date')
    ax.set_ylabel('Energy [MWh]')
    ax.legend()
    plt.tight_layout()
    plt.savefig('test.png')


# @profile
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


