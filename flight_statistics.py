#!/usr/bin/env python3
import argparse
import logging
import os.path as path
import re
from typing import Optional, Dict
from tqdm import tqdm
import pandas as pd
from datetime import datetime
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from flight_index import load_index

logger = logging.getLogger('print_index')


class VerbosityParsor(argparse.Action):
    """ accept debug, info, ... or theirs corresponding integer value formatted as string."""

    def __call__(self, parser, namespace, values, option_string=None):
        try:  # in case it represent an int, directly get it
            values = int(values)
        except ValueError:  # else ask logging to sort it out
            assert isinstance(values, str)
            values = logging.getLevelName(values.upper())
        setattr(namespace, self.dest, values)


def main():
    try:
        parser = argparse.ArgumentParser(description='.')
        parser_verbosity = parser.add_mutually_exclusive_group()
        parser_verbosity.add_argument(
            '-v', '--verbose', nargs='?', default=logging.WARNING, const=logging.INFO, action=VerbosityParsor,
            help='verbosity level (debug, info, warning, critical, ... or int value) [warning]')
        parser_verbosity.add_argument(
            '-q', '--silent', '--quiet', action='store_const', dest='verbose', const=logging.CRITICAL)
        parser.add_argument('-i', '--input', required=True,
                            help='path to index file.')

        args = parser.parse_args()

        logger.setLevel(args.verbose)
        logger.debug('config:\n' + '\n'.join(f'\t\t{k}={v}' for k, v in vars(args).items()))

        # load existing
        df = load_index(args.input)

        # wing_popularity = df['wing_name'].value_counts() \
        #     .reset_index(name='count') \
        #     .sort_values(['count'], ascending=False) \
        #     .head(10)
        #
        # print(wing_popularity)

        my_dpi = 96
        fig, ax = plt.subplots(2, 2, figsize=(2000 / my_dpi, 1200 / my_dpi), dpi=my_dpi)
        plt.tight_layout()
        distances = df['distance'].to_numpy()
        durations = df['duration'].to_numpy()
        dates = df['date']
        timestamps = (dates - pd.Timestamp("2014-01-01")) // pd.Timedelta('1d')
        day_range = [np.min(timestamps), np.max(timestamps)]
        day_range[0] = 0
        # day_range[1] = 16000
        distance_range = [0, 400]
        duration_range = [0, 12*60]
        a = ax[0, 0]
        a.hist(timestamps, bins=np.arange(*day_range))
        a.set_ylabel('#fligths')
        a.set_xlabel('month')
        a.set_xlim(day_range)
        a = ax[1, 0]
        a.hist(distances, bins=range(*distance_range))
        a.set_ylabel('#fligths')
        a.set_xlabel('distances (km)')
        a = ax[0, 1]
        a.hist(durations, bins=range(*duration_range))
        a.set_ylabel('#fligths')
        a.set_xlabel('durations (min)')
        a = ax[1, 1]

        speed_matrix = np.zeros((distance_range[1], duration_range[1]), dtype=int)
        for dist, dura in tqdm(zip(distances, durations)):
            try:
                dist = min(1, (dist - distance_range[0]) / (distance_range[1] - distance_range[0])) * (speed_matrix.shape[0]-1)
                dura = min(1, (dura - duration_range[0]) / (duration_range[1] - duration_range[0])) * (speed_matrix.shape[1]-1)
                speed_matrix[int(dist), int(dura)] += 1
            except ValueError:
                pass
        # speed_matrix[speed_matrix == 0] = -1
        speed_matrix = np.log(speed_matrix.astype(float))
        # a.scatter(durations, distances, marker='.')
        # cmap = matplotlib.cm.viridis
        # cmap.set_under('w')
        a.matshow(speed_matrix, origin='lower')
        a.set_xlabel('durations (min)')
        a.set_ylabel('distances (km)')

        plt.savefig('doc/stats.png', bbox_inches='tight', dpi=my_dpi)
        plt.show()

    except Exception as e:
        if args.verbose <= logging.DEBUG:
            logger.critical(e)
            raise


if __name__ == '__main__':
    main()
