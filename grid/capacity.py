import numpy as np
import functools


class PowerCapacity:
    def __init__(self, historic_capacity, simulated_capacity):
        self.historic = {}
        for name, sourcedict in historic_capacity.items():
            times = []
            values = []
            for t, v in sourcedict.items():
                times.append(t)
                values.append(v)
            times = np.array(times)
            values = np.array(values)
            inds = np.argsort(times)

            self.historic[name] = {
                "times": times[inds],
                "values": values[inds],
            }
        self.simulated = simulated_capacity

    def get_installed_capacity(self, key, t):
        # Drop tzinfo since capacity numbers only change slowly so that a couple
        # of hours offset don't matter
        ind = self.historic[key]["times"].searchsorted(t.replace(tzinfo=None))
        # ind is now the point where we would need to insert the value if a new value
        # at time t were known. At that point we had the previous capacity installed
        # return that
        # TODO: Gracefully deal with earlier times
        return self.historic[key]["values"][ind-1]

    @functools.lru_cache(maxsize=1000, typed=False)
    def get_scale_factor(self, key, t):
        try:
            return self.simulated[key] / self.get_installed_capacity(key, t)
        except KeyError:
            if key not in ["hydro"]:
                print(f"Missing key {key}")
            return 1.
