import datetime
import functools
from scipy.interpolate import interp1d



@functools.lru_cache(maxsize=1000, typed=False)
def battery_interaction(current_load, 
                        current_production, 
                        current_storage, 
                        max_power=0.,     # GW
                        max_capacity=0.,  # GWh
                        efficiency=0.9,   # fraction, applied at storage time
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
                current_storage = 0.
            else:
                battery = -residual
                other = 0.
                current_storage += residual
        # we cannot deal with this demand solely from batteries
        else:
            # we need to recoup more than we have, so take everything
            if current_storage < max_power:
                battery = current_storage
                other = -residual - current_storage
                current_storage = 0.
            else:
                battery = max_power
                other = -residual - max_power
                current_storage -= max_power
    # we can store energy
    else: 
        other = 0.
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


def get_production(t, observed_data, sources, observed_capacity, parameters):
    production = 0.
    # production = 9000.
    for s in sources:
        m = t.month
        y = t.year
        for i in range(6):
            newm = m - i
            newy = y
            if newm < 1:
                newy = y - 1
                newm += 12
            try:
                obs_cap = observed_capacity[s][t.replace(year=newy, month=newm, day=1, minute=0, second=0, hour=0, tzinfo=None)]
                scale_factor = parameters[s] / obs_cap
                break
            except KeyError:
                # print(s, t)
                continue
        else:
           scale_factor = 1.
        production += observed_data[s][t] * scale_factor

    return production
    # sum(observed_data[s][t] for s in sources)


def get_obs_capacity_fcts(observed_capacity):
    obs_caps = {}
    for k, v in observed_capacity.items():
        days = sorted(v.keys())
        values = [v[d] for d in days]
        days = [d.timestamp() for d in days]
        obs_caps[k] = interp1d(days, values, fill_value='extrapolate')
    return obs_caps


def run_simulation(observed_data, 
                   observed_capacity, 
                   parameters, 
                   add_extra=False, 
                   nsteps=100, 
                   simstart=None, 
                   extra_capacity=5., 
                   start_extra_dt=-4*24*7, # one week
                   extra_starts=[]):
    sources = parameters['sources']
    print(parameters.get('capacity', {}))
    print(parameters.get('storage', {}))

    obs_caps = get_obs_capacity_fcts(observed_capacity)
    
    times = sorted(observed_data['solar'].keys())
    times = [t for t in times if t > simstart.replace(tzinfo=t.tzinfo)]

    extra_start_ts = []
    extra_end_ts = []
    for s, e in extra_starts:
        extra_start_ts.append(times[s])
        extra_end_ts.append(times[e])
    if extra_start_ts:
        next_extra_start = extra_start_ts.pop(0)
        next_extra_end = extra_end_ts.pop(0)
    else:
        next_extra_start = times[-1]
        next_extra_end = times[-1]
    
    current_storage = 0.
    current_extra_prod = 0.
    storages = []
    loads = []
    production = []
    battery = []
    others = []
    oldt = None
    for t in times[:nsteps]:
        if t >= next_extra_start:
            current_extra_prod = extra_capacity * 1000.
            try:
                next_extra_start = extra_start_ts.pop(0)
            except IndexError:
                next_extra_start = times[-1]
            # print('start', t, len(extra_start_ts), next_extra_start, len(extra_end_ts), next_extra_end)
        if t >= next_extra_end:
            current_extra_prod = 0.
            try:
                next_extra_end = extra_end_ts.pop(0)
            except IndexError:
                next_extra_end = times[-1]
            # print('end', t, len(extra_start_ts), next_extra_start, len(extra_end_ts), next_extra_end)
        if oldt:
            deltat = t - oldt
        else:
            deltat = datetime.timedelta(minutes=15)
        current_load = observed_data['load'][t]
        
        current_production = get_production(t, observed_data, sources, observed_capacity, parameters.get('capacity', {})) + current_extra_prod

        loads.append(current_load)
        production.append(current_production)

        current_storage, bat, other = battery_interaction(current_load, current_production, current_storage, **parameters.get('storage', {}))
        battery.append(bat)
        others.append(other)
        storages.append(current_storage)
        
        
        oldt = t

    if add_extra:
        return run_simulation(observed_data, observed_capacity, parameters, 
                              add_extra=False, 
                              nsteps=nsteps, 
                              simstart=simstart, 
                              extra_capacity=extra_capacity, 
                              extra_starts=add_reserve_times(others, start_extra=start_extra_dt))

    return times, storages, loads, production, battery, others


def add_reserve_times(others, start_extra=-4*24*7):
    lack_of_capacity = []
    extra_needed = False
    cur_start = None
    for i, o in enumerate(others):
        if extra_needed:
            if o == 0:
                extra_needed = False
                duration = i - cur_start

                next_start = cur_start+start_extra
                if next_start < 0:
                    next_start = 0
                try:
                    last_end = lack_of_capacity[-1][1]
                except IndexError:
                    last_end = None
                if last_end and next_start < last_end:
                    lack_of_capacity[-1] = ((lack_of_capacity[-1][0], i))
                else:
                    lack_of_capacity.append((next_start, i))
        else:
            if o > 0:
                cur_start = i
                extra_needed = True
    
    return lack_of_capacity
    
    
    
        