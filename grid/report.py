import numpy as np


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
        return f"Start: {self.start}\n  Duration: {self.get_duration_in_hours():.2f} hours\n  Total: {self.get_deficit_in_GWh():.1f} GWh\n  Peak: {self.get_peak_deficit_in_GW():.1f} GW"


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
    return shortfalls


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
