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
    print(f"  av. battery prod {np.mean(battery[battery>0]):.1f}, av. battery cons {np.mean(battery[battery<0]):.1f}")


def analyse(storages, loads, production, battery, others):
    prod = sum(production) / sum(loads)
    missing = sum(others) / sum(loads)
    battery = sum([b for b in battery if b>0]) / sum(loads)
    return {'prod_frac': prod, 'miss_frac': missing, 'bat_frac': battery}


def analyse(storages, loads, production, battery, others):
    prod = sum(production) / sum(loads)
    missing = sum(others) / sum(loads)
    battery = sum([b for b in battery if b>0]) / sum(loads)
    return {'prod_frac': prod, 'miss_frac': missing, 'bat_frac': battery, 'max_others': max(others)}


def plot(res, st_pow=60.):
    productionscales = [1.5, 2., 2.25, 2.5, 2.75, 3.]
    # fig0xq = plt.figure()
    # ax = fig0.add_subplot(111)
    fig = plt.figure(figsize=(8,8))
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
        if not r['storage_power'] == st_pow:
            continue
        xs[r['productionscale']].append(r['storage_capacity'])
        ys[r['productionscale']].append(r['prod_frac'])
        ys2[r['productionscale']].append(r['miss_frac'])
        ys3[r['productionscale']].append(r['bat_frac'])
        ys4[r['productionscale']].append(r['max_others'])
        prod_fracs[productionscales.index(r['productionscale'])] = r['prod_frac']

    for k in xs:
        # ax.plot(xs[k], ys[k], label=str(k))
        ax2.plot(xs[k], ys2[k], label=str(k))
        ax3.plot(xs[k], ys3[k], label=str(k))
        ax4.plot(xs[k], ys4[k], label=str(k))
    # ax.plot(productionscales, prod_fracs)
    # ax.set_xlabel('production scaling [vs Okt 2024]')
    # ax.set_ylabel('Demand covered by ren production')
    ax4.set_xlabel('Battery capacity [GWh]')
    # ax.set_ylabel('Demand covered by ren production')
    ax2.set_ylabel('Demand covered by other')
    ax3.set_ylabel('Demand covered by battery')
    ax4.set_ylabel('Max other production [MW]')
    ax2.set_title(f'Battery power {st_pow} GW')
    # ax2.set_ylim(0., None)
    # ax3.set_ylim(0., None)
    ax3.legend()
    ax2.set_xscale('log')
    ax3.set_xscale('log')
    ax4.set_xscale('log')
    ax2.set_yscale('log')
    ax3.set_yscale('log')
    ax4.set_yscale('log')