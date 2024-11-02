
from collections import defaultdict
import csv
import datetime
import os

import logging
logger = logging.getLogger(__name__)


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