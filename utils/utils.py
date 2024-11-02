def my_conv(values, days):
    bins = int(days * 4 * 24)
    return np.convolve(values, np.ones(bins)/bins, mode='same')


def plot_daily(times, production, loads):
    totalp = defaultdict(float)
    totall = defaultdict(float)
    for t, p, l in zip(times, production, loads):
        dt = t.replace(year=2000, month=1, day=1)
        totalp[dt] += p
        totall[dt] += l
    ts = sorted(totalp.keys())
    ps = [totalp[t] for t in ts]
    ls = [totall[t] for t in ts]
    plt.plot(ts, ps, label='prod')
    plt.plot(ts, ls, label='load')
    plt.legend()
    plt.xticks(rotation=45)
