import numpy as np
from collections import Sequence
import datetime


class ShortFall:
    def __init__(self, t, s):
        self.start = t
        self.end = None
        self.deficits = [s]

    def add(self, s):
        self.deficits.append(s)

    def set_end(self, t):
        self.end = t

    def get_duration_in_hours(self):
        return (self.end-self.start).total_seconds() / 3600.

    def get_deficit_in_GWh(self):
        # all values are in MW and all times are in 15mins
        return np.sum(self.deficits) / 1000. / 4.

    def get_average_deficit_in_GW(self):
        return self.get_deficit_in_GWh() / self.get_duration_in_hours()

    def get_peak_deficit_in_GW(self):
        return np.max(self.deficits) / 1000.

    def __repr__(self):
        print(self.start, self.get_duration_in_hours())
        return f"Start: {self.start}\n  Duration: {self.get_duration_in_hours():.2f} hours\n  Total: {self.get_deficit_in_GWh():.1f} GWh\n  Peak: {self.get_peak_deficit_in_GW():.1f} GW"


class ShortFallSeries(Sequence):
    def __init__(self, shortfalls):
        self.shortfalls = shortfalls

    def get_duration_in_hours(self):
        return np.sum(s.get_duration_in_hours() for s in self.shortfalls)

    def get_deficit_in_GWh(self):
        return np.sum(s.get_deficit_in_GWh() for s in self.shortfalls)

    def get_peak_deficit_in_GW(self):
        return np.max([s.get_peak_deficit_in_GW() for s in self.shortfalls])

    def summary(self):
        return f"Duration: {self.get_duration_in_hours():.2f} hours\n  Total: {self.get_deficit_in_GWh():.1f} GWh\n  Peak: {self.get_peak_deficit_in_GW():.1f} GW"

    def __repr__(self):
        return "\n".join(str(s) for s in self.shortfalls) + "\n\n" + self.summary()

    def __len__(self):
        return len(self.shortfalls)

    def __getitem__(self, index):
        return self.shortfalls[index]




def find_compensate_time(shortfall, m_cap, reserve_power):
    # Assumptions:  Battery is fully available before any shortfall, i.e. we can start a long
    #               time before and end with a fully charged battery at the start of the
    #               shortfall
    #               It is sufficient to end with an exactly empty battery at the end of each
    #               shortfall
    # If the battery capacity / reserve power combination does not allow for the compensation
    # of the shortfall a ValueError is raised
    deficits = np.array(shortfall.deficits)
    cum_deficit = np.cumsum(deficits / 1000. / 4.) # make it GWh
    time_needed = cum_deficit[-1] / reserve_power # in hours
    latest_start = shortfall.end - datetime.timedelta(hours=time_needed)
    quarters_needed = int(np.ceil(time_needed * 4.))
    if quarters_needed < len(shortfall.deficits):
        reserve_generated = np.zeros_like(deficits)
        reserve_generated[:quarters_needed] = reserve_power / 4.
        reserve_generated = np.cumsum(reserve_generated)
    else:
        reserve_generated = np.cumsum([reserve_power / 4. for _ in range(quarters_needed)])
    if len(reserve_generated) > len(deficits):
        reserve_generated = reserve_generated[-len(deficits):]
    print(reserve_generated[-1], deficits[-1])
    quarter_shifts = 0
    while (reserve_generated < cum_deficit).any():
        reserve_generated[:-1] = reserve_generated[1:]
        quarter_shifts += 1

    print(max(reserve_generated - cum_deficit))
    if max(reserve_generated - cum_deficit) < m_cap:
        return quarters_needed / 4., quarter_shifts

    raise ValueError
    return -1, -1


