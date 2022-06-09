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
import matplotlib.pyplot as plt


logger = logging.getLogger('print_index')

FFVL_ROOT_URL = 'https://parapente.ffvl.fr'
DEBUG_MODE = False

COLUMNS =  {
        'flight_id': str,
        'pilot': str,
        'date': str,
        'wing_name': str,
        'igc': str,
        'fai_type': str,
        'takeoff': str,
        'landing': str,
        'distance': float,
        'duration': str,
        'points': float
    }


def load_index(index_filepath: str):
    # update or create flight file
    df = pd.read_csv(index_filepath, index_col='flight_id', dtype=COLUMNS)
    # pd.to_datetime(df['date'], format="%d/%m/%Y")
    return df


def save_index(index_filepath: str,
               df: pd.DataFrame):
    df.drop_duplicates(keep='last', inplace=True)
    df.sort_index(inplace=True)
    df.to_csv(index_filepath, index_label='flight_id')


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
        parser = argparse.ArgumentParser(description='Crawl FFVL website to collect flight info.')
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
        durations = df['distance'].to_numpy()
        print(durations)
        plt.hist(durations, bins=range(0, 200, 2))
        plt.show()
        # save_index(args.input + '.bak', df)

    except Exception as e:
        logger.critical(e)
        if args.verbose <= logging.DEBUG:
            raise


if __name__ == '__main__':
    main()
