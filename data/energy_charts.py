
from collections import defaultdict
import csv
import json
import datetime
import os
import requests

import logging
logger = logging.getLogger(__name__)


ENERGY_CHARTS_URL = "https://api.energy-charts.info"

# TODO: Add dictionary structure and key names. If energy-charts
#       ever changes its API the query_* functions will have to
#       learn how to fix up the data


# TODO: Add more info reporting for the failure case
def query_capacity_api():
    # Documentation at https://api.energy-charts.info/#
    # Returns a dictionary of a 'time' list and a 'production_types'
    # dictionary with monthly values for each production type
    # the times will be once per month
    r = requests.get(
        url=ENERGY_CHARTS_URL + "/installed_power",
        # time_step "monthly" only returns a small subset of the data, for now use yearly data
        params={"country": "de", "time_step": "yearly"}
    )
    data = json.loads(r.content)
    # data["data_querytime"] = datetime.datetime.now()
    data['production_types'] = {
        k['name']: k['data'] for k in data['production_types']
    }
    return data


# TODO: Add more info reporting for the failure case
def query_power_api(start=None, end=None):
    # Documentation at https://api.energy-charts.info/#
    # Returns a dictionary of a 'unix_seconds' list and a 'production_types'
    # dictionary with monthly values for each production type
    # the times will represent 15 minute intervals
    if isinstance(start, float):
        start = datetime.datetime.fromtimestamp(start)
    if isinstance(end, float):
        end = datetime.datetime.fromtimestamp(end)
    r = requests.get(
        url=ENERGY_CHARTS_URL + "/total_power",
        params={
            "country": "de",
            "start": start,
            "end": end,
        }
    )
    data = json.loads(r.content)
    print(len(data['production_types']), [d['name'] for d in data['production_types']])
    data['production_types'] = {
        k['name']: k['data'] for k in data['production_types']
    }
    # data["data_querytime"] = datetime.datetime.now()
    return data


def acquire_data(use_sources, datadir='.'):
    data = defaultdict(dict)
    logger.info(f"Searching {datadir}")
    for fname in os.listdir(datadir):
        logger.debug(f"Deal with {fname}")
        if fname.startswith('energy-charts_Public'):
            logger.debug(f"Identified {fname} as electricity file")
            for k, v in read_electricity_file(os.path.join(datadir, fname), use_sources).items():
                data[k].update(v)
        if fname.startswith('energy-charts_Net'):
            logger.debug(f"Identified {fname} as capacity file")
            capacity = read_capacity(os.path.join(datadir, fname), use_sources)
    
    return data, capacity


def get_assignment_matrix(header, use_sources):
    assignment_matrix = {}
    for k, v in use_sources.items():
        assignment_matrix[k] = []
        for vv in v:
            try:
                assignment_matrix[k].append(header.index(vv))
            except ValueError:
                # not all files contain all fields
                pass
    return assignment_matrix


def identify_header(line):
    # some files have an extra disclaimer line in the beginning. So we can't just
    # hard code the line number. Instead we hope that there is always a component
    # named "Solar" in there..
    return 'Solar' in line


def read_capacity(fname, use_sources):
    data = {k: {} for k in use_sources}
    assignment_matrix = None
    with open(fname, newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        for i, line in enumerate(spamreader):
            if assignment_matrix is None:
                if identify_header(line):
                    assignment_matrix = get_assignment_matrix(line, use_sources)
                else:
                    continue
            try:
                month = datetime.datetime.strptime(line[0], '%m.%Y')
            except ValueError:
                # The first line gives the units and will fail to parse
                continue
            for k, indlist in assignment_matrix.items():
                d = 0.
                try:
                    for ind in indlist:
                        d += float(line[ind])
                    data[k][month] = d
                except:
                        d += 0.
    return data


def read_electricity_file(fname, use_sources):
    data = {k: {} for k in use_sources}

    assignment_matrix = None
    with open(fname, newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        for i, line in enumerate(spamreader):
            if assignment_matrix is None:
                if identify_header(line):
                    assignment_matrix = get_assignment_matrix(line, use_sources)
                else:
                    continue
            try:
                day = datetime.datetime.fromisoformat(line[0])
            except ValueError:
                # The first line gives the units and will fail to parse
                continue
            for k, indlist in assignment_matrix.items():
                d = 0.
                for ind in indlist:
                    try:
                        d += float(line[ind])
                    except:
                        print(i, line, k, indlist)
                data[k][day] = d
    return data