def find_shortfalls(times, others):
    shortfalls = []
    is_shortfall = False
    for t, o in zip(times, others):
        if not is_shortfall and o > 0:
            new_shortfall = ShortFall(t, o)
            is_shortfall = True
        if is_shortfall:
            if o > 0:
                new_shortfall.add(o)
            else:
                # print(new_shortfall)
                is_shortfall = False
                new_shortfall.set_end(t)
                shortfalls.append(new_shortfall)
    return ShortFallSeries(shortfalls)


def report(storages, loads, production, battery, others, last=None):
    if last:
        storages = storages[-last:]
        loads = loads[-last:]
        production = production[-last:]
        battery = battery[-last:]
        others = others[-last:]
    battery = np.array(battery)
    print(f"{sum(production) / sum(loads):.3f} ren production of load")
    print(f"{sum(others) / sum(loads):.3f} fraction of load not met")
    print(f"{sum([b for b in battery if b>0]) / sum(loads):.3f} met through batteries")
    print(
        f"  av. battery prod {np.mean(battery[battery>0]):.1f}, av. battery cons {np.mean(battery[battery<0]):.1f}"
    )


def analyse(storages, loads, production, battery, others):
    prod = sum(production) / sum(loads)
    missing = sum(others) / sum(loads)
    battery = sum([b for b in battery if b > 0]) / sum(loads)
    return {"prod_frac": prod, "miss_frac": missing, "bat_frac": battery}


def analyse(storages, loads, production, battery, others):
    prod = sum(production) / sum(loads)
    missing = sum(others) / sum(loads)
    battery = sum([b for b in battery if b > 0]) / sum(loads)
    return {
        "prod_frac": prod,
        "miss_frac": missing,
        "bat_frac": battery,
        "max_others": max(others),
    }


def plot(res, st_pow=60.0):
    productionscales = [1.5, 2.0, 2.25, 2.5, 2.75, 3.0]
    # fig0xq = plt.figure()
    # ax = fig0.add_subplot(111)
    fig = plt.figure(figsize=(8, 8))
    # ax = fig.add_subplot(311)
    ax2 = fig.add_subplot(311)
    ax3 = fig.add_subplot(312)
    ax4 = fig.add_subplot(313)

    prod_fracs = [None for _ in productionscales]
    xs = {k: [] for k in productionscales}
    ys = {k: [] for k in productionscales}
    ys2 = {k: [] for k in productionscales}
    ys3 = {k: [] for k in productionscales}
    ys4 = {k: [] for k in productionscales}
    for r in res:
        if not r["storage_power"] == st_pow:
            continue
        xs[r["productionscale"]].append(r["storage_capacity"])
        ys[r["productionscale"]].append(r["prod_frac"])
        ys2[r["productionscale"]].append(r["miss_frac"])
        ys3[r["productionscale"]].append(r["bat_frac"])
        ys4[r["productionscale"]].append(r["max_others"])
        prod_fracs[productionscales.index(r["productionscale"])] = r["prod_frac"]

    for k in xs:
        # ax.plot(xs[k], ys[k], label=str(k))
        ax2.plot(xs[k], ys2[k], label=str(k))
        ax3.plot(xs[k], ys3[k], label=str(k))
        ax4.plot(xs[k], ys4[k], label=str(k))
    # ax.plot(productionscales, prod_fracs)
    # ax.set_xlabel('production scaling [vs Okt 2024]')
    # ax.set_ylabel('Demand covered by ren production')
    ax4.set_xlabel("Battery capacity [GWh]")
    # ax.set_ylabel('Demand covered by ren production')
    ax2.set_ylabel("Demand covered by other")
    ax3.set_ylabel("Demand covered by battery")
    ax4.set_ylabel("Max other production [MW]")
    ax2.set_title(f"Battery power {st_pow} GW")
    # ax2.set_ylim(0., None)
    # ax3.set_ylim(0., None)
    ax3.legend()
    ax2.set_xscale("log")
    ax3.set_xscale("log")
    ax4.set_xscale("log")
    ax2.set_yscale("log")
    ax3.set_yscale("log")
    ax4.set_yscale("log")
